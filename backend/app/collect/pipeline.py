"""统一采集 pipeline：编排 discover → fetch → parse → upsert，记录 collect_jobs/items。"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collect.base import CollectContext, SourceConnector
from app.models import CollectItem, CollectJob, Exhibit, Museum

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def _raw_path(source: str, museum_id: int, name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "._-") or "item"
    return RAW_DIR / source / f"{museum_id}_{safe}.txt"


def _upsert_exhibit(
    db: Session, museum_id: int, fields: dict, connector: SourceConnector
) -> tuple[Exhibit, bool]:
    """按 (museum_id, name) 去重 upsert。返回 (exhibit, created)。"""
    name = fields["name"]
    existing = db.scalar(
        select(Exhibit).where(Exhibit.museum_id == museum_id, Exhibit.name == name)
    )
    if existing:
        existing.category = fields.get("category") or existing.category
        existing.dynasty = fields.get("dynasty") or existing.dynasty
        existing.source = connector.source
        existing.confidence = connector.default_confidence
        existing.source_ref = fields.get("source_ref")
        existing.fetched_at = datetime.utcnow()
        return existing, False

    exhibit = Exhibit(
        museum_id=museum_id,
        name=name,
        name_i18n={"zh": name},
        category=fields.get("category"),
        dynasty=fields.get("dynasty"),
        status="active",
        source=connector.source,
        confidence=connector.default_confidence,
        source_ref=fields.get("source_ref"),
        fetched_at=datetime.utcnow(),
    )
    db.add(exhibit)
    db.flush()
    return exhibit, True


def _upsert_museum(
    db: Session, fields: dict, connector: SourceConnector
) -> tuple[Museum, bool]:
    """按 name 去重 upsert 博物馆。返回 (museum, created)。"""
    name = fields["name"]
    existing = db.scalar(select(Museum).where(Museum.name == name))
    if existing:
        if fields.get("description"):
            existing.description = fields["description"]
        existing.source_ref = fields.get("source_ref")
        existing.fetched_at = datetime.utcnow()
        return existing, False

    museum = Museum(
        name=name,
        name_i18n={"zh": name},
        city=fields.get("city") or "待补充",
        country=fields.get("country") or "中国",
        lat=fields.get("lat") or 0.0,
        lng=fields.get("lng") or 0.0,
        geo_fence=[],
        description=fields.get("description"),
        source_ref=fields.get("source_ref"),
        fetched_at=datetime.utcnow(),
    )
    db.add(museum)
    db.flush()
    return museum, True


async def run_pipeline(
    connector: SourceConnector,
    museum_id: int | None,
    db: Session,
    ctx: CollectContext,
) -> CollectJob:
    """执行完整采集流程，返回完成的 CollectJob。

    流程：discover → 逐条(fetch→落盘→parse→upsert→写 item) → 更新 job 状态。
    每条 item 前检查取消信号。
    """
    job = CollectJob(
        museum_id=museum_id,
        source=connector.source,
        stage="running",
        total=0,
        done=0,
        failed=0,
        log=[],
    )
    db.add(job)
    db.flush()

    try:
        items_data = await connector.discover(ctx)
    except Exception as e:
        job.stage = "failed"
        job.error = f"discover 失败: {e}"
        job.finished_at = datetime.utcnow()
        db.commit()
        return job

    job.total = len(items_data)
    db.commit()

    for raw_item in items_data:
        if ctx.cancelled:
            job.stage = "canceled"
            break

        name = raw_item.get("name", "?")
        item = CollectItem(
            job_id=job.id,
            source_ref=raw_item.get("source_ref"),
            name=name,
            stage="pending",
            target_type=connector.target_type,
        )
        db.add(item)
        db.flush()

        try:
            # 1. fetch
            raw = await connector.fetch(raw_item, ctx)
            if raw is None:
                raise RuntimeError("fetch 返回空")
            item.stage = "fetched"

            # 2. 落盘 raw（供 parse 重跑，无需重新抓站）
            if museum_id is not None:
                p = _raw_path(connector.source, museum_id, name)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(raw, encoding="utf-8")

            # 3. parse
            fields = await connector.parse(raw, raw_item, ctx)
            if not fields:
                raise RuntimeError("parse 返回空")
            fields.setdefault("source_ref", raw_item.get("source_ref"))
            item.stage = "parsed"

            # 4. upsert（按 target_type 分发）
            if connector.target_type == "exhibit":
                exhibit, _ = _upsert_exhibit(db, museum_id, fields, connector)
                item.target_id = exhibit.id
            elif connector.target_type == "museum":
                museum, _ = _upsert_museum(db, fields, connector)
                item.target_id = museum.id

            item.stage = "saved"
            job.done += 1

        except Exception as e:
            item.stage = "failed"
            item.error = str(e)[:300]
            job.failed += 1
            job.log.append({"name": name, "error": str(e)[:200]})

        await ctx.sleep(ctx.min_interval)
        db.commit()

    if job.stage == "running":
        job.stage = "succeeded" if job.failed == 0 else "partial"
    job.finished_at = datetime.utcnow()
    db.commit()
    return job

"""采集 CLI。

用法:
  uv run python -m app.collect --museum 1 --source baike
  uv run python -m app.collect --museum 1 --source wiki

本阶段（阶段1）仅支持规则源（baike/wiki）。LLM 与官网源在后续阶段。
"""

import argparse
import asyncio

from sqlalchemy import select

from app.collect.base import CollectContext, SourceConnector
from app.collect.pipeline import run_pipeline
from app.collect.registry import available_sources, get_connector
from app.db import SessionLocal
from app.models import Exhibit, Museum


def _load_exhibit_names(db, museum_id: int) -> list[str]:
    """取出该馆现有展品名，作为百科/维基 discover 的查询种子。"""
    rows = db.scalars(
        select(Exhibit.name).where(
            Exhibit.museum_id == museum_id,
            Exhibit.status.in_(["active", "moved"]),
        )
    ).all()
    return list(rows)


async def _run(museum_id: int, source: str, refine: bool = False):
    db = SessionLocal()
    try:
        museum = db.get(Museum, museum_id)
        if not museum:
            print(f"✗ museum_id={museum_id} 不存在")
            return
        connector = get_connector(source, museum_id=museum_id)
        ctx = CollectContext()

        if source == "official":
            # 官网源：connector 自带 discover（抓目录页），无需展品名种子
            job = await run_pipeline(
                connector, museum_id, db, ctx, enable_llm_refine=refine
            )
        else:
            # 百科/维基：需展品名种子，用闭包注入预发现的 items
            names = _load_exhibit_names(db, museum_id)
            if not names:
                print(f"✗ {museum.name} 无展品名可采集")
                return
            items = await connector.discover(ctx, exhibit_names=names)
            print(f"=== {museum.name} · source={source} · {len(items)} 条 · refine={refine} ===")

            class _BoundConnector(SourceConnector):
                source = connector.source
                default_confidence = connector.default_confidence
                target_type = connector.target_type

                async def discover(self, ctx):
                    return items

                async def fetch(self, item, ctx):
                    return await connector.fetch(item, ctx)

                async def parse(self, raw, item, ctx):
                    return await connector.parse(raw, item, ctx)

            job = await run_pipeline(_BoundConnector(), museum_id, db, ctx, enable_llm_refine=refine)

        print(
            f"\n=== 完成 ===\n"
            f"  stage={job.stage}\n"
            f"  total/done/failed = {job.total}/{job.done}/{job.failed}\n"
            f"  job_id={job.id}"
        )
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="博物馆采集 CLI")
    p.add_argument("--museum", type=int, required=True, help="博物馆 id")
    p.add_argument("--source", type=str, required=True, choices=available_sources())
    p.add_argument("--refine", action="store_true", help="启用 LLM 数据整理层（LLM#2）")
    args = p.parse_args()
    asyncio.run(_run(args.museum, args.source, args.refine))


if __name__ == "__main__":
    main()

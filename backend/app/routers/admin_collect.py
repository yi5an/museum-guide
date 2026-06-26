"""采集管理 API（/admin/collect/*）。"""

import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import CollectItem, CollectJob, Exhibit, Museum
from app.schemas_collect import (
    CollectItemOut,
    CollectJobDetailResponse,
    CollectJobListResponse,
    CollectJobOut,
    CollectStartRequest,
    CollectStartResponse,
)
from app.services.collect_runner import collect_runner

router = APIRouter(prefix="/admin", tags=["admin-collect"])


def _check_token(x_admin_token: str | None = Header(None)):
    """简单 token 校验。admin_token 为空时跳过（本地开发）。"""
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


def _job_to_out(job: CollectJob, museum_name: str | None) -> CollectJobOut:
    return CollectJobOut(
        id=job.id, museum_id=job.museum_id, museum_name=museum_name,
        source=job.source, stage=job.stage, total=job.total,
        done=job.done, failed=job.failed, started_at=job.started_at,
        finished_at=job.finished_at, error=job.error,
    )


@router.post(
    "/collect/start",
    response_model=CollectStartResponse,
    dependencies=[Depends(_check_token)],
)
async def start(req: CollectStartRequest):
    # 必须 async：collect_runner.start 内部用线程，但仍保持 async 语义。
    # 校验官网源：该馆是否已接入
    if req.source == "official":
        from app.collect.registry import has_official
        if req.museum_id is None or not has_official(req.museum_id):
            raise HTTPException(
                400, f"博物馆 id={req.museum_id} 暂未接入官网采集"
            )
    try:
        job_id = collect_runner.start(req.museum_id, req.source, req.enable_llm_refine)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return CollectStartResponse(job_id=job_id)


@router.get(
    "/collect/jobs",
    response_model=CollectJobListResponse,
    dependencies=[Depends(_check_token)],
)
def list_jobs(
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    jobs = list(
        db.scalars(
            select(CollectJob).order_by(CollectJob.id.desc()).limit(limit).offset(offset)
        )
    )
    out = []
    for j in jobs:
        mname = (
            db.scalar(select(Museum.name).where(Museum.id == j.museum_id))
            if j.museum_id
            else None
        )
        out.append(_job_to_out(j, mname))
    return CollectJobListResponse(total=len(out), jobs=out)


@router.get(
    "/collect/jobs/{job_id}",
    response_model=CollectJobDetailResponse,
    dependencies=[Depends(_check_token)],
)
def job_detail(job_id: int, db: Session = Depends(get_db)):
    job = db.get(CollectJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    mname = (
        db.scalar(select(Museum.name).where(Museum.id == job.museum_id))
        if job.museum_id
        else None
    )
    items = list(db.scalars(select(CollectItem).where(CollectItem.job_id == job_id)))
    return CollectJobDetailResponse(
        job=_job_to_out(job, mname),
        items=[
            CollectItemOut(
                id=i.id, name=i.name, stage=i.stage,
                target_type=i.target_type, target_id=i.target_id, error=i.error,
            )
            for i in items
        ],
    )


@router.post("/collect/jobs/{job_id}/cancel", dependencies=[Depends(_check_token)])
def cancel(job_id: int, db: Session = Depends(get_db)):
    ok = collect_runner.cancel(job_id)
    if not ok:
        # 任务可能已结束；查库确认是否存在
        job = db.get(CollectJob, job_id)
        if not job:
            raise HTTPException(404, "job not found")
    return {"ok": True}


@router.get("/collect/jobs/{job_id}/stream", dependencies=[Depends(_check_token)])
async def stream(job_id: int, db: Session = Depends(get_db)):
    """SSE：每秒推送一次进度直到任务结束。"""

    async def event_gen():
        while True:
            job = db.get(CollectJob, job_id)
            if not job:
                yield "event: error\ndata: not found\n\n"
                return
            payload = (
                f'{{"done":{job.done},"total":{job.total},'
                f'"stage":"{job.stage}","failed":{job.failed}}}'
            )
            yield f"data: {payload}\n\n"
            if job.stage != "running":
                yield f"event: done\ndata: {payload}\n\n"
                return
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/museums", dependencies=[Depends(_check_token)])
def admin_museums(db: Session = Depends(get_db)):
    from app.collect.registry import has_official

    museums = list(db.scalars(select(Museum).order_by(Museum.id)))
    result = []
    for m in museums:
        c = db.scalar(
            select(func.count(Exhibit.id)).where(
                Exhibit.museum_id == m.id, Exhibit.status == "active"
            )
        )
        result.append(
            {
                "id": m.id, "name": m.name, "city": m.city,
                "exhibit_count": c or 0,
                "has_official": has_official(m.id),  # 该馆是否已接入官网采集
            }
        )
    return {"total": len(result), "museums": result}

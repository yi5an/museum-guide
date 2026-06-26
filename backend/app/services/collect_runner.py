"""采集任务编排服务：启动后台采集、跟踪进度、支持取消。

设计：
- start() 创建 collect_jobs 记录 + asyncio.create_task 后台跑 pipeline。
- 内存 _TASKS 维护 job_id → (asyncio.Task, CollectContext)，供取消。
- pipeline 自身在每个 item 后 commit done/total/failed（已在阶段1实现），
  因此进度查询直接读 collect_jobs 表，无需额外 IPC。
- SSE 推送：服务端 stream 定时读表推送。
"""

import asyncio
from datetime import datetime

from sqlalchemy import select

from app.collect.base import CollectContext, SourceConnector
from app.collect.pipeline import run_pipeline
from app.collect.registry import get_connector
from app.db import SessionLocal
from app.models import CollectJob, Exhibit


class CollectRunner:
    def __init__(self):
        self._tasks: dict[int, tuple[asyncio.Task, CollectContext]] = {}

    def start(self, museum_id: int | None, source: str, enable_llm_refine: bool) -> int:
        """启动一个采集任务，返回 job_id。后台异步执行。"""
        db = SessionLocal()
        try:
            job = CollectJob(
                museum_id=museum_id, source=source, stage="running",
                total=0, done=0, failed=0, log=[],
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
        finally:
            db.close()

        ctx = CollectContext()
        task = asyncio.create_task(self._run(job_id, museum_id, source, enable_llm_refine, ctx))
        self._tasks[job_id] = (task, ctx)
        return job_id

    async def _run(self, job_id, museum_id, source, enable_llm_refine, ctx):
        """实际执行（后台协程）。每步用独立 session。"""
        db = SessionLocal()
        try:
            connector = get_connector(source)
            # 对百科/维基：从该馆现有展品名取种子；对官网/发现源：connector 自带 discover
            items = await self._discover_with_seeds(connector, museum_id, ctx, db)

            if items is not None:
                # 用闭包注入预发现的 items
                class _Bound(SourceConnector):
                    pass

                _Bound.source = connector.source
                _Bound.default_confidence = connector.default_confidence
                _Bound.target_type = connector.target_type

                async def _discover(self_bound, c):
                    return items

                async def _fetch(self_bound, item, c):
                    return await connector.fetch(item, c)

                async def _parse(self_bound, raw, item, c):
                    return await connector.parse(raw, item, c)

                _Bound.discover = _discover
                _Bound.fetch = _fetch
                _Bound.parse = _parse
                bound = _Bound()
            else:
                bound = connector

            await run_pipeline(
                bound, museum_id, db, ctx, enable_llm_refine=enable_llm_refine
            )
        except Exception as e:
            self._mark_failed(job_id, str(e))
        finally:
            db.close()
            self._tasks.pop(job_id, None)

    async def _discover_with_seeds(self, connector, museum_id, ctx, db):
        """百科/维基需要展品名种子；官网/发现源自带 discover（返回 None 表示用 connector 自身）。"""
        if connector.target_type != "exhibit" or connector.source in ("official",):
            return None
        if museum_id is None:
            return None
        names = list(db.scalars(
            select(Exhibit.name).where(
                Exhibit.museum_id == museum_id,
                Exhibit.status.in_(["active", "moved"]),
            )
        ))
        try:
            return await connector.discover(ctx, exhibit_names=names)
        except TypeError:
            # discover 不接受 exhibit_names（发现源等），用 connector 自身
            return None

    def _mark_failed(self, job_id, error):
        db = SessionLocal()
        try:
            job = db.get(CollectJob, job_id)
            if job and job.stage == "running":
                job.stage = "failed"
                job.error = error[:500]
                job.finished_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    def cancel(self, job_id: int) -> bool:
        """取消任务。返回是否找到运行中的任务。"""
        entry = self._tasks.get(job_id)
        if not entry:
            return False
        task, ctx = entry
        ctx.cancel()
        task.cancel()
        db = SessionLocal()
        try:
            job = db.get(CollectJob, job_id)
            if job:
                job.stage = "canceled"
                job.finished_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        return True

    def is_running(self, job_id: int) -> bool:
        return job_id in self._tasks


# 全局单例
collect_runner = CollectRunner()

"""采集任务编排服务：启动后台采集、跟踪进度、支持取消。

设计：
- start() 创建 collect_jobs 记录，并用守护线程后台跑 pipeline。
  用线程而非 asyncio.create_task：后者在 uvicorn ASGI loop 中调度不可靠
  （实测后台 task 不推进），线程独立 event loop（asyncio.run）稳定。
- 内存 _TASKS 维护 job_id → CollectContext，供取消。
- pipeline 自身在每个 item 后 commit done/total/failed（已在阶段1实现），
  因此进度查询直接读 collect_jobs 表，无需额外 IPC。
- SSE 推送：服务端 stream 定时读表推送。
"""

import asyncio
import threading
from datetime import datetime

from sqlalchemy import select

from app.collect.base import CollectContext, SourceConnector
from app.collect.pipeline import run_pipeline
from app.collect.registry import get_connector
from app.db import SessionLocal
from app.models import CollectJob, Exhibit


def _make_bound(connector, items):
    """构造一个 discover 返回预发现 items、fetch/parse 委托给原 connector 的实例。

    用 type() 动态创建，把方法实现在创建字典中提供（而非类创建后赋值），
    这样 ABC 能在类创建时识别抽象方法已被实现，可正常实例化。
    """

    class _Bound(SourceConnector):
        source = connector.source
        default_confidence = connector.default_confidence
        target_type = connector.target_type

        async def discover(self, c):
            return items

        async def fetch(self, item, c):
            return await connector.fetch(item, c)

        async def parse(self, raw, item, c):
            return await connector.parse(raw, item, c)

    return _Bound()


class CollectRunner:
    def __init__(self):
        self._tasks: dict[int, CollectContext] = {}

    def start(self, museum_id: int | None, source: str, enable_llm_refine: bool) -> int:
        """启动一个采集任务，返回 job_id。后台守护线程执行。"""
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
        self._tasks[job_id] = ctx
        # 守护线程跑独立 event loop，避免 uvicorn ASGI loop 调度问题
        thread = threading.Thread(
            target=self._thread_run,
            args=(job_id, museum_id, source, enable_llm_refine, ctx),
            daemon=True,
        )
        thread.start()
        return job_id

    def _thread_run(self, job_id, museum_id, source, enable_llm_refine, ctx):
        """线程入口：创建独立 event loop 跑 async pipeline。"""
        asyncio.run(self._run(job_id, museum_id, source, enable_llm_refine, ctx))

    async def _run(self, job_id, museum_id, source, enable_llm_refine, ctx):
        """实际执行（后台协程）。每步用独立 session。"""
        db = SessionLocal()
        try:
            connector = get_connector(source)
            # 对百科/维基：从该馆现有展品名取种子；对官网/发现源：connector 自带 discover
            items = await self._discover_with_seeds(connector, museum_id, ctx, db)

            if items is not None:
                # 用闭包注入预发现的 items。注意：必须用 type() 动态创建并
                # 在字典中提供全部抽象方法实现，否则 ABC 实例化时报错
                # （ABC 在类创建时扫描 __abstractmethods__，类创建后再赋值无效）。
                bound = _make_bound(connector, items)
            else:
                bound = connector

            await run_pipeline(
                bound, museum_id, db, ctx,
                enable_llm_refine=enable_llm_refine, job_id=job_id,
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
        """取消任务。返回是否找到运行中的任务。

        线程模式下无法直接杀死线程，通过 ctx.cancel() 设置取消信号，
        pipeline 在下一条 item 前检查并退出循环。
        """
        ctx = self._tasks.get(job_id)
        if not ctx:
            return False
        ctx.cancel()
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

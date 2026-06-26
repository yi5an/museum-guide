"""采集引擎基础设施：CollectContext 与 SourceConnector 抽象基类。"""

import asyncio
from abc import ABC, abstractmethod

import httpx


async def async_get(url: str, headers: dict, timeout: int = 10) -> httpx.Response:
    """同步 httpx.get 的 async 包装，避免在 event loop 里阻塞。

    connector 的 discover/fetch 在 async 上下文里调用，但底层用同步 httpx。
    用 asyncio.to_thread 把网络阻塞隔离到线程池，防止卡死 uvicorn 主 loop。
    默认跟随重定向（不少官网详情页是 302 跳转）。
    """
    return await asyncio.to_thread(
        httpx.get, url, headers=headers, timeout=timeout, follow_redirects=True
    )





class CollectContext:
    """单次采集运行的共享上下文：限速、重试、取消信号。

    所有 connector 通过 ctx.sleep() 做礼貌延迟，pipeline 在每条 item 前
    检查 ctx.cancelled 以支持取消。
    """

    def __init__(self, min_interval: float = 0.5, max_retries: int = 3):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    async def sleep(self, seconds: float) -> None:
        """礼貌延迟；若已取消则立即返回。"""
        if self._cancelled:
            return
        await asyncio.sleep(seconds)


class SourceConnector(ABC):
    """采集源抽象基类。每个来源实现 discover/fetch/parse 三阶段。

    discover/fetch/parse 分离的设计，使 parse 可对已落盘的 raw 文件反复重跑，
    无需重新抓取源站。
    """

    source: str = ""          # "baike" / "wiki" / "official" / "wiki_list"
    default_confidence: float = 0.5
    target_type: str = "exhibit"  # museum / exhibit / image

    @abstractmethod
    async def discover(self, ctx: CollectContext) -> list[dict]:
        """发现阶段：返回原始待采条目列表。

        每条至少含: {"name": str, "source_ref": str}
        其余原始字段由各 connector 自定义。
        """

    @abstractmethod
    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        """抓取阶段：返回单个条目的原始内容文本（HTML/JSON），失败返回 None。"""

    @abstractmethod
    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        """解析阶段：raw 文本 -> 标准字段 dict。

        标准字段: {"name","category","dynasty","description","images":[...]}
        返回 None 表示解析失败。
        """

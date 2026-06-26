"""source 名 -> connector 工厂的注册表。"""

from app.collect.base import SourceConnector
from app.collect.sources.baike import BaikeConnector
from app.collect.sources.official_guobo import OfficialGuoboConnector
from app.collect.sources.wiki import WikiConnector
from app.collect.sources.wiki_list import WikiListConnector

_REGISTRY: dict[str, type[SourceConnector]] = {
    "baike": BaikeConnector,
    "wiki": WikiConnector,
    "wiki_list": WikiListConnector,
    "official": OfficialGuoboConnector,
}


def get_connector(source: str, **kwargs) -> SourceConnector:
    cls = _REGISTRY.get(source)
    if cls is None:
        raise ValueError(f"未知 source: {source}（可选: {list(_REGISTRY)}）")
    return cls(**kwargs)


def available_sources() -> list[str]:
    return list(_REGISTRY)

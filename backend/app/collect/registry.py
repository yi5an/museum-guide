"""source 名 -> connector 的注册表。

官网(official)源是 per-site 的：不同博物馆有不同的官网 connector。
通过 museum_id 查找对应的官网 connector；找不到则该馆不支持官网采集。
"""

from app.collect.base import SourceConnector
from app.collect.sources.baike import BaikeConnector
from app.collect.sources.official_guobo import OfficialGuoboConnector
from app.collect.sources.official_henan import OfficialHenanConnector
from app.collect.sources.wiki import WikiConnector
from app.collect.sources.wiki_list import WikiListConnector

# 通用源（所有博物馆适用）
_REGISTRY: dict[str, type[SourceConnector]] = {
    "baike": BaikeConnector,
    "wiki": WikiConnector,
    "wiki_list": WikiListConnector,
}

# 官网源（per-site）：museum_id -> 该馆的官网 connector
_OFFICIAL_REGISTRY: dict[int, type[SourceConnector]] = {
    1: OfficialGuoboConnector,    # 中国国家博物馆
    7: OfficialHenanConnector,    # 河南博物院
}


def get_connector(source: str, museum_id: int | None = None, **kwargs) -> SourceConnector:
    """获取 connector 实例。

    source="official" 时需提供 museum_id，按馆查对应官网 connector；
    若该馆未接入官网采集，抛 ValueError。
    """
    if source == "official":
        if museum_id is None:
            raise ValueError("官网采集(official)需要 museum_id")
        cls = _OFFICIAL_REGISTRY.get(museum_id)
        if cls is None:
            raise ValueError(
                f"博物馆 id={museum_id} 暂未接入官网采集"
                f"（已接入：{list(_OFFICIAL_REGISTRY)}）"
            )
        return cls(**kwargs)

    cls = _REGISTRY.get(source)
    if cls is None:
        raise ValueError(f"未知 source: {source}（可选: {available_sources()}）")
    return cls(**kwargs)


def available_sources() -> list[str]:
    """所有可用的 source 名（不含 official，因后者 per-site）。"""
    return list(_REGISTRY) + ["official"]


def official_museum_ids() -> list[int]:
    """已接入官网采集的博物馆 id 列表。"""
    return list(_OFFICIAL_REGISTRY)


def has_official(museum_id: int) -> bool:
    """该博物馆是否已接入官网采集。"""
    return museum_id in _OFFICIAL_REGISTRY

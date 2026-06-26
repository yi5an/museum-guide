"""维基"中国博物馆列表"分类页采集 connector（发现源）。

从维基分类页提取博物馆名称清单，作为后续内容采集的目标集合。
target_type=museum。纯规则，不接 LLM。
"""

import re
import urllib.parse

from app.collect.base import CollectContext, SourceConnector, async_get

_HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}
# 维基"中国的博物馆"分类页
_LIST_URL = "https://zh.wikipedia.org/wiki/Category:%E4%B8%AD%E5%9B%BD%E7%9A%84%E5%8D%9A%E7%89%A9%E9%A6%86"

# 噪声词：维基功能链接、非博物馆条目
_SKIP = {
    "编辑", "分类", "首页", "Wikipedia", "Help", "维基百科", "登录", "创建账户",
    "最近更改", "随机条目", "资助", "关于维基百科", "免责声明",
}


class WikiListConnector(SourceConnector):
    source = "wiki_list"
    default_confidence = 0.6
    target_type = "museum"

    async def discover(self, ctx: CollectContext) -> list[dict]:
        try:
            resp = await async_get(_LIST_URL, _HEADERS, timeout=15)
            if resp.status_code != 200:
                return []
            html = resp.text
        except Exception:
            return []

        # 提取分类成员链接：<a href="/wiki/XXX" title="XXX">
        names = set()
        for href, title in re.findall(
            r'<a[^>]*href="(/wiki/[^"]*)"[^>]*title="([^"]*)"', html
        ):
            title = title.strip()
            if (
                not title or title in _SKIP
                or title.startswith("Category:")
                or title.startswith("Wikipedia:")
                or ("博物馆" not in title and "博物院" not in title)  # 只保留博物馆/博物院条目
            ):
                continue
            names.add(title)

        return [
            {
                "name": n,
                "source_ref": f"https://zh.wikipedia.org{urllib.parse.quote('/wiki/' + n)}",
            }
            for n in sorted(names)
        ]

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        # 发现源本身不抓详情；详情靠后续 wiki connector。
        # 此处返回占位，让 pipeline 流程闭合（parse 解析占位为最小博物馆字段）。
        return "{}"

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        return {
            "name": item["name"],
            "lat": 0.0,
            "lng": 0.0,
            "description": None,
            "source_ref": item.get("source_ref"),
        }

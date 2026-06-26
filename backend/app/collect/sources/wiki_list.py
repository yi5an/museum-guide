"""维基中国博物馆列表采集 connector（发现源）。

策略：维基「中华人民共和国博物馆列表」主页只列省份索引，单馆分散在各省份
子列表条目里。故两步：
  1. 从「中国博物馆列表」分类页拿到各省份子列表条目 URL
  2. 从每个省份子列表条目提取博物馆/博物院名称

target_type=museum。纯规则，不接 LLM。
"""

import re
import urllib.parse

from app.collect.base import CollectContext, SourceConnector, async_get

_HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}

# 「中国博物馆列表」分类页（含各省份子条目）
_CATEGORY_URL = (
    "https://zh.wikipedia.org/wiki/Category:"
    "%E4%B8%AD%E5%9B%BD%E5%8D%9A%E7%89%A9%E9%A6%86%E5%88%97%E8%A1%A8"
)

_SKIP = {
    "编辑", "分类", "首页", "Wikipedia", "Help", "维基百科", "登录", "创建账户",
    "最近更改", "随机条目", "资助", "关于维基百科", "免责声明",
    "博物馆", "博物馆列表", "中国博物馆列表", "中华人民共和国博物馆列表",
    "国家一级博物馆", "国家二级博物馆", "国家三级博物馆",
    "Category:中国博物馆列表",
}

# 省份子条目 URL 提取（标题含"博物馆列表"且是 wiki 条目链接）
_PROV_REGEX = r'<a[^>]*href="(/wiki/[^"]*)"[^>]*title="([^"]*博物馆列表)"'


def _is_museum_title(title: str) -> bool:
    """是否是博物馆/博物院条目（排除导航、分类、列表索引本身）。"""
    if not title or title in _SKIP:
        return False
    if title.startswith("Category:") or title.startswith("Wikipedia:"):
        return False
    if "列表" in title:
        return False
    return "博物馆" in title or "博物院" in title


class WikiListConnector(SourceConnector):
    source = "wiki_list"
    default_confidence = 0.6
    target_type = "museum"

    async def discover(self, ctx: CollectContext) -> list[dict]:
        # 1. 从分类页拿省份子列表条目 URL
        try:
            resp = await async_get(_CATEGORY_URL, _HEADERS, timeout=15)
            if resp.status_code != 200:
                return []
        except Exception:
            return []

        prov_pages = []
        for href, title in re.findall(_PROV_REGEX, resp.text):
            prov_pages.append("https://zh.wikipedia.org" + href)

        if not prov_pages:
            return []

        # 2. 从每个省份页提取博物馆名（限定数量，避免过多请求）
        names = set()
        for page_url in prov_pages[:30]:  # 最多 30 个省份页
            try:
                presp = await async_get(page_url, _HEADERS, timeout=15)
                if presp.status_code != 200:
                    continue
            except Exception:
                continue
            # 提取 wiki 内部链接，title 含博物馆/博物院
            for href, title in re.findall(
                r'<a[^>]*href="(/wiki/[^"]*)"[^>]*title="([^"]*)"', presp.text
            ):
                if _is_museum_title(title):
                    names.add(title.strip())
            await ctx.sleep(0.5)  # 礼貌延迟

        return [
            {
                "name": n,
                "source_ref": f"https://zh.wikipedia.org{urllib.parse.quote('/wiki/' + n)}",
            }
            for n in sorted(names)
        ]

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        # 发现源本身不抓详情；详情靠后续 wiki connector。
        # 返回占位，让 pipeline 流程闭合（parse 解析占位为最小博物馆字段）。
        return "{}"

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        return {
            "name": item["name"],
            "lat": 0.0,
            "lng": 0.0,
            "description": None,
            "source_ref": item.get("source_ref"),
        }

"""维基百科采集 connector。

整合自 app/seed_from_wiki.py（展品摘要）与 app/fetch_museum_images.py（博物馆建筑图）。
纯规则解析，不接 LLM。
"""

import json
import urllib.parse

from app.collect.base import CollectContext, SourceConnector, async_get

_HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}


class WikiConnector(SourceConnector):
    """展品摘要维基采集。target_type=exhibit。"""

    source = "wiki"
    default_confidence = 0.6
    target_type = "exhibit"

    async def discover(
        self, ctx: CollectContext, exhibit_names: list[str] | None = None
    ) -> list[dict]:
        names = exhibit_names or []
        return [
            {"name": n, "source_ref": f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(n)}"}
            for n in names
        ]

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        """先搜索词条标题，再取摘要，合并成一个 JSON 文本返回。"""
        encoded = urllib.parse.quote(item["name"])
        search_url = (
            "https://zh.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={encoded}&format=json&srlimit=1"
        )
        try:
            sresp = await async_get(search_url, _HEADERS, timeout=10)
            results = sresp.json().get("query", {}).get("search", [])
            if not results:
                return None
            title = results[0]["title"]
            tenc = urllib.parse.quote(title)
            sum_url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{tenc}"
            mresp = await async_get(sum_url, _HEADERS, timeout=10)
            if mresp.status_code != 200:
                return None
            return json.dumps({"title": title, "data": mresp.json()}, ensure_ascii=False)
        except Exception:
            return None

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return None
        extract = obj.get("data", {}).get("extract", "")
        if not extract:
            return None

        dynasty = None
        for d in ["商", "西周", "东周", "春秋", "战国", "秦", "汉", "唐", "宋", "元", "明", "清"]:
            if d in extract:
                dynasty = d
                break

        return {
            "name": item["name"],
            "category": None,
            "dynasty": dynasty,
            "description": extract,
            "source_ref": f"https://zh.wikipedia.org/wiki/{obj.get('title', item['name'])}",
        }

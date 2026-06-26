"""百度百科采集 connector。

迁自 app/seed_from_baike.py，纳入统一 pipeline 框架。
不接 LLM，纯规则解析百科 openapi 返回的 JSON。
"""

import json
import urllib.parse

from app.collect.base import CollectContext, SourceConnector, async_get

_HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}


class BaikeConnector(SourceConnector):
    source = "baike"
    default_confidence = 0.5
    target_type = "exhibit"

    async def discover(
        self, ctx: CollectContext, exhibit_names: list[str] | None = None
    ) -> list[dict]:
        """discover 阶段需要传入展品名列表（来自该馆已入库或待采清单）。

        与基类签名不同：百科需要"查什么"。实际调用时由 pipeline/CLI 传入。
        """
        names = exhibit_names or []
        return [
            {
                "name": name,
                "source_ref": f"https://baike.baidu.com/item/{urllib.parse.quote(name)}",
            }
            for name in names
        ]

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        encoded = urllib.parse.quote(item["name"])
        url = (
            "https://baike.baidu.com/api/openapi/BaikeLemmaCardApi"
            f"?scope=103&format=json&appid=379020&bk_key={encoded}&bk_length=600"
        )
        try:
            resp = await async_get(url, _HEADERS, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data.get("key"):
                return None
            return json.dumps(data, ensure_ascii=False)
        except Exception:
            return None

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        abstract = data.get("abstract", "")
        if not abstract:
            return None

        # 朝代/类别推断（迁自 seed_from_baike 的轻规则）
        text = abstract
        dynasty = None
        for d in ["商", "西周", "东周", "春秋", "战国", "秦", "汉", "唐", "宋", "元", "明", "清"]:
            if d in text:
                dynasty = d
                break
        category = None
        for k, v in [("青铜", "青铜器"), ("陶", "陶器"), ("瓷", "瓷器"), ("玉", "玉器"), ("金", "金器")]:
            if k in text:
                category = v
                break

        return {
            "name": item["name"],
            "category": category,
            "dynasty": dynasty,
            "description": abstract,
            "source_ref": item.get("source_ref"),
        }

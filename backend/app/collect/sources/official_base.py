"""官网采集共享基类：per-site 可配置的 OfficialConnector。

每家博物馆官网结构不同，但采集流程相同：
- discover：抓目录页（可能分页），用 site_link_regex 提取展品名+详情链接
- fetch：抓详情页 HTML
- parse：交 LLM#1 提取标准字段（LLMExtractor，与具体官网解耦）

子类只需配置类属性：museum_name / catalog_urls / link_regex / skip_titles 等。
LLM#1 提取复用，无需 per-site 实现。
"""

import re

from app.collect.base import CollectContext, SourceConnector, async_get
from app.collect.llm_extractor import LLMExtractor

HEADERS = {"User-Agent": "Mozilla/5.0"}


class OfficialConnector(SourceConnector):
    """官网采集基类。子类配置类属性即可，无需重写方法。"""

    source = "official"
    default_confidence = 0.9
    target_type = "exhibit"

    # === 子类必须配置 ===
    museum_name: str = ""           # 博物馆中文名（喂给 LLM 提取器）
    catalog_urls: list[str] = []     # 目录页 URL 列表（分页则列全）
    link_regex: str = ""             # 从目录页 HTML 提取 (href, title) 的正则
    link_regex_flags: int = 0        # 正则标志（如 re.DOTALL 用于跨标签匹配）
    base_url: str = ""               # 相对链接补全用的站点根（含协议，如 https://x.cn）

    # === 可选配置 ===
    skip_titles: set[str] = set()    # 目录页里的噪声标题（导航项等）
    catalog_delay: float = 1.0       # 目录页之间的礼貌延迟

    def __init__(self):
        self._llm = LLMExtractor()

    def _absolutize(self, href: str) -> str:
        """把相对链接补成绝对 URL。支持多种相对形式。"""
        if href.startswith("//"):
            return "https:" + href           # 协议相对 URL
        if href.startswith("./"):
            return self.base_url.rstrip("/") + "/" + href[2:]
        if href.startswith("/"):
            return self.base_url.rstrip("/") + href
        return href

    async def discover(self, ctx: CollectContext) -> list[dict]:
        results = []
        for url in self.catalog_urls:
            try:
                resp = await async_get(url, HEADERS, timeout=15)
                if resp.status_code != 200:
                    break
            except Exception:
                break
            for href, title in re.findall(self.link_regex, resp.text, self.link_regex_flags):
                title = title.strip()
                if not title or title in self.skip_titles:
                    continue
                results.append({
                    "name": title,
                    "source_ref": self._absolutize(href),
                })
            await ctx.sleep(self.catalog_delay)

        # 去重
        seen, unique = set(), []
        for r in results:
            if r["name"] not in seen:
                seen.add(r["name"])
                unique.append(r)
        return unique

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        try:
            resp = await async_get(item["source_ref"], HEADERS, timeout=15)
            return resp.text if resp.status_code == 200 else None
        except Exception:
            return None

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        # LLM#1 提取；LLM 失败则返回带名称的最小字段（不阻断流程）
        fields = await self._llm.extract_exhibit(raw, item["source_ref"], self.museum_name)
        if fields:
            fields["name"] = fields.get("name") or item["name"]
            return fields
        # 兜底：至少把名称入库
        return {
            "name": item["name"], "category": None, "dynasty": None,
            "description": item["name"], "source_ref": item["source_ref"],
        }

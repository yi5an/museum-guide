"""国博官网采集 connector（per-site）。

迁自 app/crawl_guobo.py。目录页用正则提展品名+详情链接（规则，免费），
详情页正文交 LLMExtractor（LLM#1）提取标准字段。
每家官网结构不同，单独写一个 connector；其他馆照此模板扩展。
"""

import re

from app.collect.base import CollectContext, SourceConnector, async_get
from app.collect.llm_extractor import LLMExtractor

BASE = "https://www.chnmuseum.cn/zp/zpml/kgfjp/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

SKIP_TITLES = {
    "国家博物馆", "首页", "征集", "保管", "研究", "展览", "社教", "文创", "服务",
    "学习", "视频", "登录", "注册", "分享", "下载", "导航", "馆藏精品",
    "隐私政策", "隐私安全声明", "版权声明", "留言板", "联系我们", "网站地图",
}


class OfficialGuoboConnector(SourceConnector):
    source = "official"
    default_confidence = 0.9
    target_type = "exhibit"

    def __init__(self):
        self._llm = LLMExtractor()

    async def discover(self, ctx: CollectContext) -> list[dict]:
        results = []
        # 11 个分页
        for i in range(11):
            page = "" if i == 0 else f"_{i}"
            url = f"{BASE}index{page}.shtml"
            try:
                resp = await async_get(url, HEADERS, timeout=15)
                if resp.status_code != 200:
                    break
            except Exception:
                break
            for href, title in re.findall(
                r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"', resp.text
            ):
                title = title.strip()
                if not title or title in SKIP_TITLES:
                    continue
                if href.startswith("./"):
                    href = BASE + href[2:]
                elif href.startswith("/"):
                    href = "https://www.chnmuseum.cn" + href
                results.append({"name": title, "source_ref": href})
            await ctx.sleep(1)  # 礼貌延迟

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
        fields = await self._llm.extract_exhibit(raw, item["source_ref"], "中国国家博物馆")
        if fields:
            fields["name"] = fields.get("name") or item["name"]
            return fields
        # 兜底：至少把名称入库
        return {
            "name": item["name"], "category": None, "dynasty": None,
            "description": item["name"], "source_ref": item["source_ref"],
        }

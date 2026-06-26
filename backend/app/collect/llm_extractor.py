"""LLM#1 提取器：从任意博物馆官网详情页 HTML 提取结构化展品字段。

只服务官网 per-site connector。链接发现用规则，LLM 负责把详情页正文
提取成 {name, dynasty, category, description}。复用 model_router 通道。
"""

import re

from app.services.model_router import model_router

_SCHEMA = (
    '{"name":"展品名","dynasty":"朝代(无则null)","category":"类别(无则null)","description":"简介"}'
)

# 朝代/类别兜底规则（迁自 crawl_guobo.py）
_DYNASTIES = [
    "新石器", "商", "西周", "东周", "春秋", "战国", "秦", "汉",
    "魏晋", "南北朝", "唐", "五代", "宋", "辽", "金", "元", "明", "清", "民国", "现代",
]
_CATEGORY_RULES = [
    ("青铜", "青铜器"), ("陶", "陶器"), ("瓷", "瓷器"), ("玉", "玉器"),
    ("金", "金器"), ("银", "银器"), ("石", "石刻"), ("骨", "骨器"),
    ("漆", "漆器"), ("砖", "砖瓦"), ("镜", "铜镜"),
]


def _strip_html(html: str) -> str:
    """去标签噪声，截取正文（控 token）。"""
    text = re.sub(
        r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:3000]  # 截断，控成本


class LLMExtractor:
    async def extract_exhibit(self, html: str, url: str, museum_name: str) -> dict | None:
        text = _strip_html(html)
        if len(text) < 10:
            return None

        prompt = (
            f"你是博物馆文物信息提取专家。下面是{museum_name}官网某展品页面的正文，"
            "提取展品的结构化信息。\n\n"
            f"页面正文：\n{text[:2000]}"
        )
        try:
            data = await model_router.generate_structured(prompt, _SCHEMA)
        except Exception:
            data = {}

        if not data:
            return None

        name = data.get("name") or ""
        dynasty = data.get("dynasty")
        category = data.get("category")
        description = data.get("description") or name

        # 兜底：缺朝代从描述/名称匹配
        if not dynasty:
            for d in _DYNASTIES:
                if d in description or d in name:
                    dynasty = d
                    break

        # 兜底：缺类别从名称/描述匹配
        if not category:
            for k, v in _CATEGORY_RULES:
                if k in name or k in description:
                    category = v
                    break

        return {
            "name": name,
            "category": category,
            "dynasty": dynasty,
            "description": description,
            "source_ref": url,
        }

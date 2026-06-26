"""LLM#2 数据整理层：入库前对所有来源字段的通用整理工序。

与来源解耦。允许改写描述、补全空字段、朝代/类别格式归一化。
按任务/源开关（pipeline 的 enable_llm_refine）。LLM 失败时优雅兜底。
"""

from app.services.model_router import model_router

_SCHEMA = (
    '{"description":"精简后的简介(≤120字)","category":"归一化类别或null","dynasty":"归一化朝代或null"}'
)

# 朝代/类别归一化表（把各种写法归到标准值）
_DYNASTY_NORMALIZE = {
    "商朝": "商代", "商晚期": "商代晚期", "周朝": "周代",
    "汉朝": "汉代", "西汉": "西汉", "东汉": "东汉",
    "唐朝": "唐代", "宋朝": "宋代", "元朝": "元代",
    "明朝": "明代", "清朝": "清代", "民国": "民国", "现代": "现代",
}


class LLMRefiner:
    async def refine(self, fields: dict, enable: bool = True) -> dict:
        """整理单条字段。enable=False 直接返回原 dict（不拷贝）。

        LLM 失败时返回原字段，不阻断 pipeline。
        """
        if not enable:
            return fields

        desc = fields.get("description") or ""
        if len(desc) < 5:
            # 内容太少不值得调 LLM
            return fields

        prompt = (
            "你是博物馆文物数据清洗专家。整理下面这条展品信息：\n"
            "1. 精简描述（去噪声标点、重复字句，≤120字，保留关键事实）\n"
            "2. 归一化类别（如'青铜器'）和朝代（如'商代'）\n"
            "3. 不确定的留 null\n\n"
            f"原始信息：\n{fields}"
        )
        try:
            data = await model_router.generate_structured(prompt, _SCHEMA)
        except Exception:
            return fields

        refined = dict(fields)
        if data.get("description"):
            refined["description"] = data["description"]
        if data.get("category"):
            refined["category"] = data["category"]
        elif fields.get("category"):
            refined["category"] = _DYNASTY_NORMALIZE.get(fields["category"], fields["category"])
        if data.get("dynasty"):
            refined["dynasty"] = data["dynasty"]
        elif fields.get("dynasty"):
            refined["dynasty"] = _DYNASTY_NORMALIZE.get(fields["dynasty"], fields["dynasty"])

        return refined

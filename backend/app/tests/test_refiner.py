from unittest.mock import AsyncMock, patch

from app.collect.refiner import LLMRefiner


async def test_refine_cleans_description_and_fills_fields():
    refiner = LLMRefiner()
    raw_fields = {
        "name": "后母戊鼎",
        "category": None,
        "dynasty": "商朝",  # 非标准写法
        "description": "后母戊鼎。。。。。是商代晚期青铜方鼎，1939年出土于河南安阳。。",
    }

    fake_llm = AsyncMock()
    fake_llm.generate_structured.return_value = {
        "description": "后母戊鼎是商代晚期青铜方鼎，1939年出土于河南安阳。",
        "category": "青铜器",
        "dynasty": "商代",
    }

    with patch("app.collect.refiner.model_router", fake_llm):
        refined = await refiner.refine(raw_fields)

    assert "。。。。" not in refined["description"]  # 噪声已清
    assert refined["category"] == "青铜器"
    assert refined["dynasty"] == "商代"  # 归一化
    assert refined["name"] == "后母戊鼎"  # 名称不动


async def test_refine_disabled_returns_original():
    """enable=False 时原样返回。"""
    refiner = LLMRefiner()
    raw = {"name": "x", "category": None, "dynasty": None, "description": "y"}
    out = await refiner.refine(raw, enable=False)
    assert out is raw


async def test_refine_llm_failure_falls_back_gracefully():
    """LLM 调用失败时，返回原字段（不阻断流程）。"""
    refiner = LLMRefiner()
    raw = {"name": "x", "category": None, "dynasty": None, "description": "足够长的描述文本"}

    fake_llm = AsyncMock()
    fake_llm.generate_structured.side_effect = Exception("LLM 挂了")

    with patch("app.collect.refiner.model_router", fake_llm):
        refined = await refiner.refine(raw)

    assert refined["name"] == "x"  # 兜底返回原值

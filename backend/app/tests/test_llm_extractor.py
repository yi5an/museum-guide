from unittest.mock import AsyncMock, patch

from app.collect.llm_extractor import LLMExtractor


async def test_extract_exhibit_parses_llm_json():
    extractor = LLMExtractor()
    html = "<html><body>后母戊鼎 商代 青铜器 正文...</body></html>"

    # mock model_router.generate_structured 返回标准字段
    fake_llm = AsyncMock()
    fake_llm.generate_structured.return_value = {
        "name": "后母戊鼎",
        "dynasty": "商代",
        "category": "青铜器",
        "description": "后母戊鼎是商代晚期青铜方鼎。",
    }

    with patch("app.collect.llm_extractor.model_router", fake_llm):
        fields = await extractor.extract_exhibit(html, "http://guobo/x", "中国国家博物馆")

    assert fields["name"] == "后母戊鼎"
    assert fields["dynasty"] == "商代"
    assert fields["category"] == "青铜器"
    assert "商代" in fields["description"]


async def test_extract_exhibit_fallback_when_llm_missing_fields():
    """LLM 缺 category 时，用名称/描述规则兜底。"""
    extractor = LLMExtractor()
    html = "<html><body>司母戊鼎，商代王室祭祀用青铜方鼎。</body></html>"

    fake_llm = AsyncMock()
    fake_llm.generate_structured.return_value = {
        "name": "司母戊鼎",
        "dynasty": None,
        "category": None,
        "description": "某青铜大鼎",
    }

    with patch("app.collect.llm_extractor.model_router", fake_llm):
        fields = await extractor.extract_exhibit(html, "http://x", "国博")

    # 描述含"青铜"-> 兜底成青铜器
    assert fields["category"] == "青铜器"

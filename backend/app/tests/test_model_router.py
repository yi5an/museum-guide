from unittest.mock import AsyncMock, patch

import pytest

from app.services.model_router import ModelRouter


@pytest.mark.asyncio
async def test_recognize_returns_candidates():
    router = ModelRouter(base_url="http://fake/v1", api_key="fake", model="glm-5.2")
    fake_response = {
        "candidates": [
            {"exhibit_id": None, "name": "商代青铜鼎", "confidence": 0.72},
        ],
        "best_match": {"exhibit_id": None, "name": "商代青铜鼎", "confidence": 0.72},
        "best_confidence": 0.72,
        "raw_meta": {"name": "商代青铜鼎", "category": "青铜器", "dynasty": "商代", "confidence": 0.72},
    }
    with patch.object(router, "_call_vision_llm", new=AsyncMock(return_value=fake_response)):
        result = await router.recognize(image_base64="fake", museum_id=1, hint="青铜器")
    assert result["best_confidence"] == 0.72
    assert result["best_match"]["name"] == "商代青铜鼎"


@pytest.mark.asyncio
async def test_generate_narration_returns_blocks():
    router = ModelRouter(base_url="http://fake/v1", api_key="fake", model="glm-5.2")
    fake_blocks = {"blocks": [{"type": "text", "section": "历史脉络", "text": "测试"}]}
    with patch.object(router, "_call_text_llm_json", new=AsyncMock(return_value=fake_blocks)):
        result = await router.generate_narration(
            exhibit_info={"name": "测试鼎", "category": "青铜器"},
            lang="zh",
        )
    assert result["blocks"][0]["text"] == "测试"
    assert result["blocks"][0]["section"] == "历史脉络"


@pytest.mark.asyncio
async def test_chat_returns_reply():
    router = ModelRouter(base_url="http://fake/v1", api_key="fake", model="glm-5.2")
    with patch.object(router, "_call_text_llm", new=AsyncMock(return_value="这是回复")):
        reply = await router.chat(
            exhibit_info={"name": "司母戊鼎"},
            message="铭文什么意思",
            lang="zh",
            chat_history=[],
        )
    assert reply == "这是回复"


@pytest.mark.asyncio
async def test_recognize_handles_invalid_json():
    """LLM 返回非 JSON 时降级为默认值。"""
    router = ModelRouter(base_url="http://fake/v1", api_key="fake", model="glm-5.2")
    # mock _client.chat.completions.create 返回非 JSON content
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "这不是JSON"
    with patch.object(router._client.chat.completions, "create", new=AsyncMock(return_value=mock_resp)):
        result = await router.recognize(image_base64="fake", museum_id=1)
    assert result["best_match"]["name"] == "未知"
    assert result["best_confidence"] == 0.0

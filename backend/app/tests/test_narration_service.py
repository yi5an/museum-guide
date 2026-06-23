from unittest.mock import AsyncMock, patch

import pytest

from app.models import Exhibit, Museum, Narration
from app.services.narration import NarrationService


def _seed_exhibit(test_db, with_narration=False, lang="zh"):
    m = Museum(name="x", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    e = Exhibit(
        museum_id=m.id,
        name="司母戊鼎",
        category="青铜器",
        dynasty="商代",
        status="active",
        source="official",
    )
    test_db.add(e)
    test_db.flush()
    if with_narration:
        n = Narration(
            exhibit_id=e.id,
            lang=lang,
            content={"blocks": [{"type": "text", "section": "历史", "text": "官方讲解"}]},
            tier=1,
            source_label="官方",
        )
        test_db.add(n)
        test_db.flush()
    return e


def test_tier1_returns_official_narration(test_db):
    exhibit = _seed_exhibit(test_db, with_narration=True)
    svc = NarrationService()
    result = svc.get_narration(test_db, exhibit.id, "zh")
    assert result is not None
    assert result["tier"] == 1
    assert result["source_label"] == "官方"


@pytest.mark.asyncio
async def test_tier2_generates_and_persists(test_db):
    """Tier 1 没命中 → 调 AI 生成 → 回流入库 → 第二次命中。"""
    exhibit = _seed_exhibit(test_db, with_narration=False)
    svc = NarrationService()
    fake_blocks = {"blocks": [{"type": "text", "section": "历史", "text": "AI 生成"}]}
    with patch("app.services.narration.model_router") as mr:
        mr.generate_narration = AsyncMock(return_value=fake_blocks)
        result = await svc.get_or_generate_narration(test_db, exhibit.id, "zh")
    assert result["tier"] == 2
    assert result["source_label"] == "AI 推测，仅供参考"

    # 验证已回流：第二次调用不再调 AI
    with patch("app.services.narration.model_router") as mr:
        mr.generate_narration = AsyncMock(
            side_effect=AssertionError("不应该再调 AI")
        )
        result2 = await svc.get_or_generate_narration(test_db, exhibit.id, "zh")
    assert result2["tier"] == 2  # 回流的也是 tier 2


def test_lang_fallback_to_zh(test_db):
    """请求日语但只有中文 → 退回中文官方内容。"""
    exhibit = _seed_exhibit(test_db, with_narration=True, lang="zh")
    svc = NarrationService()
    result = svc.get_narration(test_db, exhibit.id, "ja")
    assert result is not None
    assert result["tier"] == 1
    assert result["source_label"] == "官方"


def test_no_narration_returns_none(test_db):
    """库里没有任何讲解，且不调 AI 时返回 None。"""
    exhibit = _seed_exhibit(test_db, with_narration=False)
    svc = NarrationService()
    result = svc.get_narration(test_db, exhibit.id, "zh")
    assert result is None

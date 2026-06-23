from unittest.mock import AsyncMock, patch

from app.models import Exhibit, Museum, Narration


def _seed(test_db, with_narration=True):
    m = Museum(name="x", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    e = Exhibit(museum_id=m.id, name="司母戊鼎", status="active", source="official")
    test_db.add(e)
    test_db.flush()
    if with_narration:
        n = Narration(
            exhibit_id=e.id,
            lang="zh",
            content={"blocks": [{"type": "text", "section": "历史", "text": "官方"}]},
            tier=1,
            source_label="官方",
        )
        test_db.add(n)
        test_db.flush()
    return e


def test_narrate_tier1(client, test_db):
    exhibit = _seed(test_db, with_narration=True)
    resp = client.post("/api/narrate", json={"exhibit_id": exhibit.id, "lang": "zh"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == 1
    assert data["source_label"] == "官方"
    assert len(data["content"]["blocks"]) == 1


def test_narrate_tier2_generates(client, test_db):
    exhibit = _seed(test_db, with_narration=False)
    fake_blocks = {"blocks": [{"type": "text", "section": "历史脉络", "text": "AI 生成内容"}]}
    with patch("app.services.narration.model_router") as mr:
        mr.generate_narration = AsyncMock(return_value=fake_blocks)
        resp = client.post("/api/narrate", json={"exhibit_id": exhibit.id, "lang": "zh"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == 2
    assert "AI" in data["source_label"]
    assert data["content"]["blocks"][0]["text"] == "AI 生成内容"


def test_narrate_lang_fallback(client, test_db):
    """请求日语，库里只有中文 → 退回中文 tier 1。"""
    exhibit = _seed(test_db, with_narration=True)
    resp = client.post("/api/narrate", json={"exhibit_id": exhibit.id, "lang": "ja"})
    assert resp.status_code == 200
    assert resp.json()["tier"] == 1

from unittest.mock import AsyncMock, patch

from app.models import Exhibit, Museum


def _seed(test_db):
    m = Museum(
        name="国博", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0
    )
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
    return m, e


def test_recognize_high_confidence_match(client, test_db):
    """GLM-4V 返回高置信度且名字匹配库里展品 → 命中库里记录。"""
    _, exhibit = _seed(test_db)
    fake_resp = {
        "candidates": [{"exhibit_id": None, "name": "司母戊鼎", "confidence": 0.92}],
        "best_match": {"exhibit_id": None, "name": "司母戊鼎", "confidence": 0.92},
        "best_confidence": 0.92,
        "raw_meta": {"name": "司母戊鼎", "category": "青铜器"},
    }
    with patch("app.routers.recognize.model_router") as mr:
        mr.recognize = AsyncMock(return_value=fake_resp)
        resp = client.post(
            "/api/recognize",
            json={"museum_id": exhibit.museum_id, "image": "fake_base64", "heading": 180},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["best_confidence"] >= 0.85
    assert data["best_match"]["name"] == "司母戊鼎"
    # 命中库里，exhibit_id 应该是真实 ID
    assert data["best_match"]["exhibit_id"] == exhibit.id


def test_recognize_low_confidence_returns_candidates(client, test_db):
    """低置信度时返回候选列表，best_confidence < 阈值。"""
    _, exhibit = _seed(test_db)
    fake_resp = {
        "candidates": [{"exhibit_id": None, "name": "商代青铜器", "confidence": 0.4}],
        "best_match": {"exhibit_id": None, "name": "商代青铜器", "confidence": 0.4},
        "best_confidence": 0.4,
        "raw_meta": {"name": "商代青铜器", "category": "青铜器"},
    }
    with patch("app.routers.recognize.model_router") as mr:
        mr.recognize = AsyncMock(return_value=fake_resp)
        resp = client.post(
            "/api/recognize",
            json={"museum_id": exhibit.museum_id, "image": "fake_base64"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["best_confidence"] < 0.85
    # 没匹配到库里 → 用 GLM 原始候选
    assert data["candidates"][0]["name"] == "商代青铜器"


def test_recognize_no_db_match_uses_raw_candidates(client, test_db):
    """库里没有匹配展品时，返回 GLM 原始候选（无 exhibit_id）。"""
    m, _ = _seed(test_db)
    fake_resp = {
        "candidates": [{"exhibit_id": None, "name": "新展品", "confidence": 0.88}],
        "best_match": {"exhibit_id": None, "name": "新展品", "confidence": 0.88},
        "best_confidence": 0.88,
        "raw_meta": {"name": "新展品"},
    }
    with patch("app.routers.recognize.model_router") as mr:
        mr.recognize = AsyncMock(return_value=fake_resp)
        resp = client.post(
            "/api/recognize",
            json={"museum_id": m.id, "image": "fake_base64"},
        )
    data = resp.json()
    # 库里没有"新展品"，用原始候选
    assert data["best_match"]["exhibit_id"] is None
    assert data["best_match"]["name"] == "新展品"

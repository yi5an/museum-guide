from unittest.mock import AsyncMock, patch

from app.models import Exhibit, Museum


def _seed(test_db):
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
    return e


def test_chat_returns_reply(client, test_db):
    exhibit = _seed(test_db)
    with patch("app.routers.chat.model_router") as mr:
        mr.chat = AsyncMock(return_value="这是回复")
        resp = client.post(
            "/api/chat",
            json={"exhibit_id": exhibit.id, "lang": "zh", "message": "铭文什么意思"},
        )
    assert resp.status_code == 200
    assert resp.json()["reply"] == "这是回复"


def test_chat_with_history(client, test_db):
    exhibit = _seed(test_db)
    with patch("app.routers.chat.model_router") as mr:
        mr.chat = AsyncMock(return_value="追问回复")
        resp = client.post(
            "/api/chat",
            json={
                "exhibit_id": exhibit.id,
                "lang": "zh",
                "message": "为什么这么大",
                "chat_history": [{"role": "user", "content": "铭文什么意思"}, {"role": "assistant", "content": "..."}],
            },
        )
    assert resp.status_code == 200
    assert resp.json()["reply"] == "追问回复"

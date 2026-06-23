from app.models import Feedback


def test_submit_position_correction(client, test_db):
    resp = client.post(
        "/api/feedback",
        json={
            "type": "wrong_pos",
            "content": "司母戊鼎现在在 F3",
            "heading": 180,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_submit_supplement_with_exhibit(client, test_db):
    from app.models import Exhibit, Museum

    m = Museum(name="x", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    e = Exhibit(museum_id=m.id, name="x", status="active", source="official")
    test_db.add(e)
    test_db.flush()

    resp = client.post(
        "/api/feedback",
        json={
            "exhibit_id": e.id,
            "type": "supplement",
            "content": "这件展品的铭文还有另一种解读",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_feedback_persisted(client, test_db):
    """反馈应写入数据库。"""
    resp = client.post(
        "/api/feedback",
        json={"type": "wrong_info", "content": "朝代标注错误"},
    )
    assert resp.status_code == 200
    # 查数据库
    fb = test_db.query(Feedback).filter_by(type="wrong_info").first()
    assert fb is not None
    assert fb.content == "朝代标注错误"
    assert fb.status == "pending"

from app.models import Exhibit, Floor, Museum


def _seed_museum(test_db):
    museum = Museum(
        name="中国国家博物馆",
        name_i18n={"zh": "中国国家博物馆"},
        city="北京",
        country="中国",
        lat=39.9042,
        lng=116.4074,
        geo_fence=[[116.404, 39.904], [116.410, 39.904], [116.410, 39.908], [116.404, 39.908]],
    )
    test_db.add(museum)
    test_db.flush()
    floor = Floor(museum_id=museum.id, level=2, name="F2 青铜厅", sort_order=2)
    test_db.add(floor)
    test_db.flush()
    exhibit = Exhibit(
        museum_id=museum.id, floor_id=floor.id, name="司母戊鼎", status="active", source="official"
    )
    test_db.add(exhibit)
    test_db.flush()
    # 一件 moved 状态的展品（不应计入 active 数量）
    moved = Exhibit(museum_id=museum.id, name="借展品", status="moved", source="official")
    test_db.add(moved)
    test_db.flush()
    return museum, floor, exhibit


def test_locate_inside_fence(client, test_db):
    _seed_museum(test_db)
    resp = client.post("/api/museums/locate", json={"lat": 39.906, "lng": 116.407})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_inside"] is True
    assert data["name"] == "中国国家博物馆"
    assert data["museum_id"] is not None


def test_locate_outside_fence(client, test_db):
    _seed_museum(test_db)
    resp = client.post("/api/museums/locate", json={"lat": 40.0, "lng": 117.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_inside"] is False
    assert data["museum_id"] is None


def test_museum_detail(client, test_db):
    museum, floor, _ = _seed_museum(test_db)
    resp = client.get(f"/api/museums/{museum.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "中国国家博物馆"
    assert data["city"] == "北京"
    assert len(data["floors"]) == 1
    assert data["floors"][0]["name"] == "F2 青铜厅"
    # 只有 1 件 active（moved 的不计）
    assert data["exhibit_count"] == 1


def test_museum_detail_not_found(client, test_db):
    resp = client.get("/api/museums/9999")
    assert resp.status_code == 404

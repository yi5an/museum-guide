from app.models import (
    ChatSession,
    Exhibit,
    ExhibitImage,
    Feedback,
    Floor,
    Museum,
    Narration,
    Route,
)


def test_create_museum_with_relations(test_db):
    museum = Museum(
        name="中国国家博物馆",
        name_i18n={"zh": "中国国家博物馆", "en": "National Museum of China"},
        city="北京",
        country="中国",
        lat=39.9042,
        lng=116.4074,
        geo_fence=[[116.40, 39.90], [116.41, 39.90], [116.41, 39.91], [116.40, 39.91]],
        description="国家级综合性博物馆",
    )
    test_db.add(museum)
    test_db.flush()

    floor = Floor(museum_id=museum.id, level=2, name="F2 青铜厅", sort_order=2)
    test_db.add(floor)
    test_db.flush()

    exhibit = Exhibit(
        museum_id=museum.id,
        floor_id=floor.id,
        name="司母戊鼎",
        name_i18n={"zh": "司母戊鼎", "en": "Houmuwu Ding"},
        category="青铜器",
        dynasty="商代",
        location_hint="中央展柜",
        plan_x=140.0,
        plan_y=160.0,
        status="active",
        source="official",
        confidence=0.95,
    )
    test_db.add(exhibit)
    test_db.flush()

    assert museum.id is not None
    assert floor.museum_id == museum.id
    assert exhibit.floor_id == floor.id
    assert exhibit.status == "active"


def test_create_narration(test_db):
    museum = Museum(name="测试馆", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(museum)
    test_db.flush()
    exhibit = Exhibit(museum_id=museum.id, name="测试展品", status="active", source="official")
    test_db.add(exhibit)
    test_db.flush()

    narration = Narration(
        exhibit_id=exhibit.id,
        lang="zh",
        content={"blocks": [{"type": "text", "section": "历史", "text": "测试内容"}]},
        tier=1,
        source_label="官方",
    )
    test_db.add(narration)
    test_db.flush()

    assert narration.id is not None
    assert narration.tier == 1


def test_exhibit_status_pending_review(test_db):
    """回流的 AI 生成展品用 pending_review 状态。"""
    museum = Museum(name="x", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(museum)
    test_db.flush()
    exhibit = Exhibit(
        museum_id=museum.id, name="新展品", status="pending_review", source="crowdsource"
    )
    test_db.add(exhibit)
    test_db.flush()
    assert exhibit.status == "pending_review"


def test_create_all_models_smoke(test_db):
    """冒烟：所有 8 张表都能实例化并 flush。"""
    m = Museum(name="x", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    f = Floor(museum_id=m.id, level=1, name="F1", sort_order=1)
    test_db.add(f)
    test_db.flush()
    e = Exhibit(museum_id=m.id, name="e", status="active", source="official")
    test_db.add(e)
    test_db.flush()
    test_db.add(ExhibitImage(exhibit_id=e.id, image_url="http://x/a.jpg", source="official"))
    test_db.add(Narration(exhibit_id=e.id, lang="zh", content={"blocks": []}, tier=1))
    test_db.add(Route(museum_id=m.id, title="r", theme="精选", duration_min=60, exhibit_order=[e.id]))
    test_db.add(Feedback(type="wrong_pos"))
    test_db.add(ChatSession(exhibit_id=e.id, lang="zh", messages=[]))
    test_db.flush()
    # 触发 import 防 lint
    assert ChatSession and Feedback and ExhibitImage and Route

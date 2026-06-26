
from sqlalchemy import select

from app.collect.base import CollectContext, SourceConnector
from app.collect.pipeline import run_pipeline
from app.models import CollectItem, Exhibit, Museum


class _FakeConnector(SourceConnector):
    """假 connector：discover 返回 2 条，parse 返回固定字段，不做真实网络。"""
    source = "fake"
    default_confidence = 0.5
    target_type = "exhibit"

    async def discover(self, ctx):
        return [
            {"name": "司母戊鼎", "source_ref": "http://fake/1"},
            {"name": "四羊方尊", "source_ref": "http://fake/2"},
        ]

    async def fetch(self, item, ctx):
        return f"<html>{item['name']}</html>"

    async def parse(self, raw, item, ctx):
        return {
            "name": item["name"],
            "category": "青铜器",
            "dynasty": "商代",
            "description": f"{item['name']}的描述",
        }


def _setup_museum(db):
    m = Museum(name="测试馆", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    db.add(m)
    db.flush()
    return m


def _setup_museum_with_name(db, name):
    m = Museum(name=name, geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    db.add(m)
    db.flush()
    return m


async def test_run_pipeline_inserts_exhibits_and_records_job(test_db):
    m = _setup_museum(test_db)
    connector = _FakeConnector()
    ctx = CollectContext()

    job = await run_pipeline(connector, museum_id=m.id, db=test_db, ctx=ctx)

    # job 完成态
    assert job.stage == "succeeded"
    assert job.total == 2 and job.done == 2 and job.failed == 0
    assert job.finished_at is not None

    # 两条 exhibit 已入库
    exhibits = list(test_db.scalars(select(Exhibit).where(Exhibit.museum_id == m.id)))
    assert len(exhibits) == 2
    names = {e.name for e in exhibits}
    assert names == {"司母戊鼎", "四羊方尊"}

    # 两条 collect_items 均为 saved
    items = list(test_db.scalars(select(CollectItem).where(CollectItem.job_id == job.id)))
    assert len(items) == 2
    assert all(i.stage == "saved" for i in items)


async def test_run_pipeline_upsert_dedup_by_name(test_db):
    """同名展品重复采集应更新而非新增。"""
    m = _setup_museum(test_db)
    ctx = CollectContext()
    await run_pipeline(_FakeConnector(), m.id, test_db, ctx)
    # 再跑一次同样的
    job2 = await run_pipeline(_FakeConnector(), m.id, test_db, ctx)

    exhibits = list(test_db.scalars(select(Exhibit).where(Exhibit.museum_id == m.id)))
    assert len(exhibits) == 2  # 不翻倍
    assert job2.stage == "succeeded"


async def test_run_pipeline_inserts_museum(test_db):
    """target_type=museum 时，pipeline upsert 博物馆。"""
    import json

    class _MuseumFinder(SourceConnector):
        source = "wiki_list"
        default_confidence = 0.6
        target_type = "museum"

        async def discover(self, ctx):
            return [
                {"name": "新发现的博物馆A", "source_ref": "http://wiki/A"},
                {"name": "中国国家博物馆", "source_ref": "http://wiki/B"},  # 已存在
            ]

        async def fetch(self, item, ctx):
            return '{"lat":30.1,"lng":120.2,"description":"测试馆"}'

        async def parse(self, raw, item, ctx):
            d = json.loads(raw)
            return {"name": item["name"], "lat": d["lat"], "lng": d["lng"],
                    "description": d["description"], "source_ref": item["source_ref"]}

    # 预置一个已存在的馆
    _setup_museum_with_name(test_db, "中国国家博物馆")
    ctx = CollectContext()

    job = await run_pipeline(_MuseumFinder(), None, test_db, ctx)

    assert job.stage == "succeeded"
    museums = list(test_db.scalars(select(Museum).where(
        Museum.name.in_(["新发现的博物馆A", "中国国家博物馆"]))))
    assert len(museums) == 2

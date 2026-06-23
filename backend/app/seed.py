"""种子数据：国家博物馆 + 司母戊鼎等明星展品。

运行：uv run python -m app.seed
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Exhibit, Floor, Museum, Narration, Route


def seed():
    db = SessionLocal()
    try:
        if db.scalar(select(Museum).where(Museum.name == "中国国家博物馆")):
            print("Seed already exists, skip.")
            return

        museum = Museum(
            name="中国国家博物馆",
            name_i18n={"zh": "中国国家博物馆", "en": "National Museum of China"},
            city="北京",
            country="中国",
            lat=39.9042,
            lng=116.4074,
            geo_fence=[
                [116.404, 39.904],
                [116.410, 39.904],
                [116.410, 39.908],
                [116.404, 39.908],
            ],
            description="国家级综合性博物馆",
        )
        db.add(museum)
        db.flush()

        f2 = Floor(museum_id=museum.id, level=2, name="F2 青铜厅", sort_order=2)
        db.add(f2)
        db.flush()

        exhibits_data = [
            (
                "司母戊鼎",
                "青铜器",
                "商代",
                "中央展柜",
                140.0,
                160.0,
                "重达 832.84 公斤，是世界上已发现最大的青铜器。1939 年河南安阳出土，为商王祭祀母亲戊所铸。",
            ),
            (
                "四羊方尊",
                "青铜器",
                "商代",
                "东展柜",
                220.0,
                100.0,
                "商代晚期青铜方尊，四角饰以圆雕羊首，工艺精湛，是商代青铜器的代表作。",
            ),
            (
                "红山玉龙",
                "玉器",
                "新石器时代",
                "西展柜",
                70.0,
                260.0,
                "C 形玉龙，红山文化代表作，被誉为中华第一龙。",
            ),
        ]
        exhibit_ids = []
        for name, cat, dynasty, loc, x, y, desc in exhibits_data:
            e = Exhibit(
                museum_id=museum.id,
                floor_id=f2.id,
                name=name,
                name_i18n={"zh": name},
                category=cat,
                dynasty=dynasty,
                location_hint=loc,
                plan_x=x,
                plan_y=y,
                status="active",
                source="official",
                confidence=0.95,
            )
            db.add(e)
            db.flush()
            exhibit_ids.append(e.id)
            n = Narration(
                exhibit_id=e.id,
                lang="zh",
                content={"blocks": [
                    {"type": "text", "section": "历史脉络", "text": desc},
                    {"type": "text", "section": "文物意义", "text": "（待补充）"},
                ]},
                tier=1,
                source_label="官方",
            )
            db.add(n)

        db.add(
            Route(
                museum_id=museum.id,
                title="一小时精华路线",
                title_i18n={"zh": "一小时精华路线"},
                theme="精选",
                duration_min=60,
                exhibit_order=exhibit_ids,
                description="明星展品串联",
            )
        )
        db.commit()
        print(f"Seed complete: 国家博物馆 + {len(exhibits_data)} 件展品 + 1 条路线")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

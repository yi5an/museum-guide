"""补全国博展品 + 楼层 + 讲解。

国博十大镇馆之宝，已有 3 件（司母戊鼎/四羊方尊/红山玉龙），补 7 件。
楼层：古代中国基本陈列在 B1（地下一层）。

运行：uv run python -m app.seed_guobo
"""

import asyncio
import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Exhibit, Floor, Museum, Narration
from app.services.model_router import model_router

# 国博展品数据（已有 3 件不重复，这里列全 10 件，脚本会跳过已存在的）
GUOBO_EXHIBITS = [
    {"name": "鹳鱼石斧图彩陶缸", "category": "陶器", "dynasty": "新石器时代",
     "description": "仰韶文化，国家一级文物，首批禁止出境展览文物，彩陶画杰作"},
    {"name": "陶鹰鼎", "category": "陶器", "dynasty": "新石器时代",
     "description": "仰韶文化，造型为一只雄鹰，兼具实用与艺术，国宝级陶器"},
    {"name": "红山玉龙", "category": "玉器", "dynasty": "新石器时代",
     "description": "红山文化 C 形玉龙，被誉为中华第一龙"},
    {"name": "大盂鼎", "category": "青铜器", "dynasty": "西周",
     "description": "西周康王时期青铜重器，内壁铸有长篇铭文，记载周康王对贵族盂的训诫"},
    {"name": "司母戊鼎", "category": "青铜器", "dynasty": "商代",
     "description": "又称后母戊鼎，重达 832.84 公斤，是世界上已发现最大的青铜器"},
    {"name": "四羊方尊", "category": "青铜器", "dynasty": "商代",
     "description": "商代晚期青铜方尊，四角饰以圆雕羊首，工艺精湛"},
    {"name": "妇好鸮尊", "category": "青铜器", "dynasty": "商代",
     "description": "商代妇好墓出土，造型为一只站立的鸮（猫头鹰），商代青铜艺术精品"},
    {"name": "虢季子白盘", "category": "青铜器", "dynasty": "西周",
     "description": "西周宣王时期，晚清四大国宝之一，盘内底部铸有长篇铭文"},
    {"name": "鎏金舞马衔杯纹银壶", "category": "金银器", "dynasty": "唐代",
     "description": "唐代金银器瑰宝，壶身錾刻舞马衔杯图案，再现唐玄宗舞马祝寿盛况"},
    {"name": "九龙九凤冠", "category": "金银器", "dynasty": "明代",
     "description": "明孝端皇后凤冠，缀满宝石珍珠，明代金银工艺巅峰之作"},
]


async def seed_guobo():
    db = SessionLocal()
    try:
        museum = db.scalar(select(Museum).where(Museum.name == "中国国家博物馆"))
        if not museum:
            print("✗ 国博不存在，先跑 seed.py")
            return

        # 补全楼层
        floors_data = [
            {"level": -1, "name": "B1 古代中国", "sort_order": 1},
            {"level": 1, "name": "F1 中央大厅", "sort_order": 2},
            {"level": 2, "name": "F2 青铜器专题", "sort_order": 3},
        ]
        floor_map = {}
        for fdata in floors_data:
            floor = db.scalar(select(Floor).where(
                Floor.museum_id == museum.id, Floor.level == fdata["level"]))
            if not floor:
                floor = Floor(museum_id=museum.id, **fdata)
                db.add(floor)
                db.flush()
                print(f"  🏛 创建楼层：{fdata['name']}")
            floor_map[fdata["level"]] = floor

        # 古代中国基本陈列在 B1
        b1 = floor_map[-1]

        print(f"\n🏛 {museum.name} · 补全展品（B1 古代中国展厅）\n")

        new_count = 0
        narration_count = 0

        for e_data in GUOBO_EXHIBITS:
            # 检查展品是否已存在
            existing = db.scalar(select(Exhibit).where(
                Exhibit.museum_id == museum.id, Exhibit.name == e_data["name"]))
            if existing:
                print(f"  ⏭ {e_data['name']} 已存在")
                continue

            exhibit = Exhibit(
                museum_id=museum.id,
                floor_id=b1.id,
                name=e_data["name"],
                name_i18n={"zh": e_data["name"]},
                category=e_data["category"],
                dynasty=e_data["dynasty"],
                location_hint="古代中国基本陈列",
                plan_x=80 + (new_count % 4) * 60,
                plan_y=80 + (new_count // 4) * 80,
                status="active",
                source="official",
                confidence=0.95,
            )
            db.add(exhibit)
            db.flush()
            new_count += 1

            # 生成讲解
            print(f"  📜 {e_data['name']}…", end=" ", flush=True)
            exhibit_info = {
                "name": e_data["name"],
                "category": e_data["category"],
                "dynasty": e_data["dynasty"],
                "description": e_data["description"],
                "museum": "中国国家博物馆",
            }

            content = None
            for attempt in range(3):
                try:
                    content = await model_router.generate_narration(exhibit_info, "zh")
                    break
                except Exception as e:
                    print(f"\n    ⚠ 重试 {attempt+1}/3: {str(e)[:60]}")
                    await asyncio.sleep(5)

            if content:
                narration = Narration(
                    exhibit_id=exhibit.id, lang="zh",
                    content=content, tier=1, source_label="官方",
                )
                db.add(narration)
                narration_count += 1
                blocks = content.get("blocks", [])
                print(f"✓ ({len(blocks)} 段)")
            else:
                print("✗ 跳过")

            db.commit()
            await asyncio.sleep(3)

        print(f"\n{'='*50}")
        print(f"✅ 国博补全完成")
        print(f"   新增展品：{new_count}")
        print(f"   新增讲解：{narration_count}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(seed_guobo())

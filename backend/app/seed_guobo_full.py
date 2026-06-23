"""将国博官网馆藏精品全量入库。

读取 crawl_guobo.py 抓取的 guobo_exhibits.json（约 210 件），
跳过已存在的展品，为新增展品入库 + 生成讲解。

运行：uv run python -m app.seed_guobo_full
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Exhibit, Floor, Museum, Narration
from app.services.model_router import model_router

DATA_FILE = Path(__file__).parent / "data" / "guobo_exhibits.json"
MAX_RETRIES = 3


async def seed_guobo_full():
    with open(DATA_FILE, encoding="utf-8") as f:
        exhibits_data = json.load(f)

    # 过滤掉非展品（导航项等）
    exhibits_data = [
        e for e in exhibits_data
        if e.get("detail_url", "").startswith("http")
        and e["name"] not in ("登录/注册", "分享网站", "国博视频", "下载共享")
    ]

    db = SessionLocal()
    try:
        museum = db.scalar(select(Museum).where(Museum.name == "中国国家博物馆"))
        if not museum:
            print("✗ 国博不存在")
            return

        # 用 B1 古代中国楼层
        floor = db.scalar(select(Floor).where(
            Floor.museum_id == museum.id, Floor.level == -1))
        if not floor:
            floor = Floor(museum_id=museum.id, level=-1, name="B1 古代中国", sort_order=1)
            db.add(floor)
            db.flush()

        print(f"=== 国博馆藏精品入库：{len(exhibits_data)} 件 ===\n")

        new_count = 0
        exist_count = 0
        narration_count = 0
        failed = []

        for idx, e_data in enumerate(exhibits_data):
            name = e_data["name"]

            # 跳过已存在的
            existing = db.scalar(select(Exhibit).where(
                Exhibit.museum_id == museum.id, Exhibit.name == name))
            if existing:
                exist_count += 1
                continue

            exhibit = Exhibit(
                museum_id=museum.id,
                floor_id=floor.id,
                name=name,
                name_i18n={"zh": name},
                category=e_data.get("category", "其他"),
                dynasty=e_data.get("dynasty", "待补充"),
                location_hint="馆藏精品",
                plan_x=40 + (new_count % 8) * 30,
                plan_y=40 + (new_count // 8) * 40,
                status="active",
                source="official",
                confidence=0.9,
            )
            db.add(exhibit)
            db.flush()
            new_count += 1

            # 生成讲解
            print(f"[{idx+1}/{len(exhibits_data)}] {name}…", end=" ", flush=True)
            exhibit_info = {
                "name": name,
                "category": e_data.get("category", ""),
                "dynasty": e_data.get("dynasty", ""),
                "description": e_data.get("description", name),
                "museum": "中国国家博物馆",
            }

            content = None
            for attempt in range(MAX_RETRIES):
                try:
                    content = await model_router.generate_narration(exhibit_info, "zh")
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(5)
                    else:
                        print(f"✗ {str(e)[:40]}")

            if content and content.get("blocks") and not (
                len(content.get("blocks", [])) == 1
                and content["blocks"][0].get("text") == "讲解生成失败，请稍后重试。"
            ):
                narration = Narration(
                    exhibit_id=exhibit.id, lang="zh",
                    content=content, tier=1, source_label="官方",
                )
                db.add(narration)
                narration_count += 1
                print(f"✓ ({len(content['blocks'])} 段)")
            else:
                print("✗ 跳过")

            db.commit()
            await asyncio.sleep(2)

        print(f"\n{'='*50}")
        print(f"✅ 完成")
        print(f"   已存在：{exist_count}")
        print(f"   新增：{new_count}")
        print(f"   讲解：{narration_count}")
        if failed:
            print(f"   失败：{len(failed)}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(seed_guobo_full())

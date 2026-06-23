"""批量导入博物馆 + 展品 + 生成讲解。

流程：
1. 读 museums_exhibits.json
2. 创建博物馆/楼层/展品记录
3. 对每件展品调 glm-5.2 生成中文讲解（503 重试 3 次）
4. 写入 narrations 表（tier=1, source_label="官方"）

运行：uv run python -m app.seed_batch
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Exhibit, Floor, Museum, Narration
from app.services.model_router import model_router

DATA_FILE = Path(__file__).parent / "data" / "museums_exhibits.json"
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒


async def generate_with_retry(exhibit_info: dict, lang: str) -> dict | None:
    """调 glm-5.2 生成讲解，503 时重试。"""
    for attempt in range(MAX_RETRIES):
        try:
            return await model_router.generate_narration(exhibit_info, lang)
        except Exception as e:
            err_str = str(e)
            print(f"    ⚠ 第 {attempt + 1}/{MAX_RETRIES} 次失败: {err_str[:100]}")
            if attempt < MAX_RETRIES - 1:
                print(f"    等待 {RETRY_DELAY}s 后重试…")
                await asyncio.sleep(RETRY_DELAY)
    return None


async def seed_batch():
    # 读数据
    with open(DATA_FILE, encoding="utf-8") as f:
        museums_data = json.load(f)

    db = SessionLocal()
    total_exhibits = sum(len(m["exhibits"]) for m in museums_data)
    print(f"=== 批量导入：{len(museums_data)} 家博物馆，{total_exhibits} 件展品 ===\n")

    try:
        museum_count = 0
        exhibit_count = 0
        narration_count = 0
        failed = []

        for m_data in museums_data:
            # 检查是否已存在：复用记录，仍要遍历展品补讲解
            museum = db.scalar(select(Museum).where(Museum.name == m_data["name"]))
            if museum:
                print(f"🏛 {museum.name}（已存在，检查展品讲解）")
            else:
                # 创建博物馆
                museum = Museum(
                    name=m_data["name"],
                    name_i18n={"zh": m_data["name"], "en": m_data.get("name_en", "")},
                    city=m_data["city"],
                    country=m_data["country"],
                    lat=m_data["lat"],
                    lng=m_data["lng"],
                    geo_fence=[],  # 精确围栏后续补充
                    description=m_data.get("description", ""),
                )
                db.add(museum)
                db.flush()
                museum_count += 1
                print(f"🏛 {museum.name}（新建）")
            db.flush()
            # 获取或创建默认楼层
            floor = db.scalar(select(Floor).where(Floor.museum_id == museum.id))
            if not floor:
                floor = Floor(
                    museum_id=museum.id,
                    level=1,
                    name="主展厅",
                    sort_order=1,
                )
                db.add(floor)
                db.flush()

            # 创建展品 + 生成讲解
            for e_data in m_data["exhibits"]:
                # 检查展品是否已存在（断点续传）
                existing_exhibit = db.scalar(
                    select(Exhibit).where(
                        Exhibit.museum_id == museum.id,
                        Exhibit.name == e_data["name"],
                    )
                )
                if existing_exhibit:
                    exhibit = existing_exhibit
                else:
                    exhibit = Exhibit(
                        museum_id=museum.id,
                        floor_id=floor.id,
                        name=e_data["name"],
                        name_i18n={"zh": e_data["name"]},
                        category=e_data["category"],
                        dynasty=e_data["dynasty"],
                        status="active",
                        source="official",
                        confidence=0.95,
                    )
                    db.add(exhibit)
                    db.flush()
                    exhibit_count += 1

                # 检查是否已有讲解（断点续传）
                existing_narration = db.scalar(
                    select(Narration).where(
                        Narration.exhibit_id == exhibit.id,
                        Narration.lang == "zh",
                    )
                )
                if existing_narration:
                    print(f"  ⏭ {e_data['name']} 已有讲解，跳过")
                    continue

                # 生成讲解
                exhibit_info = {
                    "name": e_data["name"],
                    "category": e_data["category"],
                    "dynasty": e_data["dynasty"],
                    "description": e_data["description"],
                    "museum": m_data["name"],
                }
                print(f"  📜 生成讲解：{e_data['name']}…", end=" ", flush=True)

                content = await generate_with_retry(exhibit_info, "zh")
                if content:
                    narration = Narration(
                        exhibit_id=exhibit.id,
                        lang="zh",
                        content=content,
                        tier=1,
                        source_label="官方",
                    )
                    db.add(narration)
                    db.commit()  # 每条立即提交，断点续传
                    narration_count += 1
                    blocks = content.get("blocks", [])
                    print(f"✓ ({len(blocks)} 段)")
                else:
                    db.commit()  # 提交展品记录
                    print(f"✗ 失败，跳过")
                    failed.append(f"{museum.name} - {exhibit.name}")

                # 每件间隔 3 秒，避免触发 rate limit
                await asyncio.sleep(3)

            print()

        # 汇总
        print("=" * 50)
        print(f"✅ 导入完成")
        print(f"   博物馆：{museum_count} 家")
        print(f"   展品：{exhibit_count} 件")
        print(f"   讲解：{narration_count} 条")
        if failed:
            print(f"   ❌ 失败：{len(failed)} 件")
            for f in failed:
                print(f"      - {f}")
            print(f"   失败的展品可后续重跑（已存在的会自动跳过）")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(seed_batch())

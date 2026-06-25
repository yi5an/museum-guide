"""为国博所有缺讲解的展品批量生成讲解。

不关心展品是否已存在，只查 narrations 表——没有中文讲解的就补。

运行：uv run python -m app.seed_narrations_only
"""

import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Exhibit, Narration
from app.services.model_router import model_router


async def fill_narrations():
    db = SessionLocal()
    try:
        # 找所有没有中文讲解的展品
        all_exhibits = list(db.scalars(select(Exhibit).where(
            Exhibit.museum_id == 1,
            Exhibit.status.in_(["active", "moved"]),
        )))
        print(f"国博总展品：{len(all_exhibits)}")

        missing = []
        for e in all_exhibits:
            has = db.scalar(select(Narration).where(
                Narration.exhibit_id == e.id, Narration.lang == "zh"
            ))
            if not has:
                missing.append(e)

        print(f"缺讲解：{len(missing)}\n")

        success = 0
        failed = 0

        for i, exhibit in enumerate(missing):
            print(f"[{i+1}/{len(missing)}] {exhibit.name}…", end=" ", flush=True)

            exhibit_info = {
                "name": exhibit.name,
                "category": exhibit.category or "",
                "dynasty": exhibit.dynasty or "",
                "description": exhibit.location_hint or exhibit.name,
                "museum": "中国国家博物馆",
            }

            content = None
            for attempt in range(3):
                try:
                    content = await model_router.generate_narration(exhibit_info, "zh")
                    break
                except Exception as e:
                    if attempt < 2:
                        await asyncio.sleep(5)

            if content and content.get("blocks") and not (
                len(content.get("blocks", [])) == 1
                and content["blocks"][0].get("text") == "讲解生成失败，请稍后重试。"
            ):
                narration = Narration(
                    exhibit_id=exhibit.id, lang="zh",
                    content=content, tier=1, source_label="官方",
                )
                db.add(narration)
                db.commit()
                success += 1
                print(f"✓ ({len(content['blocks'])} 段)")
            else:
                failed += 1
                print("✗")

            await asyncio.sleep(2)

        print(f"\n{'='*50}")
        print(f"✅ 完成：成功 {success}，失败 {failed}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(fill_narrations())

"""重新生成占位讲解（source_label='简介' 的那些）。

这些展品 Wikipedia 没有独立词条，之前用了占位文字。
现在用 glm-5.2 根据展品名+类别+朝代生成真实讲解。

运行：uv run python -m app.regenerate_placeholders
"""

import asyncio
import json
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Exhibit, Narration
from app.services.model_router import model_router


async def main():
    db = SessionLocal()
    try:
        # 找所有 source_label='简介' 的讲解（占位内容）
        placeholders = list(db.scalars(select(Narration).where(
            Narration.source_label == "简介"
        )))
        print(f"占位讲解：{len(placeholders)}\n")

        success = 0
        failed = 0

        for i, narration in enumerate(placeholders):
            exhibit = db.get(Exhibit, narration.exhibit_id)
            if not exhibit:
                continue

            print(f"[{i+1}/{len(placeholders)}] {exhibit.name}…", end=" ", flush=True)

            exhibit_info = {
                "name": exhibit.name,
                "category": exhibit.category or "文物",
                "dynasty": exhibit.dynasty or "",
                "description": exhibit.location_hint or "",
                "museum": "中国国家博物馆",
            }

            content = None
            for attempt in range(3):
                try:
                    content = await model_router.generate_narration(exhibit_info, "zh")
                    break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(5)

            if content and content.get("blocks") and not (
                len(content.get("blocks", [])) == 1
                and content["blocks"][0].get("text", "").startswith("讲解生成失败")
            ):
                # 更新现有 narration 记录
                narration.content = content
                narration.source_label = "AI 生成"
                db.commit()
                success += 1
                print(f"✓ ({len(content['blocks'])} 段)")
            else:
                failed += 1
                print("✗")

            await asyncio.sleep(2)

        print(f"\n{'='*50}")
        print(f"✅ 成功 {success}，失败 {failed}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

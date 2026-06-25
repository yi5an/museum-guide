"""为占位讲解用类别+朝代生成通用介绍。

不调 glm-5.2，而是：
1. 从 Wikipedia 抓"朝代+类别"的通用介绍（如"唐代陶器"、"商代青铜器"）
2. 缓存同类别的介绍，避免重复请求
3. 拼接展品名 + 类别介绍 = 完整讲解

运行：uv run python -m app.fill_by_category
"""

import asyncio
import re
import time
import urllib.parse

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Exhibit, Narration

HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}


def fetch_summary(keyword: str) -> str | None:
    encoded = urllib.parse.quote(keyword)
    url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json().get("extract") or None
    except Exception:
        return None


def search_and_fetch(keyword: str) -> str | None:
    """搜索 + 获取摘要"""
    encoded = urllib.parse.quote(keyword)
    url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json&srlimit=1"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return None
        title = results[0]["title"]
        time.sleep(0.3)
        return fetch_summary(title)
    except Exception:
        return None


async def main():
    db = SessionLocal()
    try:
        # 找占位讲解
        placeholders = list(db.scalars(select(Narration).where(
            Narration.source_label == "简介"
        )))
        print(f"占位讲解：{len(placeholders)}\n")

        # 缓存：类别+朝代 → 通用介绍
        category_cache: dict[str, str] = {}

        def get_category_intro(category: str, dynasty: str) -> str:
            # 构建搜索关键词
            parts = []
            if dynasty and dynasty != "待补充":
                parts.append(dynasty.replace("时代", ""))
            if category and category != "其他":
                parts.append(category)
            key = "·".join(parts)

            if key in category_cache:
                return category_cache[key]

            # 搜索 Wikipedia
            search_term = "".join(parts) if parts else category
            print(f"    搜索类别: {search_term}", end=" → ", flush=True)
            extract = search_and_fetch(search_term)
            time.sleep(0.3)

            if not extract:
                # 试试只搜类别
                extract = search_and_fetch(category)
                time.sleep(0.3)

            if extract:
                category_cache[key] = extract
                print(f"✓ {len(extract)} 字")
                return extract
            else:
                category_cache[key] = ""
                print("✗")
                return ""

        success = 0
        skipped = 0

        for i, narration in enumerate(placeholders):
            exhibit = db.get(Exhibit, narration.exhibit_id)
            if not exhibit:
                continue

            category = exhibit.category or "文物"
            dynasty = exhibit.dynasty or "待补充"
            name = exhibit.name

            # 检查是否还是占位文字
            current_text = ""
            if narration.content.get("blocks"):
                current_text = narration.content["blocks"][0].get("text", "")
            if "请咨询现场工作人员" not in current_text:
                skipped += 1
                continue

            # 获取类别介绍
            intro = get_category_intro(category, dynasty)

            if intro:
                # 拼接：展品名 + 类别介绍
                blocks = []

                # 第一段：展品概述
                dynasty_str = dynasty if dynasty != "待补充" else ""
                overview = f"{name}，{dynasty_str}{category}，现藏于中国国家博物馆。"
                blocks.append({"type": "text", "section": "展品概述", "text": overview})

                # 第二段：类别介绍（按句子切分）
                sentences = re.split(r'(?<=[。！？；])', intro)
                sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

                if sentences:
                    n = min(4, len(sentences))
                    blocks.append({"type": "text", "section": f"{category}概览", "text": "".join(sentences[:n])})

                if len(sentences) > 4:
                    blocks.append({"type": "text", "section": "历史背景", "text": "".join(sentences[4:8])})

                narration.content = {"blocks": blocks}
                narration.source_label = f"维基百科·{category}"
                db.commit()
                success += 1
                print(f"  [{i+1}] {name} ✓ ({len(blocks)} 段)")
            else:
                # 类别也搜不到，用展品名再试一次
                extract = search_and_fetch(name)
                time.sleep(0.3)
                if extract and len(extract) > 30:
                    blocks = [{"type": "text", "section": "历史脉络", "text": extract[:500]}]
                    narration.content = {"blocks": blocks}
                    narration.source_label = "维基百科"
                    db.commit()
                    success += 1
                    print(f"  [{i+1}] {name} ✓ (展品名搜到)")
                else:
                    print(f"  [{i+1}] {name} △ 无内容")

        print(f"\n{'='*50}")
        print(f"✅ 成功 {success}，跳过 {skipped}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

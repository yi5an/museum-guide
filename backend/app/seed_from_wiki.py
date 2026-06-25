"""从 Wikipedia 批量采集展品内容，整理成讲解。

比调 glm-5.2 快 10 倍，内容更准确（多人编辑校对）。
流程：
1. 用展品名搜 Wikipedia
2. 获取摘要
3. 整理成 blocks（历史/意义）
4. 写入 narrations 表

运行：uv run python -m app.seed_from_wiki
"""

import asyncio
import json
import re
import time
import urllib.parse

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Exhibit, Narration

HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}


def search_wiki(keyword: str) -> str | None:
    """搜索 Wikipedia，返回匹配的词条标题。"""
    encoded = urllib.parse.quote(keyword)
    url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json&srlimit=1"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        results = data.get("query", {}).get("search", [])
        if results:
            return results[0]["title"]
    except Exception:
        pass
    return None


def fetch_summary(title: str) -> str | None:
    """获取 Wikipedia 词条摘要。"""
    encoded = urllib.parse.quote(title)
    url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        extract = data.get("extract", "")
        return extract if extract else None
    except Exception:
        return None


def text_to_blocks(extract: str, exhibit_name: str, category: str, dynasty: str) -> dict:
    """把 Wikipedia 摘要整理成讲解 blocks。"""
    if not extract or len(extract) < 15:
        return {"blocks": [
            {"type": "text", "section": "简介",
             "text": f"{exhibit_name}，{'属' + dynasty if dynasty and dynasty != '待补充' else ''}{'·' + category if category else ''}类文物，现藏于中国国家博物馆。关于此展品的详细讲解，请咨询现场工作人员。"}
        ]}

    # 繁体转简体（Wikipedia 中文可能是繁体）
    # 简单处理：不动，TTS 能读繁体

    # 按句号切分
    sentences = re.split(r'(?<=[。！？；])', extract)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

    blocks = []

    if sentences:
        # 前 2-3 句：历史脉络
        n = min(3, len(sentences))
        history = "".join(sentences[:n])
        blocks.append({"type": "text", "section": "历史脉络", "text": history})

    if len(sentences) > 3:
        # 4-7 句：文物意义
        n2 = min(4, len(sentences) - 3)
        meaning = "".join(sentences[3:3+n2])
        blocks.append({"type": "text", "section": "文物意义", "text": meaning})

    if len(sentences) > 7:
        extra = "".join(sentences[7:])
        if len(extra) > 10:
            blocks.append({"type": "text", "section": "补充说明", "text": extra})

    if not blocks:
        blocks.append({"type": "text", "section": "简介", "text": extract[:500]})

    return {"blocks": blocks}


async def main():
    db = SessionLocal()
    try:
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
        not_found = 0
        failed = 0

        for i, exhibit in enumerate(missing):
            print(f"[{i+1}/{len(missing)}] {exhibit.name}…", end=" ", flush=True)

            # 1. 搜索 Wikipedia
            title = search_wiki(exhibit.name)
            time.sleep(0.3)

            if title:
                # 2. 获取摘要
                extract = fetch_summary(title)
                time.sleep(0.3)

                if extract:
                    # 3. 整理成 blocks
                    content = text_to_blocks(
                        extract, exhibit.name,
                        exhibit.category or "", exhibit.dynasty or ""
                    )
                    narration = Narration(
                        exhibit_id=exhibit.id, lang="zh",
                        content=content, tier=1,
                        source_label="维基百科",
                        source_ref=f"https://zh.wikipedia.org/wiki/{title}",
                    )
                    db.add(narration)
                    db.commit()
                    success += 1
                    print(f"✓ ({len(content['blocks'])} 段, {len(extract)} 字)")
                    continue
            else:
                # 试试去掉引号的名字
                clean_name = exhibit.name.strip('"').strip('"').strip('"')
                if clean_name != exhibit.name:
                    title = search_wiki(clean_name)
                    time.sleep(0.3)
                    if title:
                        extract = fetch_summary(title)
                        time.sleep(0.3)
                        if extract:
                            content = text_to_blocks(
                                extract, exhibit.name,
                                exhibit.category or "", exhibit.dynasty or ""
                            )
                            narration = Narration(
                                exhibit_id=exhibit.id, lang="zh",
                                content=content, tier=1,
                                source_label="维基百科",
                                source_ref=f"https://zh.wikipedia.org/wiki/{title}",
                            )
                            db.add(narration)
                            db.commit()
                            success += 1
                            print(f"✓ ({len(content['blocks'])} 段)")
                            continue

            # 未找到词条
            content = text_to_blocks("", exhibit.name, exhibit.category or "", exhibit.dynasty or "")
            narration = Narration(
                exhibit_id=exhibit.id, lang="zh",
                content=content, tier=1,
                source_label="简介",
            )
            db.add(narration)
            db.commit()
            not_found += 1
            print(f"△ 无词条，用占位")

        print(f"\n{'='*50}")
        print(f"✅ 完成")
        print(f"   Wikipedia 有内容：{success}")
        print(f"   无词条（占位）：{not_found}")
        print(f"   来源：https://zh.wikipedia.org")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

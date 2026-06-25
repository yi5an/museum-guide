"""从百度百科批量采集展品内容，整理成讲解。

比调 glm-5.2 快 10 倍，内容更准确。
每件展品：
1. 用展品名搜百度百科
2. 提取摘要
3. 整理成 blocks（历史/意义/工艺/趣闻 不一定全有，有什么放什么）
4. 写入 narrations 表

运行：uv run python -m app.seed_from_baike
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

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def fetch_baike(keyword: str) -> dict | None:
    """从百度百科获取展品摘要。"""
    encoded = urllib.parse.quote(keyword)
    url = f"https://baike.baidu.com/api/openapi/BaikeLemmaCardApi?scope=103&format=json&appid=379020&bk_key={encoded}&bk_length=600"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("key"):
            return None
        return {
            "title": data.get("key", keyword),
            "abstract": data.get("abstract", ""),
            "description": data.get("card", {}).get("summary", ""),
        }
    except Exception:
        return None


def abstract_to_blocks(abstract: str, exhibit_name: str) -> dict:
    """把百度百科摘要整理成讲解 blocks 结构。

    百度百科摘要通常是连续段落，我们按句号切分，
    前 2-3 句作为"历史脉络"，其余作为"文物意义"。
    """
    if not abstract or len(abstract) < 20:
        # 内容太少，用占位
        return {"blocks": [
            {"type": "text", "section": "简介",
             "text": f"{exhibit_name}，是中国历史文物中的珍贵藏品。关于此展品的详细信息，请咨询现场工作人员。"}
        ]}

    # 按句号切分成句子
    sentences = re.split(r'(?<=[。！？；])', abstract)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

    blocks = []
    if sentences:
        # 前 2-3 句作为历史脉络
        history = "".join(sentences[:3]) if len(sentences) >= 3 else "".join(sentences)
        blocks.append({"type": "text", "section": "历史脉络", "text": history})

    if len(sentences) > 3:
        # 4-6 句作为文物意义
        meaning = "".join(sentences[3:6]) if len(sentences) >= 6 else "".join(sentences[3:])
        blocks.append({"type": "text", "section": "文物意义", "text": meaning})

    if len(sentences) > 6:
        # 剩余作为补充说明
        extra = "".join(sentences[6:])
        if len(extra) > 10:
            blocks.append({"type": "text", "section": "补充说明", "text": extra})

    if not blocks:
        blocks.append({"type": "text", "section": "简介", "text": abstract[:500]})

    return {"blocks": blocks}


async def main():
    db = SessionLocal()
    try:
        # 找所有没有讲解的展品
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

            # 抓百度百科
            data = fetch_baike(exhibit.name)
            time.sleep(0.3)  # 礼貌延迟

            if data and data.get("abstract"):
                content = abstract_to_blocks(data["abstract"], exhibit.name)
                narration = Narration(
                    exhibit_id=exhibit.id, lang="zh",
                    content=content, tier=1,
                    source_label="百度百科",
                    source_ref=f"https://baike.baidu.com/item/{exhibit.name}",
                )
                db.add(narration)
                db.commit()
                success += 1
                blocks_count = len(content["blocks"])
                print(f"✓ ({blocks_count} 段, {len(data['abstract'])} 字)")
            else:
                failed += 1
                print(f"✗ 未找到词条")

        print(f"\n{'='*50}")
        print(f"✅ 完成：成功 {success}，失败 {failed}")
        print(f"   来源：百度百科（https://baike.baidu.com）")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

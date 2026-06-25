"""为博物馆批量获取建筑照片 URL，存入数据库 cover_image_url 字段。"""

import time
import urllib.parse

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Museum

HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}

# 博物馆中文名 → Wikipedia 搜索词
SEARCH_TERMS = {
    "中国国家博物馆": "中国国家博物馆",
    "故宫博物院": "故宫",
    "上海博物馆": "上海博物馆",
    "陕西历史博物馆": "陕西历史博物馆",
    "南京博物院": "南京博物院",
    "湖南博物院": "湖南博物院",
    "河南博物院": "河南博物院",
    "浙江省博物馆": "浙江省博物馆",
    "三星堆博物馆": "三星堆博物馆",
    "湖北省博物馆": "湖北省博物馆",
}


def get_thumb(search_term: str) -> str | None:
    encoded = urllib.parse.quote(search_term)
    url = f"https://zh.wikipedia.org/w/api.php?action=query&titles={encoded}&prop=pageimages&format=json&pithumbsize=600"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            thumb = page.get("thumbnail", {}).get("source", "")
            if thumb:
                return thumb
    except Exception:
        pass
    return None


def main():
    db = SessionLocal()
    try:
        museums = list(db.scalars(select(Museum)))
        print(f"共 {len(museums)} 家博物馆\n")

        for museum in museums:
            search_term = SEARCH_TERMS.get(museum.name, museum.name)
            print(f"{museum.name}…", end=" ", flush=True)

            thumb = get_thumb(search_term)
            time.sleep(0.5)

            if thumb:
                museum.cover_image_url = thumb
                db.commit()
                print(f"✓ {thumb[:60]}...")
            else:
                print("✗ 无图片")

        print("\n✅ 完成")
    finally:
        db.close()


if __name__ == "__main__":
    main()

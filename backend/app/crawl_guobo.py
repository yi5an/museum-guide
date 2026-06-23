"""抓取国博官网馆藏精品全部展品。

遍历 kgfjp 目录的 11 个分页，提取展品名 + 详情页链接，
再进详情页拿朝代/类别/简介，输出 JSON。

运行：uv run python -m app.crawl_guobo
"""

import json
import re
import time
from pathlib import Path

import httpx

BASE = "https://www.chnmuseum.cn/zp/zpml/kgfjp/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
OUTPUT = Path(__file__).parent / "data" / "guobo_exhibits.json"

SKIP_TITLES = {
    "国家博物馆","首页","征集","保管","研究","展览","社教","文创","服务",
    "学习","视频","登录","注册","分享","下载","导航","馆藏精品",
    "隐私政策","隐私安全声明","版权声明","留言板","联系我们","网站地图",
    "友情链接","融媒矩阵","问卷调查","安全声明",
}


def fetch_page(page: str) -> str:
    url = f"{BASE}index{page}.shtml"
    resp = httpx.get(url, headers=HEADERS, timeout=15)
    return resp.text if resp.status_code == 200 else ""


def extract_exhibits(html: str) -> list[dict]:
    """从目录页提取展品名 + 详情页链接。"""
    items = re.findall(r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"', html)
    results = []
    for href, title in items:
        title = title.strip()
        if not title or title in SKIP_TITLES:
            continue
        # 构造详情页完整 URL
        if href.startswith("./"):
            href = BASE + href[2:]
        elif href.startswith("/"):
            href = "https://www.chnmuseum.cn" + href
        results.append({"name": title, "detail_url": href})
    return results


def fetch_detail(url: str) -> dict:
    """从详情页提取朝代/类别/简介。"""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}
        html = resp.text
        # 提取正文内容（国博详情页通常有展品描述段落）
        # 尝试多个常见模式
        info = {}

        # 朝代/年代（常见在正文开头或特定标签）
        dynasty_match = re.search(r'(年代|朝代)[：:]\s*([^\s<，。]+)', html)
        if dynasty_match:
            info["dynasty"] = dynasty_match.group(2).strip()

        # 类别（从页面标题或面包屑推断）
        category_match = re.search(r'(类别|材质|种类)[：:]\s*([^\s<，。]+)', html)
        if category_match:
            info["category"] = category_match.group(2).strip()

        # 简介（提取主内容区域的文本）
        # 国博详情页的正文通常在 <div class="cp_info"> 或类似容器
        content_match = re.search(
            r'<div[^>]*class="[^"]*(?:cp_info|content|detail|text|body)[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL | re.IGNORECASE
        )
        if content_match:
            # 去 HTML 标签
            text = re.sub(r'<[^>]+>', '', content_match.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                info["description"] = text[:500]
        else:
            # 退化方案：提取所有 p 标签文本
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
            texts = []
            for p in paragraphs:
                t = re.sub(r'<[^>]+>', '', p).strip()
                if t and len(t) > 20:  # 只取较长的段落
                    texts.append(t)
            if texts:
                info["description"] = texts[0][:500]

        return info
    except Exception as e:
        print(f"    详情页抓取失败: {e}")
        return {}


def main():
    all_exhibits = []

    # 1. 遍历分页提取展品列表
    print("=== 抓取馆藏精品目录 ===")
    for i in range(11):
        page = "" if i == 0 else f"_{i}"
        html = fetch_page(page)
        if not html:
            print(f"  第 {i} 页：无法获取，停止")
            break
        exhibits = extract_exhibits(html)
        print(f"  第 {i} 页：{len(exhibits)} 件")
        all_exhibits.extend(exhibits)
        time.sleep(1)

    # 去重
    seen = set()
    unique = []
    for e in all_exhibits:
        if e["name"] not in seen:
            seen.add(e["name"])
            unique.append(e)
    print(f"\n目录页共 {len(all_exhibits)} 条，去重后 {len(unique)} 件")

    # 2. 抓取详情页（限制并发，避免被 ban）
    print(f"\n=== 抓取详情页（{len(unique)} 件）===")
    for idx, exhibit in enumerate(unique):
        print(f"  [{idx+1}/{len(unique)}] {exhibit['name']}…", end=" ", flush=True)
        detail = fetch_detail(exhibit["detail_url"])
        exhibit.update(detail)

        # 如果没有朝代，从展品名或描述推断
        if "dynasty" not in exhibit:
            # 常见朝代关键词
            for d in ["新石器","商","西周","东周","春秋","战国","秦","汉","魏晋","南北朝",
                       "唐","五代","宋","辽","金","元","明","清","民国","现代"]:
                if d in exhibit["name"] or (detail.get("description") and d in detail["description"]):
                    exhibit["dynasty"] = d + "时代" if d in ["新石器"] else d
                    break
        if "dynasty" not in exhibit:
            exhibit["dynasty"] = "待补充"

        if "category" not in exhibit:
            # 从名称推断类别
            for c in [("青铜","青铜器"),("陶","陶器"),("瓷","瓷器"),("玉","玉器"),
                       ("金","金器"),("银","银器"),("石","石刻"),("骨","骨器"),
                       ("漆","漆器"),("砖","砖瓦"),("镜","铜镜")]:
                if c[0] in exhibit["name"]:
                    exhibit["category"] = c[1]
                    break
        if "category" not in exhibit:
            exhibit["category"] = "其他"

        if "description" not in exhibit:
            exhibit["description"] = exhibit["name"]

        has_detail = "✓" if detail.get("description") else "△"
        print(f"{has_detail} 朝代={exhibit.get('dynasty','?')} 类别={exhibit.get('category','?')}")

        time.sleep(0.5)  # 礼貌延迟

    # 3. 输出 JSON
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    has_desc = sum(1 for e in unique if e.get("description") and e["description"] != e["name"])
    print(f"\n=== 完成 ===")
    print(f"  总展品：{len(unique)}")
    print(f"  有详情：{has_desc}")
    print(f"  输出：{OUTPUT}")


if __name__ == "__main__":
    main()

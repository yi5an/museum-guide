# 采集系统阶段 2：发现源 + 官网 connector + LLM#1 提取 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现博物馆发现源（维基名录）和官网 per-site connector（国博，含 LLM#1 字段提取），让采集系统能自动发现新馆并从官网采集展品。

**Architecture:** 新增 `WikiListConnector`（抓维基"中国博物馆列表"分类页提取馆名清单）与 `OfficialGuoboConnector`（抓国博官网目录页，详情页正文交给 `LLMExtractor` 提取标准字段）。`LLMExtractor` 复用现有 `model_router`，prompt 固定输出 JSON。

**Tech Stack:** Python 3.12, httpx, regex, model_router (AsyncOpenAI 兼容), pytest

**Spec:** `docs/superpowers/specs/2026-06-26-collection-system-design.md` §3 §5.2 §5.3

**前置依赖:** 阶段 0（collect 表）+ 阶段 1（SourceConnector / pipeline / registry）已完成

---

## 文件结构

- **新增** `backend/app/collect/sources/wiki_list.py` —— `WikiListConnector`（发现源）
- **新增** `backend/app/collect/llm_extractor.py` —— `LLMExtractor`（LLM#1，官网字段提取）
- **新增** `backend/app/collect/sources/official_guobo.py` —— `OfficialGuoboConnector`（迁自 `crawl_guobo.py`）
- **修改** `backend/app/collect/registry.py` —— 注册 wiki_list / official
- **修改** `backend/app/collect/pipeline.py` —— 支持 target_type=museum 的 upsert（博物馆发现）
- **新增** `backend/app/tests/test_llm_extractor.py`
- **新增** `backend/app/tests/test_collect_sources_official.py`

---

### Task 1: 实现 LLMExtractor（LLM#1 官网字段提取）

**Files:**
- Create: `backend/app/collect/llm_extractor.py`
- Create: `backend/app/tests/test_llm_extractor.py`

`LLMExtractor` 从任意官网详情页 HTML 提取 `{name, dynasty, category, description}`，复用 `model_router` 通道，prompt 固定输出 JSON，缺字段用规则兜底。

- [ ] **Step 1: 写失败测试（mock model_router）**

新建 `backend/app/tests/test_llm_extractor.py`：

```python
import asyncio
from unittest.mock import AsyncMock, patch

from app.collect.llm_extractor import LLMExtractor


def test_extract_exhibit_parses_llm_json():
    extractor = LLMExtractor()
    html = "<html><body>后母戊鼎 商代 青铜器 正文...</body></html>"

    # mock model_router.generate_structured 返回标准字段
    fake_llm = AsyncMock()
    fake_llm.generate_structured.return_value = {
        "name": "后母戊鼎",
        "dynasty": "商代",
        "category": "青铜器",
        "description": "后母戊鼎是商代晚期青铜方鼎。",
    }

    with patch("app.collect.llm_extractor.model_router", fake_llm):
        fields = asyncio.run(extractor.extract_exhibit(html, "http://guobo/x", "中国国家博物馆"))

    assert fields["name"] == "后母戊鼎"
    assert fields["dynasty"] == "商代"
    assert fields["category"] == "青铜器"
    assert "商代" in fields["description"]


def test_extract_exhibit_fallback_when_llm_missing_fields():
    """LLM 缺 category 时，用名称规则兜底。"""
    extractor = LLMExtractor()
    html = "<html>司母戊鼎 ...</html>"

    fake_llm = AsyncMock()
    fake_llm.generate_structured.return_value = {
        "name": "司母戊鼎",
        "dynasty": None,
        "category": None,
        "description": "某青铜大鼎",
    }

    with patch("app.collect.llm_extractor.model_router", fake_llm):
        fields = asyncio.run(extractor.extract_exhibit(html, "http://x", "国博"))

    # 名称含"鼎"，但描述含"青铜"-> 兜底成青铜器
    assert fields["category"] == "青铜器"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_llm_extractor.py -v`
Expected: FAIL — `ImportError`（llm_extractor 不存在）

- [ ] **Step 3: 先给 model_router 加 generate_structured 方法**

修改 `backend/app/services/model_router.py`，在 `ModelRouter` 类中（`chat` 方法之后、全局单例之前）新增：

```python
    async def generate_structured(self, prompt: str, schema_hint: str) -> dict[str, Any]:
        """让 LLM 按指定 JSON schema 返回结构化结果。

        供采集 LLM#1 提取器等需要确定性 JSON 输出的场景使用。
        解析失败返回空 dict。
        """
        full = f"{prompt}\n\n严格按此 JSON 结构返回（不要其他文字）：\n{schema_hint}"
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": full}],
        )
        text = resp.choices[0].message.content or ""
        parsed = _extract_json(text)
        return parsed if isinstance(parsed, dict) else {}
```

- [ ] **Step 4: 实现 llm_extractor.py**

新建 `backend/app/collect/llm_extractor.py`：

```python
"""LLM#1 提取器：从任意博物馆官网详情页 HTML 提取结构化展品字段。

只服务官网 per-site connector。链接发现用规则，LLM 负责把详情页正文
提取成 {name, dynasty, category, description}。复用 model_router 通道。
"""

import re

from app.services.model_router import model_router

_SCHEMA = '{"name":"展品名","dynasty":"朝代(无则null)","category":"类别(无则null)","description":"简介"}'

# 朝代/类别兜底规则（迁自 crawl_guobo.py）
_DYNASTIES = ["新石器", "商", "西周", "东周", "春秋", "战国", "秦", "汉",
              "魏晋", "南北朝", "唐", "五代", "宋", "辽", "金", "元", "明", "清", "民国", "现代"]
_CATEGORY_RULES = [
    ("青铜", "青铜器"), ("陶", "陶器"), ("瓷", "瓷器"), ("玉", "玉器"),
    ("金", "金器"), ("银", "银器"), ("石", "石刻"), ("骨", "骨器"),
    ("漆", "漆器"), ("砖", "砖瓦"), ("镜", "铜镜"),
]


def _strip_html(html: str) -> str:
    """去标签噪声，截取正文（控 token）。"""
    text = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:3000]  # 截断，控成本


class LLMExtractor:
    async def extract_exhibit(self, html: str, url: str, museum_name: str) -> dict | None:
        text = _strip_html(html)
        if len(text) < 10:
            return None

        prompt = (
            f"你是博物馆文物信息提取专家。下面是{museum_name}官网某展品页面的正文，"
            "提取展品的结构化信息。\n\n"
            f"页面正文：\n{text[:2000]}"
        )
        try:
            data = await model_router.generate_structured(prompt, _SCHEMA)
        except Exception:
            data = {}

        if not data:
            return None

        name = data.get("name") or ""
        dynasty = data.get("dynasty")
        category = data.get("category")
        description = data.get("description") or name

        # 兜底：缺朝代从描述/名称匹配
        if not dynasty:
            for d in _DYNASTIES:
                if d in description or d in name:
                    dynasty = d
                    break

        # 兜底：缺类别从名称/描述匹配
        if not category:
            for k, v in _CATEGORY_RULES:
                if k in name or k in description:
                    category = v
                    break

        return {
            "name": name,
            "category": category,
            "dynasty": dynasty,
            "description": description,
            "source_ref": url,
        }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_llm_extractor.py -v`
Expected: 两个测试 PASS

- [ ] **Step 6: 提交**

```bash
cd backend
git add app/collect/llm_extractor.py app/services/model_router.py app/tests/test_llm_extractor.py
git commit -m "feat(collect): LLMExtractor LLM#1 官网字段提取 + model_router.generate_structured"
```

---

### Task 2: pipeline 支持 target_type=museum（博物馆发现入库）

**Files:**
- Modify: `backend/app/collect/pipeline.py`（新增 `_upsert_museum`，按 name 去重）

发现源的产出是博物馆清单，需要按博物馆名去重 upsert。

- [ ] **Step 1: 写失败测试**

追加到 `backend/app/tests/test_collect_pipeline.py`：

```python
def test_run_pipeline_inserts_museum(test_db):
    """target_type=museum 时，pipeline upsert 博物馆。"""
    from app.collect.base import CollectContext, SourceConnector

    class _MuseumFinder(SourceConnector):
        source = "wiki_list"
        default_confidence = 0.6
        target_type = "museum"

        async def discover(self, ctx):
            return [
                {"name": "新发现的博物馆A", "source_ref": "http://wiki/A"},
                {"name": "中国国家博物馆", "source_ref": "http://wiki/B"},  # 已存在
            ]

        async def fetch(self, item, ctx):
            return '{"lat":30.1,"lng":120.2,"description":"测试馆"}'

        async def parse(self, raw, item, ctx):
            import json
            d = json.loads(raw)
            return {"name": item["name"], "lat": d["lat"], "lng": d["lng"],
                    "description": d["description"], "source_ref": item["source_ref"]}

    # 预置一个已存在的馆
    _setup_museum_with_name(test_db, "中国国家博物馆")
    ctx = CollectContext()

    job = asyncio.run(run_pipeline(_MuseumFinder(), None, test_db, ctx))

    assert job.stage == "succeeded"
    museums = list(test_db.scalars(select(Museum).where(
        Museum.name.in_(["新发现的博物馆A", "中国国家博物馆"]))))
    assert len(museums) == 2


def _setup_museum_with_name(db, name):
    m = Museum(name=name, geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    db.add(m); db.flush()
    return m
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_collect_pipeline.py::test_run_pipeline_inserts_museum -v`
Expected: FAIL — `_upsert_museum` 不存在 / museum 未被插入

- [ ] **Step 3: 修改 pipeline.py，新增 _upsert_museum 并在主流程分发**

在 `backend/app/collect/pipeline.py` 的 `_upsert_exhibit` 函数之后新增：

```python
def _upsert_museum(
    db: Session, fields: dict, connector: SourceConnector
) -> tuple[Museum, bool]:
    """按 name 去重 upsert 博物馆。返回 (museum, created)。"""
    name = fields["name"]
    existing = db.scalar(select(Museum).where(Museum.name == name))
    if existing:
        if fields.get("description"):
            existing.description = fields["description"]
        existing.source = connector.source
        existing.confidence = connector.default_confidence
        existing.source_ref = fields.get("source_ref")
        existing.fetched_at = datetime.utcnow()
        return existing, False

    museum = Museum(
        name=name,
        name_i18n={"zh": name},
        city=fields.get("city") or "待补充",
        country=fields.get("country") or "中国",
        lat=fields.get("lat") or 0.0,
        lng=fields.get("lng") or 0.0,
        geo_fence=[],
        description=fields.get("description"),
        source=connector.source,
        confidence=connector.default_confidence,
        source_ref=fields.get("source_ref"),
        fetched_at=datetime.utcnow(),
    )
    db.add(museum)
    db.flush()
    return museum, True
```

在 `run_pipeline` 的 upsert 分发处，把原来的：
```python
            # 4. upsert
            exhibit, created = _upsert_exhibit(db, museum_id, fields, connector) \
                if connector.target_type == "exhibit" else (None, False)
            if exhibit:
                item.target_id = exhibit.id
```
替换为：
```python
            # 4. upsert（按 target_type 分发）
            target = None
            if connector.target_type == "exhibit":
                target, _ = _upsert_exhibit(db, museum_id, fields, connector)
            elif connector.target_type == "museum":
                target, _ = _upsert_museum(db, fields, connector)
            if target:
                item.target_id = target.id
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_collect_pipeline.py -v`
Expected: 三个测试 PASS（含新增 museum upsert 测试）

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/collect/pipeline.py app/tests/test_collect_pipeline.py
git commit -m "feat(collect): pipeline 支持 target_type=museum 博物馆发现入库"
```

---

### Task 3: 实现 WikiListConnector（发现源）

**Files:**
- Create: `backend/app/collect/sources/wiki_list.py`
- Modify: `backend/app/tests/test_collect_sources_official.py`（新增）

抓维基"中国博物馆列表"分类页，正则提取馆名。target_type=museum。

- [ ] **Step 1: 写失败测试（mock HTTP）**

新建 `backend/app/tests/test_collect_sources_official.py`：

```python
import asyncio
from unittest.mock import patch

from app.collect.base import CollectContext
from app.collect.sources.wiki_list import WikiListConnector


class _Resp:
    def __init__(self, text):
        self.status_code = 200
        self.text = text


_FAKE_HTML = """
<html><body>
<a href="/wiki/中国国家博物馆" title="中国国家博物馆">中国国家博物馆</a>
<a href="/wiki/故宫博物院" title="故宫博物院">故宫博物院</a>
<a href="/wiki/上海博物馆" title="上海博物馆">上海博物馆</a>
<a href="/wiki/编辑" title="编辑">编辑</a>
</body></html>
"""


def test_wiki_list_discovers_museums():
    connector = WikiListConnector()
    ctx = CollectContext()
    with patch("app.collect.sources.wiki_list.httpx.get", return_value=_Resp(_FAKE_HTML)):
        items = asyncio.run(connector.discover(ctx))
    names = [i["name"] for i in items]
    assert "中国国家博物馆" in names
    assert "故宫博物院" in names
    # 过滤掉导航噪声
    assert "编辑" not in names
    assert all("source_ref" in i for i in items)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_collect_sources_official.py::test_wiki_list_discovers_museums -v`
Expected: FAIL — `ImportError`（wiki_list 不存在）

- [ ] **Step 3: 实现 WikiListConnector**

新建 `backend/app/collect/sources/wiki_list.py`：

```python
"""维基"中国博物馆列表"分类页采集 connector（发现源）。

从维基分类页提取博物馆名称清单，作为后续内容采集的目标集合。
target_type=museum。纯规则，不接 LLM。
"""

import re
import urllib.parse

import httpx

from app.collect.base import CollectContext, SourceConnector

_HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}
# 维基"中国的博物馆"分类页（中文名条目列表）
_LIST_URL = "https://zh.wikipedia.org/wiki/Category:%E4%B8%AD%E5%9B%BD%E7%9A%84%E5%8D%9A%E7%89%A9%E9%A6%86"

# 噪声词：维基功能链接、非博物馆条目
_SKIP = {"编辑", "分类", "首页", "Wikipedia", "Help", "维基百科", "登录", "创建账户",
         "最近更改", "随机条目", "资助", "关于维基百科", "免责声明"}


class WikiListConnector(SourceConnector):
    source = "wiki_list"
    default_confidence = 0.6
    target_type = "museum"

    async def discover(self, ctx: CollectContext) -> list[dict]:
        try:
            resp = httpx.get(_LIST_URL, headers=_HEADERS, timeout=15)
            if resp.status_code != 200:
                return []
            html = resp.text
        except Exception:
            return []

        # 提取分类成员链接：<a href="/wiki/XXX" title="XXX">
        names = set()
        for href, title in re.findall(r'<a[^>]*href="(/wiki/[^"]*)"[^>]*title="([^"]*)"', html):
            title = title.strip()
            if (not title or title in _SKIP
                    or title.startswith("Category:") or title.startswith("Wikipedia:")
                    or "博物馆" not in title):  # 只保留含"博物馆"的条目
                continue
            names.add(title)

        return [
            {"name": n, "source_ref": f"https://zh.wikipedia.org{urllib.parse.quote('/wiki/' + n)}"}
            for n in sorted(names)
        ]

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        # 发现源本身不抓详情；详情靠后续 wiki connector。
        # 此处返回占位，让 pipeline 流程闭合（parse 解析占位为最小博物馆字段）。
        return "{}"

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        return {
            "name": item["name"],
            "lat": 0.0,
            "lng": 0.0,
            "description": None,
            "source_ref": item.get("source_ref"),
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_collect_sources_official.py::test_wiki_list_discovers_museums -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/collect/sources/wiki_list.py app/tests/test_collect_sources_official.py
git commit -m "feat(collect): WikiListConnector 维基名录发现源"
```

---

### Task 4: 实现 OfficialGuoboConnector（国博官网 + LLM#1）

**Files:**
- Create: `backend/app/collect/sources/official_guobo.py`
- Modify: `backend/app/tests/test_collect_sources_official.py`（追加）

迁自 `crawl_guobo.py`：discover 抓目录页提展品名+详情链接，fetch 抓详情 HTML，parse 交 LLMExtractor。

- [ ] **Step 1: 写失败测试（mock HTTP + LLM）**

追加到 `backend/app/tests/test_collect_sources_official.py`：

```python
from unittest.mock import AsyncMock
from app.collect.sources.official_guobo import OfficialGuoboConnector


_INDEX_HTML = """
<html><body>
<a href="./kgfjp/001.shtml" title="后母戊鼎">后母戊鼎</a>
<a href="./kgfjp/002.shtml" title="四羊方尊">四羊方尊</a>
<a href="/index.shtml" title="首页">首页</a>
</body></html>
"""
_DETAIL_HTML = "<html><body>后母戊鼎 商代青铜器 方鼎...</body></html>"


def test_official_guobo_three_stages():
    connector = OfficialGuoboConnector()
    ctx = CollectContext()

    with patch("app.collect.sources.official_guobo.httpx.get",
               side_effect=[_Resp(_INDEX_HTML), _Resp(_DETAIL_HTML)]):
        items = asyncio.run(connector.discover(ctx))
        assert len(items) == 2
        assert items[0]["name"] == "后母戊鼎"
        assert items[0]["source_ref"].startswith("https://www.chnmuseum.cn")

        raw = asyncio.run(connector.fetch(items[0], ctx))
        assert raw == _DETAIL_HTML

    # parse 交 LLM，mock 它
    fake_llm = AsyncMock()
    fake_llm.extract_exhibit = AsyncMock(return_value={
        "name": "后母戊鼎", "dynasty": "商代", "category": "青铜器",
        "description": "商代方鼎", "source_ref": items[0]["source_ref"],
    })
    connector._llm = fake_llm  # 注入 mock
    fields = asyncio.run(connector.parse(_DETAIL_HTML, items[0], ctx))
    assert fields["name"] == "后母戊鼎"
    assert fields["dynasty"] == "商代"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_collect_sources_official.py::test_official_guobo_three_stages -v`
Expected: FAIL — `ImportError`（official_guobo 不存在）

- [ ] **Step 3: 实现 OfficialGuoboConnector**

新建 `backend/app/collect/sources/official_guobo.py`：

```python
"""国博官网采集 connector（per-site）。

迁自 app/crawl_guobo.py。目录页用正则提展品名+详情链接（规则，免费），
详情页正文交 LLMExtractor（LLM#1）提取标准字段。
每家官网结构不同，单独写一个 connector；其他馆照此模板扩展。
"""

import re

import httpx

from app.collect.base import CollectContext, SourceConnector
from app.collect.llm_extractor import LLMExtractor

BASE = "https://www.chnmuseum.cn/zp/zpml/kgfjp/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

SKIP_TITLES = {
    "国家博物馆", "首页", "征集", "保管", "研究", "展览", "社教", "文创", "服务",
    "学习", "视频", "登录", "注册", "分享", "下载", "导航", "馆藏精品",
    "隐私政策", "隐私安全声明", "版权声明", "留言板", "联系我们", "网站地图",
}


class OfficialGuoboConnector(SourceConnector):
    source = "official"
    default_confidence = 0.9
    target_type = "exhibit"

    def __init__(self):
        self._llm = LLMExtractor()

    async def discover(self, ctx: CollectContext) -> list[dict]:
        results = []
        # 11 个分页
        for i in range(11):
            page = "" if i == 0 else f"_{i}"
            url = f"{BASE}index{page}.shtml"
            try:
                resp = httpx.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    break
            except Exception:
                break
            for href, title in re.findall(r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"', resp.text):
                title = title.strip()
                if not title or title in SKIP_TITLES:
                    continue
                if href.startswith("./"):
                    href = BASE + href[2:]
                elif href.startswith("/"):
                    href = "https://www.chnmuseum.cn" + href
                results.append({"name": title, "source_ref": href})
            await ctx.sleep(1)  # 礼貌延迟

        # 去重
        seen, unique = set(), []
        for r in results:
            if r["name"] not in seen:
                seen.add(r["name"])
                unique.append(r)
        return unique

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        try:
            resp = httpx.get(item["source_ref"], headers=HEADERS, timeout=15)
            return resp.text if resp.status_code == 200 else None
        except Exception:
            return None

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        # LLM#1 提取；LLM 失败则返回带名称的最小字段（不阻断流程）
        fields = await self._llm.extract_exhibit(raw, item["source_ref"], "中国国家博物馆")
        if fields:
            fields["name"] = fields.get("name") or item["name"]
            return fields
        # 兜底：至少把名称入库
        return {"name": item["name"], "category": None, "dynasty": None,
                "description": item["name"], "source_ref": item["source_ref"]}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_collect_sources_official.py -v`
Expected: 两个测试 PASS

- [ ] **Step 5: 注册新 connector 到 registry**

修改 `backend/app/collect/registry.py`，import 并注册：

```python
from app.collect.sources.official_guobo import OfficialGuoboConnector
from app.collect.sources.wiki_list import WikiListConnector

_REGISTRY: dict[str, type[SourceConnector]] = {
    "baike": BaikeConnector,
    "wiki": WikiConnector,
    "wiki_list": WikiListConnector,
    "official": OfficialGuoboConnector,
}
```

- [ ] **Step 6: 运行确认注册**

Run: `cd backend && uv run python -c "from app.collect.registry import available_sources; print(available_sources())"`
Expected: `['baike', 'wiki', 'wiki_list', 'official']`

- [ ] **Step 7: 提交**

```bash
cd backend
git add app/collect/sources/official_guobo.py app/collect/registry.py app/tests/test_collect_sources_official.py
git commit -m "feat(collect): OfficialGuoboConnector 国博官网采集 + LLM#1 提取"
```

---

### Task 5: 阶段 2 收尾验证

- [ ] **Step 1: 全量测试**

Run: `cd backend && uv run pytest -q`
Expected: 全绿

- [ ] **Step 2: Lint**

Run: `cd backend && uv run ruff check app/`
Expected: 无错误

- [ ] **Step 3: CLI 可用性**

Run: `cd backend && uv run python -m app.collect --help`
Expected: choices 含 baike/wiki/wiki_list/official

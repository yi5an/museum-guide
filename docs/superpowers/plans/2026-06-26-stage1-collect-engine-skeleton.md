# 采集系统阶段 1：采集引擎骨架 + 规则源接入 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建可复用的采集引擎骨架（`SourceConnector` 基类 + 统一 pipeline），并把现有的百度百科 / 维基采集脚本改造为符合框架的 connector，通过 CLI 触发，数据入库且可观测。

**Architecture:** 新建 `app/collect/` 包：基类定义统一接口（discover/fetch/parse），`run_pipeline` 负责「发现→逐条抓取→解析→upsert 入库→写 collect_jobs/items→限速/重试」编排。`BaikeConnector` 和 `WikiConnector` 各自实现三阶段（纯规则，不接 LLM）。本阶段 LLM 完全不接入。

**Tech Stack:** Python 3.12, httpx, SQLAlchemy 2.0, pytest（含 monkeypatch mock HTTP）

**Spec:** `docs/superpowers/specs/2026-06-26-collection-system-design.md` §2 §5.1 §5.2 §5.5

**前置依赖:** 阶段 0（collect_jobs / collect_items 表 + source_ref/content_hash/fetched_at 字段）已完成

---

## 文件结构

- **新增** `backend/app/collect/__init__.py` —— 包导出
- **新增** `backend/app/collect/base.py` —— `SourceConnector` 抽象基类 + `CollectContext`（限速/重试/日志）
- **新增** `backend/app/collect/pipeline.py` —— `run_pipeline` 统一编排 + upsert 去重
- **新增** `backend/app/collect/sources/baike.py` —— `BaikeConnector`（迁自 `seed_from_baike.py`）
- **新增** `backend/app/collect/sources/wiki.py` —— `WikiConnector`（迁自 `seed_from_wiki.py` + `fetch_museum_images.py`）
- **新增** `backend/app/collect/registry.py` —— source 名 → connector 实例的注册表
- **新增** `backend/app/collect/__main__.py` —— CLI 入口（`python -m app.collect`）
- **新增** `backend/app/tests/test_collect_pipeline.py` —— pipeline + upsert 测试
- **新增** `backend/app/tests/test_collect_sources.py` —— connector 测试（mock HTTP）

---

### Task 1: 建立 collect 包与 CollectContext

**Files:**
- Create: `backend/app/collect/__init__.py`
- Create: `backend/app/collect/base.py`

`CollectContext` 封装「限速 + 重试 + 取消检查」，供 pipeline 和 connector 共享。

- [ ] **Step 1: 写失败测试**

新建 `backend/app/tests/test_collect_base.py`：

```python
import pytest

from app.collect.base import CollectContext


def test_collect_context_defaults():
    ctx = CollectContext()
    assert ctx.cancelled is False
    ctx.cancel()
    assert ctx.cancelled is True


@pytest.mark.asyncio
async def test_collect_context_sleep_cancellable(monkeypatch):
    """sleep 在被 cancel 后立即返回而非阻塞。"""
    ctx = CollectContext()
    ctx.cancel()
    # 已 cancel，sleep 应立即返回
    await ctx.sleep(100)  # 不会真的等
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_collect_base.py -v`
Expected: FAIL — `ImportError`（app.collect.base 不存在）

注：项目若未配置 `pytest-asyncio`，先确认是否已装。若未装，本计划所有 async 测试改用 `asyncio.run()` 包装（见 Task 1 Step 3 备注）。

- [ ] **Step 3: 实现 base.py**

新建 `backend/app/collect/base.py`：

```python
"""采集引擎基础设施：CollectContext 与 SourceConnector 抽象基类。"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any


class CollectContext:
    """单次采集运行的共享上下文：限速、重试、取消信号。

    所有 connector 通过 ctx.sleep() 做礼貌延迟，pipeline 在每条 item 前
    检查 ctx.cancelled 以支持取消。
    """

    def __init__(self, min_interval: float = 0.5, max_retries: int = 3):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._cancelled = False
        self._last_request = 0.0

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    async def sleep(self, seconds: float) -> None:
        """礼貌延迟；若已取消则立即返回。"""
        if self._cancelled:
            return
        await asyncio.sleep(seconds)


class SourceConnector(ABC):
    """采集源抽象基类。每个来源实现 discover/fetch/parse 三阶段。

    discover/fetch/parse 分离的设计，使 parse 可对已落盘的 raw 文件反复重跑，
    无需重新抓取源站。
    """

    source: str = ""          # "baike" / "wiki" / "official" / "wiki_list"
    default_confidence: float = 0.5
    target_type: str = "exhibit"  # museum / exhibit / image

    @abstractmethod
    async def discover(self, ctx: CollectContext) -> list[dict]:
        """发现阶段：返回原始待采条目列表。

        每条至少含: {"name": str, "source_ref": str}
        其余原始字段由各 connector 自定义。
        """

    @abstractmethod
    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        """抓取阶段：返回单个条目的原始内容文本（HTML/JSON），失败返回 None。"""

    @abstractmethod
    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        """解析阶段：raw 文本 -> 标准字段 dict。

        标准字段: {"name","category","dynasty","description","images":[...]}
        返回 None 表示解析失败。
        """
```

新建 `backend/app/collect/__init__.py`：

```python
from app.collect.base import CollectContext, SourceConnector

__all__ = ["CollectContext", "SourceConnector"]
```

**备注（async 测试）**：若 `pytest-asyncio` 未安装，将测试改为：
```python
import asyncio
def test_collect_context_sleep_cancellable():
    ctx = CollectContext(); ctx.cancel()
    asyncio.run(ctx.sleep(100))
```
执行 Step 4 前先用 `uv run pytest app/tests/test_collect_base.py -v` 实测确认项目 async 测试支持情况，按结果二选一。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_collect_base.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/collect/__init__.py app/collect/base.py app/tests/test_collect_base.py
git commit -m "feat(collect): 采集引擎基类 SourceConnector + CollectContext"
```

---

### Task 2: 实现统一 pipeline 与 upsert 去重

**Files:**
- Create: `backend/app/collect/pipeline.py`
- Create: `backend/app/tests/test_collect_pipeline.py`

`run_pipeline` 串起三阶段 + 入库 + 进度记录。这是所有 connector 共享的编排逻辑。

- [ ] **Step 1: 写失败测试（fake connector 跑通全流程）**

新建 `backend/app/tests/test_collect_pipeline.py`：

```python
import asyncio

from sqlalchemy import select

from app.collect.base import CollectContext, SourceConnector
from app.collect.pipeline import run_pipeline
from app.models import CollectItem, CollectJob, Exhibit, Museum


class _FakeConnector(SourceConnector):
    """假 connector：discover 返回 2 条，parse 返回固定字段，不做真实网络。"""
    source = "fake"
    default_confidence = 0.5
    target_type = "exhibit"

    async def discover(self, ctx):
        return [
            {"name": "司母戊鼎", "source_ref": "http://fake/1"},
            {"name": "四羊方尊", "source_ref": "http://fake/2"},
        ]

    async def fetch(self, item, ctx):
        return f"<html>{item['name']}</html>"

    async def parse(self, raw, item, ctx):
        return {
            "name": item["name"],
            "category": "青铜器",
            "dynasty": "商代",
            "description": f"{item['name']}的描述",
        }


def _setup_museum(db):
    m = Museum(name="测试馆", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    db.add(m)
    db.flush()
    return m


def test_run_pipeline_inserts_exhibits_and_records_job(test_db):
    m = _setup_museum(test_db)
    connector = _FakeConnector()
    ctx = CollectContext()

    job = asyncio.run(run_pipeline(connector, museum_id=m.id, db=test_db, ctx=ctx))

    # job 完成态
    assert job.stage == "succeeded"
    assert job.total == 2 and job.done == 2 and job.failed == 0
    assert job.finished_at is not None

    # 两条 exhibit 已入库
    exhibits = list(test_db.scalars(select(Exhibit).where(Exhibit.museum_id == m.id)))
    assert len(exhibits) == 2
    names = {e.name for e in exhibits}
    assert names == {"司母戊鼎", "四羊方尊"}

    # 两条 collect_items 均为 saved
    items = list(test_db.scalars(select(CollectItem).where(CollectItem.job_id == job.id)))
    assert len(items) == 2
    assert all(i.stage == "saved" for i in items)


def test_run_pipeline_upsert_dedup_by_name(test_db):
    """同名展品重复采集应更新而非新增。"""
    m = _setup_museum(test_db)
    ctx = CollectContext()
    asyncio.run(run_pipeline(_FakeConnector(), m.id, test_db, ctx))
    # 再跑一次同样的
    job2 = asyncio.run(run_pipeline(_FakeConnector(), m.id, test_db, ctx))

    exhibits = list(test_db.scalars(select(Exhibit).where(Exhibit.museum_id == m.id)))
    assert len(exhibits) == 2  # 不翻倍
    assert job2.stage == "succeeded"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_collect_pipeline.py -v`
Expected: FAIL — `ImportError`（run_pipeline 不存在）

- [ ] **Step 3: 实现 pipeline.py**

新建 `backend/app/collect/pipeline.py`：

```python
"""统一采集 pipeline：编排 discover → fetch → parse → upsert，记录 collect_jobs/items。"""

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collect.base import CollectContext, SourceConnector
from app.models import CollectItem, CollectJob, Exhibit, ExhibitImage, Museum

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def _raw_path(source: str, museum_id: int, name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "._-") or "item"
    return RAW_DIR / source / f"{museum_id}_{safe}.txt"


def _upsert_exhibit(
    db: Session, museum_id: int, fields: dict, connector: SourceConnector
) -> tuple[Exhibit, bool]:
    """按 (museum_id, name) 去重 upsert。返回 (exhibit, created)。"""
    name = fields["name"]
    existing = db.scalar(
        select(Exhibit).where(Exhibit.museum_id == museum_id, Exhibit.name == name)
    )
    if existing:
        existing.category = fields.get("category") or existing.category
        existing.dynasty = fields.get("dynasty") or existing.dynasty
        existing.source = connector.source
        existing.confidence = connector.default_confidence
        existing.source_ref = fields.get("source_ref")
        existing.fetched_at = datetime.utcnow()
        return existing, False

    exhibit = Exhibit(
        museum_id=museum_id,
        name=name,
        name_i18n={"zh": name},
        category=fields.get("category"),
        dynasty=fields.get("dynasty"),
        status="active",
        source=connector.source,
        confidence=connector.default_confidence,
        source_ref=fields.get("source_ref"),
        fetched_at=datetime.utcnow(),
    )
    db.add(exhibit)
    db.flush()
    return exhibit, True


async def run_pipeline(
    connector: SourceConnector,
    museum_id: int | None,
    db: Session,
    ctx: CollectContext,
) -> CollectJob:
    """执行完整采集流程，返回完成的 CollectJob。

    流程：discover → 逐条(fetch→落盘→parse→upsert→写 item) → 更新 job 状态。
    每条 item 前检查取消信号。
    """
    job = CollectJob(
        museum_id=museum_id,
        source=connector.source,
        stage="running",
        total=0,
        done=0,
        failed=0,
        log=[],
    )
    db.add(job)
    db.flush()

    try:
        items_data = await connector.discover(ctx)
    except Exception as e:
        job.stage = "failed"
        job.error = f"discover 失败: {e}"
        job.finished_at = datetime.utcnow()
        db.commit()
        return job

    job.total = len(items_data)
    db.commit()

    for raw_item in items_data:
        if ctx.cancelled:
            job.stage = "canceled"
            break

        name = raw_item.get("name", "?")
        item = CollectItem(
            job_id=job.id,
            source_ref=raw_item.get("source_ref"),
            name=name,
            stage="pending",
            target_type=connector.target_type,
        )
        db.add(item)
        db.flush()

        try:
            # 1. fetch
            raw = await connector.fetch(raw_item, ctx)
            if raw is None:
                raise RuntimeError("fetch 返回空")
            item.stage = "fetched"

            # 2. 落盘 raw（供 parse 重跑，无需重新抓站）
            if museum_id is not None:
                p = _raw_path(connector.source, museum_id, name)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(raw, encoding="utf-8")

            # 3. parse
            fields = await connector.parse(raw, raw_item, ctx)
            if not fields:
                raise RuntimeError("parse 返回空")
            fields.setdefault("source_ref", raw_item.get("source_ref"))
            item.stage = "parsed"

            # 4. upsert
            exhibit, created = _upsert_exhibit(db, museum_id, fields, connector) \
                if connector.target_type == "exhibit" else (None, False)
            if exhibit:
                item.target_id = exhibit.id

            item.stage = "saved"
            job.done += 1

        except Exception as e:
            item.stage = "failed"
            item.error = str(e)[:300]
            job.failed += 1
            job.log.append({"name": name, "error": str(e)[:200]})

        await ctx.sleep(ctx.min_interval)
        db.commit()

    if job.stage == "running":
        job.stage = "succeeded" if job.failed == 0 else "partial"
    job.finished_at = datetime.utcnow()
    db.commit()
    return job
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_collect_pipeline.py -v`
Expected: 两个测试 PASS

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/collect/pipeline.py app/tests/test_collect_pipeline.py
git commit -m "feat(collect): 统一 pipeline + (museum_id,name) upsert 去重"
```

---

### Task 3: 改造 BaikeConnector

**Files:**
- Create: `backend/app/collect/sources/__init__.py`
- Create: `backend/app/collect/sources/baike.py`
- Create: `backend/app/tests/test_collect_sources.py`

把 `seed_from_baike.py` 的抓取/解析逻辑迁成 `BaikeConnector`。三阶段对应：discover（从该馆现有展品名生成查询）→ fetch（百科 openapi）→ parse（抽 abstract/description）。

- [ ] **Step 1: 写失败测试（mock HTTP）**

新建 `backend/app/tests/test_collect_sources.py`：

```python
import asyncio
import json
from unittest.mock import patch

from app.collect.base import CollectContext
from app.collect.sources.baike import BaikeConnector


def _fake_baike_response(keyword: str):
    return {
        "status_code": 200,
        "json": lambda: {
            "key": keyword,
            "abstract": f"{keyword}是商代晚期青铜礼器，1939年出土于河南安阳。",
        },
    }


class _FakeResponse:
    def __init__(self, payload):
        self.status_code = payload["status_code"]
        self._json = payload["json"]

    def json(self):
        return self._json()


def test_baike_connector_three_stages():
    connector = BaikeConnector()
    ctx = CollectContext()

    # discover：传入展品名列表
    items = asyncio.run(connector.discover(ctx, exhibit_names=["司母戊鼎"]))
    assert len(items) == 1
    assert items[0]["name"] == "司母戊鼎"
    assert "source_ref" in items[0]

    # fetch + parse：mock httpx
    with patch("app.collect.sources.baike.httpx.get") as mock_get:
        mock_get.return_value = _FakeResponse(_fake_baike_response("司母戊鼎"))
        raw = asyncio.run(connector.fetch(items[0], ctx))
        assert raw is not None

        fields = asyncio.run(connector.parse(raw, items[0], ctx))
        assert fields["name"] == "司母戊鼎"
        assert "商代" in fields["description"] or fields["dynasty"]


def test_baike_connector_not_found():
    connector = BaikeConnector()
    ctx = CollectContext()

    items = asyncio.run(connector.discover(ctx, exhibit_names=["不存在的展品"]))
    assert len(items) == 1

    with patch("app.collect.sources.baike.httpx.get") as mock_get:
        mock_get.return_value = _FakeResponse({"status_code": 200, "json": lambda: {}})
        raw = asyncio.run(connector.fetch(items[0], ctx))
        assert raw is None  # 百科未命中
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_collect_sources.py -v`
Expected: FAIL — `ImportError`（app.collect.sources.baike 不存在）

- [ ] **Step 3: 实现 BaikeConnector**

新建 `backend/app/collect/sources/__init__.py`（空文件）。

新建 `backend/app/collect/sources/baike.py`：

```python
"""百度百科采集 connector。

迁自 app/seed_from_baike.py，纳入统一 pipeline 框架。
不接 LLM，纯规则解析百科 openapi 返回的 JSON。
"""

import urllib.parse

import httpx

from app.collect.base import CollectContext, SourceConnector

_HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}


class BaikeConnector(SourceConnector):
    source = "baike"
    default_confidence = 0.5
    target_type = "exhibit"

    async def discover(self, ctx: CollectContext, exhibit_names: list[str] | None = None) -> list[dict]:
        """discover 阶段需要传入展品名列表（来自该馆已入库或待采清单）。

        与基类签名不同：百科需要"查什么"。实际调用时由 pipeline/CLI 传入。
        """
        names = exhibit_names or []
        return [
            {
                "name": name,
                "source_ref": f"https://baike.baidu.com/item/{urllib.parse.quote(name)}",
            }
            for name in names
        ]

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        encoded = urllib.parse.quote(item["name"])
        url = (
            "https://baike.baidu.com/api/openapi/BaikeLemmaCardApi"
            f"?scope=103&format=json&appid=379020&bk_key={encoded}&bk_length=600"
        )
        try:
            resp = httpx.get(url, headers=_HEADERS, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data.get("key"):
                return None
            import json
            return json.dumps(data, ensure_ascii=False)
        except Exception:
            return None

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        import json
        import re

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        abstract = data.get("abstract", "")
        summary = data.get("card", {}).get("summary", "")
        description = abstract or summary or item["name"]
        if not abstract:
            return None

        # 朝代/类别推断（迁自 seed_from_baike 的轻规则）
        text = abstract
        dynasty = None
        for d in ["商", "西周", "东周", "春秋", "战国", "秦", "汉", "唐", "宋", "元", "明", "清"]:
            if d in text:
                dynasty = d
                break
        category = None
        for k, v in [("青铜", "青铜器"), ("陶", "陶器"), ("瓷", "瓷器"), ("玉", "玉器"), ("金", "金器")]:
            if k in text:
                category = v
                break

        return {
            "name": item["name"],
            "category": category,
            "dynasty": dynasty,
            "description": abstract,
            "source_ref": item.get("source_ref"),
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_collect_sources.py -v`
Expected: 两个测试 PASS

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/collect/sources/__init__.py app/collect/sources/baike.py app/tests/test_collect_sources.py
git commit -m "feat(collect): BaikeConnector 百度百科采集（迁自 seed_from_baike）"
```

---

### Task 4: 改造 WikiConnector

**Files:**
- Create: `backend/app/collect/sources/wiki.py`
- Modify: `backend/app/tests/test_collect_sources.py`（追加 wiki 测试）

WikiConnector 复用 `seed_from_wiki.py`（展品摘要）+ `fetch_museum_images.py`（博物馆坐标/建筑图）。本 connector 的 target_type 支持 exhibit 与 museum 两种。

- [ ] **Step 1: 写失败测试（追加到 test_collect_sources.py）**

```python
from app.collect.sources.wiki import WikiConnector


class _FakeWikiSearchResponse:
    status_code = 200
    def json(self):
        return {"query": {"search": [{"title": "司母戊鼎"}]}}


class _FakeWikiSummaryResponse:
    status_code = 200
    def json(self):
        return {"extract": "后母戊鼎是中国商代晚期青铜方鼎，1939年河南安阳出土。"}


def test_wiki_connector_exhibit():
    connector = WikiConnector()
    ctx = CollectContext()
    items = asyncio.run(connector.discover(ctx, exhibit_names=["司母戊鼎"]))
    assert len(items) == 1

    responses = [_FakeWikiSearchResponse(), _FakeWikiSummaryResponse()]
    with patch("app.collect.sources.wiki.httpx.get", side_effect=responses):
        raw = asyncio.run(connector.fetch(items[0], ctx))
        assert raw is not None
        fields = asyncio.run(connector.parse(raw, items[0], ctx))
        assert fields["name"] == "司母戊鼎"
        assert "商代" in fields["description"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_collect_sources.py::test_wiki_connector_exhibit -v`
Expected: FAIL — `ImportError`（app.collect.sources.wiki 不存在）

- [ ] **Step 3: 实现 WikiConnector**

新建 `backend/app/collect/sources/wiki.py`：

```python
"""维基百科采集 connector。

整合自 app/seed_from_wiki.py（展品摘要）与 app/fetch_museum_images.py（博物馆建筑图）。
纯规则解析，不接 LLM。
"""

import json
import urllib.parse

import httpx

from app.collect.base import CollectContext, SourceConnector

_HEADERS = {"User-Agent": "MuseumGuide/1.0 (educational project)"}


class WikiConnector(SourceConnector):
    """展品摘要维基采集。target_type=exhibit。"""

    source = "wiki"
    default_confidence = 0.6
    target_type = "exhibit"

    async def discover(self, ctx: CollectContext, exhibit_names: list[str] | None = None) -> list[dict]:
        names = exhibit_names or []
        return [{"name": n, "source_ref": f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(n)}"} for n in names]

    async def fetch(self, item: dict, ctx: CollectContext) -> str | None:
        """先搜索词条标题，再取摘要，合并成一个 JSON 文本返回。"""
        encoded = urllib.parse.quote(item["name"])
        search_url = (
            "https://zh.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={encoded}&format=json&srlimit=1"
        )
        try:
            sresp = httpx.get(search_url, headers=_HEADERS, timeout=10)
            results = sresp.json().get("query", {}).get("search", [])
            if not results:
                return None
            title = results[0]["title"]
            tenc = urllib.parse.quote(title)
            sum_url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{tenc}"
            mresp = httpx.get(sum_url, headers=_HEADERS, timeout=10)
            if mresp.status_code != 200:
                return None
            return json.dumps({"title": title, "data": mresp.json()}, ensure_ascii=False)
        except Exception:
            return None

    async def parse(self, raw: str, item: dict, ctx: CollectContext) -> dict | None:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return None
        extract = obj.get("data", {}).get("extract", "")
        if not extract:
            return None

        dynasty = None
        for d in ["商", "西周", "东周", "春秋", "战国", "秦", "汉", "唐", "宋", "元", "明", "清"]:
            if d in extract:
                dynasty = d
                break

        return {
            "name": item["name"],
            "category": None,
            "dynasty": dynasty,
            "description": extract,
            "source_ref": f"https://zh.wikipedia.org/wiki/{obj.get('title', item['name'])}",
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_collect_sources.py -v`
Expected: 三个测试 PASS（baike ×2 + wiki ×1）

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/collect/sources/wiki.py app/tests/test_collect_sources.py
git commit -m "feat(collect): WikiConnector 维基展品摘要采集"
```

---

### Task 5: 注册表 + CLI 入口

**Files:**
- Create: `backend/app/collect/registry.py`
- Create: `backend/app/collect/__main__.py`

让 `python -m app.collect --museum 1 --source baike` 能跑起来。

- [ ] **Step 1: 实现 registry.py**

新建 `backend/app/collect/registry.py`：

```python
"""source 名 -> connector 工厂的注册表。"""

from app.collect.base import SourceConnector
from app.collect.sources.baike import BaikeConnector
from app.collect.sources.wiki import WikiConnector

_REGISTRY: dict[str, type[SourceConnector]] = {
    "baike": BaikeConnector,
    "wiki": WikiConnector,
}


def get_connector(source: str, **kwargs) -> SourceConnector:
    cls = _REGISTRY.get(source)
    if cls is None:
        raise ValueError(f"未知 source: {source}（可选: {list(_REGISTRY)}）")
    return cls(**kwargs)


def available_sources() -> list[str]:
    return list(_REGISTRY)
```

- [ ] **Step 2: 实现 CLI 入口**

新建 `backend/app/collect/__main__.py`：

```python
"""采集 CLI。

用法:
  uv run python -m app.collect --museum 1 --source baike
  uv run python -m app.collect --museum 1 --source wiki

本阶段（阶段1）仅支持规则源（baike/wiki）。LLM 与官网源在后续阶段。
"""

import argparse
import asyncio

from sqlalchemy import select

from app.collect.base import CollectContext
from app.collect.pipeline import run_pipeline
from app.collect.registry import available_sources, get_connector
from app.db import SessionLocal
from app.models import Exhibit, Museum


def _load_exhibit_names(db, museum_id: int) -> list[str]:
    """取出该馆现有展品名，作为百科/维基 discover 的查询种子。"""
    rows = db.scalars(
        select(Exhibit.name).where(
            Exhibit.museum_id == museum_id,
            Exhibit.status.in_(["active", "moved"]),
        )
    ).all()
    return list(rows)


async def _run(museum_id: int, source: str):
    db = SessionLocal()
    try:
        museum = db.get(Museum, museum_id)
        if not museum:
            print(f"✗ museum_id={museum_id} 不存在")
            return
        connector = get_connector(source)
        names = _load_exhibit_names(db, museum_id)
        if not names:
            print(f"✗ {museum.name} 无展品名可采集")
            return

        # 百科/维基的 discover 需要展品名
        ctx = CollectContext()
        items = await connector.discover(ctx, exhibit_names=names)
        print(f"=== {museum.name} · source={source} · {len(items)} 条 ===")

        # 用一个轻量包装：构造一个 discover 已被预填的运行
        # 直接调用 pipeline（pipeline 会重新 discover，因此用闭包注入）
        from app.collect.base import CollectContext as _Ctx
        from app.collect.base import SourceConnector as _SC

        class _BoundConnector(_SC):
            source = connector.source
            default_confidence = connector.default_confidence
            target_type = connector.target_type

            async def discover(self, ctx):
                return items

            async def fetch(self, item, ctx):
                return await connector.fetch(item, ctx)

            async def parse(self, raw, item, ctx):
                return await connector.parse(raw, item, ctx)

        job = await run_pipeline(_BoundConnector(), museum_id, db, ctx)
        print(
            f"\n=== 完成 ===\n"
            f"  stage={job.stage}\n"
            f"  total/done/failed = {job.total}/{job.done}/{job.failed}\n"
            f"  job_id={job.id}"
        )
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="博物馆采集 CLI")
    p.add_argument("--museum", type=int, required=True, help="博物馆 id")
    p.add_argument("--source", type=str, required=True, choices=available_sources())
    args = p.parse_args()
    asyncio.run(_run(args.museum, args.source))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 手动冒烟（不连真实网络，验证参数校验路径）**

Run: `cd backend && uv run python -m app.collect --source badname --museum 1`
Expected: 报错退出，提示 `argument --source: invalid choice`（argparse 拦截未知 source）

Run: `cd backend && uv run python -m app.collect --source baike --museum 999999`
Expected: 输出 `✗ museum_id=999999 不存在`

- [ ] **Step 4: 提交**

```bash
cd backend
git add app/collect/registry.py app/collect/__main__.py
git commit -m "feat(collect): connector 注册表 + CLI 入口（baike/wiki）"
```

---

### Task 6: 阶段 1 收尾验证

- [ ] **Step 1: 全量测试**

Run: `cd backend && uv run pytest -q`
Expected: 全绿（阶段0 + 阶段1 新增测试）

- [ ] **Step 2: Lint**

Run: `cd backend && uv run ruff check app/`
Expected: 无错误

- [ ] **Step 3: 导入完整性**

Run: `cd backend && uv run python -c "from app.collect.registry import available_sources; print(available_sources())"`
Expected: 输出 `['baike', 'wiki']`

- [ ] **Step 4: （可选）真实采集小样本**

若环境可联网，跑一个极小验证（先给目标馆加 1-2 条展品名），确认能真实抓百科并入库：
Run: `cd backend && uv run python -m app.collect --museum 1 --source baike`
Expected: job 完成态 succeeded 或 partial，collect_jobs 有记录

至此阶段 1 完成。采集引擎骨架已就位，后续阶段只需新增 connector（阶段2 官网+发现源）和加 LLM 层（阶段3）。

# 采集系统阶段 3：LLM#2 数据整理层 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 pipeline 入库前增加通用 LLM 数据整理层（`LLMRefiner`），对所有来源的字段做补全/清洗/格式归一/描述改写，可按 `enable_llm_refine` 开关启用，整理后计算 `content_hash`。

**Architecture:** `LLMRefiner` 是 pipeline 的最后一道工序，与来源解耦。按批处理（按类别分批喂 LLM），允许改写描述。`run_pipeline` 增加 `enable_llm_refine` 参数，开启时在 parse 后、upsert 前调用 refiner。整理后的干净字段计算 sha256 hash 写入。

**Tech Stack:** Python 3.12, model_router (generate_structured), hashlib, pytest

**Spec:** `docs/superpowers/specs/2026-06-26-collection-system-design.md` §5.4 §5.5

**前置依赖:** 阶段 0-2（pipeline、connector、model_router.generate_structured）已完成

---

## 文件结构

- **新增** `backend/app/collect/refiner.py` —— `LLMRefiner`
- **修改** `backend/app/collect/pipeline.py` —— 加 `enable_llm_refine` 分支 + content_hash 计算
- **新增** `backend/app/tests/test_refiner.py`

---

### Task 1: 实现 LLMRefiner

**Files:**
- Create: `backend/app/collect/refiner.py`
- Create: `backend/app/tests/test_refiner.py`

`LLMRefiner.refine` 接收单条字段 dict，调 LLM 改写描述 + 补全空字段 + 朝代/类别归一化。

- [ ] **Step 1: 写失败测试（mock LLM）**

新建 `backend/app/tests/test_refiner.py`：

```python
import asyncio
from unittest.mock import AsyncMock, patch

from app.collect.refiner import LLMRefiner


def test_refine_cleans_description_and_fills_fields():
    refiner = LLMRefiner()
    raw_fields = {
        "name": "后母戊鼎",
        "category": None,
        "dynasty": "商朝",  # 非标准写法
        "description": "后母戊鼎。。。。。是商代晚期青铜方鼎，1939年出土于河南安阳。。",
    }

    fake_llm = AsyncMock()
    fake_llm.generate_structured.return_value = {
        "description": "后母戊鼎是商代晚期青铜方鼎，1939年出土于河南安阳。",
        "category": "青铜器",
        "dynasty": "商代",
    }

    with patch("app.collect.refiner.model_router", fake_llm):
        refined = asyncio.run(refiner.refine(raw_fields))

    assert "。。。。" not in refined["description"]  # 噪声已清
    assert refined["category"] == "青铜器"
    assert refined["dynasty"] == "商代"  # 归一化
    assert refined["name"] == "后母戊鼎"  # 名称不动


def test_refine_disabled_returns_original():
    """enable=False 时原样返回。"""
    refiner = LLMRefiner()
    raw = {"name": "x", "category": None, "dynasty": None, "description": "y"}
    out = asyncio.run(refiner.refine(raw, enable=False))
    assert out is raw


def test_refine_llm_failure_falls_back_gracefully():
    """LLM 调用失败时，返回原字段（不阻断流程）。"""
    refiner = LLMRefiner()
    raw = {"name": "x", "category": None, "dynasty": None, "description": "y"}

    fake_llm = AsyncMock()
    fake_llm.generate_structured.side_effect = Exception("LLM 挂了")

    with patch("app.collect.refiner.model_router", fake_llm):
        refined = asyncio.run(refiner.refine(raw))

    assert refined["name"] == "x"  # 兜底返回原值
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_refiner.py -v`
Expected: FAIL — `ImportError`（refiner 不存在）

- [ ] **Step 3: 实现 refiner.py**

新建 `backend/app/collect/refiner.py`：

```python
"""LLM#2 数据整理层：入库前对所有来源字段的通用整理工序。

与来源解耦。允许改写描述、补全空字段、朝代/类别格式归一化。
按任务/源开关（pipeline 的 enable_llm_refine）。LLM 失败时优雅兜底。
"""

from app.services.model_router import model_router

_SCHEMA = (
    '{"description":"精简后的简介(≤120字)","category":"归一化类别或null","dynasty":"归一化朝代或null"}'
)

# 朝代/类别归一化表（把各种写法归到标准值）
_DYNASTY_NORMALIZE = {
    "商朝": "商代", "商晚期": "商代晚期", "周朝": "周代",
    "汉朝": "汉代", "西汉": "西汉", "东汉": "东汉",
    "唐朝": "唐代", "宋朝": "宋代", "元朝": "元代",
    "明朝": "明代", "清朝": "清代", "民国": "民国", "现代": "现代",
}


class LLMRefiner:
    async def refine(self, fields: dict, enable: bool = True) -> dict:
        """整理单条字段。enable=False 直接返回原 dict（不拷贝）。

        LLM 失败时返回原字段，不阻断 pipeline。
        """
        if not enable:
            return fields

        desc = fields.get("description") or ""
        if len(desc) < 5:
            # 内容太少不值得调 LLM
            return fields

        prompt = (
            "你是博物馆文物数据清洗专家。整理下面这条展品信息：\n"
            "1. 精简描述（去噪声标点、重复字句，≤120字，保留关键事实）\n"
            "2. 归一化类别（如'青铜器'）和朝代（如'商代'）\n"
            "3. 不确定的留 null\n\n"
            f"原始信息：\n{fields}"
        )
        try:
            data = await model_router.generate_structured(prompt, _SCHEMA)
        except Exception:
            return fields

        refined = dict(fields)
        if data.get("description"):
            refined["description"] = data["description"]
        if data.get("category"):
            refined["category"] = data["category"]
        elif fields.get("category"):
            refined["category"] = _DYNASTY_NORMALIZE.get(fields["category"], fields["category"])
        if data.get("dynasty"):
            refined["dynasty"] = data["dynasty"]
        elif fields.get("dynasty"):
            refined["dynasty"] = _DYNASTY_NORMALIZE.get(fields["dynasty"], fields["dynasty"])

        return refined
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_refiner.py -v`
Expected: 三个测试 PASS

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/collect/refiner.py app/tests/test_refiner.py
git commit -m "feat(collect): LLMRefiner LLM#2 入库前通用数据整理层"
```

---

### Task 2: pipeline 接入 refiner + content_hash 计算

**Files:**
- Modify: `backend/app/collect/pipeline.py`

`run_pipeline` 增加 `enable_llm_refine` 参数；parse 后按开关调用 refiner；整理后的字段算 hash 写入 exhibit/item。

- [ ] **Step 1: 写失败测试**

追加到 `backend/app/tests/test_collect_pipeline.py`：

```python
def test_run_pipeline_with_llm_refine(test_db, monkeypatch):
    """enable_llm_refine=True 时，refiner 被调用且 content_hash 被写入。"""
    from unittest.mock import AsyncMock
    from app.collect.base import CollectContext, SourceConnector
    from app.collect.refiner import LLMRefiner

    class _FakeConnector(SourceConnector):
        source = "fake"
        default_confidence = 0.5
        target_type = "exhibit"
        async def discover(self, ctx):
            return [{"name": "测试鼎", "source_ref": "http://x/1"}]
        async def fetch(self, item, ctx):
            return "<html>x</html>"
        async def parse(self, raw, item, ctx):
            return {"name": item["name"], "category": None, "dynasty": "商朝",
                    "description": "测试描述文本，长度足够触发 refine。"}

    # mock refiner，使其确定性地改写
    async def _fake_refine(fields, enable=True):
        fields["dynasty"] = "商代"
        fields["content_hash_marker"] = True
        return fields
    monkeypatch.setattr(LLMRefiner, "refine", _fake_refine)

    m = _setup_museum(test_db)
    ctx = CollectContext()
    job = asyncio.run(run_pipeline(
        _FakeConnector(), m.id, test_db, ctx, enable_llm_refine=True))

    from app.models import Exhibit
    e = test_db.get(Exhibit, test_db.scalar(select(CollectItem).where(
        CollectItem.job_id == job.id)).target_id)
    assert e.content_hash is not None  # 整理后已算 hash
    assert e.dynasty == "商代"  # refiner 生效


def test_run_pipeline_without_llm_refine_skips_refiner(test_db, monkeypatch):
    """enable_llm_refine=False 时 refiner 不被调用。"""
    from app.collect.base import CollectContext, SourceConnector
    from app.collect.refiner import LLMRefiner

    called = {"n": 0}
    async def _spy_refine(fields, enable=True):
        called["n"] += 1
        return fields
    monkeypatch.setattr(LLMRefiner, "refine", _spy_refine)

    class _FakeConnector(SourceConnector):
        source = "fake2"
        default_confidence = 0.5
        target_type = "exhibit"
        async def discover(self, ctx):
            return [{"name": "测试尊", "source_ref": "http://x/2"}]
        async def fetch(self, item, ctx):
            return "<html>x</html>"
        async def parse(self, raw, item, ctx):
            return {"name": item["name"], "category": None, "dynasty": None,
                    "description": "描述"}

    m = _setup_museum(test_db)
    ctx = CollectContext()
    asyncio.run(run_pipeline(_FakeConnector(), m.id, test_db, ctx, enable_llm_refine=False))
    assert called["n"] == 0  # refiner 未被调用
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_collect_pipeline.py -k refine -v`
Expected: FAIL — `run_pipeline` 无 enable_llm_refine 参数

- [ ] **Step 3: 修改 pipeline.py**

在 `backend/app/collect/pipeline.py` 顶部 import 区加：

```python
import hashlib

from app.collect.refiner import LLMRefiner
```

新增 hash 计算辅助函数（放在 `_upsert_museum` 之后）：

```python
def _compute_hash(fields: dict) -> str:
    """对整理后的关键字段算 sha256，作为增量比对指纹。"""
    payload = {
        "name": fields.get("name"),
        "category": fields.get("category"),
        "dynasty": fields.get("dynasty"),
        "description": fields.get("description"),
    }
    import json
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
```

修改 `run_pipeline` 签名，增加参数：

```python
async def run_pipeline(
    connector: SourceConnector,
    museum_id: int | None,
    db: Session,
    ctx: CollectContext,
    enable_llm_refine: bool = False,
) -> CollectJob:
```

在 run_pipeline 内部，parse 成功之后、upsert 之前，把：
```python
            fields.setdefault("source_ref", raw_item.get("source_ref"))
            item.stage = "parsed"

            # 4. upsert（按 target_type 分发）
```
改为：
```python
            fields.setdefault("source_ref", raw_item.get("source_ref"))
            item.stage = "parsed"

            # 3.5 LLM#2 数据整理（可选开关）
            if enable_llm_refine:
                refiner = LLMRefiner()
                fields = await refiner.refine(fields, enable=True)

            # 计算 content_hash（整理后的干净数据）
            fields["content_hash"] = _compute_hash(fields)

            # 4. upsert（按 target_type 分发）
```

并在 `_upsert_exhibit` 中把 hash 写入（修改 exhibit 的赋值处，existing 和新建两处都加）：
- existing 分支加：`existing.content_hash = fields.get("content_hash")`
- 新建 Exhibit(...) 加：`content_hash=fields.get("content_hash"),`

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_collect_pipeline.py -v`
Expected: 全部测试 PASS（含原有 3 个 + 新增 2 个 refine 测试）

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/collect/pipeline.py app/tests/test_collect_pipeline.py
git commit -m "feat(collect): pipeline 接入 LLM#2 refiner + content_hash 计算"
```

---

### Task 3: CLI 增加 --refine 开关

**Files:**
- Modify: `backend/app/collect/__main__.py`

- [ ] **Step 1: 修改 CLI**

在 `backend/app/collect/__main__.py` 的 argparse 与 `_run` 中接入：

argparse 加（`--source` 之后）：
```python
    p.add_argument("--refine", action="store_true", help="启用 LLM 数据整理层（LLM#2）")
```

`_run` 签名改为 `async def _run(museum_id: int, source: str, refine: bool):`，run_pipeline 调用处改为：
```python
        job = await run_pipeline(_BoundConnector(), museum_id, db, ctx, enable_llm_refine=refine)
```

`main()` 中调用改为 `asyncio.run(_run(args.museum, args.source, args.refine))`，输出加一行 refine 状态。

- [ ] **Step 2: 冒烟**

Run: `cd backend && uv run python -m app.collect --museum 1 --source baike`
Expected: 正常运行（refine 默认关）

Run: `cd backend && uv run python -m app.collect --museum 1 --source baike --refine`
Expected: 正常运行（refine 开，输出含 refine 状态）

- [ ] **Step 3: 提交**

```bash
cd backend
git add app/collect/__main__.py
git commit -m "feat(collect): CLI 增加 --refine 开关"
```

---

### Task 4: 阶段 3 收尾验证

- [ ] **Step 1: 全量测试**

Run: `cd backend && uv run pytest -q`
Expected: 全绿

- [ ] **Step 2: Lint**

Run: `cd backend && uv run ruff check app/`
Expected: 无错误

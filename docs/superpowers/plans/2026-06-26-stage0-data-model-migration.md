# 采集系统阶段 0：数据模型与迁移 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为采集系统新增 `collect_jobs` / `collect_items` 两张表，并给 Museum/Exhibit/ExhibitImage/Narration 补 `source_ref`/`content_hash`/`fetched_at` 三个增量预留字段，附 alembic 迁移。

**Architecture:** 在现有 SQLAlchemy 2.0 `Base` 基础上，新增两个采集追踪模型；对四个业务模型追加 nullable 列（老数据填 NULL，不破坏现有功能）。迁移走项目既有的 alembic 流程，与 initial schema (`8dbcbf70f366`) 链式衔接。

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (Mapped/mapped_column), alembic, pytest, SQLite(测试)/PostgreSQL(生产)

**Spec:** `docs/superpowers/specs/2026-06-26-collection-system-design.md` §4

---

## 文件结构

- **修改** `backend/app/models.py` —— 新增 `CollectJob`、`CollectItem` 模型；Museum/Exhibit/ExhibitImage/Narration 各补 3 字段
- **新增** `backend/alembic/versions/<rev>_collect_tracking.py` —— 迁移脚本（建 2 表 + 4 表加列）
- **修改** `backend/app/tests/test_models.py` —— 新增采集模型的冒烟测试 + 新字段写入测试

---

### Task 1: 给四个业务模型补增量预留字段

**Files:**
- Modify: `backend/app/models.py`（Museum / Exhibit / ExhibitImage / Narration）

为四个模型追加 `source_ref` / `content_hash` / `fetched_at`。全部 nullable，不破坏现有逻辑。

- [ ] **Step 1: 写失败测试（新字段可写入）**

追加到 `backend/app/tests/test_models.py`：

```python
def test_exhibit_source_ref_fields(test_db):
    """采集系统预留字段：source_ref / content_hash / fetched_at 可写入可读取。"""
    from datetime import datetime

    from app.models import Exhibit, Museum

    m = Museum(name="x", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    e = Exhibit(
        museum_id=m.id, name="e", status="active", source="official",
        source_ref="https://example.com/exhibit/1",
        content_hash="sha256:abc",
        fetched_at=datetime(2026, 6, 26, 12, 0, 0),
    )
    test_db.add(e)
    test_db.flush()
    assert e.source_ref == "https://example.com/exhibit/1"
    assert e.content_hash == "sha256:abc"
    assert e.fetched_at.year == 2026
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_models.py::test_exhibit_source_ref_fields -v`
Expected: FAIL — `AttributeError`（Exhibit 无 source_ref）或建表时缺列

- [ ] **Step 3: 修改 models.py，给四个模型补字段**

在 `backend/app/models.py` 顶部 import 补上 `DateTime`：

```python
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
```

**Museum** 模型：在 `updated_at` 行之后、`floors` relationship 之前，插入：

```python
    # 采集系统预留：来源、内容指纹、采集时间（增量比对用，老数据为 NULL）
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

**Exhibit** 模型：同样在 `updated_at` 之后、`museum` relationship 之前，插入上述 3 行。

**ExhibitImage** 模型：在 `is_primary` 行注释之后、`exhibit` relationship 之前，插入上述 3 行。

**Narration** 模型：在 `audio_url` 之后、`created_at` 之前（或任意列定义区），插入上述 3 行。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_models.py -v`
Expected: PASS（含新增测试 + 原有 4 个全绿）

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/models.py app/tests/test_models.py
git commit -m "feat(models): 采集系统预留字段 source_ref/content_hash/fetched_at"
```

---

### Task 2: 新增 CollectJob 模型

**Files:**
- Modify: `backend/app/models.py`（新增 `CollectJob` 类）

`collect_jobs` 是采集进度页的核心数据源。

- [ ] **Step 1: 写失败测试**

追加到 `backend/app/tests/test_models.py`：

```python
def test_create_collect_job(test_db):
    """采集任务可实例化并 flush，默认值正确。"""
    from datetime import datetime

    from app.models import CollectJob, Museum

    m = Museum(name="x", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()

    job = CollectJob(
        museum_id=m.id,
        source="baike",
        stage="running",
        total=100,
        done=0,
        failed=0,
        log=[],
    )
    test_db.add(job)
    test_db.flush()

    assert job.id is not None
    assert job.stage == "running"
    assert job.started_at is not None
    assert job.finished_at is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_models.py::test_create_collect_job -v`
Expected: FAIL — `ImportError`（CollectJob 未定义）

- [ ] **Step 3: 在 models.py 末尾（ChatSession 类之后）新增 CollectJob**

```python
class CollectJob(Base):
    """采集任务：一次「某博物馆 + 某来源」的采集运行。进度页核心数据源。"""

    __tablename__ = "collect_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    museum_id: Mapped[int | None] = mapped_column(ForeignKey("museums.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(30))  # wiki_list / wiki / baike / official / images
    stage: Mapped[str] = mapped_column(String(30), default="running")  # running/succeeded/failed/partial/canceled
    total: Mapped[int] = mapped_column(Integer, default=0)
    done: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[list] = mapped_column(JSON, default=list)  # 最近 N 条错误/跳过
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    museum: Mapped["Museum | None"] = relationship()
    items: Mapped[list["CollectItem"]] = relationship(back_populates="job")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_models.py::test_create_collect_job -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/models.py app/tests/test_models.py
git commit -m "feat(models): 新增 CollectJob 采集任务表"
```

---

### Task 3: 新增 CollectItem 模型

**Files:**
- Modify: `backend/app/models.py`（新增 `CollectItem` 类，含与 CollectJob/Museum 的关系）

`collect_items` 记录逐条采集明细（哪条采成功/失败/原因）。

- [ ] **Step 1: 写失败测试**

追加到 `backend/app/tests/test_models.py`：

```python
def test_create_collect_item(test_db):
    """采集明细可写入，关联 job，默认 stage=pending。"""
    from app.models import CollectItem, CollectJob, Museum

    m = Museum(name="x", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    job = CollectJob(museum_id=m.id, source="baike", stage="running", total=1, done=0, failed=0, log=[])
    test_db.add(job)
    test_db.flush()

    item = CollectItem(
        job_id=job.id,
        source_ref="https://baike.baidu.com/item/司母戊鼎",
        name="司母戊鼎",
        target_type="exhibit",
    )
    test_db.add(item)
    test_db.flush()

    assert item.id is not None
    assert item.stage == "pending"
    assert item.job.source == "baike"
    assert item.target_id is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest app/tests/test_models.py::test_create_collect_item -v`
Expected: FAIL — `ImportError`（CollectItem 未定义）

- [ ] **Step 3: 在 models.py 的 CollectJob 类之后，新增 CollectItem**

```python
class CollectItem(Base):
    """采集明细：任务内逐条采集对象的状态记录。"""

    __tablename__ = "collect_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("collect_jobs.id"))
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 来源页 URL
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stage: Mapped[str] = mapped_column(String(30), default="pending")  # pending/fetched/parsed/saved/skipped/failed
    target_type: Mapped[str | None] = mapped_column(String(30), nullable=True)  # museum/exhibit/image
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    job: Mapped["CollectJob"] = relationship(back_populates="items")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest app/tests/test_models.py -v`
Expected: PASS（全部模型测试）

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/models.py app/tests/test_models.py
git commit -m "feat(models): 新增 CollectItem 采集明细表"
```

---

### Task 4: 编写 alembic 迁移脚本

**Files:**
- Create: `backend/alembic/versions/<rev>_collect_tracking.py`

把模型变更落到数据库（建 2 表 + 4 表加 3 列）。链式衔接 `8dbcbf70f366`。

- [ ] **Step 1: 用 alembic 自动生成迁移草稿**

Run: `cd backend && uv run alembic revision --autogenerate -m "collect tracking tables" -m "collect tracking"`
Expected: 在 `alembic/versions/` 下生成一个新文件 `<revision_id>_collect_tracking.py`，内容含 create_table(collect_jobs/collect_items) 和 add_column 等。

- [ ] **Step 2: 校对自动生成的迁移文件**

打开生成的文件，确认 `upgrade()` 包含：
- `op.create_table('collect_jobs', ...)` 含 id/museum_id/source/stage/total/done/failed/log/started_at/finished_at/error，及对 museums 的外键
- `op.create_table('collect_items', ...)` 含 id/job_id/source_ref/name/stage/target_type/target_id/content_hash/error/updated_at，及对 collect_jobs 的外键
- `op.add_column('museums', ...)` / `op.add_column('exhibits', ...)` / `op.add_column('exhibit_images', ...)` / `op.add_column('narrations', ...)` 各加 source_ref/content_hash/fetched_at

确认 `downgrade()` 完整对应（drop_column / drop_table，顺序与 upgrade 相反）。

- [ ] **Step 3: 修正文件头 revision 链**

确认文件顶部：
```python
revision: str = '<新生成的id>'
down_revision: Union[str, Sequence[str], None] = '8dbcbf70f366'
```
（autogenerate 应已正确填充 down_revision，核对即可）

- [ ] **Step 4: 在测试 DB（SQLite）上验证 upgrade/downgrade 可逆**

Run:
```bash
cd backend && uv run python -c "
from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command
cfg = Config('alembic.ini')
import tempfile, os
db = 'sqlite:///' + os.path.join(tempfile.gettempdir(), 'collect_test.db')
import app.config  # 确保 settings 可加载
"
```

更稳妥的验证方式（直接用 pytest 基建）——确认现有测试套件在内存库自动建表仍通过：
Run: `cd backend && uv run pytest -q`
Expected: 全绿（现有 35 测试 + 阶段0新增测试，共约 38）

- [ ] **Step 5: 提交**

```bash
cd backend
git add alembic/versions/
git commit -m "feat(db): alembic 迁移 - collect_jobs/collect_items 表 + 增量预留字段"
```

---

### Task 5: 阶段 0 收尾验证

- [ ] **Step 1: 全量测试**

Run: `cd backend && uv run pytest -q`
Expected: 全绿

- [ ] **Step 2: Lint**

Run: `cd backend && uv run ruff check app/`
Expected: 无错误

- [ ] **Step 3: 确认导出符号（防下游 import 缺失）**

确认 `app/models.py` 中 `CollectJob`、`CollectItem` 可被 import：
Run: `cd backend && uv run python -c "from app.models import CollectJob, CollectItem; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: 提交收尾（若有无谓改动）**

无新改动则跳过。至此阶段 0 完成，collect 引擎（阶段 1）可基于这两个模型构建。

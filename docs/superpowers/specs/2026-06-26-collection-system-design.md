# 采集系统设计文档

- **日期**：2026-06-26
- **状态**：已确认设计，待用户复核
- **范围**：博物馆导览项目的数据采集系统（v1）

## 1. 背景与目标

### 1.1 现状
项目现有数据采集以「分散的一次性脚本」形式存在，每个来源一个独立脚本：

- `crawl_guobo.py` —— 抓国博官网馆藏精品
- `seed_from_baike.py` —— 抓百度百科补讲解
- `seed_from_wiki.py` —— 抓维基
- `fetch_museum_images.py` —— 抓博物馆建筑图
- `seed_guobo_full.py` / `seed_batch.py` —— 入库 + 生成讲解

每个脚本都各自实现 HTTP、解析、去重、入库、限速、礼貌延迟，逻辑高度重复、不可复用；缺少统一的源抽象、断点续传（除 `seed_batch`）、去重 key 和字段映射；无法对新博物馆快速复用。

### 1.2 目标
构建一个可观测的采集系统：
1. **通用化采集**：把"加一个新来源"从"重写脚本"降为"写一个小 connector + 配置"。
2. **可观测**：通过 Web 管理后台查看采集进度（任务级 + 逐条明细）。
3. **可触发**：Web 页面按钮触发采集任务。
4. **覆盖广**：支持自动发现新博物馆（名录源），并扩充展品采集。
5. **质量分层**：默认上线，但按来源区分置信度，可追溯、可批量下线。

### 1.3 第一版关键决策（已与用户确认）
| 决策点 | 选择 |
|--------|------|
| 范围 | A —— 抓取 + 清洗 + 结构化入库；讲解文案（narration blocks）由后续独立内容加工环节处理 |
| 博物馆元数据 | 第一版覆盖博物馆本身（名称/坐标/建筑图）的采集 |
| 运行模式 | 丙 —— v1 批量导入，数据模型预留增量字段（source_ref / content_hash / fetched_at） |
| 审核 | 丙 —— 默认上线（active），按 source/confidence 区分，可批量下线，不做审核队列 |
| 博物馆发现 | B —— 从博物馆列表源（维基名录）自动发现 |
| 前端位置 | Web 管理后台（独立轻量 Web 页面） |
| 触发方式 | Web 按钮触发（后端异步执行） |
| 触发粒度 | 按源单独触发（一家馆有多个按钮：采元数据/采百科/采官网等） |
| LLM#1 用法 | 官网 per-site connector 的 parse 阶段（页面架构不同时提取字段） |
| LLM#2 用法 | 新增，入库前的通用数据整理层，所有来源过此层，允许改写描述 |
| LLM#2 成本控制 | P —— 按需开关（enable_llm_refine）+ 批处理 |
| 数据整理改写 | 允许改写描述文本 |
| Web 技术 | 原生 HTML + JS，零构建，不引框架 |
| 进度推送 | SSE（Server-Sent Events） |
| 去重 key | (museum_id, name) |

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│              Web 管理后台 (浏览器)                        │
│   博物馆列表 │ 启动采集按钮 │ 实时进度条 │ 历史任务记录      │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────┐
│              FastAPI (现有 backend)                       │
│   /admin/collect/start   POST  启动采集                   │
│   /admin/collect/jobs    GET   任务列表                    │
│   /admin/collect/jobs/{id}     GET   任务详情+明细          │
│   /admin/collect/jobs/{id}/stream  GET  SSE 实时进度       │
│   /admin/collect/jobs/{id}/cancel POST 取消任务            │
│   /admin/museums         GET   博物馆列表                  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              采集引擎 (collect 包)                        │
│                                                          │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐    │
│   │ 发现源      │   │ 内容源      │   │ 官网源      │    │
│   │ wiki_list   │   │ wiki/baike  │   │ per-site    │    │
│   │             │   │ (规则解析)  │   │ (LLM#1提取) │    │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘    │
│          └────────┬────────┴─────────────────┘           │
│                   ▼                                       │
│          ┌────────────────┐   ┌──────────────────┐       │
│          │  统一 Pipeline │──▶│ LLM#2 数据整理层  │       │
│          │  限速/重试/去重 │   │ (入库前,可开关)   │       │
│          └────────────────┘   └────────┬─────────┘       │
│                   │                  ▼                    │
│                   │          ┌──────────────────┐         │
│                   ▼          │     入库 upsert   │         │
│          data/raw/*.json     │   (幂等去重)      │         │
│                                 └──────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

**关键设计点：**

1. **采集是异步后台任务**——Web 点"启动"后，后端开后台协程跑采集，立即返回 `task_id`，前端用此 id 通过 SSE 看进度。长任务不阻塞 HTTP。
2. **三层职责清晰**：Web（展示+触发）／ API（编排+状态）／ collect 引擎（抓+解析+入库）。collect 引擎不依赖 Web，CLI 也能调。
3. **LLM 两处用法**：
   - **LLM #1**：官网 per-site connector 的 parse 阶段。链接发现用规则（正则/选择器），LLM 负责把详情页正文提取成标准字段。
   - **LLM #2**：入库前通用数据整理层，所有来源过此层，做字段补全/描述清洗/格式归一/空字段推断。允许改写描述。
4. **任务状态持久化到数据库**——刷新页面/重启后端后进度还在。
5. **per-site 官网 connector**：每家官网结构不同，单独写 connector 文件，但共享框架的 pipeline（限速、重试、落盘、入库、进度、去重）。页面架构差异由各 connector 的 parse 处理，产出半结构化数据。

## 3. 采集源清单

第一版覆盖 5 类来源，每类对应一个 SourceConnector：

| # | 来源 | 采什么 | 角色 | 现有代码 | 置信度 |
|---|------|--------|------|----------|--------|
| 1 | 博物馆名录源（维基"中国博物馆列表"分类页） | 博物馆名称、所在地 | 发现：确定采哪些馆 | 无（新写） | 0.6 |
| 2 | 维基百科（zh wiki REST + pageimages） | 博物馆坐标、简介、建筑图 | 博物馆元数据补全 | `fetch_museum_images.py`、`seed_from_wiki.py` | 0.6 |
| 3 | 百度百科 | 展品名称、朝代、类别、简介原文 | 展品内容主力（通用） | `seed_from_baike.py` | 0.5 |
| 4 | 博物馆官网（per-site，如国博 chnmuseum.cn） | 馆藏精品名录、官方展品描述 | 展品内容（权威） | `crawl_guobo.py` | 0.9 |
| 5 | 图片源（维基 pageimages / 百科配图） | 展品图、博物馆建筑图 | 展品/博物馆图片 | `fetch_museum_images.py` | 0.6 |

**说明：**
- 源 1 是"发现源"，只产出博物馆清单；源 2-5 是"内容源"。
- 源 3（百科）通用、覆盖广，是任意博物馆的兜底内容源。
- 源 4（官网）权威，但每家页面架构不同，需逐家写 per-site connector。v1 先做国博作为模板，证明架构可行；其他馆按需扩展。
- 展品图和建筑图复用维基/百科图片 API（免费、无需配额）。

**质量分层（source / confidence）：**
- 官网 → `source="official"`, `confidence=0.9`
- 百科 → `source="baike"`, `confidence=0.5`
- 维基 → `source="wiki"`, `confidence=0.6`

## 4. 数据模型

### 4.1 新增表

**`collect_jobs`（采集任务）**——进度页核心：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 主键 |
| museum_id | FK museums (nullable) | 发现源任务不绑定单馆 |
| source | str | wiki_list / wiki / baike / official / images |
| stage | str | running / succeeded / failed / partial / canceled |
| total | int | 预计抓取数（发现后填充） |
| done | int | 已完成数 |
| failed | int | 失败数 |
| log | JSON | 运行日志（最近 N 条错误/跳过） |
| started_at | datetime | 开始时间 |
| finished_at | datetime | 结束时间 |
| error | str | 失败总结 |

进度页读这张表：done/total 为进度条，stage 为状态色，log 为详情展开。

**`collect_items`（采集明细）**——支撑逐条状态：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 主键 |
| job_id | FK collect_jobs | 所属任务 |
| source_ref | str | 来源页 URL（去重 key，增量比对） |
| name | str | 采集对象名 |
| stage | str | pending / fetched / parsed / saved / skipped / failed |
| target_type | str | museum / exhibit / image |
| target_id | int (nullable) | 入库后的 id |
| content_hash | str | 原始内容 hash（预留增量） |
| error | str | 失败原因 |
| updated_at | datetime | — |

发现源产出的候选博物馆清单复用此表（target_type=museum），不单独建表。

### 4.2 现有表补字段（预留增量，呼应决策"丙"）

Museum / Exhibit / ExhibitImage / Narration 各加：
- `source_ref` —— 来源 URL，去重和增量比对的核心 key
- `content_hash` —— 内容指纹（v1 可空，LLM#2 整理后计算）
- `fetched_at` —— 采集时间

Exhibit 已有 source/confidence/status，复用，不改。

### 4.3 迁移方式
用现有 alembic 加一个 migration（项目已有 `alembic/versions/`）。老数据新列填 NULL，不影响。

## 5. 采集引擎（collect 包）

### 5.1 SourceConnector 抽象基类

```python
class SourceConnector:
    source: str                          # "baike" / "wiki" / "official" / "wiki_list"
    default_confidence: float            # 该源默认置信度

    async def discover(self, ctx) -> list[dict]:
        """发现阶段：返回原始待采条目（含 source_ref / name / 原始 URL）。
        - 百科类：用展品名列表搜百科
        - 官网类：抓目录页拿详情页链接
        返回的每条落 collect_items + data/raw。"""

    async def fetch(self, item, ctx) -> str:
        """抓取阶段：拿一个条目的原始内容（HTML / JSON 文本）。
        内置限速 + 重试（ctx 统一管理）。"""

    async def parse(self, raw, item, ctx) -> dict:
        """解析阶段：raw → 标准字段 {name, dynasty, category, description, images...}。
        - 结构化源(百科/维基)直接抽
        - 官网等自由 HTML 交给 LLM#1 提取器"""
```

三个阶段分开：parse 可对已落盘的 raw 文件反复重跑（含调 LLM），不用重新抓站。

### 5.2 各 Connector 的三阶段

| Connector | discover | fetch | parse |
|-----------|----------|-------|-------|
| WikiListConnector（发现源） | 抓维基名录分类页，正则提馆名+链接 | — | — |
| WikiConnector | 用馆名查 wiki | wiki REST API | 直接抽 JSON |
| BaikeConnector | 用展品名搜百科 | 百科 openapi | 直接抽 JSON |
| OfficialXxxConnector（per-site） | 抓官网目录页，正则提展品名+详情链接 | 抓详情页 HTML | **LLM#1 提取** |

### 5.3 LLM 提取器（LLM#1，服务官网 connector）

```python
class LLMExtractor:
    """从任意博物馆官网详情页 HTML 提取结构化展品字段。"""

    async def extract_exhibit(self, html, url, museum_name) -> dict:
        # 1. 预处理：去标签噪声，截取正文（控 token 成本）
        # 2. 调 model_router（复用现有 narration 通道），prompt 固定输出
        #    JSON schema：{name, dynasty, category, description}
        # 3. 校验 + 兜底：LLM 缺字段时用规则补（如从名称推断类别）
```

- 复用现有 `model_router`，不另开 LLM 通道。
- Prompt 固定输出 JSON，加校验，解析失败重试 N 次。
- 成本控制：只对详情页调 LLM；预处理砍 nav/script/footer 噪声。

### 5.4 LLM 数据整理层（LLM#2，入库前通用）

```python
class LLMRefiner:
    """所有来源入库前的通用数据整理工序。"""

    async def refine(self, items: list[dict], enable=True) -> list[dict]:
        # 字段补全、描述清洗去噪、格式归一（朝代/类别）、空字段推断、允许改写描述
        # 按 enable 开关（P 方案）+ 批处理（按类目或名称批次）
        # 整理后数据计算 content_hash
```

- 与来源解耦，pipeline 最后一道工序。
- 按任务/源开关（start 接口的 enable_llm_refine）。
- 批处理：按展品类目或名称批次喂 LLM，非纯逐条。

### 5.5 统一 Pipeline 编排

一个 `run_pipeline(connector, museum, job)` 串起三阶段，所有 connector 共享：

```
discover → 逐条:
            ├─ collect_items 记 pending
            ├─ fetch(限速+重试) → 落 data/raw/<source>/<id>.html
            ├─ parse(规则 or LLM#1) → 半结构化字段
            ├─ [若 enable_llm_refine] LLMRefiner → 干净字段 + content_hash
            ├─ upsert(去重: museum_id + name)
            └─ collect_items 记 saved/failed + job.done++ + SSE 推进度
          → job.stage = succeeded/partial/failed
```

去重 key：`(museum_id, name)`（同一馆同名展品视为同一条，更新而非新增）。

## 6. API 设计

```
POST /admin/collect/start        启动一个采集任务
    body: { museum_id, source, enable_llm_refine? }
    resp: { job_id }
    行为: 后端起后台协程异步跑 pipeline，立即返回 job_id

GET  /admin/collect/jobs         任务列表（分页，最近在前）
    resp: [{ id, museum_name, source, stage, done, total, started_at, finished_at }]

GET  /admin/collect/jobs/{id}    单任务详情 + 明细
    resp: { job, items: [{ name, stage, target_type, target_id, error }] }

GET  /admin/collect/jobs/{id}/stream   SSE 实时进度流
    行为: 服务端推送 {done, total, stage, last_log}，前端订阅

POST /admin/collect/jobs/{id}/cancel   取消任务
    行为: 通过协程取消信号，pipeline 每条 item 前检查取消标志

GET  /admin/museums              博物馆列表（管理用，带展品数/采集状态）
```

- **SSE 推进度**——浏览器原生支持，单向上行推送正合适，不用轮询。pipeline 每完成一条就推一次。
- **enable_llm_refine 开关**挂 start 接口，对应 P 方案。
- **鉴权**：`/admin/*` 加简单 token 校验（环境变量配），v1 不做完整账号体系，但不裸奔。

## 7. Web 管理后台

单页应用，FastAPI 托管静态资源，**原生 HTML + JS（不引框架）**，零构建：

```
┌──────────────────────────────────────────────────────┐
│  博物馆导览 · 采集后台                       [刷新]     │
├──────────────┬───────────────────────────────────────┤
│ 博物馆列表    │  右侧：采集面板                         │
│              │                                       │
│ ▸ 中国国家博物馆│  当前任务                              │
│   展品 210   │  ┌─────────────────────────────────┐  │
│ ▸ 故宫博物院  │  │ 采百科展品 · 国博                 │  │
│   展品 48    │  │ ████████████░░░░░░ 156/210      │  │
│ ▸ 上海博物馆  │  │ running · 2 失败         [取消]  │  │
│   展品 0     │  └─────────────────────────────────┘  │
│              │                                       │
│ [+ 发现新馆]  │  启动采集（选中：中国国家博物馆）        │
│              │  ○ 维基补元数据  (wiki)                │
│              │  ○ 百科展品      (baike)               │
│              │  ○ 官网展品      (official)            │
│              │  □ 启用 LLM 数据整理                    │
│              │                    [开始采集]          │
│              │                                       │
│              │  历史任务                              │
│              │  ✓ baike · 国博 · 210件 · 12:30        │
│              │  ⚠ official · 国博 · 部分 · 11:02      │
└──────────────┴───────────────────────────────────────┘
┌ 详情点开：collect_items 逐条状态表（name / stage / 原因）┐
```

**交互流程：**
1. 左侧选馆 → 右侧"启动采集"面板亮起
2. 勾选来源 + 是否开 LLM 整理 → 点"开始采集"
3. 调 /start 拿 job_id → 建 SSE 连接 /stream → 进度条实时涨
4. 完成后进度条变绿，可点开看逐条明细，失败条目标红

## 8. 实施分阶段

每个阶段结束都是"能跑、能验证"的状态，不依赖下一阶段。

### 阶段 0：数据模型与迁移（地基）
- 新增 collect_jobs / collect_items 表
- Museum/Exhibit/ExhibitImage/Narration 补 source_ref / content_hash / fetched_at
- 写 alembic migration，老数据填 NULL
- **验证**：alembic upgrade 成功；pytest 全绿（现有 35 测试不回归）

### 阶段 1：采集引擎骨架 + 规则源接入
- 建 collect/ 包：SourceConnector 基类、统一 pipeline（限速/重试/落盘/去重/upsert）、run_pipeline
- 改造现有脚本为 connector：BaikeConnector、WikiConnector
- LLM 先不接
- **验证**：CLI 能跑 `python -m app.collect --museum 1 --source baike`，数据入库、去重正确、collect_jobs 有记录

### 阶段 2：发现源 + 官网 per-site connector
- WikiListConnector（维基博物馆名录，自动发现新馆）
- OfficialGuoboConnector（迁 crawl_guobo.py，含 LLM#1 提取）
- **验证**：能从名录发现博物馆并入库；国博官网能采集，LLM 提取字段非空

### 阶段 3：LLM#2 数据整理层
- LLMRefiner（入库前通用整理，允许改写）
- pipeline 加 enable_llm_refine 开关
- **验证**：开关开/关各跑一次，对比整理前后字段质量；content_hash 基于整理后数据计算

### 阶段 4：API + Web 后台
- 采集 API（start/jobs/detail/SSE stream/cancel）+ admin token 鉴权
- Web 单页（原生 HTML+JS）：博物馆列表、启动采集、SSE 进度条、历史任务、逐条明细
- **验证**：浏览器点按钮启动 → 进度条实时涨 → 完成看明细；刷新页面进度不丢（读库）

### 阶段间依赖
```
0 ─▶ 1 ─▶ 2 ─▶ 3 ─▶ 4
LLM#1(在2) 与 LLM#2(在3) 是两处，分别落地
```

## 9. 非目标（明确不做，防止 scope 蔓延）

- ❌ 定时调度（v1 手动触发）
- ❌ 完整账号体系（v1 仅 token）
- ❌ 图片/POI 类来源（高德/百度地图）
- ❌ 多语言展品名采集（i18n 暂只 zh）
- ❌ pgvector 向量入库
- ❌ 展品讲解文案（narration blocks）的 LLM 生成（属后续独立内容加工环节）

## 10. 风险与对策

| 风险 | 对策 |
|------|------|
| 维基名录源解析不稳/覆盖不全 | 名录只做发现入口，坐标/详情靠 wiki connector 补全；缺失项标 confidence 低 |
| 官网 per-site connector 工作量随馆数线性增长 | v1 只做国博做模板；架构保证加新馆只写 connector 不动框架 |
| LLM#2 调用慢/贵 | P 方案按需开关 + 批处理；官方源质量高时可关闭 #2 |
| 采集被源站限流/ban | pipeline 内置限速 + 重试 + 礼貌延迟 + User-Agent；落盘 raw 可重跑 |
| 后台协程在进程重启后丢失 | collect_jobs/items 持久化状态；重启后未完成任务标 canceled，可手动重跑（幂等） |

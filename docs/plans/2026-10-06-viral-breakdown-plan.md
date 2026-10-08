# 爆款拆解 + 对标账号拆解 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).
> **红线：本功能内不做任何星算 AI 宣传**（星算只在模型中心与 MCP/skill 露出）。报告只把模型名记为技术元数据。

**Goal:** 一条作品 → 结构化「爆款拆解报告」（为什么火 + 怎么复刻）；一个作者 → 「对标账号拆解」（账号级内容策略）；纯复用已有转录/视频理解/评论/指标，不新增采集、不做受众画像。

**Architecture:** 新 `briefdown` job（worker）拼装「转录+视频理解+评论区+指标上下文」→ 调 OpenAI 兼容 LLM 产出严格 JSON → 后端确定性计算 data_context → 落 `viral_breakdown` 表 → API/前端展示；对标账号报告为实时聚合端点（不新增表）。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / httpx / pytest / Vue 3 + Element Plus。

## Global Constraints
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- **不做星算宣传**：无品牌露出/升级引导；仅 `model` 字段记模型名。
- 供应商可换、模型名/base_url 来自配置（DB `system_setting` 优先、回退 config），不硬编码。
- 数字（相对中位数倍数、互动率、分位、对标基准）由后端确定性计算；LLM 只做定性。
- 提示词/threshold 存 `system_setting`，有内置默认、可在线改、写侧校验。
- 复用 `understand_service._resolve_llm` 的解析约定（DB 优先）；复用 httpx 封装与 `_post_json` 测试注入点。
- 现有 185 测试保持全绿。

---

### Task 1: 数据模型 + 迁移 0006
**Files:** Modify `app/models.py`；Create `alembic/versions/0006_viral_breakdown.py`；Test `tests/test_breakdown.py`
**Produces:** `ViralBreakdown(id, asset_id unique FK, score:float, verdict:Text, sections:JSON, comment_insights:JSON, data_context:JSON, understanding_available:bool, model:str, prompt_version:str, usage:JSON, status:str, error:str, created_at)`
- [ ] 失败测试：表存在 + `asset_id` 唯一
- [ ] 实现模型 + 迁移（`revision="0006"`, `down_revision="0005"`），往返 + `alembic check`
- [ ] 提交 `feat: add viral_breakdown model and migration 0006`

### Task 2: 拆解配置 + 提示词模块
**Files:** Create `app/core/breakdown_settings.py`、`app/modules/breakdown.py`；Test `tests/test_breakdown.py`
**Produces:** `get_breakdown_settings(db)->{"prompt":str,"viral_multiple":float}`；`DEFAULT_BREAKDOWN_PROMPT`；`build_breakdown_prompt(payload)->(system,user)`；`async run_llm(system,user,*,base_url,api_key,model,timeout=90)->dict(严格JSON)`（内部 `_post_json` 注入点）
- [ ] 测试：默认值/覆盖；prompt 含各维度且禁编造；`run_llm` 解析 JSON、非法→抛
- [ ] 实现；提交 `feat: add breakdown settings and prompt module`

### Task 3: 拆解服务 + handler
**Files:** Create `app/services/breakdown_service.py`；Modify `app/workers/handlers.py`；Test `tests/test_breakdown_service.py`
**Produces:** `async run_breakdown(db, asset_id, *, force=False) -> ViralBreakdown`；`_data_context(db, content, asset)`（确定性）；`_comment_digest(db, content_id, top_n=30)`；`handle_breakdown` + 注册 `"breakdown"`
- [ ] 测试：mock LLM；断言落库字段、data_context 计算（相对中位数倍数/互动率）、无 L3 时 `understanding_available=false` 仍出报告、评论摘要参与 prompt
- [ ] 实现；提交 `feat: add breakdown service and handler`

### Task 4: API（拆解 + 对标账号）
**Files:** Modify `app/api/assets.py`、`app/api/analytics.py`；Test `tests/test_breakdown_api.py`
**Produces:**
- `POST /api/assets/{id}/breakdown`（入队，可 `force`）→ 404/422/200
- `GET /api/assets/{id}/breakdown` → 结果或 `{"status":"pending"}`
- `GET /api/analytics/creator/{author_id}/report?platform=` → 账号级聚合（概览/发布节奏/Top/爆款规律/内容支柱/对标基准/缺口）
- [ ] 测试：鉴权 401、入队、pending、账号报告字段与中位数/爆款倍数正确
- [ ] 实现；提交 `feat: add breakdown and creator-report APIs`

### Task 5: 前端（素材详情 + 数据看板）
**Files:** Modify `web/src/pages/Assets.vue`、`web/src/pages/Analytics.vue`；build
**Produces:** 素材详情「爆款拆解」区（按钮+轮询+报告卡片：结论/评分/钩子/结构/节奏/文案/评论洞察/复刻蓝图）；数据看板作者行点击→对标账号报告弹层
- [ ] 实现接线；`cd web && npm run build` 通过
- [ ] 提交 `feat: viral breakdown and creator report UI`

## Self-Review
- 覆盖 A（爆款拆解）、B（对标账号）、降级路径、确定性数字、KV 可配、无星算宣传、API 即产品（MCP 后续同能力）。
- 不新增采集、不依赖完播/画像；爆发提醒记 backlog。

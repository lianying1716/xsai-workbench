# 架构地基补全 + kuaishou/zhihu 原生抽离 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).
> 设计：`docs/plans/2026-10-06-architecture-foundation-and-native-crawlers-design.md`

**Goal:** 补齐三张地基表（creator_profile / raw_payload / task_log）并把 kuaishou、zhihu 抽离为原生抓取（去掉 MediaCrawler 子进程依赖）。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / httpx / pyexecjs / pytest。

## Global Constraints
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 迁移往返 + `alembic check` 干净（PG 5433 + SQLite）。
- 不新增运行时依赖；不破坏既有 252 测试，最终全绿。
- `raw_payload`/`task_log` 写入失败不得翻转主任务成功态。
- 子进程回退保留 weibo/tieba，移除 kuaishou/zhihu。

---

### Task 1: 三张地基表 + 迁移 0007
**Files:** Modify `app/models.py`；Create `alembic/versions/0007_foundation_tables.py`；Test `tests/test_foundation_models.py`
**Produces:**
- `CreatorProfile(id, platform, author_id, author_name, avatar, bio, follower_count, following_count, verified, homepage_url, last_synced_at, raw(JSON), created_at, updated_at)`，唯一 `(platform, author_id)`
- `RawPayload(id, platform, source, external_id, payload(JSON), content_id(FK nullable), captured_at)`，索引 `(platform, external_id)`
- `TaskLog(id, job_id(FK nullable), job_type, level, message, detail(JSON), actor, created_at)`，索引 `(job_type, created_at)`
- [ ] 失败测试（表存在/唯一约束）→ 实现模型+迁移 → 往返 + check → 提交 `feat: add foundation tables (creator/raw_payload/task_log)`

### Task 2: 写入接入（creator upsert + raw_payload + task_log）
**Files:** Create `app/services/foundation.py`；Modify `app/services/crawl_service.py`、`sync_service.py`、`app/workers/runner.py`；Test `tests/test_foundation_service.py`
**Produces:**
- `upsert_creator(db, platform, author_id, *, author_name="", avatar="", **fields) -> CreatorProfile`
- `record_raw(db, platform, source, external_id, payload, content_id=None) -> None`（超限截断/可选关闭）
- `log_task(db, job_id, job_type, level, message, detail=None, actor="worker") -> None`
- `_upsert_content`（crawl/sync）后调用 upsert_creator + record_raw；`runner._run_one` 在完成/失败/重试各写 task_log
- [ ] 测试：creator upsert 幂等/更新；raw_payload 落库且内容截断；task_log 在成功/失败路径各写；**写入失败 try/except 不影响主流程**
- [ ] 提交 `feat: persist creators, raw payloads, task logs`

### Task 3: analytics 改用 creator_profile（回退兼容）
**Files:** Modify `app/api/analytics.py`；Test `tests/test_foundation_service.py`（追加）
**Produces:** `/analytics/creators` 与 creator report 优先读 `creator_profile`（含粉丝数），无记录时回退现有 group-by 逻辑
- [ ] 测试：有 profile 时返回其 follower/信息；无 profile 时回退且结果与原来一致
- [ ] 提交 `feat: creator analytics prefers creator_profile`

### Task 4: 快手原生抓取
**Files:** Create `app/modules/crawler/graphql/kuaishou/search_query.graphql`、`app/modules/crawler/kuaishou.py`；Modify `app/modules/crawler/client.py`(加 `search_kuaishou`)、`app/modules/crawler/__init__.py`(`_NATIVE` 加 kuaishou、`_MAP` 移除)；Test `tests/test_crawler_kuaishou.py`
**Produces:** `search_kuaishou(keyword, cookie, limit, sort) -> list[dict]`（GraphQL `visionSearchPhoto`，pcursor 分页，归一化 item；mock httpx 断言 URL/body/header 与解析）
- [ ] 测试（mock httpx：body 含 operationName/query/variables，解析 caption/id/metrics）
- [ ] 提交 `feat: native kuaishou keyword crawler`

### Task 5: 知乎原生抓取
**Files:** Create `app/modules/crawler/libs/zhihu.js`（从 MediaCrawler 拷贝，头部注明来源）、`app/modules/crawler/zhihu_sign.py`（pyexecjs 编译 `get_sign(url, cookies)`）、`app/modules/crawler/zhihu.py`；Modify `client.py`、`__init__.py`(`_NATIVE` 加 zhihu、`_MAP` 移除)；Test `tests/test_crawler_zhihu.py`
**Produces:** `search_zhihu(keyword, cookie, limit, sort) -> list[dict]`（`/api/v4/search_v3`，带 x-zst-81/x-zse-96，解析 answer/article/zvideo 归一化）
- [ ] 测试（mock httpx 断言签名头存在、URL/params、混合类型解析）
- [ ] 提交 `feat: native zhihu keyword crawler`

## Self-Review
- 地基：三表 + 迁移 + 写入接入 + analytics 复用 + 写失败隔离。
- 抽离：kuaishou/zhihu 原生、_NATIVE 扩展、子进程仅剩 weibo/tieba。
- 不破坏既有能力；不新增依赖。

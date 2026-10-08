# 订阅打通 + 抓取缓存 + 风控 实施计划

> 设计：`docs/plans/2026-10-06-sync-cache-and-risk-control-design.md`

**Goal:** 关注博主↔订阅打通（creator 订阅能拉到投稿）+ 全平台读操作 TTL 缓存 + 风控冷却/节流。

## Global Constraints
- 只在 `platform-api/` 内改动/提交；Conventional Commits；不新增运行时依赖。
- 缓存/冷却默认生效；风控不硬重试；现有 390 测试全绿；迁移往返 + check 干净。

---

### Task 1: `fetch_cache` 表 + 迁移 0010 + `core/fetch_cache.py`
**Files:** Modify `app/models.py`；Create `alembic/versions/0010_fetch_cache.py`、`app/core/fetch_cache.py`；Test `tests/test_fetch_cache.py`
**Produces:** get/set/purge + 冷却写入/查询 + TTL 常量 + 进程内合并锁；调度器清理过期
- [ ] 测试 → 提交

### Task 2: `fetch_source` 支持 creator（B站 UP 投稿 / 抖音博主视频）
**Files:** Modify `app/modules/bilibili.py`、`app/modules/douyin.py`；Test `tests/test_fetch_creator_videos.py`
**Produces:** 两个平台 creator 拉取 + 风控可读异常
- [ ] mock 测试 → 提交

### Task 3: 缓存/节流/冷却接入 refresh + stats + sync
**Files:** Modify `app/api/followed_creators.py`、`app/services/sync_service.py`
**Produces:** refresh 命中缓存零请求；stats 24h 缓存且只补已开启同步者；creator 同步 15m 缓存；风控冷却
- [ ] 测试（命中缓存不发请求/冷却期不发请求）→ 提交

### Task 4: 订阅页打通（来源标识）
**Files:** Modify `app/api/subscriptions.py`、`web/src/pages/Subscriptions.vue`；Test `tests/test_subscription_settings.py`
**Produces:** `from_followed_creator` + 头像，前端标签
- [ ] 测试 + build → 提交

### Task 5: 前端缓存/风控提示 + 真机验收
**Files:** Modify `web/src/pages/FollowedCreators.vue`
**Produces:** 更新于 X / 风控提示
- [ ] build + Playwright 验收 → 提交

## Self-Review
- creator 订阅真能拉到内容；重复操作不重复打平台；风控有冷却与提示。

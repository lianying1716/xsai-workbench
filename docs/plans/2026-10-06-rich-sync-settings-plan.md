# 订阅同步丰富化 + 模拟数据 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
> 设计：`docs/plans/2026-10-06-rich-sync-settings-and-demo-data.md`

**Goal:** 丰富抖音/B站订阅同步的设置与前端；并为开发环境造模拟数据。

## Global Constraints
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 迁移往返 + `alembic check`（PG+SQLite）干净；现有 290 测试全绿。
- 模拟数据脚本只造开发数据、幂等、`--reset`、不联网。

---

### Task 1: Subscription 设置字段 + 迁移 0008
**Files:** Modify `app/models.py`；Create `alembic/versions/0008_subscription_settings.py`；Test `tests/test_subscription_settings.py`
**Produces:** `Subscription.min_play(int,0), publish_after_days(int,0), max_items(int,50), only_new(bool,True), download_quality(str,"best"), with_comments(bool,False)`
- [ ] 失败测试（列存在/默认）→ 实现模型+迁移 → 往返+check → 提交 `feat: add subscription sync settings (filters/quality/comments)`

### Task 2: 同步执行接入设置 + API 校验
**Files:** Modify `app/services/sync_service.py`、`app/api/subscriptions.py`；Test `tests/test_subscription_settings.py`
**Produces:**
- `sync_service`：按 `min_play`/`publish_after_days` 过滤、`max_items` 截断；`only_new=False` 时更新既有内容；`with_comments` 控制评论门控。
- `SubscriptionIn` 加范围校验（422）。
- [ ] 测试：过滤/截断/only_new/with_comments/422 → 提交 `feat: apply subscription settings on sync (+validation)`

### Task 3: 远端来源选择器（B站扩展 + 抖音新增）
**Files:** Modify `app/modules/bilibili.py`、`app/modules/douyin.py`；Test `tests/test_remote_sources.py`
**Produces:** B站 `list_sources` 支持 favorite/collection/creator；抖音新增 `list_sources`（favorite/creator，mock）
- [ ] 测试（mock httpx）→ 提交 `feat: richer remote-source listing for bilibili/douyin`

### Task 4: 前端订阅页丰富化
**Files:** Modify `web/src/pages/Subscriptions.vue`（+ 如需 `web/src/api`）
**Produces:** 表格（筛选列/状态/下次预计）、编辑弹窗、来源选择器、同步历史抽屉、保存子目录模板
- [ ] 实现 → `cd web && npm run build` → 提交 `feat: rich subscription UI (editor/source-picker/history)`

### Task 5: 开发模拟数据脚本
**Files:** Create `scripts/seed_demo.py`；Test `tests/test_seed_demo.py`
**Produces:** 幂等 seed（账号/订阅/采集/内容/快照/创作者/原始/任务日志/素材/转写/理解/分析/拆解/评论/队列），支持 `--reset`
- [ ] 测试（跑 seed 两次幂等 + 关键表有数据）→ 提交 `feat: demo data seed script for dev`

## Self-Review
- 覆盖抖音/B站同步设置与前端丰富化；模拟数据填满所有页面；不破坏既有功能。

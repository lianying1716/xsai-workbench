# 关注博主列表（抖音 / B站）实施计划

> 设计：`docs/plans/2026-10-06-followed-creators-design.md`

**Goal:** 抖音/B站关注博主卡片列表（真头像/昵称/主页跳转）+ 每博主同步开关（含全量开关）+ 平台/账号 tab。

## Global Constraints
- 只在 `platform-api/` 内改动/提交；Conventional Commits；不新增运行时依赖。
- 头像/昵称/主页必须来自平台真实响应；现有 374 测试全绿。

---

### Task 1: `followed_creator` 表 + 迁移 0009
**Files:** Modify `app/models.py`；Create `alembic/versions/0009_followed_creators.py`；Test `tests/test_followed_creators_model.py`
**Produces:** FollowedCreator(account_id, platform, author_id, author_name, avatar, home_url, signature, verified, follower_count, like_count, sync_enabled, full_sync, last_synced_at, raw, …)；唯一 (account_id, author_id)
- [ ] 失败测试 → 模型+迁移 → 往返+check → 提交

### Task 2: 适配器 `list_followings`（富字段）
**Files:** Modify `app/modules/bilibili.py`、`app/modules/douyin.py`；Test `tests/test_list_followings.py`
**Produces:** B站/抖音富关注列表（头像/昵称/签名/认证/主页；B站粉丝数）
- [ ] mock httpx 测试 → 提交

### Task 3: followed-creators API + 同步联动
**Files:** Create `app/api/followed_creators.py`；Modify `app/main.py`；Test `tests/test_followed_creators_api.py`
**Produces:** list/refresh/update/立即同步；sync_enabled→维护 Subscription(source_type=creator)
- [ ] 测试 → 提交

### Task 4: 前端 `FollowedCreators.vue` + 路由/菜单
**Files:** Create `web/src/pages/FollowedCreators.vue`；Modify `web/src/router.ts`、`web/src/layout/Layout.vue`
**Produces:** 平台一级 tab / 账号二级 tab / 卡片（点击跳主页）/ 同步+全量开关 / 刷新
- [ ] `npm run build` → 提交

### Task 5: seed 演示数据 + 真机验收
**Files:** Modify `scripts/seed_demo.py`
**Produces:** 演示关注博主（真实感头像/昵称）；Playwright 验收
- [ ] 提交

## Self-Review
- 满足全部需求点；不破坏既有同步/订阅；头像昵称真实。

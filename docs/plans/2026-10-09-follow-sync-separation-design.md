# 收藏 / 点赞 / 关注列表 同步分离 · 设计

> 日期：2026-10-09
> 需求：收藏和点赞必须分开，摆到显眼位置、用户手动打开才同步；关注列表默认同步，
> 但同步「某个博主名下的视频」必须手动开启；手动开启后的链路要能追踪是否真的生效，
> 包括全量更新（only_new=false）。参照实现：`dysync.net`（抖小云）。

## 1. 参照：抖小云怎么分类

`dysync.net/model/dto/VideoTypeEnum.cs` 用**独立枚举**区分同步类型：
点赞 `dy_favorite`、收藏 `dy_collects`、关注 `dy_follows`、
自定义收藏夹 `dy_custom_collect`、收藏合集 `dy_mix`、收藏短剧 `dy_series`、
关注列表 `dy_followuser`（周期）/ `dy_followuser_once`（一次性）。

`service/DouyinQuartzJobService.cs` 里每一类都是**独立的 job + trigger + 开关**
（`IsFavoriteEnabled` / `IsCollectEnabled` / `IsFollowedEnabled` …）。
关键点：收藏、点赞、关注列表在「枚举 / 调度配置 / 开关」三处都是独立个体。

抖小云的关注列表 job 固定 60 分钟无条件跑（只同步"关注了谁"），
而"同步关注博主名下视频"（`dy_follows`）是另一个独立开关——两者本就是两件事。

## 2. 本平台现状与差距

现状（`platform-api`）：
- 三类源（收藏/点赞/关注）都塞进 `subscription.source_type`，靠一个 `enabled` 控制；
- 导入关注列表**默认不开同步**（与新需求相反）；
- 收藏、点赞在筛选 UI 里被合并成「收藏夹 / 合集」，用户分不清；
- 拉了博主视频的 `enabled` 与"关注关系"共用一个布尔，语义含糊；
- `sync_run` 只有 `added`，全量同步（`only_new=false`）刷新已有内容时**看不出任何效果**；
- `subscription.interval_minutes` 存了但**没有任何调度器消费**——
  "开启同步"其实只在用户手点「立即同步」时才会跑。

## 3. 设计

### 3.1 三个开关彼此独立（对齐抖小云）

| 类别 | 默认 | 手动开关 | 说明 |
|---|---|---|---|
| 收藏 | 关闭 | 是 | 账号级单例源（抖音 `remote_id=sec_user_id`） |
| 点赞 | 关闭 | 是 | 同上 |
| 关注列表 | **开启** | 关注关系的暂停/恢复 | 导入即跟踪 |
| 博主名下视频 | **关闭** | 是（二级） | `subscription.sync_videos` |

- 收藏/点赞通过新增的账号级开关 API 打开：
  `GET /api/accounts/{id}/sync-switches`、`PUT /api/accounts/{id}/sync-switches/{favorite|like|creator}`。
  打开时按需创建订阅（幂等）；关闭只置 `enabled=false`，不物理删除。
- `sync_videos` 只对 `source_type='creator'` 有意义：**不打开则不拉该博主视频**，
  同步请求会直接返回明确原因，杜绝"看着开着、其实没同步"。
- "立即同步"归入用户显式意图：会把 `enabled` 与 `sync_videos` 都打开，然后跑一次。

### 3.2 数据模型（迁移 0016）

- `subscription.sync_videos BOOLEAN NOT NULL DEFAULT false`
- `sync_run.updated INTEGER NOT NULL DEFAULT 0`（全量刷新命中的已有内容条数）
- 回填：`UPDATE subscription SET enabled=true WHERE source_type='creator'`
  （把旧逻辑"默认关闭"的存量关注对齐到新需求；仅动关系跟踪，不碰 `sync_videos`）

### 3.3 全链路可追踪

一次手动/自动同步的完整证据链：
`开关写库` → `scheduler 入队 sync` → `worker 跑 run_subscription_sync` → `sync_run(fetched/added/updated/status/error)`。

`updated` 是关键补充：`only_new=false` 时已有内容会被覆盖刷新，光看 `added=0` 无法判断
全量是否生效；现在历史抽屉里能直接看到「全量刷新 N 条」。

### 3.4 补上缺失的周期同步

`scheduler.enqueue_due_subscriptions()` 每 `PLATFORM_SUBSCRIPTION_SCAN_INTERVAL`（默认 5）分钟扫描：
`enabled` 且账号 `active` 且未删除，且距 `last_sync_at` 超过 `interval_minutes` 的订阅 → 入队 `sync`（dedup）。
creator 还要 `sync_videos` 打开。这样"关注列表默认同步"才真正闭环，而不是只存一个布尔。

## 4. 前端

`web/src/pages/FollowedCreators.vue`：
- 页头下方新增**三块独立同步开关面板**（收藏 / 点赞 / 关注列表），状态一眼可见、可直接开关；
- 博主卡片拆两条链路：主开关「视频同步」+ 次级「关注关系」；
- 类型筛选把「收藏」「点赞」从原来的合并项拆成独立 chip；
- 同步历史抽屉新增「全量刷新」列。

## 5. 兼容与保留策略

- 删除/取消关注仍只停用来源（`content_source.active=false` + 软删），**绝不物理删素材**；
- 唯一约束 `(account_id, source_type, remote_id)` 不看 `deleted_at`，重新打开开关时**复活**原行；
- `PUT /api/subscriptions/{id}` 仍是全字段覆盖，但未显式带来的 `enabled/only_new/sync_videos`
  不再被重置为默认值（防止局部更新误关开关）。

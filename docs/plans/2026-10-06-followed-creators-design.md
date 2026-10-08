# 关注博主列表（抖音 / B站）· 设计

> 日期：2026-10-06
> 需求：抖音、B站要有一个「关注列表」，卡片式展示，**真实头像 + 昵称**，点击跳转博主主页；
> 每个博主可**开启/关闭同步**，开启后可再切**全量同步**（关闭＝只同步新发布）；
> 条件允许时展示博主的**粉丝数 / 获赞数**；**平台为一级 tab，账号为二级 tab**。

---

## 1. 参考实现（已核实）

| 平台 | 关注列表接口 | 头像/昵称字段 | 粉丝/获赞 |
|---|---|---|---|
| B站 | `GET api.bilibili.com/x/relation/followings?mid&pn&ps` | `list[].face`（头像 URL）、`uname`、`sign`、`mid` | 粉丝：`GET /x/relation/stat?vmid={mid}` → `data.follower`（**免登录**，实测可用）；获赞：`/x/space/upstat` 需 wbi，best-effort |
| 抖音 | `GET www.douyin.com/aweme/v1/web/user/following/list?sec_user_id&offset&count` | `followings[].avatar_larger.url_list[0]`、`nickname`、`sec_uid`、`signature`、`enterprise_verify_reason` | 需逐用户 `/aweme/v1/web/user/profile/other/`（要 a_bogus 签名），best-effort |

来源：
- dysync.net `model/entity/DouyinFollowed.cs`（SecUid/UperName/UperAvatar/Enterprise/OpenSync/FullSync）+
  `service/DouyinHttpClientService.cs:482`；
- bili-sync `bilibili/me.rs:get_followed_uppers`（`/x/relation/followings` + `FollowedUpper{mid,uname,face,sign}`）。

## 2. 数据模型（迁移 0009）

新表 `followed_creator`（关注博主实体，与 `creator_profile` 区分：后者是所有抓到的作者，本表只存「我关注的人 + 同步开关」）：

| 字段 | 说明 |
|---|---|
| `id` | PK |
| `account_id` FK→platform_account（CASCADE） | 归属账号（多账号 tab 的关键） |
| `platform` | douyin / bilibili |
| `author_id` | B站 mid / 抖音 sec_uid |
| `author_name` | 昵称（真实） |
| `avatar` | 头像 URL（真实） |
| `home_url` | 主页 URL（点击跳转） |
| `signature` | 个性签名 |
| `verified` | 是否认证 |
| `follower_count` | 粉丝数（0=未知） |
| `like_count` | 获赞数（0=未知） |
| `sync_enabled` | 是否开启同步（默认 False） |
| `full_sync` | 全量同步（仅 sync_enabled 时有意义；False＝只同步新发布） |
| `last_synced_at` | 上次同步时间 |
| `raw` JSON | 原始接口数据 |
| `created_at`/`updated_at` | 时间戳 |

唯一约束 `(account_id, author_id)`；索引 `(platform, account_id)`。

## 3. 适配器扩展

新增适配器方法 `list_followings(credential) -> list[dict]`（**富字段**，供本功能用；`list_sources('creator')`
保持原有轻量契约不变以免破坏订阅页）。

返回字段：`author_id, author_name, avatar, home_url, signature, verified, follower_count, like_count, raw`。

- B站：`/x/relation/followings` 分页（pn/ps，最多 N 页）→ 每条补 `/x/relation/stat`（粉丝）。
- 抖音：`following/list` 分页（offset/count）→ 头像/昵称/签名/认证；粉丝/获赞**本期留 0**
  （实现说明：需逐用户调 `/aweme/v1/web/user/profile/other/` 且每个都要 a_bogus 签名，
  N 位博主＝N 次 JS 签名 + N 次请求，刷新会很慢且易触发风控；<br>
  故列表现阶段只返回列表接口自带的字段，粉丝/获赞作为**后续可选增强**（可批量/带缓存补）。
  UI 对「未知」显示为 `—`，不误导）。
- 两个平台都**防御式解析**：字段缺失跳过该条；网络异常返回已拿到的部分（或抛可读异常给上层）。

## 4. API

| 端点 | 用途 |
|---|---|
| `GET /api/followed-creators?platform=&account_id=` | 读已入库的关注博主（卡片数据源） |
| `POST /api/followed-creators/refresh` `{account_id}` | 从平台拉取关注列表 → upsert 入库，返回数量 |
| `PUT /api/followed-creators/{id}` `{sync_enabled, full_sync}` | 开关同步 / 全量 |
| `POST /api/followed-creators/{id}/sync` | 立即同步该博主（建/更新 Subscription 后跑一次） |

同步语义：`sync_enabled=True` 时，为该博主维护一条 `Subscription(source_type="creator", remote_id=author_id)`；
`only_new = not full_sync`（全量＝覆盖刷新既有内容；非全量＝只入库新发布）。

## 5. 前端（新页 `FollowedCreators.vue`，菜单「关注博主」）

- **一级 tab＝平台**（抖音 / B站，只显示有账号的平台）；**二级 tab＝账号**（同平台多账号区分）。
- 卡片网格：头像（圆形，失败走占位）→ 昵称 → 粉丝/获赞（未知则省略）→ 认证标 → 签名（截断）。
  - **点击头像或昵称**：新窗口打开 `home_url`（博主主页）。
- 卡片操作区：
  - 「开启同步」开关（`sync_enabled`）；开启后**出现**「全量同步」开关（`full_sync`）。
  - 顶部工具条：「刷新关注列表」（调 refresh）。
- 状态反馈：拉取 loading、空态（未登录/无关注/凭证失效提示）、保存 toast。

## 6. 集成与不破坏

- 复用既有 `Subscription` + `run_subscription_sync`；不新增同步引擎。
- `list_sources('creator')` 契约**不变**（订阅页不依赖富字段）。
- 现有 374 测试全绿；迁移 PG+SQLite 往返 + `alembic check` 干净。
- 无凭证 / 被风控 → 可读异常，前端提示切换账号或重新登录。

## 红线
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 不新增运行时依赖；不造假数据（真实接口，失败即如实报错/空态）。
- 头像/昵称/主页链接**必须来自平台真实响应**。

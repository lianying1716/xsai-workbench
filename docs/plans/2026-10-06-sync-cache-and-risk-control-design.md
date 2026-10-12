# 订阅打通 + 抓取缓存 + 风控 · 设计

> 日期：2026-10-06
> 需求（用户原话）：**继续打通**（关注博主 ↔ 订阅同步）；**加上补缓存方案不要频繁拉取数据**；
> **风控方面必须做好**。

---

## 1. 现状与问题（已实测）

| 问题 | 事实 |
|---|---|
| **订阅未打通** | `bilibili.fetch_source` 只支持 `favorite`；`douyin.fetch_source` 只支持 favorite/collection。关注博主的 `creator` 订阅**拉不到投稿**（静默 `fetched=0`）。 |
| **无缓存** | 每次「刷新关注列表」都全量打平台；粉丝数逐条请求（B站每博主 1 次），点一下就几十次请求。 |
| **无节流/退避** | 无最小间隔、无风控冷却、无失败退避；`crawler/client.py` 仅少数循环有 sleep。 |
| **风控实测** | B站 `x/space/wbi/arc/search` 免登录 → `-352 风控校验失败`（412 HTML）；带登录 Cookie 通常可过。抖音 `aweme/post` → `403 Blocked by ArgusSecurityPlugin Uifid Not Found`（需登录态 uifid）。 |

## 2. 设计目标

1. **打通**：关注博主开启同步后，`creator` 订阅能真正拉到该博主的投稿/视频。
2. **不频繁拉取**：所有平台读操作走**带 TTL 的缓存**，命中即返回、零网络请求。
3. **风控兜底**：最小请求间隔 + 命中风控后**冷却期**（期间只读缓存并明确提示）+ 失败退避。

## 3. 缓存与节流层（`app/core/fetch_cache.py` + 迁移 0010）

新表 `fetch_cache`：`key(PK str) / value(JSON) / expires_at / created_at`。统一存**任意可缓存响应**。

```python
get_cache(db, key) -> dict | None          # 未命中/过期 → None
set_cache(db, key, value, ttl_seconds)     # upsert
purge_expired(db)                          # 调度器周期清理
```

**TTL（集中常量，可调）**：

| 数据 | key | TTL |
|---|---|---|
| 关注列表 | `followings:{platform}:{account_id}` | **6 小时** |
| 博主统计（粉丝/获赞） | `stats:{platform}:{author_id}` | **24 小时** |
| 博主投稿/视频 | `creator_videos:{platform}:{account_id}:{author_id}` | **15 分钟** |

**风控冷却**（同一张表，`cooldown:{platform}:{account_id}:{op}`）：命中平台风控（HTTP 412/403 或业务码 `-352`/`-412`）时写入冷却；冷却期内该操作**直接返回缓存并提示**，不发网络请求。

**节流**：进程内 `asyncio.Lock` + 最小间隔（同 key 的并发刷新合并为一次请求；避免用户连点）。

## 4. 打通：`fetch_source` 支持 `creator`

- **B站**：`/x/space/wbi/arc/search`（WBI 签名，复用 `crawler/bili_sign`）+ 登录 Cookie；
  分页（`pn`/`ps`），映射 `bvid/title/author/pic/created/stat`。
- **抖音**：`/aweme/v1/web/aweme/post/`（a_bogus 签名，复用 `crawler/douyin_sign`）+ 登录 Cookie；
  `max_cursor` 分页，映射 `aweme_list[].{aweme_id,desc,author,video.cover,create_time,statistics}`。
- **失败可读**：风控 → 抛带「风控/请稍后」的异常；`sync_run.error` 记清楚，不再静默 0。
- **订阅页打通**：`GET /api/subscriptions` 增加 `from_followed_creator`（按 `account_id+remote_id` 反查）+ `creator_avatar`，前端在来源列显示「关注博主」标签。

## 5. 接入点

| 调用方 | 缓存键 | 行为 |
|---|---|---|
| `POST /followed-creators/refresh` | `followings:*`(6h) | 命中缓存直接 upsert（0 请求）；未命中才拉，拉完写缓存；风控则冷却 |
| 统计补全（粉丝/获赞） | `stats:*`(24h) | 仅对**已开启同步**的博主补，且逐条走缓存/节流 |
| `run_subscription_sync`（creator） | `creator_videos:*`(15m) | 命中缓存直接用；未命中才拉；风控写冷却并记 error |

## 6. 前端

- 关注博主页：显示「数据更新于 X（缓存）」；命中冷却时提示「平台风控中，N 分钟后可刷新，当前展示缓存」。
- 订阅页：`creator` 来源显示「关注博主」标签 + 头像。

## 红线
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 不新增运行时依赖；缓存/冷却必须**默认生效**（不是可选开关）。
- 风控时**绝不重试硬打**；宁可返回缓存 + 明确提示。
- 现有 390 测试全绿；迁移 0010 往返 + `alembic check` 干净。

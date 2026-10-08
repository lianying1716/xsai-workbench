# 抖音评论富集 设计文档（Design Spec）

> 状态：待用户确认 · 2026-10-05
> 决策记录见文末「已定决策」。实施计划另出 `2026-10-05-douyin-comment-enrichment-plan.md`。

## 1. 目标

给平台补上**评论级数据**：拉取抖音作品的评论**正文 + 评论人昵称 + 该评论点赞数**，并保证**只对"够热"的作品**才去抓，避免无差别抓取导致风控与存储爆炸。

抖音优先（接口/签名最现成），B站、小红书留作后续扩展。

## 2. 范围（本版做什么 / 不做什么）

**做**
- 抖音作品：拉一级评论（`content` / `nickname` / `avatar` / `like_count` / `ip_location` / `cid` / `reply_id` / `create_time`）。
- **动态门控**：每次采集/同步后自动判断哪些作品值得抓评论。
- 评论走 **worker 队列**（不阻塞 API），带**预算**与**限速**。
- 素材详情页展示评论；接口 `/api/assets/{id}/comments`。
- 门控参数可在**系统设置**里调（不写死在代码）。

**不做（本版明确排除）**
- ❌ 楼中楼/二级评论（`comment/list/reply/`）——留在后续增强。
- ❌ 已抓过的作品重复抓取（“不重抓”B1）——留增量刷新（“变热才补”）到后续。
- ❌ B站 / 小红书评论（接口与签名已具备，但本版只做抖音）。
- ❌ 公众号评论（需客户端凭据 + mitmproxy，按既有决定不做）。

## 3. 已定决策（来自与用户的对齐）

| # | 决策 | 取值 |
|---|---|---|
| D1 | 动态阈值机制 | **C：批内分位 + 预算 + 下限** |
| D2 | 高赞保证 | **C：默认排序抓 K 页 → 本地按点赞排序取 Top-N** |
| D3 | 触发入口 | **C：采集(crawl) 与 订阅同步(sync) 共用同一门控** |
| D4 | 重复遇到 | **B1：不重抓**（已有评论直接跳过） |
| D5 | 抓取量级 | **随机/自适应**（由分位+预算决定，非固定条数） |
| D6 | 互动分权重 | **评论数 × 20**（1 条评论 ≈ 20 赞，让评论热度真正参与排序） |
| D7 | 层级 | **仅一级评论**（不做楼中楼） |

## 4. 架构总览

```
采集(crawl) / 同步(sync)
        │  产出 content_item + 指标快照(play/like/comment/favorite/share)
        ▼
   [comment_gate]  ──► 选出「够热」的作品（动态分位+预算+下限）
        │
        ▼  enqueue("fetch_comments", {content_id}, priority=150)
   [worker: handle_fetch_comments]
        │  取该平台在线账号 cookie → crawler.fetch_comments()
        │  （默认排序抓 K 页 → 本地按点赞排序取 Top-N）
        ▼
   写 comment 表 + comment_fetch_state（标记已抓，供"不重抓"）
        ▼
   GET /api/assets/{id}/comments  ←  前端素材详情「评论」区
```

**关键红线**：门控只在**已有指标**上做决策（不额外请求）；真正的评论 HTTP 请求只在 worker 里发生，受预算与限速约束。

## 5. 数据模型（新增 2 张表）

### 5.1 `comment`
| 字段 | 类型 | 说明 |
|---|---|---|
| id | PK | |
| content_id | FK→content_item.id, index | 归属作品 |
| platform | String(32) | 本版恒为 `douyin` |
| comment_id | String(64), index | 平台评论 ID |
| parent_comment_id | String(64), default "0" | 本版恒 "0"（仅一级） |
| user_id / nickname / avatar | String | 评论人 |
| content | Text | 评论正文 |
| like_count | BigInteger | 评论点赞数 |
| ip_location | String(32) | IP 归属（抖音 `ip_label`） |
| created_at | DateTime nullable | 评论发布时间（平台 `create_time`） |
| fetched_at | DateTime | 抓取时间 |

约束：`UniqueConstraint(content_id, comment_id)`，重复抓取幂等。

### 5.2 `comment_fetch_state`
| 字段 | 类型 | 说明 |
|---|---|---|
| content_id | PK, FK→content_item.id | 一作品一行 |
| last_fetched_at | DateTime | |
| last_score | Float | 抓取时的互动分（供未来"变热才补"用） |
| fetched_count | Integer | 实际入库评论数 |

用途：实现 D4「不重抓」——门控时排除已存在的 state 行；同时为后续增量刷新留 `last_score`。

### 5.3 既有表改动
无需改 `content_item` / `content_metric_snapshot`。评论总数继续用 `content_metric_snapshot.comment`。

## 6. 动态门控逻辑 `app/services/comment_gate.py`

纯函数，便于单测：

```python
def select_targets(
    db, contents: list[ContentItem], *, platform: str,
    top_pct: float, budget: int, min_comments: int, min_likes: int, weight: float,
) -> list[ContentItem]:
    """选出需要抓评论的作品。"""
```
算法（**唯一"动态"的地方是分位，不是固定阈值**）：
1. 只考虑 `platform` 匹配、且该作品尚无 `comment_fetch_state`（D4 不重抓）的作品。
2. 取每个作品**最新** `content_metric_snapshot`；无指标则跳过。
3. `score = like + comment * weight`（D6）。
4. 按 score 降序，取 **前 `top_pct`**（默认 20%；批内 <5 条时全取）→ 这一步随账号/话题冷热自适应。
5. **下限兜底**：剔除 `comment < min_comments` 或 `like < min_likes` 的（防小号被 3 个赞触发）。
6. **预算封顶**：最多取 `budget` 条（D1）。
7. 返回入选作品。

> 语义顺序：分位决定"相对够热"，下限决定"绝对够格"，预算决定"别失控"。三者共同构成 C。

**参数来源**：`system_setting` KV（下节），带代码内默认值兜底。

## 7. 配置项（存 `system_setting`，可在系统设置页调整）

| key | 默认 | 含义 |
|---|---|---|
| `comment_gate_top_pct` | 0.2 | 批内前 N% 进候选 |
| `comment_gate_budget` | 10 | 每次运行最多抓多少作品 |
| `comment_gate_min_comments` | 20 | 绝对下限：评论数 |
| `comment_gate_min_likes` | 100 | 绝对下限：点赞数 |
| `comment_gate_weight` | 20 | 互动分里评论的权重 |
| `comment_fetch_pages` | 2 | 每作品抓几页（D2 的 K） |
| `comment_fetch_per_page` | 20 | 每页条数 |
| `comment_fetch_top_n` | 20 | 本地按点赞排序取前 N |
| `comment_fetch_interval_sec` | 1.0 | 翻页间 sleep（限速，防风控） |

`app/api/system.py` 的 `_PUBLIC_SETTINGS` 扩展以支持读写；新增 `GET/PUT /api/system/comment-settings`（或并入现有 settings）。

## 8. 抓取 `app/modules/crawler/`

新增 `fetch_comments(aweme_id, cookie, *, pages, per_page, top_n, interval) -> list[dict]`：
- 端内 API：`GET https://www.douyin.com/aweme/v1/web/comment/list/`，参数 `aweme_id`、`cursor`、`count`、`item_type=0` + 既有 `BASE_PARAMS`。
- 签名复用现有 `douyin_sign.get_a_bogus(base, qs, ua)`（该函数已按 URL 含 `/reply` 分流，本轮用不到）。
- 翻 `pages` 页，每页 sleep `interval`；汇总后**本地按 `digg_count` 降序取 Top `top_n`**（D2）。
- 规整为统一 item：`{comment_id, parent_comment_id:"0", user_id, nickname, avatar, content, like_count, ip_location, created_at}`。
- 失败（Cookie 失效/风控 `has_more` 异常）抛可读错误 → worker 走既有失败重试。

## 9. 队列与 worker

- 新增 job 类型 `fetch_comments`，payload `{content_id}`，`priority=150`（低于下载/转录默认 100，让重活先跑）。
- `app/workers/handlers.py` 增 `handle_fetch_comments`：
  1. 取 content + 该平台在线账号 cookie；
  2. 调 `crawler.fetch_comments`；
  3. 幂等写 `comment`（按 `content_id+comment_id` 去重）+ 写/更新 `comment_fetch_state`；
  4. 失败抛异常，交给既有 `queue.fail` 重试。
- 门控在 `crawl_service.run_crawl_task` 与 `sync_service.run_subscription_sync` 的**收尾处**调用，仅 `enqueue`（快），真实抓取在 worker。

## 10. API

- `GET /api/assets/{asset_id}/comments?limit=50&offset=0`
  返回 `{total, comments:[{comment_id, nickname, avatar, content, like_count, ip_location, created_at}]}`（按 like_count 降序）。
- 素材列表/详情已有 `metrics.comment`（总数）——**低于阈值时只显示数量，不显示正文**（前端依据是否存在 comment 行判断）。
- （可选）skills 通道：`GET /api/skills/assets/{id}/comments`，与前端同能力（红线：API 即产品）。

## 11. 前端

`web/src/pages/Assets.vue` 详情抽屉新增「评论」区：
- 顶部始终显示**评论总数**（来自指标）。
- 若已抓取：按点赞降序展示评论卡片（昵称 / 正文 / 点赞数 / IP / 时间），支持分页/加载更多。
- 若未达阈值或未抓取：显示灰字说明（"评论数/点赞未达抓取门槛，仅显示数量"），**没有"手动抓取"按钮**（保持全自动，符合 D3）。

`web/src/pages/Settings.vue` 新增「评论抓取」tab：9 个配置项（数字输入），保存到 `system_setting`。

## 12. 测试计划（TDD）

- `comment_gate.select_targets`：分位选择、下限过滤、预算封顶、已抓跳过、无指标跳过、批<5 全取。
- `fetch_comments` 解析：用固定 JSON 夹具（不联网），验证字段映射 + Top-N 排序。
- `handle_fetch_comments`：幂等写库、state 落库、重复不重抓。
- API：`GET /api/assets/{id}/comments` 鉴权 + 排序 + 分页。
- 现有 38 测试保持全绿。

## 13. 风险与对策

| 风险 | 对策 |
|---|---|
| 抖音风控（高频评论接口） | 预算封顶 + 翻页 sleep + 走 worker 低优先级 + 失败重试退避 |
| 评论接口改版 | 解析集中在 `fetch_comments` 一处；失败不阻塞主流程 |
| 存储膨胀 | 每作品仅存 Top-N（默认 20）；只对够热作品抓 |
| 门控调参不当 | 全部走 `system_setting` 可调，无需改代码/重启（读取时取最新） |

## 14. 后续增强（本版不做）

- 楼中楼（二级评论）。
- 增量刷新：作品"明显变热"（`score` 较 `last_score` 涨 X%）时补抓新评论（已预留 `last_score`）。
- B站（`/x/v2/reply/wbi/main`，WBI 签名已有）/ 小红书评论。
- 评论情感分析 / 关键词提取，接入既有 AI 分析。

## 15. 待用户确认

- [ ] 数据模型（2 张新表）是否认可？
- [ ] 门控参数默认值（pct 20% / budget 10 / 下限 评论≥20 且 赞≥100 / 权重 20 / 抓 2 页取 Top20）是否认可？
- [ ] 前端"没有手动抓取按钮、纯自动"是否认可？

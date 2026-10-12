# 订阅同步设置丰富化 + 开发模拟数据 · 设计+计划

> 日期：2026-10-06
> 背景：用户指出「抖小云（dysync=抖音同步）和 B站同步的大部分设置、前端功能必须丰富」；且当前是开发环境，需要**模拟数据**以便前端验收。
> 现状：`Subscription` 模型有 `subdir_template` 但前端未暴露；无筛选字段；订阅页仅「新建/立即同步/启停/删除」，无编辑、无同步历史、无来源选择器；无任何种子数据。

---

## Part A：订阅同步设置丰富化（抖音 + B站 为主）

### A1. `Subscription` 新增设置字段（迁移 0008）
| 字段 | 含义 | 默认 |
|---|---|---|
| `min_play` | 最低播放量门槛，低于则不入库 | 0（不限） |
| `publish_after_days` | 只同步最近 N 天发布的内容（0=不限） | 0 |
| `max_items` | 单次同步最多入库条数 | 50 |
| `only_new` | 只入库新内容（已存在则只更新指标） | True |
| `download_quality` | 下载画质偏好（best/1080/720/audio） | "best" |
| `with_comments` | 同步后是否对该批走评论门控 | False |
| （已有）`subdir_template` | 保存子目录模板，前端暴露 | "{platform}/{creator}/{date}" |

### A2. 同步执行接入设置
`sync_service.run_subscription_sync`：拉取后按 `min_play` / `publish_after_days` 过滤，按 `max_items` 截断；`only_new=False` 时覆盖更新已有内容的标题/URL/封面；`with_comments` 决定是否调用评论门控（覆盖全局默认）。数字/时间过滤为确定性逻辑，便于测试。

### A3. 来源选择器（remote_sources）
- B站 `list_sources` 扩展：`favorite`（既有）+ `collection`（需 UP mid）+ `creator`（UP 主投稿，列出关注列表）。
- 抖音新增 `list_sources`：`favorite`（收藏）+ `creator`（关注列表，用 `following_list`）。
- 前端「新建/编辑订阅」用来源选择器替代手工填 remote_id（仍允许手填兜底）。

### A4. 订阅 API 校验
`SubscriptionIn` 加范围校验：`interval_minutes>=10`、`min_play>=0`、`max_items 1..500`、`publish_after_days>=0`、`download_quality ∈ {best,1080,720,audio}`；非法 422。

### A5. 前端 `Subscriptions.vue` 丰富化
- 表格列：平台 / 来源（含类型标签）/ 自动下载 / 周期 / 筛选（最低播放·最近天数）/ 上次同步 / 下次预计 / 状态。
- 操作：立即同步、**编辑**（新弹窗，复用创建表单）、启停、**同步历史**（抽屉，展示 SyncRun 列表）、删除。
- 创建/编辑弹窗：账号 → 来源类型 → **来源选择器**（调 remote-sources，带加载态；可切「手动填 ID」）→ 备注 → 自动下载 → 周期 → 最低播放 → 最近天数 → 单次上限 → 只同步新 → 画质 → 同步评论 → 保存子目录模板。
- 前端保存前本地校验（与后端一致）。

---

## Part B：开发模拟数据

### B1. `scripts/seed_demo.py`（幂等）
造出足以填满每个页面的数据：
- 账号：抖音×2、B站×2、小红书×1（凭证用示例 JSON 加密入库，标记 `demo`；不连真实平台）。
- 订阅：覆盖 favorite/collection/creator，参数各不相同（含筛选/画质/评论开关/子目录模板）。
- 采集任务 + 运行记录（含成功/失败）。
- 内容：约 40 条（抖音/B站/小红书），标题/作者/封面/发布时间真实感；多平台。
- 指标快照：每条 5–7 个时间点（画趋势）。
- 创作者档案（含粉丝数/认证）、原始数据、任务日志。
- 素材：部分 downloaded/transcribed/understood（含视频理解结果、分析结果、爆款拆解）。
- 评论：几条热评（含昵称/点赞/内容）。
- 队列：若干 queued/done/error。
- 命令行：`python scripts/seed_demo.py --reset`（清 demo 数据后重建）/ 默认增量幂等。
- 只写 demo 标记数据，绝不触碰真实账号/生产。

---

## 红线
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 迁移往返 + `alembic check` 干净；现有 290 测试全绿。
- 模拟数据脚本只造开发数据、默认幂等、可 `--reset`、不联网、不写真实凭证。
- 不破坏既有同步/采集/评论/分档行为。

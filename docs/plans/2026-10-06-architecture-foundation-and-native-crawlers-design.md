# 架构地基补全 + kuaishou/zhihu 原生抽离 · 设计

> 日期：2026-10-06
> 背景：复盘「参考项目的核心组件是否已抽进自有仓库」，结论是**协议层已抽，但完整模型层缺 3 张地基表，且 kuaishou/zhihu 仍走 MediaCrawler 子进程**。
> 用户决策：**地基表全部补齐**；**kuaishou、zhihu 继续抽离为原生**（不再依赖 MediaCrawler 子进程）。

---

## Part 1：架构地基补全（3 张表）

### 1.1 `creator_profile`（创作者实体）
把现在"从 content 里 group by 作者"升级为**独立创作者实体**——这是对标账号分析、涨粉追踪、作者主页信息的落点。

字段：`id, platform, author_id(, author_name, avatar, bio, follower_count, following_count, verified(bool), homepage_url, last_synced_at, raw(JSON), created_at, updated_at`；唯一约束 `(platform, author_id)`。

- 抓取时 upsert（crawl/sync/subscription 都能顺带写）。
- `follower_count` 用于**涨粉趋势**（配合 `creator_metric_snapshot` 可选，先存当前值）。

### 1.2 `raw_payload`（原始数据留存）
平台一改版，抓到的原始 JSON 还在，可回溯、可重解析。

字段：`id, platform, source(crawl/sync/import/subscription), external_id, payload(JSON), captured_at, content_id(FK nullable)`；索引 `(platform, external_id)`。

- 抓取/同步收尾把原始 item 存一份。
- 设保留上限/清理策略（可配，避免无限增长）。

### 1.3 `task_log`（结构化任务事件流）
现在任务只有 `JobQueue.error` 一句话；补结构化事件流，为 `/api/events/stream`（SSE）和排障打地基。

字段：`id, job_id(FK nullable), job_type, level(info/warn/error), message, detail(JSON), actor, created_at`；索引 `(job_type, created_at)`。

- worker 在 claim/完成/失败/重试时各写一条。
- 保留关键日志，供 pipeline 详情页与诊断。

### 1.4 连带
- 迁移 `0007`（三张表）。
- 既有"从 content group by 作者"的 analytics 端点**改为优先读 `creator_profile`**（回退 group by，保证兼容）。
- `/api/sources` 与 `/api/events/stream` 属规划但未实现——本期**只补数据地基**，端点按需后续。

---

## Part 2：kuaishou / zhihu 原生抽离

沿用既有模式（`bili_sign/douyin_sign/xhs_sign` + `client.py` 直接 HTTP），**不再子进程调 MediaCrawler**。

### 2.1 快手（kuaishou）
- 接口：`POST https://www.kuaishou.com/graphql`，GraphQL `visionSearchPhoto`。
- 签名：**无独立 sign 头**（原项目即纯 GraphQL + Cookie + Referer/Origin）。
- 需拷贝 GraphQL 查询文件：`search_query.graphql`（→ `app/modules/crawler/graphql/kuaishou/`）。
- 产出归一化 item：external_id(photo id)、title(caption)、author、cover、url、metrics(like/view/comment)。
- 分页用 `pcursor`。

### 2.2 知乎（zhihu）
- 接口：`GET https://www.zhihu.com/api/v4/search_v3`。
- 签名：`x-zst-81` + `x-zse-96`，由 **`libs/zhihu.js`**（约 6.5KB，`get_sign(url, cookies)`）计算 →
  拷贝到 `app/modules/crawler/libs/zhihu.js`，用 **pyexecjs**（与抖音 a_bogus 同款模式，无活浏览器）。
- 支持内容类型：answer / article / zvideo（`search_v3` 返回混合类型）。
- 产出归一化 item：external_id、type→content_type、title、author、url、metrics（赞同/评论/浏览）。

### 2.3 分发与清理
- `_NATIVE = {"bilibili","douyin","xhs","kuaishou","zhihu"}`；`crawler/__init__.py` 的 `_MAP`（子进程回退）**移除 kuaishou/zhihu**（保留 weibo/tieba）。
- 无 Cookie/被风控 → 抛可读异常由上层记 error（沿用既有约定）。
- 许可证：两平台的算法/查询来源同为 MediaCrawler（NON-COMMERCIAL），在文件头声明来源；是否正式授权仍是独立合规议题（本次不改变既定边界）。

---

## 红线
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 不新增运行时依赖（pyexecjs 已有；GraphQL 用文本文件）。
- 不破坏既有 crawl/sync/subscription 行为；`raw_payload` 写入失败不得翻转主任务成功态。
- 不引入 MediaCrawler 运行时依赖；子进程回退仅保留 weibo/tieba。

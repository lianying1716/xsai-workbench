# 下载节奏与封控：保守档统一限速 · 设计

> 日期：2026-10-10
> 需求：「更保守的吧 接收慢一点 但是绝对不能出现封号」

## 0. 与上游的关系（先回答用户的问题）

上一轮做的是**下载链路**（URL 取法、镜像轮换、合并），节奏/封控只对齐了一部分。
本轮把节奏与封控补成"比上游更保守"，而不是照搬上游默认值：

| 维度 | 抖小云 | bili-sync | 我们（本轮后） |
|---|---|---|---|
| 下载串行 | `[DisallowConcurrentExecution]` | video semaphore 3 | 全局串行（`_download_gate`） |
| 下载间隔 | `random(1,4)s` | 无（靠限速器） | **`4 + random(0,6)`s** |
| 翻页间隔 | `random(2,10)s` | 无限速（靠限速器） | 抖音 2–10s；**B站 2–6s（新补）** |
| 请求级限速 | 无（靠串行+延迟） | 4 次/250ms ≈ 16/s | **12 次/分钟 ≈ 5s/次（新加）** |
| 失败重试退避 | 1→2→4s | 换 URL | **3→6→12s（上限 30s）** |
| 风控冷却 | — | — | **2 小时（原 30 分钟）** |
| 分片阈值/并发 | — | 20MB / 4 | 20MB / **2** |
| 流空闲超时 | 60s | — | 60s |

结论：**关键路径现在都比上游更慢**，因为我们的场景（多账号批量同步）比上游
（单人、少量追番）更容易触发风控。

## 1. 统一限速器（`app/core/rate_limit.py`）

- 按平台分桶的令牌桶，**容量固定 1** ⇒ 严格最小间隔，**不做"攒满一批再突发"**
  （突发是最像机器人的形态）。
- 默认 `PLATFORM_RATE_LIMIT_PER_MINUTE=12`（≈5 秒/次）。
- `acquire()` 有等待上限（默认 5 分钟），超时抛错 —— 宁可单任务失败，也不无限堆积或绕过。
- `http_client()` / `_ThrottledClient.wrap()` 提供**逐请求**限速的 httpx 封装。

## 2. 覆盖了哪些出站路径

首轮只罩住了抖音/B站适配器的一部分。审计后发现这些**漏网**并已补齐：

| 路径 | 问题 | 处理 |
|---|---|---|
| `modules/crawler/client.py::fetch_comments` | 裸 httpx + 自己的 `interval`，实测 **1.4s 连发 4 个** comment/list | 走 douyin 桶 |
| `modules/crawler/client.py` 搜索（bili/douyin/xhs） | 裸 httpx | 走对应平台桶 |
| `modules/crawler/{kuaishou,zhihu}.py` | 裸 httpx | 走对应平台桶 |
| `modules/crawler/bili_sign.py::fetch_wbi_keys` | 每次签名都打 B站 API，未限速 | 走 bilibili 桶 |
| `modules/{xhs,crawl_platforms}.py` 探活 | 裸 httpx | 走对应平台桶 |
| 封面代理 `GET /api/assets/{id}/cover` | 素材页一屏几十张，会瞬时回源 | **本地缓存**（不带 Cookie，非封号风险，故不限速） |

## 3. 逐请求 vs 逐会话（本轮踩到并修掉的坑）

第一版限速在**进入会话时取一次令牌**。实测评论抓取仍 1.4s 连发 4 个 —— 因为
一个会话里 `for` 循环翻页，等于"进会话就把后面的请求全放行"。
改为 `_ThrottledClient` 在**每次 `get/post/head/stream` 前**取令牌后，
实测评论请求变为 **每 ~5 秒一个**。

## 4. 测试策略

保守限速是**生产风控**措施，测试既不该因此变慢，也不该依赖时序：

- `tests/conftest.py`：`rate_limit.disable()` + 两平台 `_PAGE_DELAY_RANGE=(0,0)`
  + 下载间隔清零；测试本就在 socket 层禁止联网。
- `tests/test_rate_limit.py`（12 条）：单独 `enable` 后验证桶行为本身
  （严格最小间隔、超时抛错、平台隔离、逐请求取令牌、适配器确实过桶）。

## 5. 真机验收（真实账号）

- 抖音真实同步：`sync success`，评论请求 **03:07:12 → 03:07:17（+4.6s）**
  （修复前 1.4s 内 4 个）。
- B站真实 API：连续 3 次 `resolve_play_urls` 分别落在 **+5.1s / +15.2s / +25.2s**
  （每次 2 个请求 × 5s 间隔）。
- 下载间隔生效：一次收藏同步（30 条）耗时从 ~8s 变为 ~25s。
- `uv run pytest tests/ -q` → **587 passed, 1 skipped**；`npx vite build` 通过。

## 6. 可调项（想更慢就调大）

```
PLATFORM_RATE_LIMIT_PER_MINUTE=12     # 调小=更慢（最小间隔 = 60/该值 秒）
PLATFORM_DOWNLOAD_MIN_GAP_SECONDS=4
PLATFORM_DOWNLOAD_JITTER_SECONDS=6
```

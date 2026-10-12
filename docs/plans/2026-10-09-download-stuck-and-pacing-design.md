# 下载卡死 / 触发条件 / 风控节流 · 设计

> 日期：2026-10-09
> 触发：用户反馈「很多任务一直在下载中，很久了」，并要求核查触发条件与抖音健康度、
> 尤其关心**下载间隔与风控**。参照实现：`dysync.net`（抖小云）。

## 1. 核查结论（真实数据）

| 项 | 实测 |
|---|---|
| 抖音账号 | `星算xsai5点xyz` (id=7) `status=active`，适配器 `check -> True 在线` |
| B站账号 | `bili_63409005747` (id=6) `active`，在线 |
| 队列 | 无 queued/running；error 67 / done 17 |
| 素材 | **32 条长期停在 `downloading`**（其中 30 条真实抖音素材，最早 12:56，多数 14:24） |

**下载中卡死的根因**：`handle_download` 在真正下载**之前**就 `commit` 了
`download_status="downloading"`（为了让前端立刻看到进度）。当时的 worker 进程因
`_platform_cookie` 导入错误（已在该轮重命名中修掉）崩溃，队列里的 job 变成 error/消失，
而素材行永远停在 `downloading` —— **没有任何机制去复位它**。

**第二个真 bug**：`resolve_asset_dir` 返回 `str`，而 `media_download` 按 `Path` 使用
（`.mkdir()`）。此前下载都在更早的导入错误处就挂了，所以这个错从未暴露；
一旦修掉导入错误，立刻变成 `'str' object has no attribute 'mkdir'`。

**第三个真 bug**：`media_asset.error` 是**共享**错误位。视频理解失败（未配置大模型）
把自己的错误写进这一列，导致 `download_status='done'`（下载成功）的素材在前端显示成失败。

**触发条件缺陷**：调度器用 `last_sync_at`（**仅成功时更新**）判到期，
于是持续失败的订阅被每 5 分钟重新入队 —— 在平台风控期持续打平台。

**风控/间隔缺陷**：批量同步一次入队几十条下载，两个 worker 槽**零间隔**并发打 CDN；
对比抖小云：下载 job 是 `[DisallowConcurrentExecution]`（串行），下载循环里还有
`Task.Delay(random(2,10)s)` 与失败后镜像轮换 + 指数退避。

## 2. 修复

### 2.1 素材状态对账（`services/asset_state.py`）

把「进行中」状态拉回真实值：
对 `downloading/transcribing/analyzing` 的素材，若**队列里没有对应 queued/running 任务**
且状态超过阈值未更新 → 复位为 `error` 并写可读原因（既有具体错误不覆盖）。
另提供 `clear_success_error()`：清掉 `done` 素材上残留的 error。

接线：worker **启动时**先对账一次，janitor 每 120s 再对账。

### 2.2 下载器修正

- `_as_dir()`：在边界把 `str`/`Path` 归一化，空目录明确报错（`Path("")` 会变成 `"."`）。
- `download_direct(..., mirror_urls, retries)`：失败后**轮换同一视频的其它镜像**，
  每次重试退避 1→2→4s（照抄抖小云 `otherUrls` + 指数退避）。
- `douyin._play_url_list()`：抓取时保留 `play_addr` 全部镜像；`extra.download_urls` 一并入库。

### 2.3 风控节流

- 新增 `PLATFORM_DOWNLOAD_MIN_GAP_SECONDS`(默认 2s) + `PLATFORM_DOWNLOAD_JITTER_SECONDS`(默认 3s)。
- `handle_download` 所有下载走一条进程级串行通道 + 最小间隔，避免并发零间隔打 CDN。

### 2.4 失败退避（迁移 0017）

- `subscription.last_attempt_at`：**每次**尝试都更新（成败皆然）。
- 调度器改用 `last_attempt_at or last_sync_at` 判到期 → 失败也退避满一个 interval，
  不再在风控期反复入队。存量按 `last_sync_at` 回填，升级后不会立刻重排。

### 2.5 可观测性

- `GET /api/assets` 返回 `error`（失败原因），前端失败标签带 tooltip。
- 素材卡片新增「重新下载 / 开始下载」按钮（`POST /api/assets/{id}/download`），
  转录/分析按钮在未下载完成时置灰。

## 3. 验收证据

- 后端 `uv run pytest tests/ -q` → 552 passed, 1 skipped；`npx vite build` 通过。
- 真机（Playwright 真事件）：素材页 `下载中=0`，30 失败 / 31 完成 / 2 待处理，
  失败标签 tooltip 显示真实原因；点「重新下载」后真实产出 mp4 并转为 `done`。
- 节流实测：3 条下载被串行化，相邻启动相隔 ≥ 一个最小间隔。
- 真机下载产出：`data/demo_storage/douyin/.../v0300fg10000db4au5fog65ge0pfo900.mp4`（3.2MB）。

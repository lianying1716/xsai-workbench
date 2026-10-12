# 下载全链路对齐上游（抖音→抖小云 / B站→bili-sync）· 审计与修复

> 日期：2026-10-09
> 需求：「抖音所有下载相关看齐抖小云 哔哩哔哩下载看齐上游 进行一次深入详细的检查，并修复」

## 1. 审计方法

逐行对照两个上游参考实现：

- **抖音**：`dysync.net`（抖小云）`service/DouyinHttpClientService.cs`（`DownloadAsync` /
  `TryDownloadOnceAsync`）、`job/DouyinBasicSyncJob.cs`（`GetBestMatchedVideoUrl` /
  `SwitchOtherUrlAddressDown` / `CreateSaveFolder`）、`utils/DouyinFileNameHelper.cs`。
- **B站**：`bili-sync`（Rust，MIT）`crates/bili_sync/src/downloader.rs`（`fetch_serial` /
  `fetch_parallel` / `multi_fetch*`）、`bilibili/analyzer.rs`（`Stream::urls` / `best_stream`）、
  `bilibili/client.rs`（默认 Header）。

结论用**真实网络请求**验证（本机真实账号 + 真实 CDN），不是纸面推演。

## 2. 发现的真实缺口

| # | 平台 | 缺口 | 上游做法 | 修复前实测 |
|---|---|---|---|---|
| 1 | B站 | **下载完全不可用** | `view`→`playurl` 取 DASH 流 | 无 `download_url` → 一律落 yt-dlp → **HTTP 412 风控**，连公开视频都下不动 |
| 2 | B站 | 不传 UA/Referer | Client 默认带 Chrome UA + Referer | 直链 GET **403**（实测：只带 UA 也 403，必须 UA+Referer） |
| 3 | B站 | 无备用 URL / 无并行 | `Stream::urls()` 多 CDN 轮换；Range 分片并行 | 单地址，失败即整体失败 |
| 4 | B站 | 不合并音视频 | `multi_fetch_and_merge` 用 ffmpeg `-c copy` | DASH 是音视频分离的，没有合并等于没有成品 |
| 5 | 抖音 | 只取顶层 `play_addr` | `bit_rate[]` 里按编码+码率选最佳档 | 只用了顶层 `url_list`，高码率档全浪费 |
| 6 | 抖音 | 重试只看一条流 | `SwitchOtherUrlAddressDown` 遍历**所有档所有镜像** | 单个地址失败即失败（早期） |
| 7 | 抖音 | 文件名不带内容 ID | `SanitizeLinuxFileName(desc, awemeId)` | 用 URL 里的 `video_id`，与标题无关 |
| 8 | 抖音 | 无流空闲超时 | `streamTimeout`（默认 60s） | CDN 挂住会永久占用 worker 槽 |

## 3. 修复

### 3.1 新增 DASH 下载器（`media_download.py`）

照抄 bili-sync：
- `_fetch_to_file`：一组候选 URL 依次尝试（主地址失败轮换 backupUrl）；
- `_fetch_serial`：流式 + Content-Length 校验 + **60s 空闲超时**；
- `_fetch_parallel`：Range 分片并行（≥8MB 才分片，4 并发），每片校验字节数；
- `_merge_dash`：ffmpeg `-c copy -strict unofficial -f mp4` 合并（不重编码）；
- `_bili_headers`：Chrome UA + Referer（实测缺一即 403）；
- `_safe_name`：去非法字符 + UTF-8 字节截断到 100 字节（照抖小云）。

### 3.2 B站 playurl 解析（`bilibili.py`）

`resolve_play_urls()`：`/x/web-interface/view` 取 cid → `/x/player/playurl`
（`fnval=4048` 全开 4K/8K/AV1/HDR）→ 取最高画质视频流 + 最高码率音频流，
每流返回 `baseUrl + backupUrl` 全部候选；无 DASH 的老视频回退 `durl`。

### 3.3 抖音码率档（`douyin.py`）

- `_best_bitrate()`：H.264 优先（兼容性）、同编码取最高码率；只有 H.265 才用它；
- `_play_url_list()`：最佳档镜像 → 顶层 play_addr → **其它所有档全镜像** → download_addr，
  去重保序（对应抖小云 `SwitchOtherUrlAddressDown`）。

### 3.4 分派与命名（`handlers.py`）

- `_download_content()`：抖音走直链、B站走 DASH、其它回退 yt-dlp；
- `_download_output_name()`：`标题_内容ID`，标题按**字节**让位（150 字节上限），
  保证长中文标题不会把 ID 截掉（实测踩到过这个坑）。

### 3.5 封面代理（`GET /api/assets/{id}/cover`）

抖音封面是**带 `sign=` 的 CDN 地址、会过期**；B站封面有防盗链（缺 Referer 直接 403）。
抖小云的做法是把封面/头像落到本地；web 场景下用**服务端代理**等效解决：
浏览器只请求 `/api/assets/{id}/cover`，服务端补 UA+Referer 取图并回传，
前端封面 `<img>` 一律指向该代理（不再直连签名地址）。

## 4. 验收证据（真实数据）

- `uv run pytest tests/ -q` → **573 passed, 1 skipped**；`npx vite build` 通过。
- 新增 `tests/test_bilibili_download.py`（12 条）+ `tests/test_douyin_bitrate_download.py`（11 条）。
- **B站真机**：`fetch real BV1QJmaYKEv4` → `resolve_play_urls` 返回 3 视频 + 3 音频 CDN；
  经真实队列 + worker 下载 → `ffprobe` 确认 **h264 1920x1080 + aac**，62.6 MB，
  文件名 `【8K120帧】aespaWhiplash超高清MV_BV1QJmaYKEv4.mp4`。
- **抖音真机**：真实账号抓取 → 单条内容 **60 个候选地址**（多档多镜像）；
  经真实队列 + worker 下载成功，文件名带完整 aweme id。
- 修复前对照：同一条 B站视频 `yt-dlp` 直接 **HTTP 412**；直链只带 UA 时 **403**。
- **封面代理**：真机素材页 65 张封面全部改为 `/api/assets/{id}/cover`；
  真实抖音素材封面经代理返回 200 image/jpeg（如 /api/assets/79/cover 17.8KB）。
  `GET /api/assets/{id}/media` 对下好的 B站素材返回 **206 video/mp4**（可拖动播放）。

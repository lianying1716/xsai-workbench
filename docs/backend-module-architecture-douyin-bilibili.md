# 抖音与哔哩哔哩模块后端架构拆解设计

## 1. 文档目标

本文档基于对 `/path/to/xsai-workbench/dysync.net` 与 `/path/to/xsai-workbench/bili-sync` 的源码复盘，定义两个项目并入统一平台时的后端模块拆解、抽离策略、统一数据模型、统一 API、以及必须进入统一前端工作台的配置页面。

本轮只覆盖抖音与哔哩哔哩账号内同步模块。`MediaCrawler` 负责多平台公开抓取，`yt-dlp` 负责通用 URL 下载，`faster-whisper` 负责转录，均不替代本模块的账号收藏/关注同步职责。

## 2. 总体结论

- `dysync.net` 已具备抖音账号 Cookie 管理、关注博主、收藏夹/合集/短剧、视频同步、下载、动态图合成、日志和配置能力。
- `bili-sync` 已具备 B 站扫码登录、凭据刷新、收藏夹/合集/UP 主投稿/稍后再看同步、视频下载、规则过滤、下载状态、WebSocket 日志、系统状态和通知器能力。
- 已验证 `dysync.net` 基线为 .NET 6、SqlSugar、Quartz、Serilog、JWT、端口 `10101`、MIT 许可；默认账号 `douyin/douyin2026` 必须在统一平台中废弃并强制初始化管理员密码。
- 已验证 `bili-sync` 基线为 Rust workspace `2.11.1`、Axum、SeaORM SQLite、Svelte 5、端口 `12345`、MIT 许可；首次启动生成 `auth_token`，该鉴权机制不进入统一平台。
- 两者都不能以原独立应用形态长期存在。最终要抽成统一平台模块，由 `platform-api` 统一认证、配置、调度、日志、数据存储和前端管理。
- 第一阶段允许通过内部适配器调用现有服务，第二阶段抽离核心逻辑，第三阶段删除原 Web UI、原账号体系、原配置入口和原独立数据库依赖。
- 后端主控仍建议使用 `Python + FastAPI`。`dysync.net` 与 `bili-sync` 的能力通过模块接口接入，必要时保留 Rust/.NET 内部实现，但不再作为用户可独立访问的应用。

## 3. 目标后端结构

建议新增统一项目结构：

```text
platform-api/
  app/
    main.py
    core/
      config.py
      security.py
      database.py
      scheduler.py
      events.py
    modules/
      accounts/
      storage/
      media_assets/
      sync_tasks/
      douyin/
      bilibili/
      media_download/
      logs/
      diagnostics/
    adapters/
      legacy_dysync/
      legacy_bilisync/
```

核心原则：

- `modules/*` 是最终自有模块，不依赖原项目目录结构。
- `adapters/legacy_*` 只用于过渡期，封装原项目接口或进程调用。
- 前端只访问 `platform-api`，不直接访问 `dysync.net` 或 `bili-sync`。
- 所有配置进入 PostgreSQL，视频、音频、封面、转录、分析文件进入本机或 NAS 路径。
- 本篇只展开 `douyin` 与 `bilibili` 模块；完整模块矩阵以 `docs/backend-module-final-review.md` 为准。

## 4. 统一模块接口

两个平台模块统一暴露相同语义接口：

```text
AccountService
  login_start(platform)
  login_poll(platform, session_id)
  validate_credential(account_id)
  refresh_credential(account_id)
  disable_account(account_id)

SourceDiscoveryService
  list_remote_sources(account_id, source_type)
  list_local_sources(account_id, source_type)
  subscribe_source(account_id, source)
  update_source(source_id, settings)
  remove_source(source_id)

SyncService
  run_sync_task(task_id)
  run_source_once(source_id)
  full_resync_source(source_id)
  get_sync_status(task_id)

MediaService
  list_assets(filters)
  get_asset(asset_id)
  retry_download(asset_id)
  delete_asset(asset_id, delete_file)

ConfigService
  get_module_config(platform)
  update_module_config(platform, config)

LogService
  stream_logs(platform, task_id)
  list_logs(filters)
```

## 5. dysync.net 拆解

### 5.1 现有后端能力

代码位置：

- 控制器：`dysync.net/Controllers`
- 服务：`dysync.net/service`
- 调度任务：`dysync.net/job`
- 实体：`dysync.net/model/entity`
- Vue 管理端：`dysync.net/app/src/pages`
- 二进制文件：`dysync.net/lib/dy.sync.lib.dll`、`dysync.net/dy.cookie.exe`
- 图文合成扩展：`dysync.net/expand/dy.image`

源码基线：

```text
TargetFramework: net6.0
HTTP: http://*:10101
Database/ORM: SqlSugar
Scheduler: Quartz
Logging: Serilog
Auth: JWT + 原 AdminUser
Docker: mcr.microsoft.com/dotnet/aspnet:6.0 + ffmpeg
License: MIT
```

核心后端能力：

- 管理员登录与密码修改：`AuthController`、`AdminUserService`
- 抖音账号/Cookie 管理：`ConfigController`、`DouyinCookieService`
- Cookie 有效性检测：`DouyinHttpClientService.CheckCookie`
- 系统配置：`AppConfig`、`DouyinCommonService`
- 关注博主管理：`FollowController`、`DouyinFollowService`
- 收藏夹/合集/短剧分类管理：`CateController`、`DouyinCollectCateService`
- 视频资产管理：`VideoController`、`DouyinVideoService`
- 视频播放、重下、删除、统计、趋势：`VideoController`
- Quartz 调度：`DouyinQuartzJobService`
- 同步任务：`DouyinBasicSyncJob` 及收藏、喜欢、关注、合集、短剧任务
- 下载与动态图合成：`DouyinHttpClientService.DownloadAsync`、`DouyinMergeVideoService`
- 日志读取：`LogsController`、`LogInfoService`
- 配置导入导出：`ConfigController.exportConf/importConf`
- 原 README 要求手工提取 Cookie 和 `sec_user_id`；`dy.cookie.exe` 是快速重置 Cookie 工具，不是浏览器自动登录能力。

源码确认的主要路由：

```text
POST /api/Auth/Login
POST /api/Auth/UpdatePwd
GET  /api/Auth/GetUserAvatar
POST /api/Config/paged
GET  /api/Config/list
GET  /api/Config/isInit
POST /api/Config/FastResetCookie
GET  /api/Config/Cookies
POST /api/Config/deskinit
POST /api/Config/switch
POST /api/Config/update
GET  /api/Config/delete
GET  /api/Config/GetConfig
POST /api/Config/UpdateConfig
GET  /api/Config/ExecuteJobNow
POST /api/Follow/paged
GET  /api/Follow/sync
POST /api/Follow/add
POST /api/Follow/openOrCloseSync
POST /api/Follow/openOrCloseFullSync
POST /api/Cate/paged
POST /api/Cate/BatchSave
POST /api/Video/paged
GET  /api/Video/statics
GET  /api/Video/play/{vid}
POST /api/Video/redown
GET  /api/Video/vdelete/{vid}
GET  /api/logs/list
GET  /api/logs/content
```

### 5.2 需要抽出的后端模块

建议抽成 `modules/douyin`：

```text
modules/douyin/
  account.py
  browser_login.py
  credential.py
  client.py
  source_discovery.py
  source_sync.py
  downloader.py
  dynamic_media.py
  mapper.py
  config.py
```

模块职责：

- `account.py`：抖音账号、Cookie、sec_user_id、登录状态、启停。
- `browser_login.py`：新增浏览器自动登录能力。现项目主要是手动 Cookie/工具写入，不满足扫码/浏览器自动登录优先的目标。
- `client.py`：封装抖音请求，替代原 `DouyinHttpClientService`。
- `source_discovery.py`：发现关注列表、收藏夹、合集、短剧。
- `source_sync.py`：统一执行收藏、喜欢、关注博主、合集、短剧同步。
- `downloader.py`：下载视频、封面、头像，写入统一资产库。
- `dynamic_media.py`：图文/动态视频合成，调用 FFmpeg。
- `mapper.py`：将原项目 DTO/实体映射到统一数据模型。
- `config.py`：抖音模块配置校验。

### 5.3 现有实体映射

| dysync.net 实体 | 统一平台对象 | 说明 |
|---|---|---|
| `DouyinCookie` | `PlatformAccount` + `AccountCredential` + `AccountSyncProfile` | 账号、Cookie、sec_user_id、保存路径、同步开关 |
| `DouyinFollowed` | `CreatorSubscription` | 关注/非关注博主、是否同步、是否全量同步、自定义文件夹 |
| `DouyinCollectCate` | `RemoteCollectionSource` | 自定义收藏夹、合集、短剧及启停状态 |
| `DouyinVideo` | `ContentItem` + `MediaAsset` | 视频元数据、作者、路径、文件大小、类型、下载状态 |
| `AppConfig` | `PlatformModuleConfig` | 抖音模块全局配置 |
| `DouyinVideoDelete` | `AssetDeleteRecord` | 已删除、不再下载记录 |

关键字段必须进入迁移映射：

- `DouyinCookie`：`Cookies`、`SecUserId`、`SavePath`、`FavSavePath`、`UpSavePath`、`MixPath`、`SeriesPath`、`UseSinglePath`、`DownCollect`、`DownFavorite`、`DownFollowd`、`DownMix`、`DownSeries`、`StatusCode`、`StatusMsg`。
- `DouyinFollowed`：`SecUid`、`UperName`、`OpenSync`、`FullSync`、`SavePath`、`IsNoFollowed`、`DouyinNo`。
- `DouyinCollectCate`：`CookieId`、`XId`、`SaveFolder`、`Sync`、`CateType`、`IsEnd`、`Total`。
- `AppConfig`：`Cron`、`BatchCount`、`DownImageVideo`、`DownImage`、`DownMp3`、`LogKeepDay`、`PriorityLevel`、`OnlySyncNew`、`DownDynamicVideo`、`MegDynamicVideo`、`KeepDynamicVideo`、`VideoEncoder`、`CloseNfo`。
- `DouyinVideo`：`AwemeId`、`VideoTitle`、`VideoUrl`、`VideoSavePath`、`VideoCoverSavePath`、`Author/AuthorId`、`FileHash`、`FileSize`、`Resolution`、`ViedoType`、`DynamicVideos`、`OnlyImgOrOnlyMp3`、`CateId/CateXId`。

### 5.4 必须进入统一前端的 dysync 能力

- 抖音账号页：账号名称、登录状态、Cookie 状态、sec_user_id、启停、重新登录、凭证检测。
- 抖音浏览器登录页：启动登录、显示浏览器/二维码状态、保存 Cookie、失败诊断。
- 抖音同步源页：收藏、喜欢、关注博主、收藏夹、合集、短剧开关。
- 关注博主页：关注列表同步、搜索、手动新增非关注博主、启停、全量同步、自定义保存文件夹。
- 收藏夹/合集/短剧页：远程列表、同步开关、自定义文件夹、批量保存。
- 抖音视频资产页：视频列表、作者、来源类型、保存路径、播放、重下、删除、删除记录。
- 抖音配置页：同步周期、批量数、仅同步新视频、动态图/图文视频、保留原文件、视频编码、命名模板、NFO 开关。
- 抖音日志页：按任务、账号、日期、级别查看日志。
- 抖音诊断页：Cookie 有效性、保存目录权限、FFmpeg、NAS 路径、网络请求状态。

### 5.5 不并入的 dysync 能力

- 原独立登录页、原 Vue 管理端菜单、原移动端页面不保留。
- 原 SQLite/SqlSugar 数据结构不作为统一平台主数据结构，只做迁移来源。
- 原 Docker 路径 `/app/collect`、`/app/favorite` 等不直接暴露给用户，统一为平台存储目录模板。
- `dy.sync.lib.dll` 和 `dy.cookie.exe` 是二进制文件，未来开源前必须确认来源、授权、跨平台兼容性和可替换方案；不能无记录并入。
- 原默认账号密码、`db/pwd.txt` 重置机制不进入统一平台；统一平台只保留单管理员初始化和密码重置流程。

## 6. bili-sync 拆解

### 6.1 现有后端能力

代码位置：

- Rust 后端：`bili-sync/crates/bili_sync/src`
- 实体：`bili-sync/crates/bili_sync_entity/src/entities`
- 迁移：`bili-sync/crates/bili_sync_migration`
- Svelte 管理端：`bili-sync/web/src/routes`

源码基线：

```text
Version: 2.11.1
Runtime: Rust 2024 + Tokio
HTTP API: Axum, /api 前缀
Default bind: 0.0.0.0:12345
Database: {CONFIG_DIR}/data.sqlite
Config dir: BILI_SYNC_CONFIG_DIR 或系统配置目录/bili-sync
Auth: 首次启动生成 auth_token
Docker: scratch runtime，/app/.config/bili-sync volume
License: MIT
```

核心后端能力：

- B 站扫码登录：`api/routes/login`
- Credential 自动刷新：`bilibili/credential.rs`、`task/video_downloader.rs`
- 当前账号收藏夹、合集、关注 UP 主发现：`api/routes/me`
- 视频源管理：`api/routes/video_sources`
- 视频源类型：收藏夹、合集/列表、UP 主投稿、稍后再看
- 视频源过滤规则：`Rule`、`rule-editor`
- 视频下载任务调度：`DownloadTaskManager`
- 视频详情填充、分页下载、封面、NFO、UP 主头像：`workflow.rs`
- 并发下载、分块下载、FFmpeg 合并：`downloader.rs`
- 视频资产列表、下载状态重置、批量状态更新：`api/routes/videos`
- WebSocket 日志、任务状态、系统信息：`api/routes/ws`
- 全局配置：B 站凭据、质量、弹幕、跳过项、通知器、并发、限速、命名模板。
- 启动参数：`--scan-only`、`--log-level`、`--disable-credential-refresh`、`--config-dir`、`--ffmpeg-path`；原 `docs/args.md` 未完整反映当前源码，应以 `config/args.rs` 为准。
- 启动前会执行 `ffmpeg -version` 检查；FFmpeg 不存在会直接失败。

源码确认的主要 API：

```text
GET    /api/config
PUT    /api/config
POST   /api/config/notifiers/ping
POST   /api/login/qrcode/generate
GET    /api/login/qrcode/poll
GET    /api/me/favorites
GET    /api/me/collections
GET    /api/me/uppers
GET    /api/video-sources
GET    /api/video-sources/details
GET    /api/video-sources/{type}/default-path
PUT    /api/video-sources/{type}/{id}
DELETE /api/video-sources/{type}/{id}
POST   /api/video-sources/{type}/{id}/evaluate
POST   /api/video-sources/{type}/{id}/full-sync
POST   /api/video-sources/favorites
POST   /api/video-sources/collections
POST   /api/video-sources/submissions
GET    /api/videos
GET    /api/videos/{id}
POST   /api/videos/{id}/clear-and-reset-status
POST   /api/videos/{id}/reset-status
POST   /api/videos/{id}/update-status
POST   /api/videos/reset-status
POST   /api/videos/update-status
GET    /api/dashboard
POST   /api/task/download
WS     /api/ws
```

### 6.2 需要抽出的后端模块

建议抽成 `modules/bilibili`：

```text
modules/bilibili/
  account.py
  qr_login.py
  credential.py
  client.py
  source_discovery.py
  source_sync.py
  rules.py
  downloader.py
  danmaku.py
  nfo.py
  mapper.py
  config.py
```

模块职责：

- `qr_login.py`：复用 B 站二维码生成和轮询逻辑。
- `credential.py`：Credential 保存、检查、刷新。
- `source_discovery.py`：读取收藏夹、收藏合集、关注 UP 主。
- `source_sync.py`：统一处理收藏夹、合集、UP 主投稿、稍后再看。
- `rules.py`：迁移视频源过滤规则，映射到统一规则模型。
- `downloader.py`：下载视频、音频、封面、头像，执行 FFmpeg 合并。
- `danmaku.py`：弹幕下载和 ASS 渲染配置。
- `nfo.py`：媒体服务器 NFO 生成。
- `mapper.py`：将 B 站实体映射到统一平台对象。
- `config.py`：B 站模块配置校验。

Rust 代码质量较高，下载与 B 站接口逻辑可以优先保留为内部模块或库化实现。最终形态不保留原 Web UI 和独立 API，所有管理入口迁移到 `platform-api`。

### 6.3 现有实体映射

| bili-sync 实体 | 统一平台对象 | 说明 |
|---|---|---|
| `config` | `PlatformModuleConfig` | B 站全局配置 JSON |
| `favorite` | `RemoteCollectionSource` | 用户创建或收藏的收藏夹 |
| `collection` | `RemoteCollectionSource` | 合集/列表 |
| `submission` | `CreatorSubscription` | UP 主投稿同步 |
| `watch_later` | `RemoteCollectionSource` | 稍后再看 |
| `video` | `ContentItem` + `MediaAsset` | 视频主信息、作者、来源、有效性、下载状态 |
| `page` | `MediaPage` | 分 P 视频、分页路径、分页下载状态 |

关键字段必须进入迁移映射：

- `config`：完整 JSON，含 `auth_token`、`bind_address`、`credential`、`filter_option`、`danmaku_option`、`skip_option`、`interval`、`upper_path`、`nfo_time_type`、`concurrent_limit`、默认路径模板、通知器。
- `favorite/collection/submission/watch_later`：`path`、`latest_row_at`、`rule`、`enabled`；`submission` 还包含 `use_dynamic_api`。
- `video`：`bvid`、`upper_id/name/face`、`staff`、`path`、`category`、`intro`、`cover`、`ctime/pubtime/favtime`、`download_status`、`valid`、`should_download`、`tags`、`single_page`。
- `page`：`cid`、`pid`、`name`、`width/height`、`duration`、`path`、`image`、`download_status`。

### 6.4 必须进入统一前端的 bili-sync 能力

- B 站账号页：扫码登录、Credential 状态、自动刷新状态、手动刷新、重新登录。
- B 站同步源发现页：我的收藏夹、收藏的合集/列表、关注 UP 主，支持订阅。
- B 站同步源管理页：收藏夹、合集、UP 主投稿、稍后再看，包含路径、启停、最近同步时间。
- B 站规则配置页：每个同步源的过滤规则，规则评估，是否下载。
- B 站下载配置页：视频质量、音频质量、编码优先级、杜比/HDR/Hi-Res 开关、CDN 排序。
- B 站弹幕配置页：字体、字号、透明度、描边、轨道、滚动/底部弹幕比例、时间偏移、粗体。
- B 站高级配置页：同步周期、Cron/间隔、视频/分页并发、请求限速、分块下载、NFO 时间类型。
- B 站通知配置页：Telegram、Webhook、测试通知、忽略常见错误。
- B 站视频资产页：视频、分 P、来源筛选、下载状态、状态重置、批量更新。
- B 站任务状态页：下载任务运行状态、下次执行时间、手动触发。
- B 站系统诊断页：FFmpeg、存储目录、磁盘、内存、CPU、请求风控状态。

### 6.5 不并入的 bili-sync 能力

- 原 Svelte 管理端、原 token 鉴权、原 Axum API 路由不对用户保留。
- 原 SQLite/SeaORM 表结构不作为平台主库结构，只作为迁移参考。
- 原配置文件目录和 `CONFIG_DIR` 逻辑不直接暴露，由统一配置中心替代。
- 原通知器 token、Webhook headers、Credential 必须迁移到统一加密凭证表，日志展示时脱敏。

## 7. 统一数据模型草案

建议 PostgreSQL 第一批表：

```text
platform_account
  id, platform, display_name, external_user_id, status, created_at, updated_at

account_credential
  id, account_id, credential_type, encrypted_payload, expires_at, last_checked_at, status

remote_source
  id, platform, account_id, source_type, external_id, external_owner_id,
  name, path_template, enabled, full_sync, latest_remote_at, latest_sync_at

creator_subscription
  id, platform, account_id, external_creator_id, sec_uid_or_mid,
  name, avatar_url, signature, enabled, full_sync, custom_folder

sync_task
  id, platform, account_id, source_id, task_type, schedule, status,
  last_run_at, last_finish_at, next_run_at, last_error

content_item
  id, platform, external_content_id, source_id, creator_id,
  title, description, url, cover_url, published_at, collected_at, raw_metrics

media_asset
  id, content_item_id, asset_type, storage_root, relative_path,
  file_size, resolution, download_status, transcribe_status, analysis_status

media_page
  id, media_asset_id, external_page_id, page_index, title, relative_path, download_status

source_rule
  id, source_id, rule_json, enabled, last_evaluated_at

module_config
  id, platform, config_key, config_json, updated_at

task_log
  id, platform, task_id, account_id, level, message, created_at
```

## 8. 统一 API 草案

平台 API 不按原项目暴露，而按平台语义设计：

```text
GET    /api/accounts
POST   /api/accounts/{platform}/login/start
GET    /api/accounts/{platform}/login/poll
POST   /api/accounts/{id}/validate
POST   /api/accounts/{id}/disable

GET    /api/sources?platform=bilibili|douyin
GET    /api/sources/discover?platform=...
POST   /api/sources/subscribe
PUT    /api/sources/{id}
DELETE /api/sources/{id}
POST   /api/sources/{id}/sync
POST   /api/sources/{id}/full-sync

GET    /api/sync-tasks
POST   /api/sync-tasks/{id}/run
GET    /api/sync-tasks/{id}/status

GET    /api/media-assets
GET    /api/media-assets/{id}
POST   /api/media-assets/{id}/retry-download
DELETE /api/media-assets/{id}

GET    /api/module-configs/{platform}
PUT    /api/module-configs/{platform}

GET    /api/logs
GET    /api/events/stream
GET    /api/diagnostics
```

## 9. 统一前端页面清单

本轮两个项目调查后，统一前端至少需要以下页面：

### 9.1 账号管理

- 抖音账号：浏览器自动登录、Cookie 兜底导入、sec_user_id、账号状态、启停。
- B 站账号：扫码登录、Credential 展示、自动刷新状态、重新登录。

### 9.2 同步源管理

- 抖音来源：收藏、喜欢、关注博主、收藏夹、合集、短剧。
- B 站来源：收藏夹、合集/列表、UP 主投稿、稍后再看。
- 公共能力：路径模板、启停、全量同步、手动同步、最近同步时间。

### 9.3 创作者管理

- 抖音博主：关注列表同步、非关注博主手动添加、启停、全量同步、自定义文件夹。
- B 站 UP 主：关注 UP 主发现、订阅投稿、动态 API 开关、规则过滤。

### 9.4 视频资产库

- 跨平台列表：标题、平台、作者、来源、发布时间、保存路径、下载状态、转录状态、分析状态。
- 操作：播放、打开路径、重试下载、删除记录、删除文件、重新入队。

### 9.5 平台模块配置

- 抖音配置：同步周期、批量数、仅同步新视频、图文/动态视频、视频编码、命名模板、NFO。
- B 站配置：质量、编码、弹幕、跳过项、CDN、并发、限速、分块下载、NFO、通知器。

### 9.6 调度与日志

- 任务列表：平台、账号、来源、状态、上次运行、下次运行、耗时、错误。
- 日志：平台、账号、任务、级别、日期过滤，实时流。

### 9.7 存储与诊断

- 存储根目录：本机/NAS 路径、Windows UNC、权限检测、容量检测。
- 依赖诊断：Docker、PostgreSQL、FFmpeg、浏览器自动化、本地网络、目标平台访问。

## 10. 抽离实施顺序

### P1：接口与数据模型先行

- 建立统一 PostgreSQL 表。
- 建立 `modules/douyin`、`modules/bilibili` 空模块和统一接口。
- 前端只接入统一 API，不接入原 API。

### P2：临时适配原项目能力

- `dysync.net`：临时通过内部 HTTP 或命令适配账号、关注、收藏、视频、日志能力。
- `bili-sync`：临时通过内部 HTTP 或库化 Rust 服务适配扫码、视频源、下载任务、日志能力。
- 适配层只用于迁移，不作为最终公开架构。

### P3：核心逻辑抽离

- 优先抽离账号/凭证、同步源发现、任务状态、资产映射。
- 第二批抽离下载、FFmpeg 合并、规则过滤、日志。
- 第三批抽离通知器、NFO、弹幕等增强能力。

### P4：移除原独立应用形态

- 删除原 Web UI 暴露。
- 删除原独立认证入口。
- 删除原数据库作为主库的依赖。
- 保留必要源代码、版权声明、授权记录和内部模块测试。

## 11. 风险与处理

- `dysync.net` 包含 `lib/dy.sync.lib.dll` 和 `dy.cookie.exe`，需要确认是否有源码、再分发授权和跨平台方案。若无法确认，必须重写相关能力或仅作本地可选适配。
- 抖音自动登录能力现项目不完整，需要新增浏览器自动化实现，并提供失败诊断。
- `bili-sync` Rust 能力成熟，不建议盲目改写为 Python；可以通过内部模块服务或 FFI/CLI 方式过渡，最终由统一 API 接管管理面。
- 两个项目的路径模型都偏单项目，需要统一成 `{storage_root}/{platform}/{creator}/{date}/{content_id}` 类模板，并支持 Windows/UNC。
- 两个项目都有自己的任务调度，需要统一收敛到平台调度中心，避免重复运行和状态不一致。

## 12. 本轮最终架构设计

最终形态：

```text
Unified Workbench Frontend
  -> platform-api (FastAPI)
      -> accounts module
      -> storage module
      -> scheduler module
      -> media_assets module
      -> douyin module
          -> douyin account / login / source / sync / download adapters
      -> bilibili module
          -> bilibili qr login / source / rules / sync / download adapters
      -> logs/events module
      -> diagnostics module
  -> PostgreSQL
  -> Local/NAS Storage
  -> FFmpeg
  -> browser automation runtime
```

用户只看到一个工作台。抖音和 B 站都是平台内的功能模块，不再保留原应用的独立前端、独立账号系统和独立配置页。后端可以在过渡期保留原技术实现，但必须被统一 API、统一调度、统一日志和统一数据库包裹。

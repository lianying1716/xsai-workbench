# 五篇后端架构文档最终复盘

## 1. 复盘范围

本文件复盘以下五篇文档，并逐项回查本地源码，不使用未验证推测：

- `docs/backend-module-architecture-douyin-bilibili.md`
- `docs/backend-module-architecture-mediacrawler.md`
- `docs/backend-module-architecture-faster-whisper.md`
- `docs/backend-module-architecture-wechat-article-exporter.md`
- `docs/backend-module-architecture-yt-dlp.md`

复盘目标是为统一后端主框架、功能路由和统一前端工作台页面提供最终输入。

## 2. 源码基线

| 项目 | 本地提交/版本 | 技术栈 | 许可 | 必须确认的事实 |
|---|---|---|---|---|
| `dysync.net` | `e48bada60` | .NET 6、SqlSugar、Quartz、Serilog、JWT、Vue | MIT | 监听 `10101`；默认账号 `douyin/douyin2026`；含 `lib/dy.sync.lib.dll` 和 `dy.cookie.exe` 二进制文件；Docker 安装 FFmpeg。 |
| `bili-sync` | `3ac56f6c4` / `2.11.1` | Rust 2024、Tokio、Axum、SeaORM SQLite、Svelte 5 | MIT | 默认 `0.0.0.0:12345`；数据库 `data.sqlite`；首次生成 `auth_token`；启动强依赖 FFmpeg。 |
| `MediaCrawler` | `165776886` / `0.1.0` | Python `>=3.11`、Playwright/CDP、httpx、FastAPI WebUI、SQLAlchemy | NON-COMMERCIAL LEARNING LICENSE 1.1 | CLI 支持 `postgres` 和 `--save_data_path`；WebUI schema 不支持 `postgres/save_data_path/代理/CDP` 等完整配置。 |
| `faster-whisper` | `ed9a06cd8` / `1.2.1` | Python `>=3.9`、CTranslate2、PyAV、ONNX Runtime | MIT | 不是服务；无 API/DB/队列；转录 generator 必须由平台 worker 消费。 |
| `wechat-article-exporter` | `757e6bf1f` / `2.3.18` | Node `>=22`、Nuxt 3、Vue、Nitro、Dexie、Puppeteer | MIT | `ssr:false`；服务端 API 27 个；主数据在 IndexedDB；Cookie KV 未加密且过期判断 TODO。 |
| `yt-dlp` | `5faffa999` / `2026.03.17` | Python `>=3.10`、`yt_dlp.YoutubeDL` | Unlicense | extractor 文件 1022 个；测试文件 33 个；自更新、插件、Exec、file URL 必须默认禁用。 |

## 3. 统一后端模块结论

主框架应采用 `platform-api` 统一入口，原项目不再对用户暴露独立 API、独立前端、独立认证和独立配置。

第一批后端模块：

```text
accounts
storage
media_assets
scheduler
logs_events
diagnostics
douyin
bilibili
crawler
wechat_articles
media_download
transcription
analysis
skills_api
proxy
browser_runtime
```

原项目只作为能力来源：

- `dysync.net` -> `modules/douyin`，负责抖音账号内收藏、喜欢、关注博主、合集、短剧同步。
- `bili-sync` -> `modules/bilibili`，负责 B 站扫码、收藏夹、合集/列表、UP 主投稿、稍后再看、高质量下载。
- `MediaCrawler` -> `modules/crawler`，负责多平台关键词、详情、创作者公开内容抓取。
- `wechat-article-exporter` -> `modules/wechat_articles`，负责微信公众号文章、合集、评论、阅读量、导出。
- `yt-dlp` -> `modules/media_download`，负责通用 URL 探测和下载。
- `faster-whisper` -> `modules/transcription`，负责本地转录引擎适配。

## 4. 统一路由边界

推荐主路由：

```text
/api/accounts
/api/sources
/api/sync-tasks
/api/media-assets
/api/crawler
/api/wechat
/api/media-download
/api/transcription
/api/storage
/api/proxy
/api/browser-runtime
/api/module-configs
/api/logs
/api/events/stream
/api/diagnostics
/api/skills/*
```

路由原则：

- 不复刻原项目路由，例如 `dysync.net/api/Config/*`、`bili-sync/api/video-sources/*`、`MediaCrawler/api/crawler/start`。
- 外部 skill 只开放高层受控能力，不允许传任意服务器路径、任意 CLI 参数、任意 headers、任意 shell 命令。
- 所有账号、Cookie、Credential、token 统一进入 `accounts` 和 `account_credential`，必须加密、脱敏、审计。

## 5. 统一数据模型

必须先落地的共享表：

```text
platform_account
account_credential
credential_audit_log
storage_root
storage_profile
creator_profile
remote_source
creator_subscription
sync_task
task_log
content_item
content_metric
content_comment
media_asset
media_page
raw_payload
```

模块专用表：

```text
crawl_task / crawl_run / crawl_source
wechat_article / wechat_comment / wechat_resource / wechat_export_job
media_download_job / media_download_run / media_download_artifact
transcription_model / transcription_profile / transcription_job / transcript_document / transcript_segment / transcript_word
```

所有文件路径必须通过 `storage_root + relative_path` 保存，支持 Linux/macOS、Windows 盘符和 Windows UNC。外部 API 不得提交绝对输出路径。

## 6. 统一前端页面

统一工作台至少需要：

- 总览看板：任务、账号状态、下载量、转录量、分析量、磁盘和错误。
- 账号与登录：抖音浏览器/Cookie、B 站扫码、微信后台扫码、抓取平台 Cookie。
- 存储/NAS：根目录、临时目录、路径模板、权限、容量、UNC/挂载诊断。
- 关键词抓取：平台、关键词、排序、上限、评论、媒体、周期、启停。
- 同步源/创作者：抖音关注与收藏，B 站收藏夹/合集/UP 主，路径和规则配置。
- 微信文章：公众号、文章、合集、Credential、评论/指标、导出、预览。
- 通用下载：URL 探测、下载队列、Download/Storage/Cookie/Network Profile。
- 转录：任务队列、模型管理、Profile、详情、导出、硬件诊断。
- 平台配置：抖音、B 站、MediaCrawler、微信、yt-dlp、Whisper 分模块配置。
- 日志与诊断：实时日志、历史日志、依赖、浏览器、FFmpeg、PostgreSQL、网络、代理。
- Skill/API：API Key、权限范围、调用日志、限流。

## 7. 必须重写或禁止项

- `dysync.net` 默认密码不能进入正式平台；首次启动必须强制设置管理员密码。
- `dysync.net/lib/dy.sync.lib.dll` 和 `dysync.net/dy.cookie.exe` 未看到源码，开源前必须确认授权、平台兼容性或替换。
- `bili-sync` 原 `auth_token` 鉴权和 Axum API 不作为最终用户 API。
- `MediaCrawler` WebUI 单例子进程管理不可作为最终任务系统；CLI 可做第一阶段适配。
- `MediaCrawler` 非商业许可证与未来开源/商业使用目标冲突，必须以授权文件为准。
- `wechat-article-exporter` 的 `_debug` Cookie 导出、未加密 KV、外部 eval API、公共代理节点、浏览器 IndexedDB 主存储不可保留。
- `yt-dlp` 的插件、自更新、`ExecPP`、`enable_file_urls`、任意 postprocessor 参数、任意外部下载器参数默认禁用。
- `faster-whisper` 不能直接暴露 Python API；必须通过任务队列和 worker 封装。

## 8. 最终落地顺序

1. 建立统一数据模型、存储模块、账号/凭证模块、任务/日志模块。
2. 建立统一前端框架和路由，不接入原项目前端。
3. 优先接入 `bili-sync` 和 `dysync.net` 的账号同步能力，形成视频资产库。
4. 接入 `MediaCrawler` 关键词抓取，写入统一 `content_item/media_asset`。
5. 接入 `faster-whisper` 转录队列，完成视频到文本闭环。
6. 接入 `wechat_articles` 和 `media_download`，补齐文章、通用 URL、外部 skill 能力。
7. 最后做分析模块和统一看板，所有模块只读统一数据模型。

## 9. 文档修正结果

本轮已对五篇文档做最终复盘补充：

- 补齐 `dysync.net` 和 `bili-sync` 的源码基线、路由、实体、默认凭据、运行端口、配置与前端页面证据。
- 标记 `MediaCrawler` CLI 与 WebUI 配置能力不一致的问题。
- 标记 `wechat-article-exporter` 的 Cookie、eval、IndexedDB、浏览器导出风险。
- 保持 `faster-whisper` 与 `yt-dlp` 的模块边界，避免把底层库误设计成业务服务。
- 统一五篇文档对 `platform-api`、PostgreSQL、本地/NAS 存储、Docker Compose、单管理员、外部 skill/API 的要求。

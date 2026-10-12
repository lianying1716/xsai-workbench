# MediaCrawler 后端架构审查与模块抽离设计

> **⚠️ 状态说明（2026-10-08 更新）**：本文是**上游能力调研留痕**，写于抽离之前。
> 文中第 14 节等处的「平台多选：…微博、贴吧…」是 **MediaCrawler 上游自身**支持的平台，
> **不代表**统一平台 `platform-api` 的现状。
>
> **当前 `platform-api` 只接入 5 个采集平台：B站 / 抖音 / 小红书 / 快手 / 知乎。**
> 微博、贴吧曾一度误导入，已于 2026-10-08 全部移除（`app/modules/crawler/`、账号适配器、
> 前端平台列表均已删除），**不要据本文再重新引入这两个渠道**。以 `platform-api` 仓库代码为准。

## 1. 文档目标

本文档基于对 `/path/to/xsai-workbench/MediaCrawler` 的源码审查，整理其现有能力、运行流程、平台模块、数据存储、登录、代理、WebUI/API、测试与合规风险，并定义其并入统一平台时的后端模块设计和前端配置页面清单。

本文档只覆盖 `MediaCrawler`。抖音账号收藏/关注同步仍以 `dysync.net` 拆解结果为主，B 站账号收藏夹/UP 主投稿同步仍以 `bili-sync` 拆解结果为主。`MediaCrawler` 在统一平台中的主定位是“多平台关键词、详情、创作者公开内容抓取模块”。

## 2. 总体结论

- `MediaCrawler` 是 Python + Playwright/CDP + httpx 的多平台异步爬虫框架，支持小红书、抖音、快手、B 站、微博、贴吧、知乎。
- 统一抓取模式为 `search`、`detail`、`creator`，适合承接“指定关键词定期抓热门内容”和“指定链接/作者补抓”的需求。
- 当前项目具备 CLI、FastAPI WebUI、子进程管理、文件/数据库/MongoDB/Excel 存储、代理池、二维码/Cookie 登录、浏览器登录态保存等能力。
- 当前 WebUI/API 只能作为过渡参考，不能作为最终管理工作台：它是单进程单任务模型，配置项不完整，缺少调度、账号管理、统一数据库、NAS 路径管理和多任务状态。
- 本轮复盘确认 CLI 与 WebUI 配置存在实证差异：`cmd_arg/arg.py` 已支持 `postgres`、`--save_data_path`、代理、并发等参数，但 `api/schemas/crawler.py` 的 `SaveDataOptionEnum` 不含 `postgres`，启动请求也未暴露保存路径、代理、CDP、最大并发等关键字段；最终前端必须以 CLI/配置源码能力为准，不能以现有 WebUI schema 为准。
- 最终应抽离为统一平台的 `crawler` 模块，由 `platform-api` 统一认证、调度、日志、配置、存储和数据分析。
- `MediaCrawler` 使用 `NON-COMMERCIAL LEARNING LICENSE 1.1`。虽然授权已申请，正式合并和未来开源前仍必须归档授权凭据、允许范围、署名要求、再分发边界和商业使用边界。

## 3. 现有项目结构

关键目录：

```text
MediaCrawler/
  main.py                     # CLI 主入口和 CrawlerFactory
  cmd_arg/arg.py              # Typer 参数解析
  config/                     # 全局与平台配置
  base/base_crawler.py        # 抽象爬虫、登录、存储、客户端接口
  media_platform/             # 七个平台实现
  store/                      # 平台存储实现和媒体文件保存
  database/                   # SQLAlchemy ORM、SQLite/MySQL/Postgres
  proxy/                      # 代理池与代理服务商
  cache/                      # 内存/Redis 缓存
  tools/                      # 浏览器、CDP、文件、二维码、词云、滑块工具
  api/                        # 自带 FastAPI WebUI API
  api/webui/                  # 已构建前端静态产物
  test/、tests/               # 单元测试和部分集成测试
```

核心入口：

- `main.py`：根据 `config.PLATFORM` 创建爬虫，支持 `--init_db` 初始化数据库，结束后刷新 Excel 和生成词云。
- `cmd_arg/arg.py`：支持平台、登录方式、抓取类型、关键词、指定 ID、创作者 ID、评论、无头模式、保存方式、保存路径、代理参数。
- `api/main.py`：自带 WebUI API，运行命令为 `uvicorn api.main:app --port 8080 --reload`。
- `api/services/crawler_manager.py`：通过 `uv run python main.py ...` 启动子进程，并读取 stdout 作为日志。

## 4. 运行流程

当前 CLI 流程：

```text
parse_cmd()
  -> 修改全局 config
  -> CrawlerFactory.create_crawler(platform)
  -> crawler.start()
      -> 初始化代理
      -> 启动 Playwright 或 CDP 浏览器
      -> 创建平台 API Client
      -> 检查登录态，不通过则二维码/手机号/Cookie 登录
      -> 根据 CRAWLER_TYPE 执行 search/detail/creator
      -> 调用 store 写入内容、评论、创作者、媒体文件
  -> 可选 Excel flush
  -> 可选评论词云
```

当前 WebUI 流程：

```text
POST /api/crawler/start
  -> CrawlerManager._build_command()
  -> subprocess.Popen(["uv", "run", "python", "main.py", ...])
  -> stdout 日志进入内存列表和 WebSocket 队列
```

这个流程可用于第一阶段适配，但最终必须改成统一任务队列。原因是当前只有一个全局 `crawler_manager`，不能同时运行多个任务，任务状态也不会持久化到 PostgreSQL。

## 5. 支持平台与能力矩阵

| 平台 | 代码目录 | search | detail | creator | 评论 | 子评论 | 媒体下载 | 关键配置 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 小红书 | `media_platform/xhs` | 是 | 是 | 是 | 是 | 是 | 图片/视频 | `SORT_TYPE`、`XHS_INTERNATIONAL`、`xsec_token` |
| 抖音 | `media_platform/douyin` | 是 | 是 | 是 | 是 | 是 | 图片/视频 | `PUBLISH_TIME_TYPE`、短链解析、滑块 |
| 快手 | `media_platform/kuaishou` | 是 | 是 | 是 | 是 | 是 | 当前主要元数据 | `KS_SPECIFIED_ID_LIST`、GraphQL/V2 接口 |
| B 站 | `media_platform/bilibili` | 是 | 是 | 是 | 是 | 是 | 基础视频 | `BILI_SEARCH_MODE`、时间范围、`BILI_QN` |
| 微博 | `media_platform/weibo` | 是 | 是 | 是 | 是 | 部分支持 | 图片 | `WEIBO_SEARCH_TYPE`、长文补全 |
| 贴吧 | `media_platform/tieba` | 是 | 是 | 是 | 是 | 是 | 无 | 关键词、贴吧名、作者主页 |
| 知乎 | `media_platform/zhihu` | 是 | 是 | 是 | 是 | 是 | 无 | 回答/文章/视频详情、作者内容 |

平台能力说明：

- 小红书：支持关键词搜索、笔记详情、作者主页笔记、评论、图片和视频保存；详情/创作者 URL 强依赖 `xsec_token`。
- 抖音：支持关键词搜索、指定视频 URL/短链、创作者主页视频、评论、图文和视频保存；手机号登录有滑块逻辑，但一期不应作为主路径。
- 快手：支持搜索、指定视频、创作者视频和评论；未看到完整本地媒体二进制下载闭环，统一平台先按元数据与评论抓取处理。
- B 站：支持关键词普通搜索、按时间范围搜索、指定 BV/AV、UP 主投稿、UP 主粉丝/关注/动态抓取、基础视频下载；收藏夹/稍后再看/合集同步应由 `bili-sync` 承担。
- 微博：支持移动端搜索、默认/实时/热门/视频搜索、指定微博、博主微博、长文补全、图片保存和评论。
- 贴吧：支持关键词搜索、指定贴吧名帖子、指定帖子、作者主页帖子和评论，包含从百度首页进入贴吧与反检测脚本。
- 知乎：支持关键词搜索、回答/文章/视频详情、作者信息和回答抓取；客户端有文章/视频作者抓取方法，但核心流程默认只抓回答。

## 6. 登录与浏览器运行时

现有登录方式：

- `qrcode`：七个平台都有二维码登录路径，二维码通过本地函数展示，不适合直接嵌入统一前端。
- `cookie`：七个平台均支持将 Cookie 写入浏览器上下文。
- `phone`：小红书、抖音有较完整流程，其他平台多为 `pass` 或 TODO；且当前 `login_phone` 在爬虫启动时传空字符串。

浏览器能力：

- 默认 `ENABLE_CDP_MODE = True`，通过 `tools/cdp_browser.py` 连接或启动本机 Chrome/Edge。
- `tools/browser_launcher.py` 支持 Windows、macOS、Linux 浏览器路径探测和远程调试端口。
- `SAVE_LOGIN_STATE = True` 时保存到 `browser_data/{platform}_user_data_dir`。
- 标准 Playwright 模式会注入 `libs/stealth.min.js`，抖音/贴吧有额外反检测处理。

并入要求：

- 抽出统一 `BrowserRuntimeService`，集中管理浏览器路径、CDP 端口、用户数据目录、无头模式、清理策略。
- 抽出 `LoginSessionService`，前端能看到二维码、等待扫码、登录成功、失败原因、Cookie 有效性。
- 手机号登录不作为第一期默认能力；如保留，必须改为统一短信验证码接收服务，不能依赖当前进程内内存缓存。
- Cookie/Token 必须加密入库，前端只展示脱敏状态。

## 7. 配置审查

全局配置在 `config/base_config.py`：

- 平台与任务：`PLATFORM`、`KEYWORDS`、`LOGIN_TYPE`、`CRAWLER_TYPE`。
- 浏览器：`HEADLESS`、`SAVE_LOGIN_STATE`、`ENABLE_CDP_MODE`、`CDP_DEBUG_PORT`、`CUSTOM_BROWSER_PATH`、`CDP_CONNECT_EXISTING`、`AUTO_CLOSE_BROWSER`。
- 存储：`SAVE_DATA_OPTION`、`SAVE_DATA_PATH`、`USER_DATA_DIR`。
- 限制：`START_PAGE`、`CRAWLER_MAX_NOTES_COUNT`、`MAX_CONCURRENCY_NUM`、`CRAWLER_MAX_SLEEP_SEC`。
- 评论和媒体：`ENABLE_GET_MEIDAS`、`ENABLE_GET_COMMENTS`、`CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES`、`ENABLE_GET_SUB_COMMENTS`、`ENABLE_GET_WORDCLOUD`。
- 代理：`ENABLE_IP_PROXY`、`IP_PROXY_POOL_COUNT`、`IP_PROXY_PROVIDER_NAME`、`STATIC_PROXY_URL`。

平台配置：

- B 站：`MAX_NOTES_PER_DAY`、`START_DAY`、`END_DAY`、`BILI_SEARCH_MODE`、`BILI_QN`、`CREATOR_MODE`、粉丝/动态上限。
- 抖音：`PUBLISH_TIME_TYPE`、指定视频、指定创作者。
- 小红书：`SORT_TYPE`、指定笔记 URL、指定创作者 URL、国际版开关。
- 微博：`WEIBO_SEARCH_TYPE`、长文补全开关。
- 贴吧：指定帖子、贴吧名、创作者主页。
- 知乎：指定内容 URL、创作者 URL。

当前 WebUI 请求模型不完整：`api/schemas/crawler.py` 未包含 `postgres` 保存方式，也未暴露 `save_data_path`、代理、CDP、最大并发、B 站时间范围、B 站搜索模式、小红书排序、微博搜索类型等关键配置。因此最终前端不能复用其配置面。

## 8. 存储与数据模型审查

当前支持保存方式：

- 文件：CSV、JSON、JSONL、Excel。
- SQL：SQLite、MySQL、PostgreSQL。
- NoSQL：MongoDB。
- 媒体文件：小红书、抖音、B 站、微博各自有本地文件保存实现。

主要问题：

- SQL 表是按平台拆分的，如 `xhs_note`、`douyin_aweme`、`bilibili_video`、`weibo_note`、`tieba_note`、`zhihu_content`，不适合作为统一平台主模型。
- 记录缺少统一 `task_id`、`run_id`、`source_id`、`account_id`，只用 `source_keyword` 追踪关键词来源。
- 文件路径使用 `SAVE_DATA_PATH/{platform}/{type}` 或 `data/{platform}/{type}`，没有统一资产目录模板和路径校验。
- `api/routers/data.py` 固定读取 `MediaCrawler/data`，即使 CLI 支持 `--save_data_path`，WebUI 也无法查看外部/NAS 保存路径。
- Postgres 已在 CLI 和 DB 层接入，但 WebUI 配置枚举未暴露。
- MongoDB、MySQL 可作为参考，不建议作为统一平台第一期主存储；正式主库仍应是 PostgreSQL。

统一平台应改为：

```text
content_item        # 跨平台内容主表
content_metric      # 指标快照
content_comment     # 评论与父子评论
creator_profile     # 作者主页信息
crawl_task          # 关键词/detail/creator 任务定义
crawl_run           # 每次执行实例
crawl_source        # 关键词、URL、创作者来源
media_asset         # 视频、图片、封面、音频、文档
raw_payload         # 可选原始 JSON 归档
task_log            # 任务日志
platform_account    # 抓取账号或浏览器态
proxy_profile       # 代理配置
browser_profile     # 浏览器运行配置
```

## 9. 代理与缓存

当前代理能力：

- `kuaidaili`：从快代理 API 获取，使用 `KDL_SECERT_ID`、`KDL_SIGNATURE`、`KDL_USER_NAME`、`KDL_USER_PWD`。
- `wandouhttp`：从豌豆 HTTP API 获取，使用 `WANDOU_APP_KEY`。
- `static`：支持 `http://user:pass@host:port` 或 `https://host:port`。
- 代理池会按过期时间刷新，并可用 `https://echo.apifox.cn/` 验证 IP。

并入要求：

- 代理配置必须进入统一前端，支持禁用、静态代理、服务商代理、测试代理、过期时间、失败日志。
- 验证地址不能硬编码为外部服务；应允许配置或使用目标平台前的轻量连接检测。
- 代理密钥必须加密保存，日志中不能打印完整代理 URL 或密钥。
- 代理池应按任务或平台绑定，避免不同平台互相污染状态。

## 10. 自带 API 与 WebUI 审查

现有 API：

```text
GET  /api/health
GET  /api/env/check
GET  /api/config/platforms
GET  /api/config/options
POST /api/crawler/start
POST /api/crawler/stop
GET  /api/crawler/status
GET  /api/crawler/logs
GET  /api/data/files
GET  /api/data/files/{file_path}
GET  /api/data/download/{file_path}
GET  /api/data/stats
WS   /api/ws/logs
WS   /api/ws/status
```

可复用点：

- 子进程启动命令拼装思路。
- stdout 日志解析和 WebSocket 推送思路。
- 环境检测入口思路。
- 数据文件预览和下载的安全路径检查思路。

不保留点：

- 原 WebUI 静态产物不进入统一工作台，且源码不在当前 `api/webui` 中，维护成本高。
- 原 WebUI 含作者宣传、外链和许可证确认弹窗，不符合统一产品管理台形态。
- 原 API 不做认证，不满足单管理员工作台和外部 skill/API 鉴权要求。
- 单例 `CrawlerManager` 不满足多任务、定时任务、持久任务日志。

## 11. 需要抽出的后端模块

建议统一平台新增：

```text
platform-api/app/modules/crawler/
  registry.py
  schemas.py
  service.py
  scheduler.py
  run_manager.py
  result_writer.py
  browser_runtime.py
  login_sessions.py
  proxy_profiles.py
  storage_mapper.py
  legacy_mediacrawler.py
  platforms/
    xhs.py
    douyin_public.py
    kuaishou.py
    bilibili_public.py
    weibo.py
    tieba.py
    zhihu.py
```

模块职责：

- `registry.py`：平台能力注册，声明支持的任务类型、配置字段、登录方式和限制。
- `schemas.py`：统一任务、运行、结果、评论、作者、媒体资产 DTO。
- `service.py`：创建任务、校验配置、启动一次抓取、停止任务、查询状态。
- `scheduler.py`：周期任务调度，统一管理 Cron/间隔、重试、并发。
- `run_manager.py`：任务实例生命周期，替代当前全局子进程单例。
- `result_writer.py`：把平台回调结果写入统一 PostgreSQL 和资产目录。
- `browser_runtime.py`：CDP/Playwright、浏览器路径、用户数据目录、无头模式。
- `login_sessions.py`：二维码/Cookie 登录态、账号状态、凭证校验。
- `proxy_profiles.py`：代理服务商、静态代理、测试和运行绑定。
- `storage_mapper.py`：把现有平台字段映射到统一 `content_item`、`content_comment`、`creator_profile`。
- `legacy_mediacrawler.py`：第一阶段通过 CLI 子进程适配现有项目，第二阶段逐步删除。

## 12. 统一模块接口

建议后端接口抽象为：

```text
CrawlerPlatformAdapter
  validate_config(config)
  ensure_login(account_id, browser_profile_id)
  run_search(task, run_context)
  run_detail(task, run_context)
  run_creator(task, run_context)
  stop(run_id)

CrawlerResultWriter
  write_content(platform, item, run_context)
  write_comment(platform, comment, run_context)
  write_creator(platform, creator, run_context)
  write_media(platform, media_ref, run_context)
  write_raw_payload(platform, payload, run_context)

BrowserRuntimeService
  prepare_profile(platform, account_id)
  start_login(platform, login_type)
  poll_login(session_id)
  close_profile(profile_id)

ProxyService
  test_proxy(profile_id)
  acquire_proxy(task_id, platform)
  refresh_proxy(task_id)
```

第一阶段可由 `legacy_mediacrawler.py` 把统一任务转换为 CLI 参数，例如：

```text
uv run python main.py
  --platform xhs
  --lt qrcode
  --type search
  --keywords "关键词1,关键词2"
  --save_data_option postgres
  --save_data_path /mnt/nas/xsai-content/raw
```

但最终应将现有平台 `client.py`、`core.py`、`login.py`、`store` 回调拆入平台适配器，直接写统一库，避免通过 stdout 和临时文件反查结果。

## 13. 与抖音、B 站专用模块的关系

统一平台中需要明确职责边界：

- `modules/douyin`：负责账号收藏、喜欢、关注博主、合集、短剧、视频同步下载，来源是 `dysync.net` 拆解。
- `modules/bilibili`：负责 B 站账号扫码、收藏夹、合集、UP 主投稿、稍后再看、规则过滤和高质量下载，来源是 `bili-sync` 拆解。
- `modules/crawler/platforms/douyin_public.py`：只负责抖音公开搜索、指定视频、指定作者公开内容抓取。
- `modules/crawler/platforms/bilibili_public.py`：只负责 B 站公开搜索、指定视频、指定 UP 公开内容抓取。

这样可以避免抖音/B 站能力重复实现，也能让关键词抓取和账号同步在同一个资产库汇合。

## 14. 必须进入统一前端的页面

### 14.1 关键词抓取任务

- 平台多选：小红书、抖音、快手、B 站、微博、贴吧、知乎。
- 关键词列表、热门/最新/综合排序、抓取上限、起始页、定时周期、启停。
- 评论、子评论、媒体下载、原始 payload 归档开关。
- 每个平台的配置提示和 URL 校验。

### 14.2 指定内容补抓

- 平台、内容 URL/ID 批量输入。
- 自动识别 BV/AV、抖音短链、小红书 `xsec_token`、贴吧帖子 ID、知乎回答/文章/视频 URL。
- 抓取内容、评论、媒体文件的开关。

### 14.3 创作者抓取

- 创作者主页 URL/ID 批量输入。
- 抓取作者资料、作品列表、作品详情、评论。
- B 站需区分“抓投稿视频”和“抓粉丝/关注/动态”；后者不是视频资产主流程，默认关闭。

### 14.4 平台参数页

- 小红书：排序、国际版/国内版、`xsec_token` 校验说明。
- 抖音：发布时间范围、短链解析状态、滑块风险提示。
- 快手：创作者 URL、评论上限、接口异常提示。
- B 站：搜索模式、时间范围、每日上限、视频质量、创作者模式。
- 微博：搜索类型、长文补全、图片下载。
- 贴吧：关键词搜索、贴吧名抓取、排序、帖子类型。
- 知乎：内容类型、时间范围、排序；当前核心流程未完全暴露这些字段，抽离时补齐。

### 14.5 账号与登录态

- 每个平台账号/浏览器 profile 状态。
- 启动二维码登录、Cookie 导入、登录态检查、重新登录、清理浏览器态。
- Cookie 脱敏显示和过期/失效提醒。

### 14.6 浏览器与代理

- CDP 开关、调试端口、浏览器路径、用户数据目录、无头模式。
- 代理服务商、静态代理、代理测试、失败记录、任务绑定。

### 14.7 抓取结果与日志

- 内容列表、作者、平台、关键词、发布时间、互动指标、来源任务。
- 评论列表、父子评论、评论数、点赞数。
- 原始 JSON 查看、导出、重新入队到下载/转录流程。
- 实时日志、历史日志、失败原因、重试。

### 14.8 存储与诊断

- 本地/NAS 保存根目录，支持 Linux/macOS 路径、Windows 盘符和 UNC。
- 路径权限、剩余容量、文件写入测试。
- Playwright 浏览器、Chrome/Edge、PostgreSQL、FFmpeg、Whisper、网络可达性诊断。

## 15. 统一 API 草案

```text
GET    /api/crawler/platforms
GET    /api/crawler/platforms/{platform}/options

POST   /api/crawler/tasks
GET    /api/crawler/tasks
GET    /api/crawler/tasks/{id}
PUT    /api/crawler/tasks/{id}
POST   /api/crawler/tasks/{id}/enable
POST   /api/crawler/tasks/{id}/disable
POST   /api/crawler/tasks/{id}/run

GET    /api/crawler/runs
GET    /api/crawler/runs/{id}
POST   /api/crawler/runs/{id}/stop
POST   /api/crawler/runs/{id}/retry

POST   /api/crawler/login/{platform}/start
GET    /api/crawler/login/{session_id}/poll
POST   /api/crawler/accounts/{id}/validate

GET    /api/crawler/results
GET    /api/crawler/results/{id}
GET    /api/crawler/results/{id}/comments
GET    /api/crawler/results/{id}/raw

GET    /api/crawler/logs
GET    /api/events/stream
```

## 16. 实施顺序

### P0：合规和边界

- 归档 `MediaCrawler` 授权凭据。
- 明确是否允许合并代码、修改、开源分发、商业部署。
- 保留必要版权声明，移除统一平台中不需要的赞助、作者宣传和原 WebUI 品牌资产。

### P1：过渡适配

- 新增 `legacy_mediacrawler` 适配器，以子进程方式执行 `search/detail/creator`。
- 统一任务表、运行表、日志表先落地。
- 强制保存到统一配置目录或临时目录，抓取后导入统一 PostgreSQL。
- 前端只调用统一 API，不直接访问 `MediaCrawler/api`。

### P2：结果写入统一化

- 替换 `store/*` 写入逻辑，直接写 `content_item`、`content_comment`、`creator_profile`。
- 文件保存统一到 `{storage_root}/{platform}/{creator}/{publish_date}/{content_id}`。
- 建立 raw payload 归档和字段映射版本。

### P3：平台客户端抽离

- 逐个平台抽出 `client.py`、URL 解析、字段映射和评论分页。
- 优先顺序：小红书、微博、知乎、贴吧、快手；抖音/B 站只保留公开抓取部分。
- 登录与浏览器运行时统一到平台公共模块。

### P4：调度与可观测性

- 替换单例进程管理为任务队列。
- 支持并发限制、平台级限速、失败重试、下次运行时间、任务取消。
- 日志从内存列表改为数据库和事件流。

### P5：删除原独立形态

- 不保留原 WebUI、原 API、原 CLI 参数作为用户入口。
- 不保留原平台分散配置文件作为最终配置来源。
- 原项目目录只作为源码归档或拆分迁移来源。

## 17. 风险与处理

- 许可证风险：`NON-COMMERCIAL LEARNING LICENSE 1.1` 与未来开源/商业部署目标存在天然冲突，必须以授权文件为准。
- 平台风控风险：所有平台都可能出现验证码、滑块、Cookie 失效、接口变更，必须把失败诊断做成产品能力。
- WebUI 配置缺口：当前 WebUI 不支持完整 CLI 配置，不可直接作为最终配置源。
- 路径风险：当前路径拼接不适合完整跨平台/NAS 场景，需要统一 `pathlib` 和路径白名单。
- 数据模型风险：平台表结构不可直接作为统一主库，需要映射层和迁移脚本。
- 登录短信风险：`recv_sms.py` 与登录流程默认使用内存缓存，跨进程不可用；如保留手机号登录必须改成统一 Redis/PostgreSQL 临时验证码表。
- 代理风险：代理服务商密钥、代理 URL 可能出现在日志中，需要脱敏。
- 测试风险：部分测试依赖真实 MongoDB、代理服务和外部网络，CI 中需要分层标记。

## 18. 最终架构设计

最终形态：

```text
Unified Workbench Frontend
  -> platform-api (FastAPI)
      -> crawler task module
      -> crawler run manager
      -> browser runtime module
      -> login session module
      -> proxy module
      -> storage module
      -> media asset module
      -> crawler platform adapters
          -> xhs public crawler
          -> douyin public crawler
          -> kuaishou public crawler
          -> bilibili public crawler
          -> weibo public crawler
          -> tieba public crawler
          -> zhihu public crawler
      -> douyin account sync module
      -> bilibili account sync module
      -> transcription module
      -> analysis module
  -> PostgreSQL
  -> Local/NAS Storage
  -> Playwright/CDP Browser Runtime
  -> FFmpeg + faster-whisper
```

用户只看到一个统一工作台。`MediaCrawler` 的平台抓取能力进入 `crawler` 模块，成为关键词、详情和创作者抓取的后端能力来源；原 CLI、原 WebUI、原独立数据目录、原平台配置文件不作为最终产品入口。

## 19. 本轮复盘

本轮已完成：

- 审查 `MediaCrawler` 目录结构、入口、CLI、配置、依赖和许可证。
- 审查七个平台的 `core/client/login/store` 分层和能力边界。
- 审查 Playwright/CDP、二维码/Cookie 登录、代理池、缓存、短信接收、数据存储、WebUI/API。
- 确认最终抽离重点是多平台公开内容抓取，不替代抖音/B 站专用账号同步模块。
- 复核本地提交 `165776886`、`pyproject.toml` 版本 `0.1.0`、Python `>=3.11`、FastAPI WebUI 路由和 `NON-COMMERCIAL LEARNING LICENSE 1.1`。
- 确认 CLI 支持 `postgres` 和 `--save_data_path`，但 WebUI schema 未暴露这些能力；统一工作台必须重做配置页和任务模型。

最终落地要求：

- 先做 `platform-api/modules/crawler` 的统一数据模型和接口定义。
- 第一阶段可用 `legacy_mediacrawler` 子进程适配，但任务、日志、路径和结果必须写入统一 PostgreSQL。
- 优先从小红书或微博做 P1 到 P2 的完整样板，再扩展七个平台。
- 同步建立授权归档目录和第三方代码来源清单，避免后续开源时返工。

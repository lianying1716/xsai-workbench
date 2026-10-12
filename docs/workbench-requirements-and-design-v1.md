# 素材采集管理平台 · 需求梳理与全栈设计（v1）

> 本文是面向非全栈背景使用者的完整设计：先把需求说人话，再设计前端工作台，
> 再由前端页面倒推后端框架，最后给 AI 工具接入方案和分期落地计划。
> 与既有文档的关系：技术底座沿用 `unified-content-platform-prd.md` 和
> `backend-module-final-review.md` 的已定决策（FastAPI / PostgreSQL / Docker Compose / 单管理员），
> 本文在其上补全两大使用场景的细节，并固化用户最新确认的范围。

---

## 1. 已确认的需求输入（2026-06-10 与用户确认）

| 问题 | 用户答案 | 对设计的影响 |
|---|---|---|
| 部署环境 | 必须同时支持 macOS / Windows / Linux，不绑定某一系统 | Docker Compose 为主、路径全部走配置、依赖启动自检 |
| 第一期平台 | 抖音、B站、微信公众号、小红书 **全部要** | 一期内部再分批：抖音+B站 → 公众号 → 小红书 |
| 素材用途 | 选题对标 + 喂 AI 当原料 + 二创剪辑素材 + 行业数据监控 **全部要** | 素材库要同时做好：可读转录、可导出结构化文本、高清视频按目录归档、互动数据看板 |
| 转录量级 | 每天几十条 | 需要正式的任务队列 + 失败重试 + 并发控制，推荐 Apple Silicon 或带显卡机器跑 worker |

## 2. 两大使用场景（完善后的需求描述）

### 场景 A：Web 素材采集管理工作台

用一句话说：**打开一个网页，所有平台账号的死活、所有采集任务、所有素材的下载/转录/分析状态，一目了然且能直接操作。**

拆成用户故事：

1. **账号**：我能在一个页面看到抖音/B站/公众号/小红书所有账号是否在线、快不快过期；掉线了能扫码或粘 Cookie 一键补登录；系统定时自动体检并提醒。
2. **关键词采集**：我能建任务"在抖音搜『XX』，每天早上抓前 50 条按热度排"，能启停、改周期、看每次抓了什么、失败原因是什么。
3. **订阅同步**：我能选某个账号下的收藏夹/关注博主/合集，勾选哪些要跟踪，系统定期把新视频拉下来。
4. **素材库**：每条素材有元数据（标题/作者/发布时间/播放点赞评论）、视频文件位置、转录文本、AI 分析结果；能按平台/作者/关键词/状态筛选；能导出 Markdown/JSON。
5. **转录**：拉下来的视频自动进队列转文字，我能看进度、重试失败的、调模型参数。
6. **数据监控**：按作者/关键词/平台看互动数据走势，发现谁在涨、什么选题在火。
7. **系统**：存储目录（含 NAS）、代理、大模型 API、转录模型都在设置页配，启动时自动检测 FFmpeg/浏览器/磁盘等依赖并显示诊断结果。

### 场景 B：外部 AI 工具全功能托管

用一句话说：**Claude Code / Codex / 自研智能体能做到工作台里人能做的一切，包括帮我完成扫码登录。**

拆成用户故事：

1. 我在 Claude Code 里说"看看哪些账号掉线了"，AI 调接口返回账号状态表。
2. 我说"B站账号掉了，帮我重新登录"，AI 调登录接口拿到**二维码图片**直接展示给我，我手机一扫，AI 轮询到登录成功并确认。
3. 我说"建一个小红书关键词任务抓『露营装备』"，AI 创建任务并复述配置让我确认。
4. 我说"把昨天抓的视频转录文本都给我，总结出三个选题"，AI 拉转录文本直接分析。
5. 所有 AI 调用都有日志（谁、调了什么、参数、结果、耗时），密钥可以随时吊销。

**关键设计含义**：AI 接入不是附加品，而是要求**后端 API 必须是一等公民**——前端工作台和 AI 工具调用同一套 API，能力完全对等。二维码必须能以图片数据（base64/文件）形式通过 API 返回，而不是只渲染在网页里。

## 3. 前端工作台设计

### 3.1 技术选型

- **Vue 3 + TypeScript + Vite + Element Plus**，纯 SPA。
  理由：工作区内 dysync.net 和 wechat-article-exporter 都是 Vue，复用经验最多；Element Plus 中文生态成熟、表格/表单组件齐全，最适合管理后台。
- 构建产物由 platform-api 静态托管（与 bili-sync/dysync 的嵌入式做法一致），用户只需访问一个端口。
- 状态管理 Pinia；接口层统一 axios 封装，自动带登录 token。

### 3.2 导航与页面明细（9 个一级页面）

```text
├── 1 总览          仪表盘
├── 2 账号中心      所有平台登录态
├── 3 关键词采集    搜索抓取任务
├── 4 订阅同步      收藏夹/关注博主/合集
├── 5 素材库        内容+视频+转录+分析
├── 6 处理队列      下载/转录/分析流水线
├── 7 数据看板      互动数据监控
├── 8 AI 接入       API Key / MCP / 调用日志
└── 9 系统设置      存储/代理/模型/诊断
```

**1 总览**：账号异常数（红字置顶）、今日抓取量、待处理/失败任务数、磁盘余量、最近 24h 热门素材 Top10。每个数字可点击跳转对应页面。

**2 账号中心**（地基，沿用 `unified-account-center-design.md`）：
- 账号列表：平台、备注、状态灯（绿在线/黄快过期/红掉线/灰未检）、到期时间、上次体检、操作（体检/补登录/删除）。
- 新建/补登录弹窗，按平台给不同方式：
  - B站：**扫码**（复用 bili-sync 逻辑）或粘 Cookie。
  - 微信公众号：**扫码**（复用 wechat-exporter 逻辑）或粘 Cookie。
  - 抖音：浏览器登录（browser_runtime，二期）或粘 Cookie（一期兜底）。
  - 小红书：浏览器登录（二期）或粘 Cookie（一期兜底）。
- 全局定时体检开关与频率设置。

**3 关键词采集**：
- 任务列表：平台、关键词、周期（cron 的人话版："每天 08:00"）、排序方式、单次上限、启停开关、上次运行结果。
- 任务编辑抽屉：平台多选、关键词组、时间范围、是否抓评论、是否进视频候选池、过滤规则（最低播放量等）。
- 运行记录页：每次运行抓到多少、新增多少、失败原因、原始日志。

**4 订阅同步**：
- 左侧选账号 → 中间展示该账号的远端资源树（B站：收藏夹/合集/关注的UP主；抖音：收藏/喜欢/关注博主）→ 勾选要跟踪的。（公众号历史文章列表接口已于 2026-07 关闭，平台不支持公众号订阅同步，仅支持单篇 URL 导入）
- 每个订阅源可配：同步周期、是否下载视频、保存子目录规则。
- 同步历史：时间线展示每次同步新增的内容。

**5 素材库**（四种用途在这一页汇合）：
- 列表：缩略图、标题、作者、平台、发布时间、播放/点赞/评论、下载状态、转录状态、分析状态；筛选器全维度。
- 详情页三栏：左=视频信息+文件位置（可一键打开/复制路径，服务二创剪辑）；中=转录文本（分段+全文，可复制，服务选题阅读）；右=AI 分析（摘要/标签/结构拆解，服务喂 AI）。
- 批量操作：批量转录、批量导出 Markdown/JSON（服务 AI 原料）、批量删除。

**6 处理队列**：
- 流水线视图：待下载 → 下载中 → 待转录 → 转录中 → 待分析 → 完成 / 失败。
- 失败项展示原因 + 一键重试/批量重试；可调全局并发数。
- 转录设置：模型（如 large-v3 / distil）、设备、语言、是否词级时间戳。

**7 数据看板**：
- 作者维度：跟踪博主的发布频率、互动均值、近期爆款。
- 关键词维度：命中内容量走势、高互动内容列表。
- 快照机制：每次抓取存一份指标快照，才能画"走势"（这是行业监控的关键，光存当前值画不了趋势）。

**8 AI 接入**：
- API Key 管理：创建/吊销/备注/权限范围（只读 or 可操作）/限流。
- MCP 接入指引页：直接展示给 Claude Code / Codex 用的配置片段，复制即用。
- 调用日志：时间、Key、工具名、参数摘要、结果状态、耗时。

**9 系统设置**：
- 存储：根目录（本机路径 / NAS 挂载 / Windows 盘符或 UNC）、目录模板预览、可用性检测、容量。
- 大模型：供应商、Base URL、API Key、模型名、默认分析提示词、用量统计。
- 代理、并发、调度时区；管理员密码修改。
- 诊断页：FFmpeg、浏览器、whisper 模型文件、数据库、磁盘、网络逐项绿/红灯。

### 3.3 全局交互原则

- 单管理员登录，token 失效跳登录页。
- 所有敏感值（Cookie/Key）只显示脱敏（`AB****yz`）。
- 所有长任务（抓取/下载/转录）不阻塞页面，状态通过轮询或 SSE 刷新。
- 所有"删除"二次确认；所有失败必须能看到人话错误原因。

## 4. 后端框架设计（由前端倒推）

### 4.1 总体结构

```text
platform-api/                       # 新建的统一后端（Python + FastAPI）
├── app/
│   ├── main.py                     # FastAPI 入口，托管 SPA 静态文件
│   ├── api/                        # 路由层（与前端页面一一对应）
│   │   ├── auth.py                 #   登录/改密
│   │   ├── accounts.py             #   2 账号中心
│   │   ├── crawl_tasks.py          #   3 关键词采集
│   │   ├── subscriptions.py        #   4 订阅同步
│   │   ├── assets.py               #   5 素材库
│   │   ├── pipeline.py             #   6 处理队列
│   │   ├── analytics.py            #   7 数据看板
│   │   ├── ai_access.py            #   8 API Key/调用日志
│   │   └── system.py               #   9 设置/诊断
│   ├── modules/                    # 平台能力模块（适配层，统一接口）
│   │   ├── base.py                 #   定义统一接口：login_qr/check/list_sources/fetch/...
│   │   ├── bilibili/               #   适配 bili-sync 能力（扫码、收藏夹、UP主）
│   │   ├── douyin/                 #   适配 dysync.net 能力（收藏、关注、合集）
│   │   ├── wechat_mp/              #   适配 wechat-article-exporter 能力（文章、合集）
│   │   ├── xhs/                    #   适配 MediaCrawler 小红书能力
│   │   ├── crawler/                #   MediaCrawler 关键词搜索统一入口
│   │   ├── media_download/         #   yt-dlp 封装（安全白名单配置）
│   │   └── transcription/          #   faster-whisper 封装
│   ├── core/                       # 横切能力
│   │   ├── crypto.py               #   凭证 AES-GCM 加密（密钥来自 keyfile/环境变量）
│   │   ├── scheduler.py            #   APScheduler 定时调度
│   │   ├── queue.py                #   基于 PostgreSQL 的任务队列（不引入 Redis）
│   │   ├── storage.py              #   storage_root + relative_path 路径管理
│   │   └── events.py               #   SSE 事件流（前端实时刷新）
│   ├── models/                     # SQLAlchemy 模型（见 4.3）
│   └── workers/                    # 独立 worker 进程：下载/转录/分析消费者
├── mcp_server/                     # MCP 服务（薄壳，内部调同一套 HTTP API）
├── web/                            # Vue 3 前端源码，构建产物进 app 静态目录
├── docker-compose.yml              # api + worker + postgres 三个容器
└── alembic/                        # 数据库迁移
```

### 4.2 关键架构决策（及大白话理由）

1. **一个 API 进程 + 一个 worker 进程**。网页点起来要快（API 进程只做轻活），下载/转录这种重活全部丢给 worker 慢慢干，互不拖累。每天几十条的量，1 个 worker 串行转录 + 2~3 并发下载足够。
2. **任务队列用 PostgreSQL 表实现，不上 Redis/Celery**。单机部署每多一个组件就多一个出问题的地方；PG 行锁（`SELECT ... FOR UPDATE SKIP LOCKED`）做几十条/天的队列绰绰有余，且任务状态天然可查可审计。量级涨十倍再换专业队列，接口不变。
3. **原项目以"进程适配器"接入，不急着抄代码**。第一阶段 bili-sync/dysync.net 作为内部子服务由 platform-api 拉起和代理（用户不可见）；MediaCrawler 走 CLI 子进程；faster-whisper/yt-dlp 是 Python 库直接 import。第二阶段再逐个把核心逻辑抽进 `modules/`，删除对原仓库的依赖（许可证策略沿用 PRD 5.7）。
4. **API 即产品**。前端、MCP、外部 HTTP 客户端走同一套 `/api/*`，鉴权两种：管理员 session token（前端用）、API Key（AI 用，带 scope 和限流）。绝不出现"只有网页能做的操作"。
5. **凭证安全**：所有 Cookie/Token AES-GCM 加密入库，密钥不进库不进 git；前端和 API 响应永远脱敏；原 wechat-exporter 的 `_debug` 明文导出、dysync 默认密码等不安全设计一律不带入。
6. **跨平台**：Docker Compose 是标准跑法（三系统一致）；浏览器自动登录（抖音/小红书）需要有头浏览器，Linux 无桌面环境时容器内配 xvfb——这是已知最大的跨平台风险点，放在二期 browser_runtime 专项解决，一期用"粘 Cookie"兜底保证功能可用。

### 4.3 数据模型（首批 12 张表）

```text
-- 账号与凭证
platform_account        平台/备注/外部ID/凭证类型/状态/到期时间/上次体检
account_credential      account_id/加密blob/算法标记
credential_audit_log    谁在什么时候读写了凭证

-- 任务
crawl_task              平台/关键词/周期/排序/上限/过滤/启停
crawl_run               task_id/开始结束时间/抓取数/新增数/状态/错误
subscription            account_id/来源类型(收藏夹|博主|合集)/远端ID/周期/下载开关
sync_run                subscription_id/同步结果

-- 内容与资产
content_item            平台/外部ID/标题/作者/URL/发布时间/来源(关键词|订阅)
content_metric_snapshot content_id/采集时间/播放/点赞/评论/收藏/转发   ← 看板走势靠它
media_asset             content_id/storage_root_id/相对路径/下载|转录|分析状态
transcript              asset_id/语言/模型/分段JSON/全文
analysis_result         asset_id/摘要/标签/结构化JSON/模型/提示词版本

-- 系统
job_queue               类型(download|transcribe|analyze)/payload/状态/重试次数/错误
api_key                 名称/哈希/scope/限流/启用
api_call_log            key_id/工具名/参数摘要/状态/耗时
storage_root            名称/各系统路径/是否默认
```

### 4.4 API 一览（前端页面 ↔ 路由对应）

```text
POST /api/auth/login                              登录
GET  /api/dashboard/summary                       1 总览

GET/POST           /api/accounts                  2 账号列表/新建
POST /api/accounts/{id}/check                     2 立即体检
PUT  /api/accounts/{id}/credential                2 补 Cookie
POST /api/accounts/qr-login        {platform}     2 创建扫码会话 → 返回二维码 PNG(base64)+session_id
GET  /api/accounts/qr-login/{session_id}          2 轮询扫码状态 → pending|scanned|success|expired

GET/POST/PUT/DELETE /api/crawl-tasks              3 关键词任务 CRUD
POST /api/crawl-tasks/{id}/run                    3 立即运行
GET  /api/crawl-tasks/{id}/runs                   3 运行记录

GET  /api/accounts/{id}/remote-sources            4 拉取账号的收藏夹/关注/合集树
GET/POST/PUT/DELETE /api/subscriptions            4 订阅 CRUD
POST /api/subscriptions/{id}/sync                 4 手动同步

GET  /api/assets                                  5 素材列表（全维度筛选）
GET  /api/assets/{id}                             5 详情（元数据+文件+转录+分析）
POST /api/assets/{id}/transcribe|analyze          5/6 入队
POST /api/assets/export                           5 批量导出 md/json
GET  /api/pipeline/jobs?status=failed             6 队列视图
POST /api/pipeline/jobs/{id}/retry                6 重试
GET  /api/analytics/creators|keywords             7 看板
GET/POST/DELETE /api/ai/keys                      8 API Key
GET  /api/ai/call-logs                            8 调用日志
GET/PUT /api/system/settings                      9 设置
GET  /api/system/diagnostics                      9 依赖诊断
GET  /api/events/stream                           SSE 实时状态
```

## 5. AI 工具接入设计（场景 B 专项）

### 5.1 双通道

- **HTTP API**：上表全部接口，`Authorization: Bearer <api_key>`，任何能发 HTTP 的智能体都能用。
- **MCP Server**：`mcp_server/` 提供给 Claude Code/Codex 一键接入，工具是 API 的薄封装，约 12 个：
  `list_accounts` / `check_account` / `start_qr_login` / `poll_qr_login` / `update_cookie` /
  `create_crawl_task` / `list_crawl_tasks` / `trigger_sync` / `search_assets` /
  `get_transcript` / `get_analytics` / `export_assets`

### 5.2 AI 扫码登录流程（核心体验）

```text
用户:  "B站账号掉线了，帮我重新登录"
AI  →  start_qr_login(platform="bilibili")
API →  返回 { session_id, qr_image_base64, expires_in: 180 }
AI  →  把二维码图片展示给用户（MCP image content / 存成文件打开）
用户:  手机扫码确认
AI  →  poll_qr_login(session_id) 每 3 秒一次
API →  success 后自动加密入库新凭证、刷新账号状态
AI  →  "登录成功，账号已恢复在线"
```

后端实现要点：扫码会话存内存带 TTL；B站复用 bili-sync 的申请二维码+轮询逻辑，微信复用 wechat-exporter 的扫码逻辑；抖音/小红书扫码依赖 browser_runtime（二期），一期 AI 通道用 `update_cookie` 兜底。

### 5.3 安全边界

- API Key 分 scope：`read`（查询类）/ `operate`（建任务/登录）/ `admin`（设置类），默认发 `read+operate`。
- AI 永远拿不到明文凭证——`get_*` 类接口一律脱敏，凭证只进不出。
- 不开放任意路径/任意 shell/任意 headers 类参数（沿用 final-review 第 4 节禁令）。
- 每次调用落 `api_call_log`，前端第 8 页可审计、可吊销 Key。

## 6. 分期落地计划

| 期 | 交付物 | 验收标准（用户视角） |
|---|---|---|
| **P1 地基** | platform-api 骨架 + 登录 + 账号中心（B站扫码、抖音/小红书/公众号粘 Cookie、定时体检）+ 前端框架与账号页 | 打开网页能看到所有账号死活，掉线能补 |
| **P2 同步闭环** | B站+抖音订阅同步（收藏夹/博主）→ 素材入库 → 视频下载队列 + 素材库页 | 勾选的收藏夹/博主有新视频会自动出现在素材库且文件落盘 |
| **P3 转录流水线** | faster-whisper worker + 处理队列页 + 素材详情页转录展示 | 几十条/天自动转完，失败可重试，文本可读可导出 |
| **P4 AI 接入** | API Key + MCP Server + 扫码登录 API + 调用日志页 | 在 Claude Code 里完成"查状态/扫码登录/建任务/拿转录" |
| **P5 关键词采集** | MediaCrawler 适配（抖音/B站/小红书搜索）+ 采集页 + 指标快照 | 关键词任务定时跑，热门内容进候选池 |
| **P6 公众号+看板+分析** | wechat_mp 模块 + 数据看板 + 大模型分析（摘要/标签） | 四平台齐活，看板能看走势，素材有 AI 摘要 |

> AI 接入放 P4 而不是最后，因为这是用户的核心场景之一；P1~P3 先把 API 打磨稳定，P4 只是套薄壳。
> browser_runtime（抖音/小红书浏览器自动登录与签名）作为 P4 之后的专项，不阻塞主线。

## 7. 已识别风险（大白话）

1. **小红书最难搞**：登录态活在浏览器里，签名要现算，跨平台跑有头浏览器是硬骨头。一期用粘 Cookie 能用但体验一般，真正爽要等 browser_runtime。
2. **平台风控**：采集频率太高会触发验证码/封号。所有任务默认保守频率，代理配置一期就留口子。
3. **dysync 的闭源组件**（`dy.sync.lib.dll`/`dy.cookie.exe`）只在 Windows 可用且看不到源码，抖音 Cookie 获取一期靠手动粘贴，二期用 browser_runtime 替代，不依赖闭源件。
4. **MediaCrawler 许可证**是非商业学习许可，授权凭据必须归档后才能抽代码（PRD 已记录），一期先走 CLI 子进程调用规避。
5. **指标走势必须从第一天就存快照**（content_metric_snapshot），否则后面想看趋势没有历史数据，补不回来。

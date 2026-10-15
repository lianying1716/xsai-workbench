# wechat-article-exporter 后端架构审查与微信文章模块设计

## 1. 文档目标

本文档基于对 `/path/to/xsai-workbench/wechat-article-exporter` 的源码审查，整理其现有能力、技术栈、微信登录、公众号搜索、文章同步、评论与阅读量抓取、代理、导出、浏览器缓存、测试与合规风险，并定义其并入统一平台时的后端模块设计、数据模型、统一 API 和前端配置页面。

本文档只覆盖 `wechat-article-exporter`。它在统一平台中的定位是“微信公众号文章抓取、归档、导出和分析入口模块”，与 `MediaCrawler` 的多平台公开内容抓取互补。

## 2. 总体结论

- 该项目是 Nuxt 3 + Vue 3 + Nitro 的在线微信公众号文章批量下载工具，`ssr: false`，当前以浏览器工作台和 IndexedDB 为主。
- 服务端 Nitro 主要负责微信公众平台请求代理、扫码登录 Cookie 保存、公开 API 和 PDF 生成；没有统一数据库、任务队列、NAS 存储或长期后端任务模型。
- 核心能力包括公众号搜索、根据文章链接反查公众号、历史文章列表同步、合集下载、单篇文章下载、HTML/JSON/Excel/TXT/Markdown/DOCX/PDF 导出、评论与阅读量抓取、代理池。
- 本轮复盘确认 Cookie KV 仅存 `token + cookies`，TTL 4 天但未加密，`AccountCookie.isExpired` 仍是 TODO；`server/api/_debug.get.ts` 可通过 `DEBUG_KEY` 导出内存 Cookie，正式平台必须删除。
- 本轮复盘确认 `parseCgiDataNew` 服务端依赖 `EXTERNAL_API_SERVICE=/api/tools/eval-js-code` 执行页面脚本，客户端与导出逻辑也存在多处 `eval`；统一平台必须改为受控解析或隔离沙箱。
- 最终不应保留原 Nuxt 工作台作为独立入口。可复用其微信接口封装、HTML 解析、导出格式思路、样本和部分类型定义，但需迁移到统一 `platform-api` 后端。
- 浏览器侧 IndexedDB、`showDirectoryPicker`、`file-saver`、`window.htmlDocx`、前端 Blob 缓存、公共代理节点和外部 eval API 不适合作为最终架构基础。
- 项目源码为 MIT，适合并入；但 AG Grid Enterprise、html-docx-js vendor、公共代理服务、微信内容版权和抓包凭证采集方式必须单独审查。

## 3. 现有项目结构

关键目录：

```text
wechat-article-exporter/
  pages/dashboard/              # 原工作台页面
  components/                   # 登录、凭证、表格、设置、预览组件
  apis/index.ts                 # 客户端 API 封装
  server/api/                   # Nitro 服务端接口
  server/utils/                 # 微信请求代理、CookieStore、Puppeteer、日志
  server/kv/                    # auth-key -> token/cookies KV 存储
  store/v2/                     # Dexie IndexedDB 表：文章、HTML、评论、资源、元数据
  utils/download/               # Downloader、Exporter、ProxyManager
  shared/utils/                 # HTML 解析、渲染、请求工具
  config/                       # 常量、公共 API 文档、公共代理
  test/                         # HTML 解析样本脚本
  samples/                      # 微信文章样本
  Dockerfile                    # Node 22 + Chromium/Puppeteer
```

核心技术栈：

- Node `>=22`，Yarn `1.22.22`
- Nuxt `3.12+`，Vue `3.5+`
- Nitro server，KV storage
- Dexie/IndexedDB
- Cheerio、Turndown、ExcelJS、JSZip、html2pdf、Puppeteer
- AG Grid Enterprise、Nuxt UI、TailwindCSS
- Biome 格式化，TypeScript

## 4. 当前运行与部署

常用命令：

```text
yarn dev
yarn build
yarn preview
yarn format
yarn docker:build
```

Docker 特点：

- 构建层使用 `node:22-alpine`。
- 运行层使用 `node:22-slim`。
- 安装 `chromium`、中文字体、Emoji 字体和 CA 证书。
- 运行时设置 `PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium`。
- Nitro 服务监听 `3000`。
- 本地 KV 默认为 `.data/kv`。

环境变量：

```text
NUXT_AGGRID_LICENSE
NITRO_KV_DRIVER=fs
NITRO_KV_BASE=.data/kv
NUXT_DEBUG_MP_REQUEST
DEBUG_KEY
NUXT_WECHAT_ABOUT_BIZ_UIN
NUXT_WECHAT_ABOUT_BIZ_KEY
NUXT_WECHAT_ABOUT_BIZ_WX_HEADER
```

并入要求：

- 统一平台首选 Docker Compose，Node/Nuxt 独立运行形态不保留为主入口。
- 如果保留 PDF 生成能力，统一后端镜像或独立 worker 镜像必须内置 Chromium 和中文字体。
- 原 `.data/kv` 只能作为迁移参考，最终凭证进入 PostgreSQL 加密字段。

## 5. 微信登录与 Cookie 存储

当前扫码登录流程：

```text
POST /api/web/login/session/{sid}
  -> mp.weixin.qq.com/cgi-bin/bizlogin?action=startlogin
  -> 返回 uuid cookie

GET /api/web/login/getqrcode
  -> mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=getqrcode

GET /api/web/login/scan
  -> mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=ask

POST /api/web/login/bizlogin
  -> mp.weixin.qq.com/cgi-bin/bizlogin?action=login
  -> 从 redirect_url 提取 token
  -> 保存 token + set-cookie 到 KV
  -> 返回 auth-key cookie
```

`CookieStore` 行为：

- `auth-key` 是随机 UUID。
- KV key 为 `cookie:{authKey}`。
- value 包含 `token` 和解析后的 cookies。
- KV TTL 为 4 天。
- 内存 Map 做 LRU，最多 1000 条。
- 请求时从 `X-Auth-Key` 或 `auth-key` cookie 读取凭证。

问题：

- Cookie 未加密，仅依赖 KV 存储。
- `AccountCookie.isExpired` 是 TODO。
- `_debug.get.ts` 可通过 `DEBUG_KEY` 导出内存 Cookie，正式平台不能保留。
- 登录态没有统一账号表、状态校验、过期提醒、审计日志。

统一平台应抽为：

```text
WechatLoginService
  start_qr_login()
  get_qr_image(session_id)
  poll_qr_status(session_id)
  finalize_login(session_id)
  validate_account(account_id)
  logout(account_id)
```

凭证入库：

```text
platform_account
account_credential
login_session
credential_audit_log
```

所有 token、cookie、pass_ticket、key、uin、appmsg_token 必须加密保存，前端只展示脱敏状态和过期时间。

## 6. 微信接口能力

当前服务端接口：

| 能力 | 接口 | 微信目标接口 |
|---|---|---|
| 登录账号信息 | `/api/web/mp/info` | `/cgi-bin/home` |
| 搜索公众号 | `/api/web/mp/searchbiz` | `/cgi-bin/searchbiz` |
| 根据 URL 搜索公众号 | `/api/web/mp/searchbyurl` | 先解析文章页公众号名，再 searchbiz |
| 历史文章列表 | `/api/web/mp/appmsgpublish` | `/cgi-bin/appmsgpublish` |
| 公众号文章列表凭证模式 | `/api/web/mp/profile_ext_getmsg` | `/mp/profile_ext?action=getmsg` |
| 合集 | `/api/web/misc/appmsgalbum` | `/mp/appmsgalbum?action=getalbum` |
| 评论 | `/api/web/misc/comment` | `/mp/appmsg_comment?action=getcomment` |
| 作者主体信息 | `/api/public/beta/authorinfo` | `/mp/authorinfo` |
| aboutbiz 主体信息 | `/api/public/beta/aboutbiz` | `/mp/aboutbiz` |
| 文章下载 | `/api/public/v1/download` | 直接 fetch 文章 URL |
| PDF | `/api/web/pdf/generate` | Puppeteer 本地生成 |

公共 API：

```text
GET /api/public/v1/account
GET /api/public/v1/accountbyurl
GET /api/public/v1/article
GET /api/public/v1/download
GET /api/public/v1/authkey
GET /api/public/beta/authorinfo
GET /api/public/beta/aboutbiz
```

并入判断：

- 搜索公众号、文章列表、合集、评论、阅读量、文章下载都应进入统一后端模块。
- 原公共 API 可作为外部 skill/API 的设计参考，但鉴权、限流、审计必须重做。
- `aboutbiz` 内部使用 `eval` 执行页面脚本，必须改为受控沙箱或纯解析策略。

## 7. 文章抓取与缓存

当前文章列表流程：

```text
getArticleList(account, begin, keyword)
  -> /api/web/mp/appmsgpublish
  -> publish_page = JSON.parse(resp.publish_page)
  -> publish_info = JSON.parse(item.publish_info)
  -> appmsgex 写入 IndexedDB article 表
  -> info 表更新公众号同步进度
```

文章缓存表：

- `info`：公众号 fakeid、昵称、头像、同步进度、总数。
- `article`：文章 aid、link、title、cover、digest、create_time、update_time、author、合集、原创、类型、删除状态。
- `html`：文章 HTML Blob、commentID。
- `metadata`：阅读、点赞、分享、喜欢、留言数量。
- `comment`：评论响应。
- `comment_reply`：评论回复响应。
- `resource`：图片/音频/视频/样式资源 Blob。
- `resource-map`：文章 URL 到资源 URL 列表。
- `debug`：异常 HTML 样本。

统一平台必须迁移到：

```text
wechat_account
wechat_article
wechat_article_metric
wechat_article_html
wechat_comment
wechat_comment_reply
wechat_album
wechat_resource
raw_payload
media_asset
```

不要继续使用浏览器 IndexedDB 作为主数据源。

## 8. 下载、评论与阅读量

`Downloader` 支持四类任务：

- `html`：下载文章 HTML，校验 `#js_article`，提取 `comment_id`。
- `metadata`：使用 Credential 下载带阅读量的页面，解析 `cgiDataNew.user_info.appmsg_bar_data`。
- `comments`：分页抓取评论和评论回复。
- `fakeid`：单篇文章修复 fakeid。

关键规则：

- HTML 下载可较高并发。
- 阅读量和评论需要 Credential，最大并发会降到 2。
- 文章删除、内容违规、暂时无法查看会进入不同状态。
- 付费文章需要使用已付费微信号的 Credential 才能获取完整内容，不提供破解。

Credential 来源：

- `wxdown-service` WebSocket：默认 `wss://127.0.0.1:65001`。
- `mitmproxy` 插件：`public/plugins/credential.py`，本地 `CREDENTIAL_API_HOST=http://127.0.0.1:8088`。
- 生存时间默认 `25` 分钟。
- 字段包括 `biz`、`uin`、`key`、`pass_ticket`、`wap_sid2`、`appmsg_token`、`cookie`。

并入要求：

- 统一平台必须有“微信阅读凭证”配置页，清晰区分公众号后台登录 Cookie 与移动端文章页 Credential。
- Credential 必须加密入库，设置过期时间、来源、关联 fakeid、最后验证结果。
- 抓取阅读量/评论任务应单独限速，并记录 Credential 风险和失败原因。

## 9. 代理机制

当前代理来源：

- 公共代理：`PUBLIC_PROXY_LIST`，由多个域名生成 16 个子域名。
- 私有代理：用户在设置中输入一行一个 URL。
- 私有代理授权：`privateProxyAuthorization`。

代理调用形式：

```text
{proxy}?url={encodedUrl}&headers={encodedHeaders}&authorization={token}
```

代理调度：

- `ProxyManager` 记录 failures、lastUsed、cooldown、totalUse、totalSuccess、totalFailures。
- 连续失败达到阈值进入冷却。
- `pool.ts` 旧实现使用 busy/cooldown/usageCount/traffic。

并入要求：

- 不默认依赖原公共代理节点。
- 代理配置进入统一 `proxy_profile`，支持静态代理、私有转发代理、服务商代理。
- 后端记录代理成功率、失败率、冷却、任务绑定、平台绑定。
- 代理 URL、Authorization、Cookie 必须日志脱敏。

## 10. HTML 解析与渲染

核心工具：

- `normalizeHtml(rawHTML, format)`：清理微信文章 HTML，输出 HTML 或 text。
- `validateHTMLContent(html)`：识别成功、删除、异常、错误，并提取 `comment_id`。
- `parseCgiDataNew(html)`：提取 `window.cgiDataNew`。
- `renderHTMLFromCgiDataNew(cgiData)`：重新渲染文章 HTML。
- `renderTextFromCgiDataNew(cgiData)`：输出纯文本。
- `renderComments(url)`：把缓存评论渲染到 HTML。

支持文章类型：

- 普通图文 `item_show_type=0`
- 图片分享 `8`
- 文本分享 `10`
- 视频分享、音频、文章分享、小程序、投票等在导出逻辑中有兼容处理
- 付费订阅文章只展示付费提示或已授权内容

风险：

- 当前客户端多处使用 `eval` 解析微信页面内脚本。
- 服务端 `parseCgiDataNewOnServer` 调用外部 `EXTERNAL_API_SERVICE=/api/tools/eval-js-code`。
- Cloudflare 环境禁止动态执行脚本，原项目依赖外部服务绕过限制。

统一平台要求：

- 后端不依赖外部 eval API。
- 优先开发受控 JS 沙箱或纯解析器；若必须执行脚本，使用隔离进程、超时、无网络、无文件系统权限。
- 保留 `samples/` 作为回归测试样本，覆盖删除、违规、普通图文、图片分享、文本分享、文章分享。

## 11. 导出能力

当前导出格式：

- Excel：ExcelJS，字段包括公众号、ID、链接、标题、封面、摘要、时间、阅读、点赞、分享、喜欢、留言、作者、原创、类型、合集、内容。
- JSON：可包含文章内容和评论。
- HTML：下载图片/样式/背景图等资源，替换为本地路径。
- TXT：纯文本。
- Markdown：Turndown。
- DOCX：`window.htmlDocx.asBlob`。
- PDF：服务端 Puppeteer 生成。

当前问题：

- HTML/TXT/Markdown/DOCX/PDF 导出依赖浏览器 `showDirectoryPicker` 写入用户本机目录。
- 资源缓存是 IndexedDB Blob。
- DOCX 依赖 `public/vendors/html-docx-js@0.3.1/html-docx.js`。
- PDF 依赖服务端 Chromium，但任务状态仍在前端。

统一平台设计：

- 所有导出任务应进入后端队列。
- 文件写入统一本地/NAS 存储：`{storage_root}/wechat/{account}/{publish_date}/{article_id}/`。
- HTML 资源应作为 `media_asset` 或 `wechat_resource` 保存。
- 导出格式支持 `html`、`json`、`xlsx`、`txt`、`md`、`docx`、`pdf`。
- 导出产物入库，前端只负责下载、预览、重新生成。

## 12. 必须抽出的后端模块

建议新增：

```text
platform-api/app/modules/wechat_articles/
  schemas.py
  models.py
  service.py
  scheduler.py
  account_service.py
  login_service.py
  credential_service.py
  mp_client.py
  article_sync.py
  album_sync.py
  downloader.py
  comment_sync.py
  metric_sync.py
  html_parser.py
  renderer.py
  exporter.py
  resource_fetcher.py
  proxy_adapter.py
  legacy_wechat_exporter.py
  diagnostics.py
```

模块职责：

- `login_service.py`：扫码登录微信公众号后台，保存 Cookie 和 token。
- `credential_service.py`：管理移动端文章页 Credential，用于阅读量、评论、付费已购内容。
- `mp_client.py`：封装 searchbiz、appmsgpublish、profile_ext、comment、album、authorinfo。
- `article_sync.py`：同步公众号历史文章、关键词过滤、增量判断、分页。
- `album_sync.py`：同步合集列表和合集文章。
- `downloader.py`：下载文章 HTML，识别删除/异常/违规。
- `metric_sync.py`：抓取阅读、点赞、分享、喜欢、留言数。
- `comment_sync.py`：抓取评论和评论回复。
- `html_parser.py`：安全解析 HTML、cgiDataNew、comment_id。
- `renderer.py`：生成规范 HTML、文本和预览。
- `exporter.py`：生成 html/json/xlsx/txt/md/docx/pdf。
- `resource_fetcher.py`：下载图片、音频、视频、样式，写入资产目录。
- `proxy_adapter.py`：接入统一代理模块。
- `legacy_wechat_exporter.py`：第一阶段参考原项目接口和算法，不作为长期入口。

## 13. 统一数据模型设计

建议新增表：

```text
wechat_account
  id, fakeid, nickname, alias, avatar_url, signature,
  service_type, verify_status, total_count,
  last_sync_at, completed, status, created_at, updated_at

wechat_login_credential
  id, account_id, token, cookies_encrypted, auth_key_hash,
  expires_at, status, last_validated_at

wechat_article_credential
  id, fakeid, uin, key_encrypted, pass_ticket_encrypted,
  wap_sid2_encrypted, appmsg_token_encrypted, cookie_encrypted,
  source, captured_at, expires_at, valid

wechat_article
  id, fakeid, aid, appmsgid, itemidx, title, link,
  digest, author_name, cover_url, item_show_type,
  create_time, update_time, copyright_type, copyright_stat,
  album_ids_json, is_deleted, status, raw_payload_id

wechat_article_html
  id, article_id, html_path, normalized_html_path,
  text_path, comment_id, content_hash, downloaded_at

wechat_article_metric
  id, article_id, read_num, old_like_num, share_num,
  like_num, comment_num, captured_at, credential_id

wechat_comment
  id, article_id, comment_id, content_id, nick_name,
  content, like_num, create_time, ip_wording_json,
  author_like_status, raw_payload_id

wechat_comment_reply
  id, comment_id, content_id, reply_id, nick_name,
  to_nick_name, content, like_num, create_time, raw_payload_id

wechat_album
  id, fakeid, album_id, title, description, article_count,
  brand_icon, raw_payload_id

wechat_resource
  id, article_id, source_url, local_path, mime_type,
  size_bytes, hash, resource_type, downloaded_at

wechat_export_job
  id, scope_type, scope_id, format, status, output_path,
  include_content, include_comments, started_at, finished_at
```

与统一主模型映射：

- `wechat_article` 同步写入统一 `content_item`。
- 图片、音频、视频、HTML、导出文件写入 `media_asset`。
- 评论写入统一 `content_comment`，保留微信字段。
- 阅读、点赞、分享、留言数写入 `content_metric`。
- 后续分析模块直接读取 `content_item` + `wechat_article_html.text_path`。

## 14. 统一 API 草案

```text
POST   /api/wechat/login/start
GET    /api/wechat/login/{session_id}/qrcode
GET    /api/wechat/login/{session_id}/poll
POST   /api/wechat/login/{session_id}/finalize
POST   /api/wechat/accounts/{id}/validate
POST   /api/wechat/accounts/{id}/logout

GET    /api/wechat/accounts/search
POST   /api/wechat/accounts
GET    /api/wechat/accounts
GET    /api/wechat/accounts/{id}
DELETE /api/wechat/accounts/{id}

POST   /api/wechat/accounts/{id}/sync
GET    /api/wechat/sync-runs
POST   /api/wechat/sync-runs/{id}/cancel
POST   /api/wechat/sync-runs/{id}/retry

GET    /api/wechat/articles
POST   /api/wechat/articles/by-url
GET    /api/wechat/articles/{id}
POST   /api/wechat/articles/{id}/download-html
POST   /api/wechat/articles/{id}/sync-metrics
POST   /api/wechat/articles/{id}/sync-comments

GET    /api/wechat/albums
POST   /api/wechat/albums/{id}/sync
GET    /api/wechat/comments

GET    /api/wechat/credentials
POST   /api/wechat/credentials
POST   /api/wechat/credentials/{id}/validate
DELETE /api/wechat/credentials/{id}

POST   /api/wechat/export-jobs
GET    /api/wechat/export-jobs
GET    /api/wechat/export-jobs/{id}
GET    /api/wechat/export-jobs/{id}/download

GET    /api/wechat/diagnostics
GET    /api/wechat/events
```

外部 skill/API：

```text
GET  /api/skills/wechat/accounts/search
POST /api/skills/wechat/articles/sync
GET  /api/skills/wechat/articles
GET  /api/skills/wechat/articles/{id}/content
POST /api/skills/wechat/export
```

外部 API 不允许传任意服务器文件路径，只接受账号 ID、文章 ID、URL 或受控任务参数。

## 15. 必须进入统一前端的页面

### 15.1 微信账号与登录

- 扫码登录微信公众号后台。
- 登录状态、Cookie 过期时间、重新登录、登出、验证。
- 登录失败原因：二维码过期、未绑定邮箱、无可登录账号、Cookie 失效。

### 15.2 公众号管理

- 搜索公众号、根据文章 URL 反查公众号。
- 添加公众号、删除公众号、同步状态、文章总数、最近同步时间。
- 同步范围：24h、1d、3d、7d、1m、3m、6m、1y、全部、指定日期。
- 同步间隔、分页大小、停止/重试。

### 15.3 文章列表

- 标题、作者、发布时间、类型、原创、合集、删除状态。
- 内容下载状态、评论下载状态、阅读量/点赞/分享/喜欢/留言。
- 批量下载 HTML、抓阅读量、抓评论、导出、进入分析。

### 15.4 单篇文章

- 输入文章 URL。
- 下载内容、解析 fakeid、修复归属公众号。
- 支持预览、导出、同步评论和指标。

### 15.5 合集

- 选择公众号和合集。
- 正序/倒序、同步全部文章、批量下载。
- 合集元数据和文章列表入库。

### 15.6 Credential 管理

- 展示 Credential 来源、fakeid、公众号名、获取时间、过期时间、有效性。
- 支持 wxdown-service WebSocket 或手工导入。
- 支持 mitmproxy 插件说明，但不把抓包工具作为统一平台后端内置能力。

### 15.7 代理与限速

- 私有代理、转发代理、授权 token、测试代理。
- 任务并发、重试、冷却、失败阈值。
- 不显示原公共代理宣传页，改为统一代理诊断页。

### 15.8 导出配置

- 导出格式：HTML、JSON、XLSX、TXT、MD、DOCX、PDF。
- 文件命名模板：`${account}`、`${title}`、`${aid}`、`${author}`、`${YYYY}`、`${MM}`、`${DD}`。
- 是否包含正文、评论、资源、阅读量。
- 输出目录选择本地/NAS 路径模板。

### 15.9 预览与分析

- 文章 HTML 预览、纯文本预览、评论预览。
- 手动加入分析队列。
- 关键词、摘要、选题、爆款指标进入统一数据看板。

## 16. 与其他模块的关系

统一数据流：

```text
wechat account/login
  -> account search / article list / album sync
  -> wechat_article + content_item
  -> html/resource/comment/metric sync
  -> media_asset + content_comment + content_metric
  -> analysis_job
  -> dashboard / external skill API
```

边界：

- `wechat_articles` 负责微信公众号文章，不负责抖音/B 站视频账号同步。
- `MediaCrawler` 可覆盖部分公开平台搜索，但不替代微信公众号后台文章同步。
- `transcription` 通常不处理微信图文；若微信文章含音频/视频资源，可作为 `media_asset` 进入转录队列。
- `analysis` 读取微信正文文本、评论和指标，统一做内容分析。

## 17. 不保留或需要重写的部分

不保留：

- 原 Nuxt 工作台路由和菜单作为最终产品入口。
- 原浏览器 IndexedDB 主存储。
- 原公共代理节点列表。
- `_debug.get.ts` Cookie 调试导出。
- 原赞助、QQ群、商业版宣传入口。
- 依赖浏览器 `showDirectoryPicker` 的导出方式。

需要重写：

- 导出文件写入逻辑，改为 NAS/本地后端存储。
- DOCX 生成逻辑，避免依赖全局 `window.htmlDocx`。
- cgiDataNew 解析，避免外部 eval API。
- 任务队列、日志、进度、取消、重试。
- 凭证加密、过期检查、权限控制。

可复用：

- 微信接口参数与流程。
- HTML 清理、comment_id 提取、删除/异常识别规则。
- 导出字段设计和文件命名变量。
- 代理冷却/失败统计思路。
- `samples/` 测试样本。
- 部分 TypeScript 类型可作为 Python/Pydantic schema 参考。

## 18. 风险与处理

- 微信风控风险：登录 Cookie、Credential、代理、抓取频率均可能触发限制，必须提供限速、重试和失败诊断。
- 凭证风险：Credential 来自抓包，包含敏感 key/pass_ticket/appmsg_token，必须加密、脱敏、过期自动失效。
- 内容版权风险：微信公众号内容版权归原作者，统一平台应只作为用户自用归档和分析工具。
- 付费内容风险：只允许用户凭已购买 Credential 抓取自己的可访问内容，不能承诺破解付费文章。
- 外部服务风险：原项目依赖公共代理和外部 eval API，统一平台不能作为硬依赖。
- 浏览器 API 风险：原导出依赖浏览器文件系统 API，跨平台单机部署需要后端路径写入。
- PDF 风险：Puppeteer/Chromium 在 Windows/macOS/Linux/Docker 中依赖字体和浏览器路径，需诊断页。
- 数据迁移风险：原 IndexedDB 数据在用户浏览器内，无法直接作为统一后端主库；如需迁移需做导入工具。
- AG Grid 许可风险：原项目使用 AG Grid Enterprise，统一前端若继续使用需配置授权或替换表格组件。
- 安全风险：原调试日志可能记录 Cookie 和请求报文，正式平台日志必须脱敏。

## 19. 实施顺序

### P0：合规与边界

- 归档 MIT 许可证、AG Grid 授权要求、html-docx-js 来源。
- 明确微信公众号内容使用声明和付费内容边界。
- 禁用原 `_debug`、公共代理宣传、外部 eval 依赖。

### P1：登录和账号同步

- 实现微信扫码登录到统一账号表。
- 实现公众号搜索、添加、文章列表同步。
- 文章元数据写入 `wechat_article` 和统一 `content_item`。

### P2：文章 HTML 和资源归档

- 后端下载文章 HTML。
- 解析删除/异常/评论 ID。
- 保存原始 HTML、规范 HTML、纯文本和资源到 NAS/本地目录。

### P3：指标和评论

- 接入 Credential 管理。
- 抓取阅读量、点赞、分享、喜欢、评论和评论回复。
- 建立低并发限速和失败诊断。

### P4：导出和前端工作台

- 后端生成 HTML/JSON/XLSX/TXT/MD/DOCX/PDF。
- 前端完成账号、文章、合集、Credential、代理、导出、预览页面。
- 导出产物支持下载和重新生成。

### P5：分析联动

- 微信文章正文和评论进入分析模块。
- 支持按公众号、合集、关键词、时间范围的数据看板。
- 外部 skill/API 可触发同步、查询正文、创建分析任务。

## 20. 最终架构设计

最终形态：

```text
Unified Workbench Frontend
  -> platform-api (FastAPI)
      -> wechat_articles module
          -> login service
          -> credential service
          -> mp client
          -> article sync
          -> album sync
          -> downloader
          -> metric/comment sync
          -> html parser/renderer
          -> exporter
          -> diagnostics
      -> proxy module
      -> storage module
      -> media_asset module
      -> analysis module
      -> external skill API
  -> PostgreSQL
  -> Local/NAS Storage
      -> original html
      -> normalized html
      -> text/markdown/json/xlsx/docx/pdf exports
      -> images/audio/video/css resources
  -> Optional Chromium/Puppeteer worker
```

用户只看到统一工作台。`wechat-article-exporter` 的能力进入 `wechat_articles` 模块，成为微信公众号文章归档、评论指标抓取、导出和分析的数据来源；原 Nuxt 工作台、IndexedDB、公共代理和浏览器导出模式不作为最终产品入口。

## 21. 本轮复盘

本轮已完成：

- 审查 `wechat-article-exporter` 项目结构、技术栈、依赖、许可证、Docker 和环境变量。
- 审查扫码登录、CookieStore、Nitro API、微信接口代理和公共 API。
- 审查 IndexedDB 表、文章同步、HTML 下载、评论/阅读量 Credential、代理调度、HTML 解析、导出和 PDF。
- 审查原前端页面，整理统一工作台必须吸收的配置和管理能力。
- 复核本地提交 `757e6bf1f`、版本 `2.3.18`、Node `>=22`、Nuxt `3.12+`、`ssr:false`、MIT 许可。
- 确认服务端 API 文件 27 个，浏览器工作台页面集中在 `pages/dashboard/*`，主缓存表由 `store/v2/db.ts` 的 Dexie schema 管理。
- 确认 Docker 运行层安装 Chromium、中文字体和 Puppeteer；PDF 能力应迁移为统一 worker 或独立服务。

最终落地要求：

- 先实现微信扫码登录、公众号搜索、文章列表同步到统一 PostgreSQL。
- 后端重写 HTML/资源/评论/指标/导出队列，所有产物写入本地/NAS 存储。
- 删除 `_debug`、公共代理硬依赖、外部 eval API、浏览器 IndexedDB 主存储和 `showDirectoryPicker` 导出模式。
- 同步启动统一 `media_asset` 与 `content_item` 数据模型设计，因为微信文章、视频平台和转录分析都会依赖它。

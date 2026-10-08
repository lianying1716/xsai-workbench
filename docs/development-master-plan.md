# 素材采集管理平台 · 开发总纲（Master Plan）

> **这份文档是什么**：把分散在多份文档里的需求、设计、技术验证结论**收敛成一份可直接驱动写代码的开发规划**。
> 开发时只看这一份就够：它告诉你做什么、按什么顺序做、每一步的"完成"长什么样、第一行代码从哪写。
> 细节往哪查见第 1 节"文档地图"，不在本文重复抄写。
>
> **状态**：开发启动版 · 2026-06-10 · 准备进入编码

---

## 1. 文档地图（单一事实来源）

开发期间遇到分歧，以本表指定的"权威文档"为准，不要凭记忆：

| 主题 | 权威文档 | 用途 |
|---|---|---|
| 总需求、两大场景、前后端设计、API 清单、分期计划 | `workbench-requirements-and-design-v1.md` | **主设计**，本文不重复，只做收敛与排期 |
| 账号中心（地基）详细设计 | `unified-account-center-design.md` | P1 直接照着写 |
| 已定技术决策（FastAPI/PG/Docker/单管理员/禁令） | `unified-content-platform-prd.md` + `backend-module-final-review.md` | 架构红线 |
| 各原项目能力、登录态实现细节 | `backend-module-architecture-*.md` | 写适配器时查 |
| 本文 | `development-master-plan.md` | **开发总纲，每天对照它推进** |

> 文档若冲突：本文 > v1 设计 > 账号中心设计 > PRD/final-review > 各模块架构文档。
> 本文与 v1 设计的关系：v1 是"全景蓝图"，本文是"施工顺序与第一锹土"。

---

## 2. 一页纸说清我们在做什么

把工作区里 6 个独立项目（bili-sync / dysync.net / MediaCrawler / wechat-article-exporter / yt-dlp / faster-whisper）的能力，整合成**一个统一的素材采集管理平台**，核心价值两条：

1. **稳定持续产出素材**：关键词采集 + 账号订阅同步 → 视频/文章入库 → 转录 → AI 分析 → 看板。
2. **统一管理所有平台登录态**（用户反复强调的命脉）：一个页面看全所有号死活、加密保存、自动体检、掉线能补。

新建一个 `platform-api`（Python + FastAPI）作主控，原项目退居为后端能力模块，**不再对用户暴露各自的前端/CLI/认证/配置**。前端是一个 Vue 3 工作台。AI 工具（Claude Code / Codex）与前端共用同一套 API。

---

## 3. 架构红线（不可违反的硬约束）

这些是已定决策，写代码时当成"地基钢筋"，不要中途自行更改：

1. **后端 = Python + FastAPI**；**数据库 = PostgreSQL**（本地开发可 SQLite，表结构两者通用）；**部署 = Docker Compose**（api + worker + postgres 三容器）。
2. **单管理员模式**，不做多用户/多角色。
3. **凭证一律 AES-GCM 加密入库**；密钥来自环境变量/keyfile，**绝不进库、绝不进 git**；前端与 API 响应**永远脱敏**，明文凭证只进不出。
4. **API 即产品**：前端、MCP、外部 HTTP 客户端走同一套 `/api/*`。鉴权两轨：管理员 session token（前端）、API Key 带 scope+限流（AI/外部）。**绝不出现"只有网页能做的操作"**。
5. **任务队列用 PostgreSQL 表实现**（`SELECT ... FOR UPDATE SKIP LOCKED`），**不引入 Redis/Celery**。
6. **一个 API 进程 + 一个 worker 进程**：API 只做轻活，下载/转录/分析重活全丢 worker。
7. **文件路径一律 `storage_root + relative_path`**，兼容 Linux/macOS 挂载、Windows 盘符与 UNC；**外部 API 不得提交绝对输出路径**。
8. **指标走势从第一天就存快照**（`content_metric_snapshot`），否则历史趋势补不回来。
9. **明令禁止带入**：wechat-exporter 的 `_debug` 明文导出、明文 KV；dysync 默认密码 `douyin/douyin2026`；yt-dlp 的插件/自更新/ExecPP/file URL/任意外部参数；faster-whisper 直接暴露 Python API（必须经队列+worker）；MediaCrawler 在授权凭据归档前不抽代码（一期走 CLI 子进程规避）。

---

## 4. 关键技术结论：登录态如何"在自己电脑登录 → 传服务器用"（已验证）

这是用户核心诉求，已实测验证，结论写死如下，P1 据此实现：

1. **服务器是无头的**（无 DISPLAY），日常登录在用户自己有图形界面的电脑上。因此登录态采用**"本地浏览器提取 → 上传服务器"**模式，而非在服务器扫码。
2. **不碰任何破解**：从**活着的、已登录的浏览器**取明文 cookie 是标准做法，**完全绕开** Chrome 127+ 在 Windows 上的 App-Bound Encryption（那是防磁盘文件解密的，与活浏览器导出无关）。
3. **两种干净方案**：
   - **方案 A（P1 首选）**：用户在自己电脑装开源扩展 **Get cookies.txt LOCALLY**，登录后一键导出 Netscape/JSON cookie 文件 → 上传到账号中心 → 校验 → 加密入库。零破解、小白可用、最符合"快捷方便"。
   - **方案 B（后续自动化）**：用户电脑 Chrome 带 `--remote-debugging-port` 启动，平台经 CDP `Network.getAllCookies` 全自动抓取。本服务器现有 `127.0.0.1:9222` 调试端口实例，已证明该路径在本环境可跑。
4. **必须诚实告知用户的硬限制**：**抖音、B站走 MediaCrawler 关键词抓取时，光有 cookie 不够**——请求签名（`a_bogus`/`msToken`/WBI key）要在活浏览器 localStorage 里现算。
   - ✅ cookie 提取方案对**"账号登录态统一管理"100% 成立**。
   - ✅ 对 **bili-sync 的 B站同步、dysync 的抖音同步**（纯 cookie 路径）**完全够用**。
   - ⚠️ 仅对**抖音/B站的关键词抓取**这一项，cookie 解决登录态但解决不了签名，那部分仍需 browser_runtime（排在 P4 之后专项）。

> 详细方案与端到端流程见 `unified-account-center-design.md` 决策 C 与第 9 章。

---

## 5. 开发分期总表（施工顺序）

沿用 v1 第 6 节并锁定为开发节奏。**每期必须是"用户能验收的闭环"，不允许交付半成品。**

| 期 | 主题 | 交付物 | 用户视角验收标准 |
|---|---|---|---|
| **P0** | 工程骨架 | 仓库结构 + FastAPI 启动 + PG/SQLite 连接 + 加密工具 + Docker Compose + 前端框架空壳 + 登录 | `docker compose up` 能起来，浏览器能打开登录页并登入空工作台 |
| **P1** | 账号中心（地基） | 账号 CRUD + 加密存取 + cookie 文件上传/粘贴录入 + B站/抖音探活 + 定时体检 + 账号列表页 | 打开网页看到所有账号死活，掉线能补，凭证全程脱敏 |
| **P2** | 同步闭环 | B站+抖音订阅同步（收藏夹/博主）→ 入库 → 下载队列 → 素材库页 | 勾选的收藏夹/博主新视频自动出现在素材库且文件落盘 |
| **P3** | 转录流水线 | faster-whisper worker + 处理队列页 + 详情页转录展示 | 几十条/天自动转完，失败可重试，文本可读可导出 |
| **P4** | AI 接入 | API Key + MCP Server + 扫码登录 API + 调用日志页 | 在 Claude Code 里完成"查状态/扫码登录/建任务/拿转录" |
| **P5** | 关键词采集 | MediaCrawler 适配（抖音/B站/小红书搜索）+ 采集页 + 指标快照 | 关键词任务定时跑，热门内容进候选池 |
| **P6** | 看板+分析 | 数据看板 + 大模型分析（公众号仅保留单篇 URL 导入，不做订阅同步） | 看板看走势，素材有 AI 摘要；单篇文章可导入 |
| **专项** | browser_runtime | 抖音/小红书浏览器自动登录 + 抖音/B站抓取签名 | 不阻塞主线，P4 后插入 |

依赖关系：P0 → P1 是强前置（没有账号中心，后面都拿不到登录态）；P2~P6 都建立在 P1 的凭证之上；P4 只是把 P1~P3 已稳定的 API 套薄壳，故提前到 P3 之后。

---

## 6. 工程骨架（P0 要建出来的目录）

以 v1 第 4.1 节为准，落地为如下结构。**P0 先把目录和空文件建出来，后续每期往里填。**

```text
platform-api/
├── app/
│   ├── main.py                # FastAPI 入口 + 托管 SPA 静态文件
│   ├── config.py              # 配置加载（env / .env）
│   ├── db.py                  # SQLAlchemy 引擎 + session
│   ├── api/                   # 路由层（与前端页面一一对应）
│   │   ├── auth.py            # 登录/改密                    [P0]
│   │   ├── accounts.py        # 账号中心                      [P1]
│   │   ├── crawl_tasks.py     # 关键词采集                    [P5]
│   │   ├── subscriptions.py   # 订阅同步                      [P2]
│   │   ├── assets.py          # 素材库                        [P2]
│   │   ├── pipeline.py        # 处理队列                      [P3]
│   │   ├── analytics.py       # 数据看板                      [P6]
│   │   ├── ai_access.py       # API Key / 调用日志            [P4]
│   │   └── system.py          # 设置 / 诊断                   [P0 雏形, P6 补全]
│   ├── modules/               # 平台能力适配层（统一接口）
│   │   ├── base.py            # 统一接口定义                  [P1]
│   │   ├── bilibili/          # 适配 bili-sync                [P1 探活, P2 同步]
│   │   ├── douyin/            # 适配 dysync.net               [P1 探活, P2 同步]
│   │   ├── wechat_mp/         # 适配 wechat-exporter          [P6]
│   │   ├── xhs/               # 适配 MediaCrawler 小红书       [P5]
│   │   ├── crawler/           # MediaCrawler 关键词入口        [P5]
│   │   ├── media_download/    # yt-dlp 封装（安全白名单）      [P2]
│   │   └── transcription/     # faster-whisper 封装           [P3]
│   ├── core/
│   │   ├── crypto.py          # 凭证 AES-GCM 加解密            [P0]
│   │   ├── scheduler.py       # APScheduler 定时              [P1]
│   │   ├── queue.py           # PG 任务队列                   [P3]
│   │   ├── storage.py         # storage_root + relative_path  [P2]
│   │   └── events.py          # SSE 事件流                    [P3]
│   ├── models/                # SQLAlchemy 模型               [P0 建账号表, 各期补]
│   └── workers/               # 下载/转录/分析消费者           [P3]
├── mcp_server/                # MCP 薄壳，内部调同一套 HTTP API [P4]
├── web/                       # Vue 3 前端源码                 [P0 框架, 各期补页面]
├── alembic/                   # 数据库迁移                     [P0]
├── docker-compose.yml         # api + worker + postgres        [P0]
├── .env.example               # 配置样例（含加密密钥位）       [P0]
└── README.md                  # 启动说明                       [P0]
```

数据表落地顺序（v1 第 4.3 节共 12 张）：
- **P0/P1**：`platform_account`、`account_credential`、`credential_audit_log`
- **P2**：`subscription`、`sync_run`、`content_item`、`media_asset`、`storage_root`
- **P3**：`job_queue`、`transcript`
- **P5**：`crawl_task`、`crawl_run`、`content_metric_snapshot`
- **P6**：`analysis_result`
- **P4**：`api_key`、`api_call_log`

---

## 7. P0 详细任务清单（第一锹土，可直接开工）

P0 目标：**一个能启动、能登录、能连库、能加密的空骨架**。不含任何业务功能，但把所有红线（加密/单管理员/Docker/前后端同源）立住。

1. **建仓库骨架**：按第 6 节建 `platform-api/` 目录树与空文件，写 `README.md` 启动说明。
2. **依赖与配置**：`pyproject.toml`（fastapi / uvicorn / sqlalchemy / alembic / cryptography / apscheduler / pydantic-settings）；`.env.example` 含 `DATABASE_URL`、`CREDENTIAL_ENC_KEY`、`ADMIN_PASSWORD_HASH`、`SESSION_SECRET`。
3. **数据库接入**：`db.py` 建引擎与 session；Alembic 初始化；先建账号中心 3 张表的 migration。
4. **加密工具 `core/crypto.py`**：基于 `cryptography` 的 AES-GCM，提供 `encrypt(plaintext)->blob` / `decrypt(blob)->plaintext`；密钥从 `CREDENTIAL_ENC_KEY` 读，缺失则启动报错并提示生成方式。**写单元测试覆盖加解密往返。**
5. **登录与鉴权 `api/auth.py`**：`POST /api/auth/login` 校验管理员密码（bcrypt/argon2 哈希，不存明文）→ 发 session token；FastAPI 依赖项做 token 校验；首启若未设密码强制设置（杜绝 dysync 默认密码问题）。
6. **SPA 托管 `main.py`**：FastAPI 挂载 `web/dist` 静态目录 + SPA fallback；`/api/*` 之外都回 `index.html`。
7. **前端框架 `web/`**：Vue 3 + TS + Vite + Element Plus + Pinia + axios 封装（自动带 token、401 跳登录）；建出 9 页导航骨架（仅"总览"和"账号中心"留空壳，其余占位）；登录页可用。
8. **Docker Compose**：`api` + `postgres` 两容器先跑通（worker 容器 P3 再加）；`docker compose up` 后浏览器能打开登录页并登入。
9. **诊断雏形 `api/system.py`**：`GET /api/system/diagnostics` 先返回 数据库连通 / 加密密钥就位 两项，为后续逐项扩展打底。

**P0 验收**：`docker compose up` → 浏览器打开 → 输入管理员密码登录 → 看到空工作台导航 → 加解密单测通过。

---

## 8. 开发工作流约定

- **每个子项目独立工具链**：`platform-api` 用其自己的 venv/uv；改动 bili-sync 等原项目时 `cd` 进去用各自工具链，遵守 `CLAUDE.md` 的 per-project 命令。**不做跨项目重构**。
- **提交粒度**：在 `platform-api` 内按"一个可验收的小功能"提交；遵守 Conventional Commits（`feat:`/`fix:`/`chore:`）。本工作区无根 git 仓库，**只在受影响子项目内提交**。
- **每期收尾**：跑通该期"用户视角验收标准" + 后端单测 + 前端 `build` 通过，才算该期完成。
- **安全自查**（每次涉及凭证/路径/外部参数的改动）：凭证是否加密、响应是否脱敏、路径是否走 storage_root、外部 API 是否拒收绝对路径/任意参数。
- **不提交**：cookie、token、本地数据库、生成的媒体、日志、`.env`。

---

## 9. 当前待办（下一步）

P0 已可开工。开始编码前需用户拍板一个问题（见随后提问），其余按本文推进即可。

- [ ] **P0-1** 建 `platform-api` 骨架目录与配置
- [ ] **P0-2** 加密工具 + 单测
- [ ] **P0-3** 数据库接入 + 账号 3 表 migration
- [ ] **P0-4** 登录鉴权 + 强制改密
- [ ] **P0-5** 前端框架 + 9 页导航空壳 + 登录页
- [ ] **P0-6** Docker Compose 跑通
- [ ] **P0-7** P0 验收

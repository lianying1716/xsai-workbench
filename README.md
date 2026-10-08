# xsai-workbench · 星算工作台

统一的素材采集与管理平台工作区。这里同时存放**我们自己的代码/文档**和若干**第三方上游项目**，
两者边界严格区分。

## 仓库结构

本工作区有两类内容，**分别由不同的 git 仓库托管**：

### 我们自己的（本仓库 `xsai-workbench` 托管）

| 路径 | 内容 |
|------|------|
| `docs/` | 平台需求、设计、开发总纲与分期计划（`docs/plans/`） |
| `logo-gen/` | 品牌标志「星采 / Stargather」的生成脚本与原始素材 |
| `AGENTS.md` / `CLAUDE.md` | AI 协作规则（编码代理读取） |

### 我们自己的（独立仓库托管）

| 路径 | 仓库 |
|------|------|
| `platform-api/` | https://github.com/lianying1716/platform-api —— 统一平台的主体代码（FastAPI + Vue3） |

### 第三方上游（**不纳入本仓库**，各自是独立仓库，只读参考）

| 路径 | 上游 |
|------|------|
| `bili-sync/` | amtoaer/bili-sync（MIT）—— B站收藏/合集同步（Rust + Svelte） |
| `dysync.net/` | jianzhichu/dysync.net（MIT）—— 抖音收藏同步（.NET + Vue） |
| `faster-whisper/` | SYSTRAN/faster-whisper —— Whisper 转录（CTranslate2） |
| `MediaCrawler/` | NanmiCoder/MediaCrawler（非商业学习许可，已获授权）—— 多平台采集 |
| `wechat-article-exporter/` | wechat-article/wechat-article-exporter（MIT）—— 公众号文章导出 |
| `yt-dlp/` | yt-dlp/yt-dlp —— 通用媒体下载 |

> 上游项目的代码**只读、只参考**，按各自许可证改编进 `platform-api` 时须署名，
> 详见 [`docs/license-and-usage-compliance.md`](docs/license-and-usage-compliance.md)。

## 文档从哪里开始读

1. [`docs/development-master-plan.md`](docs/development-master-plan.md) —— **开发总纲**，每天对照推进
2. [`docs/workbench-requirements-and-design-v1.md`](docs/workbench-requirements-and-design-v1.md) —— 主设计（需求 / API / 分期）
3. [`docs/unified-account-center-design.md`](docs/unified-account-center-design.md) —— 账号中心详细设计
4. [`AGENTS.md`](AGENTS.md) —— 仓库约定、架构红线、命令速查（**动手前先读**）

## 分支约定

`main` 是唯一主线；`feat/*`、`fix/*`、`docs/*` 等一律为临时分支，验收后合回 `main` 并删除。

## 开发

主平台在 `platform-api/`，进入该目录按其 `README.md` 操作
（`uv sync` → `uv run uvicorn app.main:app --port 9100`；前端 `cd web && npm run dev`）。

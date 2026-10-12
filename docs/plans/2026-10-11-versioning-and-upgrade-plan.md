# 版本系统与快捷升级 · 实施计划

> 日期：2026-10-11 · 设计：`docs/plans/2026-10-11-versioning-and-upgrade-design.md`
> 契约：**要么完整成功，要么在对外服务前失败并保持升级前状态**（四个不变量 I1–I4）。

**Goal:** 落地"防崩溃"版本/升级系统：版本单一来源、启动双向门禁、迁移单飞加锁、强制备份、
发布流水线、兼容矩阵。全部改动只在 `platform-api/` 内。

## Global Constraints
- 只在 `platform-api/` 内改动；Conventional Commits。
- 现有测试全绿；新增测试不得依赖外网。
- 迁移保持单事务（禁止 `CONCURRENTLY` / 独立 `COMMIT`）。
- 保留逃生开关（`PLATFORM_ALLOW_UNKNOWN_DB`）供人工排障。

## 不变量到实现的映射
| 不变量 | 实现 |
|---|---|
| I1 原子性 | 保持 Alembic 单事务（默认，不启用 `transaction_per_migration`）+ 评审红线 |
| I2 排他性 | `PLATFORM_RUN_MIGRATIONS` 单飞 + `alembic/env.py` advisory lock |
| I3 门禁性 | `app/core/version_guard.py` 双向版本门禁，失败拒绝启动 |
| I4 可恢复性 | `scripts/backup.sh` / `restore.sh` / `upgrade.sh` + 兼容矩阵 |

---

### Task 1: 版本单一来源 + 版本端点
**Files:** Create `app/core/version.py`；Modify `app/main.py`、`app/api/system.py`、`web/src/pages/Diagnostics.vue`；Test `tests/test_version.py`
**Produces:** `app_version`（构建注入，回退 `0.0.0-dev+<commit>`）、`git_commit`、`build_time`、
`db_revision`、`db_head`、`db_in_sync`；`GET /api/system/version`（公开只读）。
- [x] 测试：构建注入优先 / dev 回退 / 版本端点字段齐全 + 公开可访问（`tests/test_version.py`）

### Task 2: 启动双向版本门禁
**Files:** Create `app/core/version_guard.py`；Modify `app/config.py`、`app/main.py`；Test `tests/test_version_guard.py`
**Produces:** 分支——同步放行 / 落后自动迁移 / 空库严格迁移 / 未知 revision 拒启 / 逃生开关 / 开发宽松；
`auto_migrate`、`allow_unknown_db` 设置。
- [x] 测试：全部分支 + 迁移后复核（`tests/test_version_guard.py`，10 项）

### Task 3: 迁移单飞 + advisory lock
**Files:** Modify `docker-entrypoint.sh`、`docker-compose.yml`、`alembic/env.py`；Test `tests/test_migration_lock.py`
**Produces:** `PLATFORM_RUN_MIGRATIONS` 控制；PG advisory lock + `lock_timeout`；SQLite 自动跳过。
- [x] 测试：SQLite 跳过；PG 全量迁移；并发持锁串行化；锁可重入（`tests/test_migration_lock.py`）

### Task 4: 发布流水线 + 镜像驱动 compose
**Files:** Create `.github/workflows/release.yml`；Modify `Dockerfile`、`docker-compose.yml`
**Produces:** tag → 测试 → multi-arch 镜像 → GHCR；compose `image:` + `PLATFORM_VERSION` 锁版本。
- [x] workflow YAML 合法性校验；compose（含 build override）`config` 校验通过

### Task 5: 备份 / 还原 / 升级脚本
**Files:** Create `scripts/backup.sh`、`scripts/restore.sh`、`scripts/upgrade.sh`
**Produces:** 强制备份（pg_dump + data 卷 + manifest）、还原、升级编排。
- [x] `bash -n` 语法校验；卷名解析与存在性检查

### Task 6: 兼容矩阵与升级文档
**Files:** Create `docs/upgrade-compatibility.md`；Modify `README.md`
**Produces:** 版本兼容表、Docker/本地两套升级步骤、回滚说明、保证契约与排障表。
- [x] `docs/upgrade-compatibility.md` + README「版本与升级」章节 + `.env.example` 新键

### Task 7: 升级演练测试（防回归）
**Files:** Create `tests/test_upgrade_rehearsal.py`
**Produces:** PG 上"旧版数据 → upgrade head → 断言数据/版本"的自动化演练。
- [x] 跑通（4 项）+ 全量回归 707 passed

## 验收记录（2026-10-11）
- 全量测试：`uv run pytest tests/ -q` → **707 passed**（含新增 1+10+4+4 项）。
- 端到端：严格模式（`AUTO_CREATE_TABLES=false`）空库启动 → 自动迁移到 0019 → `db_in_sync=true`。
- 门禁拒启：revision 置 `0099` → 启动报 `版本门禁未通过（reject）`，exit code 3。
- 逃生开关：`PLATFORM_ALLOW_UNKNOWN_DB=true` → 正常启动（HTTP 200）。
- 前端：`vite build` 通过（诊断页新增版本卡片）。
- 现场清理：临时库/日志已删除。

## 对抗性审查与修复（2026-10-11）

用 21 组攻击场景实际压测（非纸面推演），确认 3 处严重/中等问题并修复：

| # | 问题 | 后果 | 修复 |
|---|---|---|---|
| 1 | `restore.sh` 只校验 `db.dump`，却先 `rm -rf /data` 再解压 | 备份缺 `data.tar.gz` 时 `secret.key` 被永久抹掉 | 解压前校验存在+可解压；改为"先解压到 stage、成功再原子替换" |
| 2 | 多 head 时 `db_head()` 返回空 → 门禁 fail-open 放行 | 迁移链自相矛盾时安全闸失效 | 新增 `db_heads()`；多 head/空脚本在严格模式 fail-closed 拒启 |
| 3 | CI 无 PG service，迁移测试静默 skip | CI 绿灯但安全测试从未真跑 | workflow 加 postgres service + 就绪探测 + skip 断言 |
| 4 | 镜像未设 `AUTO_CREATE_TABLES`，直接 `docker run` 走宽松门禁 | 生产默认值不安全 | Dockerfile 显式 `PLATFORM_AUTO_CREATE_TABLES=false` |
| 5 | `create_all` 建表不写 revision，与 `alembic upgrade` 撞表 | 本地源码升级报 `table already exists` | `init_db` 建表后 stamp 到 head；已有迁移记录的库跳过 create_all |
| 6 | `lock_timeout` 泄漏到复用连接 | 后续查询莫名带 5s 超时 | 退出时复位为原值（+ 回归测试） |

### 压力测试确认站得住的（正向）
- **I1 单事务原子性**：迁移链尾部插必败脚本 → 报原始错误、整库回滚到无 `alembic_version`。
- **I2 并发排他**：全新库同时启动 3 个 API → 全 200、单次迁移、0 错误、收敛到 0019。
- **I3 门禁**：连不上库 fail-closed 拒启；逃生开关可控放行。

### 修复后回归（2026-10-11）
- 全量测试：`uv run pytest tests/ -q` → **719 passed**。
- 端到端复验：严格模式空库启动迁移到 head、未知 revision 拒启（exit 3）均保持有效。
- 修复过程中发现并修正一处测试污染（`importlib.reload(app.db)` 泄漏模块级 engine），已改为 monkeypatch 隔离。

## Task 8：前端「版本与升级」入口（2026-10-11）

**背景**：此前版本卡片挂在孤儿组件 `Diagnostics.vue`（无任何路由引用，用户看不到）。
本轮把入口放进**可达**的「系统设置」页新增标签 `版本与升级`。

- 只读区：应用版本 / commit / 构建时间 / `db_revision` / head / 同步状态（调 `GET /api/system/version`）。
- 检查更新：`GET /api/system/update/check` → 只读查 GitHub Releases，比对当前版本。
- 一键升级：`POST /api/system/upgrade` → 调 updater 边车（默认关闭）。

### 一键升级的安全形态（为什么这样做）
网页一键升级是全系统风险最高的一环，按"隔离 + 默认关闭 + 白名单"设计：

| 措施 | 说明 |
|---|---|
| 独立边车 | `app/updater/` 独立进程，持有 docker socket，**不映射宿主端口** |
| 默认关闭 | 未配置 `PLATFORM_UPDATER_URL`/`PLATFORM_UPDATER_TOKEN` → 前端不显示按钮 |
| 共享密钥 | 后端调边车带 `X-Updater-Token`，`secrets.compare_digest` 校验 |
| 版本白名单 | 正则 `^v?\d+\.\d+\.\d+...$`，拒绝 `; & \| $ /` 等注入 |
| 操作白名单 | 只重建 `platform-api`/`platform-worker`，绝不动 `db` 与自身 |
| compose profile | `--profile updater` 才启用，不需要时容器根本不起 |

启用方式（见 `.env.example` 注释）：生成密钥 → 填 `PLATFORM_UPDATER_URL=http://platform-updater:9200`
和 `PLATFORM_UPDATER_TOKEN` → `docker compose --profile updater up -d`。

> **安全提示**：updater 容器持有 docker socket（等价 root 权限），只在受信环境启用。
> 与成熟项目一致，普通用户仍推荐命令行 `./scripts/backup.sh` + `./scripts/upgrade.sh`。

### 本轮回归
- 全量测试：`uv run pytest tests/ -q` → **729 passed**（新增 updater/检查更新/白名单共 10 项）。
- 端到端：未启用 → `enabled=false`；启用后 `enabled=true`、非法版本 422、updater 不可达 502。
- 前端：`vite build` 通过。

## Task 9：网页升级 · 全套方案（2026-10-11）

用户明确要求"网页升级必须做好全套"。此前只是一个接口；本轮实现完整编排引擎，
并在真实 Docker 上端到端验收。

### 编排引擎 `app/updater/engine.py`
流程：**备份 → 拉取镜像 → 重建服务 → 健康校验 →（失败）自动回滚**。
状态机与依赖全部注入，7 项测试覆盖每条契约：

| 契约 | 保证 |
|---|---|
| 备份是硬前置 | backup 失败立即中止，绝不无备份升级 |
| 健康校验 | 重建后探测新版本；不健康自动回滚到旧版本 |
| 自动回滚 | pull/recreate/verify 任一失败 → 回滚并置 `rolled_back` |
| 并发锁 | 同一时刻只允许一个升级，第二个返回 409 |
| 进度可查 | 每步写入 `job.steps`，终态可查 |

### 为什么放在边车、为什么后台执行
升级会重建 `platform-api` 自身，主 API 进程随之退出。状态必须存活在**不会重启的边车**里，
前端才能在升级全程轮询进度。因此 `POST /upgrade` 立即返回 `accepted`，
后台线程执行编排，`GET /upgrade/status` 供轮询；主 API 提供代理端点。

### 真实 Docker 端到端（本次实测，非纸面）
起真实栈（api + worker + db + updater）→ 触发网页升级 → 观察编排：

- 备份真实产出 `backup-<ver>-<ts>.tar.gz`（含 `db.dump` + `data.tar.gz` + `manifest.json`）。
- 真实执行 `docker compose pull` / `up -d --no-deps platform-api platform-worker` 重建容器。
- 健康校验通过，终态 `success`。

### 端到端过程中发现并修复的 4 个真实缺陷
| # | 缺陷 | 后果 | 修复 |
|---|---|---|---|
| 1 | 主镜像不含 `docker` CLI | 边车调 `docker compose` 直接 `FileNotFoundError`，网页升级**任何环境都跑不起来** | 新增 `Dockerfile.updater`（主镜像 + docker CLI + compose 插件），CI 一并发布 `-updater` 镜像 |
| 2 | `docker compose` 项目名靠目录名推导 | 边车在容器内推导的项目名与真实栈不一致 → `service "db" is not running` | compose 固定 `name: platform-api` + 边车设 `COMPOSE_PROJECT_NAME` |
| 3 | `pg_dump -Fc` 经 `text=True` 解码 | 二进制转储触发 `UnicodeDecodeError`，备份失败 | 改二进制管道直接写文件 |
| 4 | 硬编码服务名 `platform-worker` | 服务集不同的栈 pull 整体失败 | `_present_services()` 探测实际服务，只操作存在的 |

### 前端（完整编排体验）
「系统设置 → 版本与升级」：版本信息卡 + 检查更新 + 一键升级（二次确认 + 进度条 `el-steps`
逐步展示 + 回滚/失败提示 + 备份路径）。升级后自动刷新版本。

### 回归
- 全量测试：`uv run pytest tests/ -q` → **739 passed**（新增引擎 7 项 + 边车 8 项 + 检查更新 5 项）。
- 真实 Docker 端到端：编排 4 步全通过，终态 `success`。
- 前端 `vite build` 通过；现场（临时栈/镜像/卷）已清理。

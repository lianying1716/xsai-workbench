# 版本系统与快捷升级设计（对标成熟开源项目）

> 日期：2026-10-11 · 状态：**调研 + 定稿方案，待实施**
> 触发问题：用户在 Docker 或本地源码方式运行平台后，如何识别版本、如何升级，
> 以及——**如何设计得足够稳，不让升级本身成为系统崩溃的来源**。

---

## 0. 结论先行

我们最初的方案（tag + 镜像 + pull/up + 备份）方向对，但**还不足以“一次做对”**。
对标 Immich / Gitea / NetBox / Grafana / Outline / Twenty 之后，成熟项目在四件事上高度一致，
而我们目前全都没有：

1. **版本双向门禁**：不仅旧代码配新库要拒启，**新代码配旧库要先自动迁移、迁移失败要拒启**。
2. **迁移单飞**：全栈只有一处、且带 DB 级互斥锁地跑迁移；绝不允许 api/worker 各跑一遍。
3. **迁移前强制备份**，且**默认不支持降级**（schema 只前进，回滚靠恢复备份）。
4. **兼容性声明**：明确“能跳多少、先升到哪、哪些是 breaking”。

**防崩溃的核心不是把升级做得更自动，而是把升级做成“要么完整成功，要么明确失败并停在安全点”。**

**关于“绝不崩溃”**：软件业没有“升级绝不失败”这回事，任何开源项目（含 Immich/Gitea/NetBox）
都不这么承诺。我们把它换成可验证、可兑现的契约——**要么完整成功，要么在对外服务前失败并
保持可运行状态，绝不留下半迁移的中间态**。详见 [3.9 保证模型](#39-绝不因升级崩溃如何兑现保证模型)。
好消息是我们的单事务迁移（I1）**已经天然满足**，缺的是排他、门禁、备份三项。

---

## 1. 我们项目的现状（核查证据）

| 事项 | 现状 | 证据 |
|---|---|---|
| 版本号 | 三处硬编码 `0.1.0`，互不联动 | `platform-api/pyproject.toml:3`、`app/main.py:44`、`web/package.json` |
| git tag | **0 个** | `git tag -l` 为空 |
| CI / 镜像仓库 | **都没有** | 无 `.github/`；`docker-compose.yml:3,30` 全是 `build: .` |
| 版本查询端点 | 无 | `app/main.py` 无 version 路由 |
| 迁移执行 | 启动时 `alembic upgrade head`，api 与 worker **各跑一次** | `docker-entrypoint.sh:6`、`docker-compose.yml:2,30` |
| 迁移互斥 | **无**（Alembic 默认不加锁） | 同上 |
| schema 兼容守卫 | **无**：旧代码可对着新库启动 | 无相关代码 |
| 降级能力 | Alembic 有 `downgrade`，但项目迁移多为单向数据合并 | `alembic/versions/0011`、`0012`、`0015` 的脏数据处理 |
| 备份脚本 | **无** | `scripts/` 下只有 seed/export/verify |
| 持久化 | `platform-data`（含 `secret.key`）+ `pg-data` | `docker-compose.yml:13,37,52` |

**关键缺口**：现在升级时“我装的是哪版、DB 到哪个 revision、升级能不能原地回退”三个问题都答不上来；
更危险的是 api/worker 双写迁移 + 旧代码可配新库，这两条已经埋着“升级即崩”的雷。

---

## 2. 成熟开源项目怎么做（带来源）

### 2.1 Immich

- 用 `.env` 里的 `IMMICH_VERSION` **锁定镜像 tag**，升级 = 改版本号 → `docker compose pull && docker compose up -d`。
- 语义化版本，**breaking changes 只允许出现在 major**；提供 `:v3` 这类跟随 major 的 metatag。
- 明确写：**降级不受支持**（"Downgrading to an earlier version, even within the same minor version, is not supported"）。
- 需要结构迁移时，文档给出**逐步 runbook**（先备份 → 改 compose → 启动 → 观察日志），并注明启动时会自动改库。
- 来源：<https://docs.immich.app/install/upgrading/>

**对我们的意义**：镜像 tag 驱动升级、`.env` 锁版本、默认不支持降级——这正是我们应该抄的骨架。

### 2.2 Gitea

- 版本兼容规则写得很清楚：同 `a.b.x` 的 patch 之间**可以升也可以降**（库结构不变）；
  跨 `a.c` 则**只升不降**，新版本会把旧库升级到新结构，旧版本无法再读。
- 因此规定：**升级数据库前必须先备份**，因为"you can not run an old Gitea with an upgraded database"。
- 启动时自动检查并执行迁移；迁移期间服务不可用，属正常。
- 提供 `contrib/upgrade.sh` 自动化"停止→备份→替换→启动"。
- 来源：<https://docs.gitea.com/installation/upgrade-from-gitea/>

**对我们的意义**：把"patch 可回滚、minor/major 只前进"这条规则显式写进我们的兼容矩阵。

### 2.3 NetBox

- 允许**直接升到任意更高版本**，但 major 升级必须先到上一 major 的**最后一个小版本**作为跳板。
- 升级前强制：读 release notes、**备份**、核对依赖版本（Python/PG）与插件兼容性。
- 迁移脚本与依赖检查纳入官方 `upgrade.sh`。
- 来源：<https://netboxlabs.com/docs/netbox/installation/upgrading/>

**对我们的意义**：即使允许直跳，也要定义"跳板版本"；依赖矩阵要随版本维护。

### 2.4 Grafana

- **有过真实事故**：两个 replica 同时启动时并发跑迁移，导致迁移失败、实例 **boot loop**；
  官方 issue 明确"解法应该是在迁移时对数据库加锁，并设 10–30s 超时"。
- 后续版本的迁移默认会对数据库加锁。
- 来源：<https://github.com/grafana/grafana/issues/41834>

**对我们的意义**：这正是我们 `platform-api` + `platform-worker` 同时跑迁移的同款风险；
**迁移加锁不是可选优化，是必修项。**

### 2.5 Outline / Twenty / Vaultwarden

- Outline、Twenty：新版本**启动时自动执行迁移**，官方要求**升级前先备份数据库**（或快照整盘）。
- Vaultwarden：可直接升到最新版，程序自动补齐缺失迁移。
- 共同点：**自动迁移 + 强制备份提示 + 靠备份而非 downgrade 回滚**。
- 来源：Outline 讨论 #6403、Twenty Upgrade guide、Vaultwarden 社区文档。

### 2.6 Alembic 并发迁移（我们的技术栈）

- Alembic **本身不带迁移锁**：多个进程同时对同一数据库执行 `alembic upgrade head` 时，
  会各自读到相同的当前 revision 并产生竞争（社区原文大意："Alembic has no built-in locking.
  Four processes calling `alembic upgrade head` against the same database at the same time
  will all read the same..."）。
- 社区通行做法：在 `env.py` 里用 **PostgreSQL advisory lock**（`pg_advisory_lock`）
  包住整个迁移；注意 advisory lock 是**会话级**的，必须在同一连接上取锁、迁移、再释放。
- 来源：<https://philipptheserver.com/posts/alembic-at-entrypoint/>、
  <https://alembic.sqlalchemy.org/en/latest/cookbook.html>

**对我们的意义**：直接在 `alembic/env.py` 加 advisory lock 是成本最低、收益最大的一个改动。

### 2.7 结论：成熟项目的一致性

| 做法 | Immich | Gitea | NetBox | Grafana | Outline/Twenty |
|---|---|---|---|---|---|
| `.env` 锁版本 + 镜像 tag | ✅ | ✅ | — | — | ✅ |
| 启动自动迁移 | ✅ | ✅ | 脚本 | ✅ | ✅ |
| 迁移加锁 | 未明确 | — | — | ✅ | — |
| 升级前强制备份 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 默认不支持降级 | ✅ | ✅ | 间接 | — | ✅ |
| 兼容矩阵 / 跳板版本 | ✅(major) | ✅ | ✅ | ✅ | ✅ |

**没有一家靠"downgrade 迁移"回滚，全部靠"备份 + 恢复"。**

---

## 3. 定稿方案

设计原则一句话：**升级必须是原子的、可检测的、可回退到安全点的；任何不满足前提的情况都拒绝启动。**

### 3.1 版本单一来源（Phase 1）

- git tag `vX.Y.Z` 是唯一发布事实；SemVer；breaking 只允许出现在 major（学 Immich）。
- 构建期注入三件套，写进镜像与前端：
  - `PLATFORM_BUILD_VERSION`（= tag）
  - `PLATFORM_BUILD_COMMIT`（= `git rev-parse --short HEAD`）
  - `PLATFORM_BUILD_TIME`
- 移除三处手写 `0.1.0`，统一从注入值读取；本地开发回退 `0.0.0-dev+<commit>`。
- 新增只读端点 `GET /api/system/version`，并显示在现有诊断页（`app/api/system.py:370`）：

```json
{
  "app_version": "v1.2.0",
  "git_commit": "be0eefe",
  "build_time": "2026-10-11T09:45:16Z",
  "db_revision": "0018",
  "db_head": "0018",
  "db_in_sync": true
}
```

### 3.2 启动双向门禁（Phase 1，防崩溃第一道闸）

新增 `app/core/version_guard.py`，在 `lifespan` 里**迁移之后、对外服务之前**执行：

| 场景 | 行为 |
|---|---|
| `db_revision == db_head` | 正常启动 |
| `db_revision` 是本镜像已知的历史 revision，且 `db_head > db_revision` | **自动执行迁移**（受 3.3 的单飞保护），再复核 |
| `db_revision` **不在**本镜像迁移链里（旧代码配新库） | **拒绝启动**，打印两个版本，提示改用匹配镜像 |
| 迁移失败 / 迁移后仍不同步 | **拒绝启动**，保持旧容器可回退 |
| `PLATFORM_ALLOW_UNKNOWN_DB=1` | 逃生开关，仅用于人工排障 |

配套：`PLATFORM_AUTO_MIGRATE`（默认 `true`）控制是否允许启动时自动迁移。
只读/演示实例可设 `false`，此时版本不匹配一律拒绝启动。

### 3.3 迁移单飞 + DB 互斥（Phase 1，防崩溃第二道闸）

- **只保留一个迁移入口**：`docker-entrypoint.sh` 不再无条件迁移，改为受
  `PLATFORM_RUN_MIGRATIONS` 控制；compose 里 `platform-api` 设 `true`、`platform-worker` 设 `false`，
  worker 通过 `depends_on: condition: service_healthy` 等 api 迁移完再起。
- **Alembic 加 advisory lock**：在 `alembic/env.py` 的 online 分支，用同一连接先
  `pg_advisory_lock(<常量key>)`，跑完迁移再 `pg_advisory_unlock`（会话级，锁-迁移-解锁必须在同一连接）。
  非 PG（本地 SQLite）自动跳过。
- 加锁后即使未来上多副本，也**只有一个实例真正迁移**，其余等待，杜绝 Grafana 那种 boot loop。
- 迁移加**超时**（如 `PLATFORM_MIGRATION_LOCK_TIMEOUT=60s`），拿不到锁就失败退出并重试，
  不让容器无限卡死。

### 3.4 升级前强制备份（Phase 2，防崩溃第三道闸）

- `scripts/backup.sh`：一次性产出带版本号的时间戳备份包，包含
  - `pg_dump`（自定义格式，可校验）
  - `/data` 卷（含 `secret.key`）
  - 当前 app 版本 + `alembic current`
- `scripts/upgrade.sh`（Docker 与本地两套）**先调用 backup.sh**，任何一步失败即中止。
- 备份是硬前置：**没有成功备份就不进入迁移**。
- `secret.key` 必须进备份——丢了等于所有凭证作废（项目红线）。

### 3.5 兼容矩阵与跳板版本（Phase 2）

新建 `docs/upgrade-compatibility.md`，每个版本一行：

| 目标版本 | 最低可直升版本 | 跳板要求 | 是否改结构 | 可否原地回滚 |
|---|---|---|---|---|
| v1.1.0 | v1.0.0 | 无 | 否 | 可（换 tag） |
| v1.2.0 | v1.0.0 | 无 | 是 | 否，需恢复备份 |
| v2.0.0 | v1.5.0 | 先升到 v1.5.x | 是 | 否 |

规则（学 Gitea/NetBox）：patch 内可升可降；minor/major 只前进；major 必须先到上一 major 的最后 patch。

### 3.6 发布流水线（Phase 2）

- GitHub Actions：打 `v*` tag → 跑测试 → 构建 multi-arch（amd64/arm64）→ 推 GHCR → 生成 release notes + checksum。
- 镜像 tag 三种：`v1.2.0`（精确）、`v1.2`（跟随 patch）、`v1`（跟随 major，学 Immich metatag）。
- compose 改 `image:` 驱动，`.env` 里 `PLATFORM_VERSION=v1.2.0` 锁定。
- 用户升级固定三步：

```bash
./scripts/backup.sh                       # 强制备份
PLATFORM_VERSION=v1.2.0 docker compose pull
PLATFORM_VERSION=v1.2.0 docker compose up -d
```

### 3.7 本地源码升级

```bash
git fetch --tags
git checkout "$TARGET_TAG"
uv sync --extra postgres --extra browser
./scripts/backup.sh                        # 同样强制
uv run alembic upgrade head
systemctl --user restart platform-api-dev platform-web-dev
```

### 3.8 回滚策略（写死为"不支持 downgrade"）

- patch 回退且未改结构：换回旧 tag 即可。
- 改了结构：**只走恢复备份**，不做 Alembic downgrade。
- 因为我们的迁移（0011/0012/0015）含不可逆的数据合并与清洗，**downgrade 会丢数据**。
  这一条要写进升级文档第一屏。

---

## 3.9 "绝不因升级崩溃"如何兑现（保证模型）

**先澄清一个必须澄清的工程事实**：软件业不存在"绝不失败"的升级系统——不是我们能力问题，
而是任何写代码的人都做不到。Immich / Gitea / NetBox 也从不这么承诺。所以目标不能设为
"升级绝不失败"，必须设为下面这个**可验证、可兑现**的契约：

> **任何一次升级，要么完整成功；要么在对外提供服务之前失败，并让系统保持/回到升级前的
> 可运行状态。绝不允许出现"迁移只做了一半、服务带着坏数据继续跑"的中间态。**

这条契约拆成四个可验证不变量（invariant）：

| 不变量 | 保证手段 | 违规即视为系统缺陷 |
|---|---|---|
| **I1 原子性** | 整次 `upgrade head` 在单事务里（Alembic 默认行为，我们已具备）；失败整体回滚到旧 revision | 出现半迁移状态 |
| **I2 排他性** | 迁移单飞（`PLATFORM_RUN_MIGRATIONS`）+ PG advisory lock | 两个进程同时迁移 |
| **I3 门禁性** | 版本双向门禁 + 迁移后复核；不同步就拒绝对外服务 | 坏代码配坏库对外服务 |
| **I4 可恢复性** | 升级前强制备份；迁移失败保留旧容器/旧 tag 可立即回退 | 失败后无法回到升级前 |

**我们已经天然满足 I1**（这是本次核查的新发现，也是好消息）：

- `alembic.ini` 未开启 `transaction_per_migration`，因此 Alembic 在 PostgreSQL 上**默认把
  整次 `upgrade head` 包在一个事务里**。任一迁移脚本抛异常，整批一起回滚，`alembic_version`
  保持旧值，数据库回到升级前——不会留下"做了一半"的 schema。
- 注意前提：迁移脚本内**不能**出现 `CREATE INDEX CONCURRENTLY`、`VACUUM`、
  独立 `COMMIT` 这类破坏单事务的动作。目前 `alembic/versions/` 里没有这类语句（已核查），
  但需要在评审清单里守住这条红线。

**I2/I3/I4 需要实现**，对应 Phase 1/2 的迁移单飞加锁、版本门禁、强制备份。

### 3.9.1 为什么"失败"仍是允许的结果

- **失败要早**：宁可在启动阶段明确报错停住，也不让服务带着不匹配的 schema 对外提供读写。
  带坏数据跑比直接不可用更危险——后者用户马上发现，前者可能悄悄写坏、几周后才发现。
- **失败要静**：容器保持 `restart: unless-stopped` 时，若迁移持续失败会反复重启、刷日志。
  因此迁移失败要**区分"可重试"与"需人工介入"**：拿不到锁属可重试；脚本报错属需人工，
  快速失败并保留现场日志，避免无限重启掩盖真实错误。

### 3.9.2 这套契约覆盖不到的边界（诚实声明，不承诺做不到的事）

- **数据语义错误无法靠事务防**：若迁移逻辑本身写错（例如回填算错字段），事务会成功提交，
  但数据是错的。这类只能靠 **I4 备份恢复 + 迁移测试（我们在 tests/ 已有 8 个迁移专项测试）
  + 升级演练** 兜底。
- **磁盘满 / OOM / 断电**属于基础设施故障；事务能保证 schema 一致，但需依赖备份恢复。
- **不可逆结构变更**（删列/合表，如 0011/0012/0015/0019）迁移一旦提交就无法自动回退，
  只能恢复备份——这正是 I4 存在的原因，也是所有成熟项目的共同选择。

**结论**：把目标从"绝不失败"改成上面的契约后，它是可以工程化保证并逐条验收的；
"绝不失败"则不可证伪、也不可验收。文档其余部分按这个契约组织。

---

## 4. 分期落地

### Phase 1 — 防崩溃底座（必须一起做，约 1 天）
1. 版本单一来源 + `GET /api/system/version`（诊断页展示）。
2. `version_guard`：双向版本门禁 + 拒启逻辑。
3. 迁移单飞：`PLATFORM_RUN_MIGRATIONS` + worker 依赖 api 健康。
4. Alembic advisory lock + 锁超时。
5. 单元测试：版本解析、门禁四分支、锁/SQLite 跳过。

### Phase 2 — 发布与升级（约 1–2 天）
6. GitHub Actions → GHCR multi-arch；tag 三种粒度。
7. compose 改镜像驱动 + `.env` 锁版本。
8. `backup.sh` / `upgrade.sh` / `restore.sh`。
9. `docs/upgrade-compatibility.md` + 升级文档（Docker/本地双份）。

### Phase 3 — 可运营与验收（约 1–2 天）
10. 诊断页"检查更新"（可选，只读查询 GitHub Releases）。
11. 升级演练进 CI：起旧版 → 灌数据 → 升新版 → 断言数据与凭证完好。
12. 回滚演练：故意让迁移失败，验证停在安全点、旧版本可恢复。

---

## 5. 验收标准（防崩溃的硬指标）

1. `docker compose up` 后 `GET /api/system/version` 的版本与镜像 tag 一致。
2. 从 vN 升 vN+1：数据、凭证、`secret.key` 全部保留，迁移**只执行一次**。
3. **并发演练**：同时启动 api+worker（或临时起 3 个 api），只有 1 个真正迁移，其余等待，无报错。
4. **旧代码配新库**：默认拒绝启动并给出可操作提示，不会静默写坏数据。
5. **迁移失败**：容器不进入对外服务，旧版本可立即回退。
6. **无备份不升级**：`upgrade.sh` 在备份失败时拒绝继续。
7. **恢复演练**：备份能在干净环境完整还原，还原后凭证仍可解密（`secret.key` 有效）。
8. patch 回滚：换回旧 tag 可正常启动（未改结构时）。

---

## 6. 参考来源

- Immich 升级与版本策略：<https://docs.immich.app/install/upgrading/>
- Gitea 升级与兼容规则：<https://docs.gitea.com/installation/upgrade-from-gitea/>
- NetBox 升级流程与跳板版本：<https://netboxlabs.com/docs/netbox/installation/upgrading/>
- Grafana 并发迁移事故：<https://github.com/grafana/grafana/issues/41834>
- Alembic 并发迁移加锁：<https://philipptheserver.com/posts/alembic-at-entrypoint/>
- Alembic 官方 Cookbook：<https://alembic.sqlalchemy.org/en/latest/cookbook.html>
- Outline 自升级讨论：<https://github.com/outline/outline/discussions/6403>
- Twenty 升级指南：<https://docs.twenty.com/developers/self-host/capabilities/upgrade-guide>

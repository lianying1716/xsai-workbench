# platform-api 收尾加固 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已经写出 P0–P6 主干、但尚不可交付的 `platform-api` 补成"一条命令起得来、测试裸跑全绿、可打包、可提交"的可验收产品。

**Architecture:** 不新增业务功能，只补齐工程闭环：测试隔离、worker 容器、环境样例、数据库迁移、前端构建托管、git 初始化、端到端验收。所有改动限定在 `platform-api/`（文档改在 `docs/`，见 Plan 2）。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / PostgreSQL(生产) + SQLite(开发测试) / uv / Docker Compose / Vue 3 + Vite / pytest / Alembic。

## Global Constraints

- 后端 = **FastAPI**；DB = **PostgreSQL**（本地开发/测试可用 SQLite，表结构须两者通用）；部署 = **Docker Compose**。
- **单管理员**模式；凭证 **AES-256-GCM** 加密入库，密钥来自环境变量/keyfile，**绝不进 git、绝不进库**，响应永远脱敏。
- **一个 API 进程 + 一个 worker 进程**：API 只做轻活，下载/转录/分析走 worker；队列用 **PostgreSQL 表**（`FOR UPDATE SKIP LOCKED`），**不引入 Redis/Celery**。
- 文件路径一律 `storage_root + relative_path`；外部 API 不得提交绝对路径或任意参数。
- 所有命令在 `platform-api/` 内执行；提交只在 `platform-api/` 内，用 Conventional Commits（`feat:`/`fix:`/`chore:`/`test:`/`docs:`）。
- Python 依赖用 **uv** 管理；前端用 **npm**（`web/package-lock.json` 为准）。
- 代码注释/文档可用中文（与现有代码一致）。

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `platform-api/tests/conftest.py` | 共享夹具：临时 SQLite + 随机密钥 + app 依赖覆盖；保证 `uv run pytest` 裸跑不连生产库 | Create |
| `platform-api/tests/test_accounts_api.py` | 去掉本地重复夹具，改用 conftest；修 `test_requires_auth` | Modify |
| `platform-api/pyproject.toml` | 加 `alembic` 依赖 | Modify |
| `platform-api/Dockerfile` | 保持单镜像，支持以 `command` 覆盖起 worker | Modify（仅注释说明） |
| `platform-api/docker-compose.yml` | 增 `platform-worker` 服务；api/worker 共用 DB 配置 | Modify |
| `platform-api/dev.sh` | 增 `worker` / `web` 子命令 | Modify |
| `platform-api/.env.example` | `PLATFORM_*` 配置样例 | Create |
| `platform-api/alembic.ini`、`platform-api/alembic/env.py`、`platform-api/alembic/versions/0001_baseline.py` | 迁移骨架 + 基线 | Create |
| `platform-api/README.md` | 补部署/迁移/worker 说明 | Modify |
| `platform-api/.git` | 初始化仓库并分次提交 | Create |

---

### Task 1: 测试基线（conftest + 裸跑全绿）

**Files:**
- Create: `platform-api/tests/conftest.py`
- Modify: `platform-api/tests/test_accounts_api.py`（删除本地 `client` 夹具，改 `test_requires_auth` 用 `anon_client`）
- Test: `platform-api/tests/`（全部）

**Interfaces:**
- Produces: pytest 夹具 `session`（内存库 Session）、`client`（已初始化管理员并带 token 的 `TestClient`）、`anon_client`（未登录 `TestClient`）。
- Consumes: 无（此任务为其余任务的测试基础）。

- [ ] **Step 1: 写失败测试（复现默认 pytest 连生产库失败）**

Run: `cd platform-api && uv run --extra dev --extra postgres pytest tests/ -q`
Expected: FAIL — `test_requires_auth` 报 `sqlalchemy.exc.OperationalError`/`ModuleNotFoundError: psycopg2`（因为未连本机 PG）。这就是要修的问题。

- [ ] **Step 2: 写 `tests/conftest.py`**

```python
"""pytest 共享夹具。

目标：`uv run pytest` 裸跑必绿——不依赖本机 PostgreSQL，也不读写真实 data/。
做法：
- 在导入任何 app.* 之前把 PLATFORM_DATABASE_URL 指到临时 SQLite 文件，
  避免模块级 engine（app.db.engine 在 import 时创建）连生产 PG。
- 每个测试用独立的内存 SQLite + 依赖覆盖，互不污染。
"""

import base64
import os
import tempfile

# 必须早于 app.config / app.db 的 import
os.environ["PLATFORM_DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.mkdtemp(prefix="platform-test-"), "test.db"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


def _fresh_key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


@pytest.fixture()
def _db_env(monkeypatch):
    """随机密钥 + 重置加密单例，保证测试之间不串。"""
    monkeypatch.setenv("PLATFORM_CREDENTIAL_ENC_KEY", _fresh_key())
    import app.config as config

    config.settings.credential_enc_key = _fresh_key()
    import app.core.crypto as crypto

    crypto._key = None


def _memory_engine():
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


@pytest.fixture()
def session(_db_env):
    """独立内存 SQLite 会话，已建全部表。"""
    engine = _memory_engine()
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    import app.models  # noqa: F401  注册全部模型
    from app.db import Base

    Base.metadata.create_all(engine)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def _app_with_overrides(_db_env, monkeypatch):
    """把 app 的 get_db 覆盖到独立内存库；关闭调度器与 init_db 连库。"""
    engine = _memory_engine()
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    import app.models  # noqa: F401
    from app.db import Base

    Base.metadata.create_all(engine)

    import app.db as db_mod
    import app.main as main_mod

    def override_get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    # main.py 用 from ... import 直接绑定了这些名字，需同时打补丁
    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    monkeypatch.setattr(main_mod, "start_scheduler", lambda: None)
    monkeypatch.setattr(main_mod, "stop_scheduler", lambda: None)
    main_mod.app.dependency_overrides[db_mod.get_db] = override_get_db
    yield main_mod.app
    main_mod.app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(_app_with_overrides):
    """未登录客户端（验证 401）。"""
    with TestClient(_app_with_overrides) as c:
        yield c


@pytest.fixture()
def client(_app_with_overrides):
    """已初始化管理员并带 token 的客户端。"""
    with TestClient(_app_with_overrides) as c:
        r = c.post("/api/auth/setup", json={"password": "test1234"})
        assert r.status_code == 200, r.text
        c.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
        yield c
```

- [ ] **Step 3: 改 `tests/test_accounts_api.py`**

删除该文件里第 15–70 行左右的本地 `@pytest.fixture() def client(...)`（整段），改用 conftest 的 `client`。文件顶部的 `import base64, os, pytest, create_engine, sessionmaker, StaticPool` 若不再使用则一并删掉（保留 `pytest` 若仍被 `_mock_check` 用到的是 `monkeypatch`，按实际清理）。

把 `test_requires_auth` 改为使用 `anon_client`：

```python
def test_requires_auth(anon_client):
    """不带 token 必须 401。"""
    assert anon_client.get("/api/accounts").status_code == 401
```

- [ ] **Step 4: 跑测试验证全绿**

Run: `cd platform-api && uv run --extra dev pytest tests/ -q`
Expected: PASS — `22 passed`（数量以实际为准），且**不出现**任何连 `127.0.0.1:5433` 或 `psycopg2` 的报错。

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add tests/conftest.py tests/test_accounts_api.py
git commit -m "test: isolate pytest from production DB with shared fixtures"
```

---

### Task 2: worker 容器化 + 本地启动脚本

**Files:**
- Modify: `platform-api/docker-compose.yml`
- Modify: `platform-api/dev.sh`
- Modify: `platform-api/Dockerfile`（仅注释，说明同一镜像可跑 worker）
- Test: `platform-api/docker-compose.yml`（`docker compose config` 校验）

**Interfaces:**
- Consumes: `python -m app.workers.runner`（已存在，轮询 `job_queue`）。
- Produces: compose 服务 `platform-worker`；`dev.sh worker` 子命令。

- [ ] **Step 1: compose 增 worker 服务**

把 `platform-api/docker-compose.yml` 改为（在 `platform-api` 与 `db` 之间插入 `platform-worker`）：

```yaml
services:
  platform-api:
    build: .
    ports:
      - "9100:9100"
    environment:
      PLATFORM_DATABASE_URL: postgresql+psycopg2://platform:platform@db:5432/platform
      PLATFORM_ACCOUNT_CHECK_INTERVAL: "15"
    volumes:
      - platform-data:/data
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  platform-worker:
    build: .
    command: ["python", "-m", "app.workers.runner"]
    environment:
      PLATFORM_DATABASE_URL: postgresql+psycopg2://platform:platform@db:5432/platform
    volumes:
      - platform-data:/data
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: platform
      POSTGRES_PASSWORD: platform
      POSTGRES_DB: platform
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U platform"]
      interval: 5s
      retries: 10
    restart: unless-stopped

volumes:
  platform-data:
  pg-data:
```

- [ ] **Step 2: Dockerfile 补注释（不改构建逻辑）**

在 `platform-api/Dockerfile` 末尾 `CMD` 上方加一行注释：

```dockerfile
# 同一镜像两种角色：默认起 API；worker 由 compose 用 command 覆盖为
# ["python", "-m", "app.workers.runner"]（一个 API 进程 + 一个 worker 进程）。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9100"]
```

- [ ] **Step 3: `dev.sh` 增 `worker` 子命令**

在 `platform-api/dev.sh` 的 `case` 里、`serve)` 分支之后加：

```bash
  worker)
    uv run python -m app.workers.runner
    ;;
```

并把末尾用法提示改为：`echo "用法: ./dev.sh [sync|serve|worker|web]"`。

- [ ] **Step 4: 校验 compose 语法**

Run: `cd platform-api && docker compose config --quiet && echo OK`
Expected: 输出 `OK`，退出码 0。

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add docker-compose.yml dev.sh Dockerfile
git commit -m "chore: add worker container and dev.sh worker target"
```

---

### Task 3: `.env.example` + 启动自检文案

**Files:**
- Create: `platform-api/.env.example`
- Modify: `platform-api/README.md`（配置表补 `.env` 用法）

**Interfaces:**
- Consumes: `app/config.py` 的 `PLATFORM_*` 字段。
- Produces: 可复制的配置样例。

- [ ] **Step 1: 写 `.env.example`**

```dotenv
# platform-api 配置样例：复制为 .env（.env 已在 .gitignore，勿提交）

# 监听
PLATFORM_HOST=0.0.0.0
PLATFORM_PORT=9100

# 数据库
# 生产：PostgreSQL DSN；本地开发容器映射 5433
PLATFORM_DATABASE_URL=postgresql+psycopg2://platform:platform@127.0.0.1:5433/platform

# 账号体检间隔（分钟），0 关闭
PLATFORM_ACCOUNT_CHECK_INTERVAL=15

# 凭证加密密钥（生产首选）：base64 编码的 32 字节
# 生成：python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"
# 优先级：本变量 > PLATFORM_CREDENTIAL_KEY_FILE > data/secret.key(开发兜底)
PLATFORM_CREDENTIAL_ENC_KEY=
PLATFORM_CREDENTIAL_KEY_FILE=

# worker / 转录
PLATFORM_WORKER_CONCURRENCY=2
PLATFORM_WHISPER_MODEL=base
PLATFORM_WHISPER_DEVICE=auto
PLATFORM_WHISPER_COMPUTE_TYPE=int8

# 外部大模型分析（P6）
PLATFORM_LLM_BASE_URL=
PLATFORM_LLM_API_KEY=
PLATFORM_LLM_MODEL=gpt-4o-mini

# 关键词采集（P5）：回退 MediaCrawler 子进程时用
PLATFORM_MEDIACRAWLER_DIR=
PLATFORM_CRAWL_TIMEOUT_SECONDS=600
```

- [ ] **Step 2: README 补 `.env` 用法**

在 `platform-api/README.md` 的「配置」小节开头加一句：

```markdown
复制 `.env.example` 为 `.env` 后按需修改（`.env` 已被 git 忽略）。**凭证加密密钥丢失即全部凭证作废，迁移机器必须随行。**
```

- [ ] **Step 3: 验证密钥生成命令可用**

Run: `cd platform-api && python3 -c "import base64,os;print(len(base64.b64decode(base64.b64encode(os.urandom(32)))))"`
Expected: 输出 `32`。

- [ ] **Step 4: 提交**

```bash
cd platform-api
git add .env.example README.md
git commit -m "docs: add .env.example for platform-api"
```

---

### Task 4: Alembic 迁移基线

**Files:**
- Modify: `platform-api/pyproject.toml`（dev extra 加 `alembic>=1.13`）
- Create: `platform-api/alembic.ini`
- Create: `platform-api/alembic/env.py`
- Create: `platform-api/alembic/script.py.mako`
- Create: `platform-api/alembic/versions/0001_baseline.py`（autogenerate 产出后重命名）
- Modify: `platform-api/README.md`（加迁移说明）

**Interfaces:**
- Consumes: `app.db.Base.metadata`、`app.config.settings.database_url`。
- Produces: `alembic upgrade head` 可建全部表。

- [ ] **Step 1: 加依赖并安装**

在 `platform-api/pyproject.toml` 的 `[project.optional-dependencies] dev` 行改为：

```toml
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "alembic>=1.13"]
```

Run: `cd platform-api && uv sync --extra dev --extra postgres`
Expected: 安装成功，`alembic` 出现在环境中。

- [ ] **Step 2: 初始化 alembic 目录**

Run: `cd platform-api && uv run alembic init alembic`
Expected: 生成 `alembic.ini`、`alembic/env.py`、`alembic/script.py.mako`、`alembic/versions/`。

- [ ] **Step 3: 改 `alembic/env.py` 接上项目元数据与 URL**

把 `alembic/env.py` 中的 `target_metadata = None` 与 URL 相关部分替换为：

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import context  # noqa: E402
from sqlalchemy import engine_from_config, pool  # noqa: E402

from app.config import settings  # noqa: E402
import app.models  # noqa: F401,E402  注册全部模型
from app.db import Base  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

（`env.py` 模板里原有的 `from logging.config import fileConfig` 等保留；确保最终只有一个 `target_metadata` 定义。）

- [ ] **Step 4: 生成基线迁移**

Run:
```bash
cd platform-api
PLATFORM_DATABASE_URL="sqlite:///$(mktemp -d)/baseline.db" uv run alembic revision --autogenerate -m "baseline"
```
Expected: 在 `alembic/versions/` 生成一个含全部表（`platform_account`、`content_item`、`job_queue` …）的迁移文件。把它重命名为 `0001_baseline.py`，并把 `down_revision` 保持为 `None`。

- [ ] **Step 5: 验证迁移可从零建表**

Run:
```bash
cd platform-api
TMP=$(mktemp -d)
PLATFORM_DATABASE_URL="sqlite:///$TMP/m.db" uv run alembic upgrade head
python3 -c "import sqlite3,sys;print(sorted(r[0] for r in sqlite3.connect('$TMP/m.db').execute(\"select name from sqlite_master where type='table'\")))"
```
Expected: 打印的表名里包含 `platform_account`、`content_item`、`job_queue`、`media_asset`、`transcript`。

- [ ] **Step 6: README 补迁移说明**

在 `platform-api/README.md` 「快速开始」里加：

```markdown
生产用 Alembic 迁移（开发期 `init_db()` 仍会自动建表作为兜底）：

```bash
uv run alembic upgrade head
```
```

- [ ] **Step 7: 提交**

```bash
cd platform-api
git add pyproject.toml uv.lock alembic.ini alembic/ README.md
git commit -m "feat: add alembic baseline migration"
```

---

### Task 5: 前端构建打通 + SPA 托管验证

**Files:**
- Create（构建产物，git 忽略）: `platform-api/app/static/`
- Modify: `platform-api/dev.sh`（`web` 分支保持，补校验）
- Test: `web/` 构建 + uvicorn 托管

**Interfaces:**
- Consumes: `web/vite.config.ts`（`outDir: '../app/static'`）、`app/main.py` 的 SPA 回退。
- Produces: `app/static/index.html` 与 `app/static/assets/*`。

- [ ] **Step 1: 安装依赖并构建**

Run:
```bash
cd platform-api/web
npm install --no-audit --no-fund
npm run build
```
Expected: `vite build` 成功，产物写入 `../app/static/`。

- [ ] **Step 2: 校验产物存在**

Run: `cd platform-api && test -f app/static/index.html && ls app/static/assets | head && echo BUILD_OK`
Expected: 输出 `BUILD_OK` 与若干 `*.js`/`*.css`。

- [ ] **Step 3: 起后端验证 SPA 回退**

Run（另开终端或后台）:
```bash
cd platform-api
PLATFORM_DATABASE_URL="sqlite:///$(mktemp -d)/dev.db" uv run --extra postgres uvicorn app.main:app --port 9100 &
```
然后：
```bash
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9100/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9100/accounts
curl -s http://127.0.0.1:9100/api/auth/status
```
Expected: 前两项 `200`（深链回退到 index.html）；`/api/auth/status` 返回 `{"initialized":false}`。

- [ ] **Step 4: `dev.sh web` 补一句校验**

在 `platform-api/dev.sh` 的 `web)` 分支末尾把 echo 改为：

```bash
    test -f app/static/index.html && echo "前端已构建并部署到 app/static/（index.html OK）"
```

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add dev.sh
git commit -m "chore: verify frontend build output in dev.sh"
```

---

### Task 6: git 初始化与首次提交

**Files:**
- Create: `platform-api/.git`（仓库）
- Verify: `platform-api/.gitignore`

**Interfaces:**
- Consumes: 前 5 个任务的改动。
- Produces: 有历史的 `platform-api` 仓库，可继续按任务提交。

> 说明：本工作区根目录不是 git 仓库，`platform-api/` 也尚未初始化。此任务建立**独立子仓库**（与其他上游项目各自独立一致）。

- [ ] **Step 1: 确认 .gitignore 覆盖敏感/生成物**

Run: `cd platform-api && cat .gitignore`
Expected: 至少包含 `data/`、`.venv/`、`*.sqlite*`、`.env`、`web/node_modules/`、`web/dist/`、`app/static/`、`._*`、`__pycache__/`。

- [ ] **Step 2: 初始化并暂存**

```bash
cd platform-api
git init
git add -A
git status --short | head -40
git status --short | grep -E "data/|secret.key|\.env$|node_modules|app/static" && echo "STOP: 有敏感/生成物被暂存" || echo "CLEAN_OK"
```
Expected: 打印 `CLEAN_OK`（即上面命令的 grep 无匹配）。

- [ ] **Step 3: 首次提交**

```bash
cd platform-api
git commit -m "chore: initial commit of platform-api (P0-P6 backbone, hardening)"
```
Expected: 提交成功，`git log --oneline` 可见。

- [ ] **Step 4: 记录**

Run: `cd platform-api && git log --oneline | head`
Expected: 至少一条初始提交。

---

### Task 7: 端到端验收（compose 一把起）

**Files:**
- Test: `platform-api/`（人工/脚本验收，不新增源码）

**Interfaces:**
- Consumes: Task 2 的 compose、Task 3 的 env 样例、Task 4 的迁移、Task 5 的构建。
- Produces: 可复现的验收结论。

- [ ] **Step 1: 起全栈**

```bash
cd platform-api
docker compose up -d --build
docker compose ps
```
Expected: `platform-api`（healthy/up，端口 9100）、`platform-worker`（up）、`db`（healthy）。

- [ ] **Step 2: 健康检查**

```bash
sleep 5
curl -s http://127.0.0.1:9100/api/auth/status
curl -s -o /dev/null -w "spa=%{http_code}\n" http://127.0.0.1:9100/
docker compose logs platform-worker --tail=20
```
Expected: `auth/status` 返回 JSON；`spa=200`；worker 日志出现「worker 启动 / 轮询」类信息，无 traceback。

- [ ] **Step 3: 账号→订阅→素材 冒烟（用无网 mock 或真实凭证）**

无真实凭证时，至少验证：`POST /api/auth/setup` → `POST /api/accounts`（`skip_check=true`）→ `GET /api/accounts` 列表可见且凭证脱敏。真实同步/下载留给有凭证时的人工验收。

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:9100/api/auth/setup -H 'Content-Type: application/json' -d '{"password":"test1234"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -X POST http://127.0.0.1:9100/api/accounts -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"platform":"bilibili","display_name":"冒烟","credential":{"sessdata":"x","bili_jct":"y","dedeuserid":"1"},"skip_check":true}'
curl -s http://127.0.0.1:9100/api/accounts -H "Authorization: Bearer $TOKEN"
```
Expected: 创建返回 200；列表里该账号存在，凭证字段为脱敏值（不含明文）。

- [ ] **Step 4: 收工清场**

```bash
cd platform-api
docker compose down
```
Expected: 容器停止（`-v` 按需是否保留数据卷由用户决定，默认保留）。

- [ ] **Step 5: 写验收结论**

把上一步真实输出（命令 + 结果）追加到 `platform-api/README.md` 的「验收记录」小节，或单独记到 `docs/`。**未验证到的项必须写"未验证到"，不得臆造。**

---

## Self-Review

- **Spec coverage:** 覆盖 master-plan P0 里未落地的四项（`.env.example`、Alembic、Docker worker、仓库提交）与测试/前端/dev.sh 缺口；每个验收标准（compose 起、pytest 绿、SPA 可托管）都有对应任务。
- **Placeholder scan:** 无 TBD/TODO；Alembic 基线文件名与 `down_revision=None` 明确；conftest 完整可粘贴。
- **Type consistency:** 夹具名 `session`/`client`/`anon_client` 全篇一致；`PLATFORM_*` 变量名与 `app/config.py` 字段一一对应。
- **依赖关系:** Task 6（git）应在 Task 1–5 之后首次提交；若用户要求不建 git，可跳过 Task 6，其余不受影响。

# 抖音评论富集 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为抖音作品拉取评论正文+评论人昵称+评论点赞数，且只对"够热"的作品自动抓取（动态分位+预算+下限），评论走 worker 队列、可配置、不写死。

**Architecture:** 采集/同步产出内容与指标 → 新增 `comment_gate.select_targets`（纯函数，分位选择）→ 入队 `fetch_comments`（低优先级，worker 消费）→ `crawler.fetch_comments` 抓默认排序 K 页并本地按点赞取 Top-N → 写 `comment` + `comment_fetch_state` → `GET /api/assets/{id}/comments` 供前端展示。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / httpx / pyexecjs（既有抖音签名）/ pytest / Vue 3 + Element Plus。

## Global Constraints

- 后端 = FastAPI；DB = PostgreSQL（开发/测试 SQLite）；单管理员；API 即产品（前端、MCP、HTTP 同能力）。
- **只抓一级评论**（不抓楼中楼）；**只做抖音**（B站/小红书/公众号不做）。
- **不重抓**：已有 `comment_fetch_state` 的作品门控时直接跳过。
- 评论抓取只在 worker 发生；API/门控只入队。抓取受**预算**与**翻页限速**约束。
- 9 个参数存 `system_setting`，**不写死在代码**（读取时取最新值，带代码默认兜底）。
- 复用既有 `douyin_sign.get_a_bogus`、`BASE_PARAMS`、`enqueue`/`queue.fail`、`_platform_cookie` 模式。
- 不新增对外绝对路径；不落凭证明文；Conventional Commits；只在 `platform-api/` 内提交。
- 依赖既有测试夹具（`tests/conftest.py` 的 `client`/`session`/`_engine`）；当前 38 测试须保持全绿。

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `app/models.py` | 新增 `Comment`、`CommentFetchState` 模型 | Modify |
| `alembic/versions/0002_comments.py` | 迁移：新增两张表 | Create |
| `app/core/comment_settings.py` | 读 `system_setting` 的评论配置（带默认） | Create |
| `app/services/comment_gate.py` | 纯函数 `select_targets`（分位+下限+预算） | Create |
| `app/modules/crawler/client.py` | 新增 `fetch_comments`（抖音，抓K页取TopN） | Modify |
| `app/modules/crawler/__init__.py` | 暴露 `fetch_comments` 统一入口 | Modify |
| `app/workers/handlers.py` | 新增 `handle_fetch_comments` + 注册 | Modify |
| `app/services/crawl_service.py` | 收尾调用门控入队 | Modify |
| `app/services/sync_service.py` | 收尾调用门控入队 | Modify |
| `app/api/assets.py` | `GET /api/assets/{id}/comments` | Modify |
| `app/api/system.py` | 评论配置读写 | Modify |
| `web/src/pages/Assets.vue` | 详情抽屉「评论」区 | Modify |
| `web/src/pages/Settings.vue` | 「评论抓取」设置 tab | Modify |
| `tests/test_comment_gate.py` | 门控单测 | Create |
| `tests/test_fetch_comments.py` | 解析/TopN 单测（不联网） | Create |
| `tests/test_comment_handler.py` | handler 幂等/state 单测 | Create |
| `tests/test_comments_api.py` | API 分页/排序/鉴权 | Create |

---

### Task 1: 数据模型 + 迁移

**Files:**
- Modify: `app/models.py`（追加两个模型）
- Create: `alembic/versions/0002_comments.py`
- Test: `tests/test_comment_gate.py`（本任务先加一个模型存在性/唯一约束测试）

**Interfaces:**
- Produces: `Comment`（`content_id, platform, comment_id, parent_comment_id, user_id, nickname, avatar, content, like_count, ip_location, created_at, fetched_at`）、`CommentFetchState`（`content_id PK, last_fetched_at, last_score, fetched_count`）。

- [ ] **Step 1: 追加模型到 `app/models.py` 末尾**

```python
class Comment(Base):
    """平台评论（一级）。本版仅抖音；comment_id 与 content_id 联合唯一保证重复抓取幂等。"""

    __tablename__ = "comment"
    __table_args__ = (UniqueConstraint("content_id", "comment_id", name="uq_comment_content_cid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_item.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    comment_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_comment_id: Mapped[str] = mapped_column(String(64), default="0")
    user_id: Mapped[str] = mapped_column(String(64), default="")
    nickname: Mapped[str] = mapped_column(String(128), default="")
    avatar: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    like_count: Mapped[int] = mapped_column(BigInteger, default=0)
    ip_location: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CommentFetchState(Base):
    """评论抓取状态：一作品一行；用于「不重抓」，last_score 供未来增量刷新。"""

    __tablename__ = "comment_fetch_state"

    content_id: Mapped[int] = mapped_column(ForeignKey("content_item.id", ondelete="CASCADE"), primary_key=True)
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_score: Mapped[float] = mapped_column(Float, default=0)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
```

同时把 `app/models.py` 顶部 import 补上 `Float` 和 `UniqueConstraint`：
`from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint`

- [ ] **Step 2: 写失败测试（`tests/test_comment_gate.py`）**

```python
"""评论门控与模型测试。"""
from sqlalchemy.exc import IntegrityError


def test_models_created(_engine):
    from sqlalchemy import inspect

    names = set(inspect(_engine).get_table_names())
    assert {"comment", "comment_fetch_state"} <= names


def test_comment_unique_constraint(_engine):
    from sqlalchemy.orm import sessionmaker

    from app.models import Comment, ContentItem

    S = sessionmaker(bind=_engine)
    db = S()
    c = ContentItem(platform="douyin", external_id="aw1", content_type="video")
    db.add(c)
    db.flush()
    db.add(Comment(content_id=c.id, platform="douyin", comment_id="c1"))
    db.commit()
    db.add(Comment(content_id=c.id, platform="douyin", comment_id="c1"))
    try:
        db.commit()
        raise AssertionError("duplicate (content_id, comment_id) should fail")
    except IntegrityError:
        db.rollback()
    finally:
        db.close()
```

- [ ] **Step 3: 运行确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_gate.py -q`
Expected: FAIL（`comment` 表不存在）。

- [ ] **Step 4: 生成迁移**

Run:
```bash
cd platform-api
PLATFORM_DATABASE_URL="sqlite:///$(mktemp -d)/m.db" uv run alembic revision --autogenerate -m "comments"
```
把生成文件重命名为 `alembic/versions/0002_comments.py`，确认 `down_revision = "0001"`，且 `upgrade()` 含 `create_table("comment")` 与 `create_table("comment_fetch_state")`。

- [ ] **Step 5: 运行确认通过 + 迁移自检**

Run:
```bash
cd platform-api
uv run --extra dev pytest tests/test_comment_gate.py -q
TMP=$(mktemp -d); PLATFORM_DATABASE_URL="sqlite:///$TMP/m.db" uv run alembic upgrade head
python3 -c "import sqlite3;print(sorted(r[0] for r in sqlite3.connect('$TMP/m.db').execute(\"select name from sqlite_master where type='table'\")))"
```
Expected: 测试 2 passed；打印的表含 `comment`、`comment_fetch_state`、`alembic_version`。

- [ ] **Step 6: 提交**

```bash
cd platform-api
git add app/models.py alembic/versions/0002_comments.py tests/test_comment_gate.py
git commit -m "feat: add comment and comment_fetch_state models with migration"
```

---

### Task 2: 评论配置读取

**Files:**
- Create: `app/core/comment_settings.py`
- Modify: `tests/test_comment_gate.py`（追加配置测试）

**Interfaces:**
- Produces: `get_comment_settings(db) -> dict`（键：`top_pct, budget, min_comments, min_likes, weight, pages, per_page, top_n, interval`），从 `system_setting` 读，缺失用默认。

- [ ] **Step 1: 写失败测试（追加到 `tests/test_comment_gate.py`）**

```python
def test_comment_settings_defaults(_engine):
    from sqlalchemy.orm import sessionmaker

    from app.core.comment_settings import get_comment_settings

    db = sessionmaker(bind=_engine)()
    s = get_comment_settings(db)
    assert s["top_pct"] == 0.2
    assert s["budget"] == 10
    assert s["min_comments"] == 20
    assert s["min_likes"] == 100
    assert s["weight"] == 20
    assert s["pages"] == 2 and s["per_page"] == 20 and s["top_n"] == 20
    assert s["interval"] == 1.0
    db.close()


def test_comment_settings_override(_engine):
    from sqlalchemy.orm import sessionmaker

    from app.core.comment_settings import get_comment_settings
    from app.models import SystemSetting

    db = sessionmaker(bind=_engine)()
    db.add(SystemSetting(key="comment_gate_budget", value="3"))
    db.add(SystemSetting(key="comment_gate_top_pct", value="0.5"))
    db.commit()
    s = get_comment_settings(db)
    assert s["budget"] == 3 and s["top_pct"] == 0.5
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_gate.py -q`
Expected: FAIL（`app.core.comment_settings` 不存在）。

- [ ] **Step 3: 实现 `app/core/comment_settings.py`**

```python
"""评论抓取配置：存 system_setting KV，读取时取最新值，缺失用默认。

红线：门控参数不写死在业务代码里，运营可在系统设置页调整。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemSetting

# system_setting key -> (默认值, 类型)
_DEFAULTS: dict[str, tuple[object, type]] = {
    "comment_gate_top_pct": (0.2, float),
    "comment_gate_budget": (10, int),
    "comment_gate_min_comments": (20, int),
    "comment_gate_min_likes": (100, int),
    "comment_gate_weight": (20.0, float),
    "comment_fetch_pages": (2, int),
    "comment_fetch_per_page": (20, int),
    "comment_fetch_top_n": (20, int),
    "comment_fetch_interval_sec": (1.0, float),
}

# 对外短名 -> system_setting key
_KEYS = {
    "top_pct": "comment_gate_top_pct",
    "budget": "comment_gate_budget",
    "min_comments": "comment_gate_min_comments",
    "min_likes": "comment_gate_min_likes",
    "weight": "comment_gate_weight",
    "pages": "comment_fetch_pages",
    "per_page": "comment_fetch_per_page",
    "top_n": "comment_fetch_top_n",
    "interval": "comment_fetch_interval_sec",
}


def get_comment_settings(db: Session) -> dict:
    rows = {s.key: s.value for s in db.scalars(select(SystemSetting)).all()}
    out: dict = {}
    for short, key in _KEYS.items():
        default, typ = _DEFAULTS[key]
        raw = rows.get(key)
        if raw is None or raw == "":
            out[short] = default
            continue
        try:
            out[short] = typ(raw)
        except (TypeError, ValueError):
            out[short] = default
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_gate.py -q`
Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add app/core/comment_settings.py tests/test_comment_gate.py
git commit -m "feat: add comment fetch settings reader"
```

---

### Task 3: 动态门控 `select_targets`

**Files:**
- Create: `app/services/comment_gate.py`
- Modify: `tests/test_comment_gate.py`（追加门控测试）

**Interfaces:**
- Consumes: `get_comment_settings`。
- Produces: `def select_targets(db, contents, *, platform, settings) -> list[ContentItem]`；纯决策，不发请求、不写库。

- [ ] **Step 1: 写失败测试（追加到 `tests/test_comment_gate.py`）**

```python
def _mk(db, ext, like, comment, platform="douyin"):
    from app.models import ContentItem, ContentMetricSnapshot

    c = ContentItem(platform=platform, external_id=ext, content_type="video", source_kind="crawl")
    db.add(c)
    db.flush()
    db.add(ContentMetricSnapshot(content_id=c.id, like=like, comment=comment))
    db.commit()
    return c


def test_gate_percentile_min_and_budget(_engine):
    from sqlalchemy.orm import sessionmaker

    from app.services.comment_gate import select_targets

    db = sessionmaker(bind=_engine)()
    # 10 条，全部过下限(评论>=20,赞>=100)，分位0.2=2条，预算10不设限
    cs = [_mk(db, f"a{i}", like=1000 - i * 10, comment=100 - i) for i in range(10)]
    picks = select_targets(db, cs, platform="douyin",
                           settings={"top_pct": 0.2, "budget": 10, "min_comments": 20,
                                     "min_likes": 100, "weight": 20})
    assert len(picks) == 2
    assert [p.external_id for p in picks] == ["a0", "a1"]  # 分最高两条
    db.close()


def test_gate_min_filters_out_cold(_engine):
    from sqlalchemy.orm import sessionmaker

    from app.services.comment_gate import select_targets

    db = sessionmaker(bind=_engine)()
    hot = _mk(db, "hot", like=5000, comment=300)
    cold = _mk(db, "cold", like=10, comment=1)  # 不过下限
    picks = select_targets(db, [hot, cold], platform="douyin",
                           settings={"top_pct": 1.0, "budget": 10, "min_comments": 20,
                                     "min_likes": 100, "weight": 20})
    assert [p.external_id for p in picks] == ["hot"]
    db.close()


def test_gate_skips_already_fetched_and_other_platform(_engine):
    from sqlalchemy.orm import sessionmaker

    from app.models import CommentFetchState
    from app.services.comment_gate import select_targets

    db = sessionmaker(bind=_engine)()
    a = _mk(db, "done", like=900, comment=200)
    b = _mk(db, "fresh", like=800, comment=150)
    _mk(db, "bili", like=9000, comment=900, platform="bilibili")
    db.add(CommentFetchState(content_id=a.id, fetched_count=5))
    db.commit()
    from app.models import ContentItem

    picks = select_targets(db, db.query(ContentItem).all(), platform="douyin",
                           settings={"top_pct": 1.0, "budget": 10, "min_comments": 20,
                                     "min_likes": 100, "weight": 20})
    assert [p.external_id for p in picks] == ["fresh"]
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_gate.py -q`
Expected: FAIL（`app.services.comment_gate` 不存在）。

- [ ] **Step 3: 实现 `app/services/comment_gate.py`**

```python
"""评论抓取门控：从一批作品里选出「够热」的，交给 worker 抓评论。

语义（动态优先，不写死）：
  score = like + comment * weight        # 互动分，评论按 weight 加权
  分位：按 score 降序取前 top_pct        # 唯一「动态」处，随批自适应
  下限：剔除 comment < min_comments 或 like < min_likes  # 绝对够格
  预算：最多 budget 条                    # 别失控
  「不重抓」：已有 CommentFetchState 的作品直接跳过。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CommentFetchState, ContentItem, ContentMetricSnapshot


def _latest_metric(db: Session, content_id: int) -> ContentMetricSnapshot | None:
    return db.scalar(
        select(ContentMetricSnapshot)
        .where(ContentMetricSnapshot.content_id == content_id)
        .order_by(ContentMetricSnapshot.captured_at.desc())
        .limit(1)
    )


def select_targets(db: Session, contents: list[ContentItem], *, platform: str, settings: dict) -> list[ContentItem]:
    """返回需要抓评论的作品（已按下限/分位/预算筛选）。"""
    fetched = set(db.scalars(select(CommentFetchState.content_id)).all())

    scored: list[tuple[float, ContentItem]] = []
    for c in contents:
        if c.platform != platform or c.id in fetched:
            continue
        m = _latest_metric(db, c.id)
        if m is None:
            continue
        if m.comment < settings["min_comments"] or m.like < settings["min_likes"]:
            continue  # 下限：绝对够格
        score = float(m.like) + float(m.comment) * float(settings["weight"])
        scored.append((score, c))

    scored.sort(key=lambda t: t[0], reverse=True)

    n = len(scored)
    if n == 0:
        return []
    take = n if n < 5 else max(1, int(round(n * float(settings["top_pct"]))))
    take = min(take, int(settings["budget"]))
    return [c for _, c in scored[:take]]
```

- [ ] **Step 4: 运行确认通过**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_gate.py -q`
Expected: PASS（7 passed）。

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add app/services/comment_gate.py tests/test_comment_gate.py
git commit -m "feat: add dynamic comment gate (percentile + floor + budget)"
```

---

### Task 4: 抖音评论抓取 `fetch_comments`

**Files:**
- Modify: `app/modules/crawler/client.py`（追加抖音评论抓取）
- Modify: `app/modules/crawler/__init__.py`（暴露统一入口）
- Create: `tests/test_fetch_comments.py`

**Interfaces:**
- Consumes: `douyin_sign.get_a_bogus`、`BASE_PARAMS`（注意 `BASE_PARAMS` 在 `app/modules/douyin.py`）。
- Produces: `async def fetch_comments(*, aweme_id, cookie, pages, per_page, top_n, interval) -> list[dict]`，item 键：`comment_id, parent_comment_id, user_id, nickname, avatar, content, like_count, ip_location, created_at`。

- [ ] **Step 1: 写失败测试（`tests/test_fetch_comments.py`）**

```python
"""抖音评论抓取解析测试（不联网）。"""
import asyncio


def test_fetch_comments_parses_and_sorts(monkeypatch):
    from app.modules.crawler import client

    pages_payload = [
        {"comments": [
            {"cid": "c1", "text": "低赞", "digg_count": 1, "reply_id": "0",
             "user": {"uid": "u1", "nickname": "甲"}, "ip_label": "北京", "create_time": 100},
            {"cid": "c2", "text": "高赞", "digg_count": 99, "reply_id": "0",
             "user": {"uid": "u2", "nickname": "乙"}, "ip_label": "上海", "create_time": 200},
        ], "has_more": 0},
    ]

    async def fake_get(self, url, params=None, **kw):
        class R:
            def json(self_inner):
                return pages_payload.pop(0)
            status_code = 200
        return R()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    out = asyncio.run(client.fetch_comments(aweme_id="a1", cookie="c", pages=1, per_page=20, top_n=2, interval=0))
    assert [c["comment_id"] for c in out] == ["c2", "c1"]  # 按点赞降序
    assert out[0]["nickname"] == "乙" and out[0]["content"] == "高赞"
```

> 若签名函数在测试环境缺 Node 导致调用失败，则在同一测试里 `monkeypatch.setattr("app.modules.crawler.douyin_sign.get_a_bogus", lambda *a, **k: "SIG")`，让解析逻辑独立于 execjs 验证。

- [ ] **Step 2: 运行确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_fetch_comments.py -q`
Expected: FAIL（`fetch_comments` 不存在）。

- [ ] **Step 3: 实现 `fetch_comments`（追加到 `app/modules/crawler/client.py`）**

```python
# ---------------- 抖音评论 ----------------
async def fetch_comments(
    *, aweme_id: str, cookie: str, pages: int = 2, per_page: int = 20,
    top_n: int = 20, interval: float = 1.0,
) -> list[dict]:
    """抓抖音作品一级评论：默认排序抓 pages 页，本地按点赞降序取 top_n。"""
    from app.modules.douyin import BASE_PARAMS
    from app.modules.crawler import douyin_sign

    base = "https://www.douyin.com/aweme/v1/web/comment/list/"
    headers = {"User-Agent": _UA, "Referer": "https://www.douyin.com/", "Cookie": cookie}
    collected: list[dict] = []
    cursor = "0"
    async with httpx.AsyncClient(headers=headers, timeout=20) as c:
        for _ in range(max(1, pages)):
            query = dict(BASE_PARAMS, aweme_id=aweme_id, cursor=cursor, count=str(per_page), item_type="0")
            qs = urlencode(query)
            a_bogus = douyin_sign.get_a_bogus(base, qs, _UA)
            resp = await c.get(f"{base}?{qs}&a_bogus={a_bogus}")
            try:
                data = resp.json()
            except ValueError:
                raise RuntimeError("抖音评论抓取失败：Cookie 可能失效或被风控")
            for it in data.get("comments") or []:
                user = it.get("user") or {}
                avatar = (((user.get("avatar_thumb") or {}).get("url_list") or [""])[0])
                collected.append({
                    "comment_id": str(it.get("cid", "")),
                    "parent_comment_id": "0",
                    "user_id": str(user.get("uid", "")),
                    "nickname": user.get("nickname", ""),
                    "avatar": avatar,
                    "content": it.get("text", ""),
                    "like_count": int(it.get("digg_count") or 0),
                    "ip_location": it.get("ip_label", ""),
                    "created_at": it.get("create_time"),
                })
            if not data.get("has_more"):
                break
            cursor = str(data.get("cursor", "0"))
            if interval:
                await asyncio.sleep(interval)
    collected.sort(key=lambda x: x["like_count"], reverse=True)
    return collected[:top_n]
```

在 `client.py` 顶部 import 补 `asyncio`（若尚未 import）。

- [ ] **Step 4: 暴露统一入口（`app/modules/crawler/__init__.py`）**

```python
async def fetch_comments(*, aweme_id: str, cookie: str, pages: int = 2, per_page: int = 20,
                         top_n: int = 20, interval: float = 1.0) -> list[dict]:
    """当前仅抖音支持评论抓取。"""
    return await _client.fetch_comments(
        aweme_id=aweme_id, cookie=cookie, pages=pages, per_page=per_page,
        top_n=top_n, interval=interval,
    )
```
（放在现有 `search` 函数之后；`_client` 已是 `from app.modules.crawler import client as _client`。）

- [ ] **Step 5: 运行确认通过**

Run: `cd platform-api && uv run --extra dev pytest tests/test_fetch_comments.py -q`
Expected: PASS（1 passed）。

- [ ] **Step 6: 提交**

```bash
cd platform-api
git add app/modules/crawler/client.py app/modules/crawler/__init__.py tests/test_fetch_comments.py
git commit -m "feat: fetch douyin comments (K pages, top-N by likes)"
```

---

### Task 5: worker handler `fetch_comments`

**Files:**
- Modify: `app/workers/handlers.py`（新增 handler + 注册）
- Create: `tests/test_comment_handler.py`

**Interfaces:**
- Consumes: `crawler.fetch_comments`、`_platform_cookie`（在 `app/services/crawl_service.py`）、`Comment`/`CommentFetchState`。
- Produces: `async def handle_fetch_comments(db, payload)`；job 类型 `fetch_comments`，payload `{content_id}`。

- [ ] **Step 1: 写失败测试（`tests/test_comment_handler.py`）**

```python
"""fetch_comments worker handler：幂等写库 + state。"""
import asyncio


def _seed(db):
    from app.models import ContentItem

    c = ContentItem(platform="douyin", external_id="aw1", content_type="video")
    db.add(c)
    db.flush()
    return c


def test_handler_writes_comments_and_state(_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from app.models import Comment, CommentFetchState
    from app.workers.handlers import handle_fetch_comments

    db = sessionmaker(bind=_engine)()
    c = _seed(db)

    async def fake_fetch(**kw):
        return [
            {"comment_id": "c1", "parent_comment_id": "0", "user_id": "u1", "nickname": "甲",
             "avatar": "", "content": "你好", "like_count": 5, "ip_location": "北京", "created_at": 100},
        ]

    monkeypatch.setattr("app.modules.crawler.fetch_comments", fake_fetch)
    monkeypatch.setattr("app.workers.handlers._comment_cookie", lambda db, platform: "cookie")
    asyncio.run(handle_fetch_comments(db, {"content_id": c.id}))

    assert db.query(Comment).filter_by(content_id=c.id).count() == 1
    st = db.get(CommentFetchState, c.id)
    assert st is not None and st.fetched_count == 1
    db.close()


def test_handler_is_idempotent(_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from app.models import Comment
    from app.workers.handlers import handle_fetch_comments

    db = sessionmaker(bind=_engine)()
    c = _seed(db)

    async def fake_fetch(**kw):
        return [{"comment_id": "c1", "parent_comment_id": "0", "user_id": "u1", "nickname": "甲",
                 "avatar": "", "content": "你好", "like_count": 5, "ip_location": "", "created_at": None}]

    monkeypatch.setattr("app.modules.crawler.fetch_comments", fake_fetch)
    monkeypatch.setattr("app.workers.handlers._comment_cookie", lambda db, platform: "cookie")
    asyncio.run(handle_fetch_comments(db, {"content_id": c.id}))
    asyncio.run(handle_fetch_comments(db, {"content_id": c.id}))
    assert db.query(Comment).filter_by(content_id=c.id).count() == 1  # 不重复
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_handler.py -q`
Expected: FAIL（`handle_fetch_comments` 不存在）。

- [ ] **Step 3: 实现 handler（追加到 `app/workers/handlers.py`）**

```python
def _comment_cookie(db: Session, platform: str) -> str:
    """取该平台一个在线账号的 cookie（复用 crawl_service 的逻辑）。"""
    from app.services.crawl_service import _platform_cookie

    return _platform_cookie(db, platform)


async def handle_fetch_comments(db: Session, payload: dict) -> None:
    from app.core.comment_settings import get_comment_settings
    from app.models import Comment, CommentFetchState, ContentItem
    from app.modules import crawler

    content_id = payload["content_id"]
    content = db.get(ContentItem, content_id)
    if content is None:
        return

    cookie = _comment_cookie(db, content.platform)
    if not cookie:
        raise ValueError(f"{content.platform} 无在线账号，无法抓评论")

    s = get_comment_settings(db)
    comments = await crawler.fetch_comments(
        aweme_id=content.external_id, cookie=cookie,
        pages=s["pages"], per_page=s["per_page"], top_n=s["top_n"], interval=s["interval"],
    )

    existing = {c.comment_id for c in db.query(Comment).filter(Comment.content_id == content_id).all()}
    added = 0
    for it in comments:
        if it["comment_id"] in existing:
            continue
        db.add(Comment(
            content_id=content_id, platform=content.platform, comment_id=it["comment_id"],
            parent_comment_id=it.get("parent_comment_id", "0"), user_id=it.get("user_id", ""),
            nickname=it.get("nickname", ""), avatar=it.get("avatar", ""), content=it.get("content", ""),
            like_count=it.get("like_count", 0), ip_location=it.get("ip_location", ""),
            created_at=_ts_to_dt(it.get("created_at")),
        ))
        added += 1

    st = db.get(CommentFetchState, content_id)
    if st is None:
        st = CommentFetchState(content_id=content_id)
        db.add(st)
    st.last_fetched_at = datetime.utcnow()
    st.fetched_count = added
    db.commit()


def _ts_to_dt(ts) -> datetime | None:
    from datetime import datetime as _dt

    try:
        return _dt.utcfromtimestamp(int(ts)) if ts else None
    except (TypeError, ValueError):
        return None
```

把 `"fetch_comments": handle_fetch_comments,` 加进文件末尾的 `HANDLERS` 字典。

- [ ] **Step 4: 运行确认通过**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_handler.py -q`
Expected: PASS（2 passed）。

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add app/workers/handlers.py tests/test_comment_handler.py
git commit -m "feat: add fetch_comments worker handler"
```

---

### Task 6: 采集/同步收尾接入门控

**Files:**
- Modify: `app/services/crawl_service.py`
- Modify: `app/services/sync_service.py`
- Modify: `tests/test_comment_gate.py`（追加"入队"测试）

**Interfaces:**
- Consumes: `comment_gate.select_targets`、`get_comment_settings`、`enqueue`。
- Produces: 采集/同步成功后，对入选作品 `enqueue("fetch_comments", {"content_id": id}, priority=150)`。

- [ ] **Step 1: 写失败测试（追加到 `tests/test_comment_gate.py`）**

```python
def test_enqueue_comment_jobs(_engine):
    from sqlalchemy.orm import sessionmaker

    from app.models import JobQueue
    from app.services.comment_gate import enqueue_comment_jobs

    db = sessionmaker(bind=_engine)()
    cs = [_mk(db, f"b{i}", like=2000, comment=200) for i in range(3)]
    settings = {"top_pct": 1.0, "budget": 10, "min_comments": 20, "min_likes": 100, "weight": 20}
    n = enqueue_comment_jobs(db, cs, platform="douyin", settings=settings)
    assert n == 3
    jobs = db.query(JobQueue).filter_by(job_type="fetch_comments").all()
    assert len(jobs) == 3 and all(j.priority == 150 for j in jobs)
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_gate.py -q`
Expected: FAIL（`enqueue_comment_jobs` 不存在）。

- [ ] **Step 3: 在 `comment_gate.py` 追加**

```python
def enqueue_comment_jobs(db: Session, contents: list[ContentItem], *, platform: str, settings: dict) -> int:
    """选出目标并入队 fetch_comments，返回入队条数。"""
    from app.core.queue import enqueue

    targets = select_targets(db, contents, platform=platform, settings=settings)
    for c in targets:
        enqueue(db, "fetch_comments", {"content_id": c.id}, priority=150, commit=False)
    db.commit()
    return len(targets)
```

- [ ] **Step 4: 接入 `crawl_service.run_crawl_task` 与 `sync_service.run_subscription_sync`**

在两个服务的成功收尾处（`db.commit()` 之后、`events.publish` 附近）加：

```python
    # 评论富集：动态门控后入队（不阻塞，worker 抓）
    from app.core.comment_settings import get_comment_settings
    from app.services.comment_gate import enqueue_comment_jobs

    touched = [c for c, _ in ...]  # 见下
```

crawl_service：把本次 `_upsert` 返回的 content 收集进 `touched` 列表，然后：
```python
    enqueue_comment_jobs(db, touched, platform=task.platform, settings=get_comment_settings(db))
```
sync_service：同理，用本次 upsert 的 content 列表 + `subscription.platform`。

> 注意顺序：必须在指标快照写入并 `commit` 之后调用，门控才能读到最新指标。

- [ ] **Step 5: 运行确认通过 + 全量回归**

Run:
```bash
cd platform-api
uv run --extra dev pytest tests/test_comment_gate.py -q
uv run --extra dev pytest tests/ -q
```
Expected: 门控测试 PASS；全量仍全绿（原 38 + 新增）。

- [ ] **Step 6: 提交**

```bash
cd platform-api
git add app/services/comment_gate.py app/services/crawl_service.py app/services/sync_service.py tests/test_comment_gate.py
git commit -m "feat: enqueue comment fetch after crawl and sync via gate"
```

---

### Task 7: 评论查询 API

**Files:**
- Modify: `app/api/assets.py`
- Create: `tests/test_comments_api.py`

**Interfaces:**
- Produces: `GET /api/assets/{asset_id}/comments?limit=50&offset=0` → `{total, comments:[...]}`（按 like_count 降序）。

- [ ] **Step 1: 写失败测试（`tests/test_comments_api.py`）**

```python
def test_comments_api_sorted_and_paged(client, _engine):
    from sqlalchemy.orm import sessionmaker

    from app.db import get_db
    from app.main import app as _app
    from app.models import Comment, ContentItem, MediaAsset

    Session = sessionmaker(bind=_engine)
    db = Session()
    c = ContentItem(platform="douyin", external_id="aw1", content_type="video")
    db.add(c)
    db.flush()
    a = MediaAsset(content_id=c.id)
    db.add(a)
    db.flush()
    for i in range(3):
        db.add(Comment(content_id=c.id, platform="douyin", comment_id=f"c{i}", content=f"评论{i}", like_count=i))
    db.commit()
    asset_id = a.id
    db.close()

    r = client.get(f"/api/assets/{asset_id}/comments")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert [x["content"] for x in body["comments"]] == ["评论2", "评论1", "评论0"]
    r2 = client.get(f"/api/assets/{asset_id}/comments?limit=1&offset=1")
    assert [x["content"] for x in r2.json()["comments"]] == ["评论1"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comments_api.py -q`
Expected: FAIL（404/路由不存在）。

- [ ] **Step 3: 实现端点（追加到 `app/api/assets.py`）**

```python
@router.get("/assets/{asset_id}/comments")
def list_comments(asset_id: int, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    base = select(Comment).where(Comment.content_id == asset.content_id)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(Comment.like_count.desc(), Comment.id).limit(min(limit, 200)).offset(offset)
    ).all()
    return {
        "total": int(total or 0),
        "comments": [
            {
                "comment_id": c.comment_id,
                "nickname": c.nickname,
                "avatar": c.avatar,
                "content": c.content,
                "like_count": c.like_count,
                "ip_location": c.ip_location,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ],
    }
```

在 `app/api/assets.py` 顶部 import 补 `Comment` 与 `func`（`from sqlalchemy import func, select`；`Comment` 加进 models import 列表）。

- [ ] **Step 4: 运行确认通过 + 回归**

Run:
```bash
cd platform-api
uv run --extra dev pytest tests/test_comments_api.py -q
uv run --extra dev pytest tests/ -q
```
Expected: PASS + 全绿。

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add app/api/assets.py tests/test_comments_api.py
git commit -m "feat: add comments API with sorting and pagination"
```

---

### Task 8: 评论配置的 API（系统设置读写）

**Files:**
- Modify: `app/api/system.py`
- Modify: `tests/test_comment_gate.py`（追加配置 API 测试）

**Interfaces:**
- Produces: `GET /api/system/comment-settings` 返回当前有效配置；`PUT` 写入 `system_setting`。

- [ ] **Step 1: 写失败测试（追加到 `tests/test_comment_gate.py`）**

```python
def test_comment_settings_api(client):
    r = client.get("/api/system/comment-settings")
    assert r.status_code == 200
    assert r.json()["budget"] == 10
    r2 = client.put("/api/system/comment-settings", json={"budget": 4, "top_pct": 0.3})
    assert r2.status_code == 200
    assert client.get("/api/system/comment-settings").json()["budget"] == 4
```

- [ ] **Step 2: 运行确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_gate.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: 实现端点（追加到 `app/api/system.py`）**

```python
_COMMENT_KEYS = {
    "top_pct": "comment_gate_top_pct",
    "budget": "comment_gate_budget",
    "min_comments": "comment_gate_min_comments",
    "min_likes": "comment_gate_min_likes",
    "weight": "comment_gate_weight",
    "pages": "comment_fetch_pages",
    "per_page": "comment_fetch_per_page",
    "top_n": "comment_fetch_top_n",
    "interval": "comment_fetch_interval_sec",
}


@router.get("/comment-settings")
def get_comment_settings_api(db: Session = Depends(get_db)):
    from app.core.comment_settings import get_comment_settings

    return get_comment_settings(db)


@router.put("/comment-settings")
def update_comment_settings_api(body: dict, db: Session = Depends(get_db)):
    for short, value in (body or {}).items():
        key = _COMMENT_KEYS.get(short)
        if key is None:
            continue
        row = db.get(SystemSetting, key)
        if row is None:
            row = SystemSetting(key=key)
            db.add(row)
        row.value = str(value)
    db.commit()
    return {"ok": True}
```
（`SystemSetting` 已在 `system.py` import；`Depends`/`Session`/`get_db` 已存在。）

- [ ] **Step 4: 运行确认通过**

Run: `cd platform-api && uv run --extra dev pytest tests/test_comment_gate.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add app/api/system.py tests/test_comment_gate.py
git commit -m "feat: comment settings read/write API"
```

---

### Task 9: 前端 —— 素材详情「评论」区 + 系统设置「评论抓取」tab

**Files:**
- Modify: `web/src/pages/Assets.vue`
- Modify: `web/src/pages/Settings.vue`

- [ ] **Step 1: Assets 详情抽屉加评论区**

在 `<el-drawer>` 内「AI 分析」之后插入：

```html
        <el-divider>评论（按点赞排序）</el-divider>
        <div v-if="comments.length">
          <div v-for="c in comments" :key="c.comment_id" class="comment">
            <div class="c-head">
              <b>{{ c.nickname || '匿名' }}</b>
              <span class="c-meta">{{ c.ip_location }} · 赞 {{ c.like_count }}</span>
            </div>
            <div class="c-body">{{ c.content }}</div>
          </div>
          <el-button v-if="comments.length < commentTotal" text @click="loadMoreComments">加载更多</el-button>
        </div>
        <p v-else class="comment-hint">
          该作品评论数或点赞数未达抓取门槛，仅显示数量（评论总数 {{ detail?.metrics?.comment ?? '—' }}）。
        </p>
```

在 `<script setup>` 加状态与函数：

```ts
const comments = ref<any[]>([])
const commentTotal = ref(0)
const commentOffset = ref(0)

async function loadComments(assetId: number, reset = true) {
  if (reset) { comments.value = []; commentOffset.value = 0 }
  const { data } = await api.get(`/api/assets/${assetId}/comments`, {
    params: { limit: 50, offset: commentOffset.value },
  })
  comments.value = reset ? data.comments : [...comments.value, ...data.comments]
  commentTotal.value = data.total
  commentOffset.value = comments.value.length
}

async function loadMoreComments() {
  if (detail.value) await loadComments(detail.value.asset_id, false)
}
```

在 `openDetail(id)` 里、拿到 detail 后调用 `await loadComments(id)`。

在 `<style scoped>` 加：

```css
.comment { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.c-head { display: flex; justify-content: space-between; }
.c-meta { color: #909399; font-size: 12px; }
.c-body { margin-top: 4px; font-size: 13px; }
.comment-hint { color: #909399; font-size: 12px; }
```

> 注意：`detail.metrics` 目前接口未返回；若详情无该字段，用 `commentTotal` 或素材列表行数据兜底——实现时确认 `/api/assets/{id}` 是否含 `metrics`，没有则改读评论总数接口的 `total`。

- [ ] **Step 2: Settings 加「评论抓取」tab**

在 `<el-tabs>` 内加一个 `el-tab-pane label="评论抓取" name="comments"`，用 9 个 `el-input-number` 绑定到 `commentSettings`，`保存` 调 `PUT /api/system/comment-settings`。

```ts
const commentSettings = reactive({ top_pct: 0.2, budget: 10, min_comments: 20, min_likes: 100, weight: 20, pages: 2, per_page: 20, top_n: 20, interval: 1 })
async function loadCommentSettings() { Object.assign(commentSettings, (await api.get('/api/system/comment-settings')).data) }
async function saveCommentSettings() { await api.put('/api/system/comment-settings', commentSettings); ElMessage.success('已保存') }
```
并在 `onMounted` 里调用 `loadCommentSettings()`。

- [ ] **Step 3: 构建校验**

Run: `cd platform-api/web && npm run build`
Expected: 构建成功，无 TS/模板错误；`app/static` 不提交。

- [ ] **Step 4: 提交**

```bash
cd platform-api
git add web/src/pages/Assets.vue web/src/pages/Settings.vue
git commit -m "feat: show comments in asset detail and add comment settings tab"
```

---

## Self-Review

- **Spec coverage:** 覆盖设计文档全部决策：动态分位(D1/D5, Task3)、Top-N 高赞(D2, Task4)、双入口(D3, Task6)、不重抓(D4, Task1+3)、权重(D6, Task3)、仅一级(D7, Task4 恒 parent="0")、可配置(Task2/8)、worker(Task5)、API(Task7)、前端(Task9)。
- **Placeholder scan:** 无 TBD；门控/解析/handler/API 均给出完整可粘贴代码与断言。
- **Type consistency:** `select_targets`/`enqueue_comment_jobs`/`fetch_comments`/`handle_fetch_comments` 签名在任务间一致；`settings` 短名（top_pct/budget/...）全程一致。
- **依赖顺序:** Task1(模型)→2(配置)→3(门控)→4(抓取)→5(handler)→6(接入)→7(API)→8(配置API)→9(前端)；每任务独立可测。
- **已知需实现者按实际微调:** Task6 中 `touched` 列表需按各服务现有返回结构收集（计划已给指引）；Task9 的 `detail.metrics` 字段存在性需实现时确认。
- **未决项（应保持现状）：** 真·随机抽样 vs 分位自适应——本计划按已确认的"分位+预算自适应"实现，不做字面随机。

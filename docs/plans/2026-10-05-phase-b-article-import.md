# 单篇公众号文章 URL 导入 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持把**单篇**微信公众号文章 URL 导入素材库：抓正文 → 入库 → 可在素材库查看/导出、可走 AI 分析。**不做**跨公众号列表/订阅同步/公开发现（微信已于 2026-07 关闭该接口，见 `docs/plans/2026-10-05-wechat-mp-investigation.md`）。

**Architecture:** 新增 `app/modules/article_import.py`（URL 校验 + 正文解析，纯函数便于单测）→ 新增 `POST /api/imports/wechat-article`（编排入库）→ 复用现有 `ContentItem` / `MediaAsset` / `Transcript` 三张表，不新增表。文章正文写入 `Transcript.full_text`（复用平台的"文本本体"存储），清洗后 HTML 存 `ContentItem.extra["html"]`。这样 AI 分析（`handle_analyze` 读 transcript）与导出（`/api/assets/export` 读 transcript）**零改动**即支持文章。

**Tech Stack:** Python 3.11+ / FastAPI / httpx / BeautifulSoup4(`html.parser`，无需 lxml) / SQLAlchemy 2.0 / pytest / Vue 3 + Element Plus。

## Global Constraints

- 后端 = **FastAPI**；DB = PostgreSQL（开发/测试 SQLite）；单管理员；API 即产品（前端、MCP、HTTP 走同一套 `/api/*`）。
- **仅允许微信域名**（`mp.weixin.qq.com`、`weixin.qq.com`）、**仅 https**、**仅文章路径 `/s...`**；拒绝重定向以防 SSRF（对齐 exporter `accountname.get.ts` 的白名单做法）。
- 不引入浏览器/无头渲染；只做纯 HTTP + 静态 HTML 解析。
- 不新增数据库表；不写绝对路径；不落任何凭证明文。
- 只在 `platform-api/` 内改代码与提交（Conventional Commits）；`docs/` 内的文档修正随本计划一起提交到 `docs/`（该目录非 git 仓库，仅落盘）。
- 遵守 Plan A（`2026-10-05-phase-a-hardening.md`）建立的测试夹具（`client`/`session`）；本计划**依赖 Plan A Task 1 已完成**。

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `platform-api/app/modules/article_import.py` | 微信单篇文章 URL 校验、正文/元数据解析（纯函数） | Create |
| `platform-api/app/services/import_service.py` | 编排：解析结果 → ContentItem + MediaAsset + Transcript 入库 | Create |
| `platform-api/app/api/imports.py` | `POST /api/imports/wechat-article` | Create |
| `platform-api/app/main.py` | 注册 imports 路由 | Modify |
| `platform-api/app/api/skills.py` | `POST /api/skills/import-article`（API Key） | Modify |
| `platform-api/mcp_server/server.py` | `import_article` MCP 工具 | Modify |
| `platform-api/web/src/pages/Assets.vue` | "导入文章"对话框 | Modify |
| `platform-api/tests/fixtures/wechat_article.html` | 解析用样例 HTML | Create |
| `platform-api/tests/test_article_import.py` | 解析 + 导入 API 测试 | Create |
| `platform-api/pyproject.toml` | 加 `beautifulsoup4` | Modify |
| `platform-api/README.md` | 记录公众号能力边界 | Modify |
| `docs/plans/2026-10-05-wechat-mp-investigation.md` | 调查报告 | Create |

---

### Task 1: 文章 URL 校验与正文解析（纯函数 + 单测）

**Files:**
- Create: `platform-api/app/modules/article_import.py`
- Create: `platform-api/tests/fixtures/wechat_article.html`
- Create: `platform-api/tests/test_article_import.py`
- Modify: `platform-api/pyproject.toml`（加 `beautifulsoup4>=4.12`）

**Interfaces:**
- Produces:
  - `class ArticleImportError(ValueError)`
  - `normalize_article_url(raw: str) -> str`（校验并规范化，非法则抛 `ArticleImportError`）
  - `article_external_id(url: str) -> str`
  - `parse_article_html(html: str, url: str) -> dict` → `{"external_id","title","author_name","author_id","url","cover_url","published_at"(datetime|None),"text","html"}`
  - `async def fetch_article(url: str, *, cookie: str = "") -> dict`

- [ ] **Step 1: 写样例 HTML 夹具**

`platform-api/tests/fixtures/wechat_article.html`：

```html
<!doctype html>
<html>
<head>
  <meta property="og:title" content="测试文章标题" />
  <meta property="og:image" content="https://mmbiz.qpic.cn/cover.jpg" />
  <meta property="og:url" content="https://mp.weixin.qq.com/s/AbCdEf123456" />
  <meta property="article:published_time" content="2026-06-01T10:00:00+08:00" />
  <script>
    var nickname = "测试公众号";
    var biz = "MzI1MjU5MjMzNA==";
    var ct = "1780279200";
  </script>
</head>
<body>
  <h1 id="activity-name">  测试文章标题  </h1>
  <span id="js_name">测试公众号</span>
  <div id="js_content" style="visibility:hidden">
    <p>第一段正文。</p>
    <p>第二段正文，含<a href="https://mp.weixin.qq.com/s/xyz">链接</a>。</p>
  </div>
</body>
</html>
```

- [ ] **Step 2: 写失败测试**

`platform-api/tests/test_article_import.py`：

```python
"""单篇公众号文章导入：URL 校验、解析、入库 API。"""
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "wechat_article.html"


def test_normalize_rejects_non_wechat_host():
    from app.modules.article_import import ArticleImportError, normalize_article_url

    with pytest.raises(ArticleImportError):
        normalize_article_url("https://evil.example.com/s/abc")


def test_normalize_rejects_http_and_non_article_path():
    from app.modules.article_import import ArticleImportError, normalize_article_url

    with pytest.raises(ArticleImportError):
        normalize_article_url("http://mp.weixin.qq.com/s/abc")
    with pytest.raises(ArticleImportError):
        normalize_article_url("https://mp.weixin.qq.com/cgi-bin/home")


def test_normalize_keeps_query_and_strips_fragment():
    from app.modules.article_import import normalize_article_url

    u = normalize_article_url("https://mp.weixin.qq.com/s?__biz=x&mid=1&idx=1#wechat_redirect")
    assert u == "https://mp.weixin.qq.com/s?__biz=x&mid=1&idx=1"


def test_parse_extracts_fields():
    from app.modules.article_import import parse_article_html

    html = FIXTURE.read_text(encoding="utf-8")
    out = parse_article_html(html, "https://mp.weixin.qq.com/s/AbCdEf123456")
    assert out["title"] == "测试文章标题"
    assert out["author_name"] == "测试公众号"
    assert out["cover_url"] == "https://mmbiz.qpic.cn/cover.jpg"
    assert "第一段正文" in out["text"]
    assert "第二段正文" in out["text"]
    assert out["external_id"]
    assert out["published_at"] is not None
    assert "js_content" in out["html"]


def test_parse_falls_back_title_to_og_when_activity_name_missing():
    from app.modules.article_import import parse_article_html

    html = FIXTURE.read_text(encoding="utf-8").replace('id="activity-name"', 'id="x"')
    out = parse_article_html(html, "https://mp.weixin.qq.com/s/AbCdEf123456")
    assert out["title"] == "测试文章标题"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_article_import.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.article_import'`。

- [ ] **Step 4: 加依赖**

在 `platform-api/pyproject.toml` 的 `dependencies` 列表末尾加：

```toml
    "beautifulsoup4>=4.12",
```

Run: `cd platform-api && uv sync --extra dev`
Expected: 安装成功。

- [ ] **Step 5: 实现 `article_import.py`**

```python
"""单篇微信公众号文章导入（协议来源：wechat-article-exporter，MIT，仅取"单篇"能力）。

背景：微信已于 2026-07 关闭"跨公众号历史文章列表"后台接口（ret=200013），
因此本模块**只做单篇文章**：给一个 mp.weixin.qq.com/s... 的公开链接，抓正文入库。
不做列表、不做订阅、不做公开搜索发现。

安全：只允许微信域名 + https + 文章路径；拒绝重定向（防 SSRF）。
"""
import hashlib
import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("platform.article_import")

_ALLOWED_HOSTS = {"mp.weixin.qq.com", "weixin.qq.com"}
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class ArticleImportError(ValueError):
    """URL 非法或文章页无法解析。"""


def normalize_article_url(raw: str) -> str:
    """校验并规范化文章 URL；非微信/https/文章路径一律拒绝。"""
    raw = (raw or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise ArticleImportError("仅支持 https 链接")
    if parsed.hostname not in _ALLOWED_HOSTS:
        raise ArticleImportError("仅支持微信公众号文章链接（mp.weixin.qq.com）")
    if not (parsed.path == "/s" or parsed.path.startswith("/s/")):
        raise ArticleImportError("仅支持微信公众号文章链接（/s...）")
    return parsed._replace(fragment="").geturl()


def article_external_id(url: str) -> str:
    """稳定去重 ID：优先 sn，其次 mid+idx，其次路径 slug，最后 URL 哈希。"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if qs.get("sn"):
        return qs["sn"][0]
    if qs.get("mid"):
        return f"{qs['mid'][0]}_{qs.get('idx', ['1'])[0]}"
    slug = parsed.path.removeprefix("/s/").strip("/")
    if slug:
        return slug
    return hashlib.sha1(url.encode()).hexdigest()[:32]


def _meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return (tag.get("content") or "").strip() if tag else ""


def _var(html: str, name: str) -> str:
    m = re.search(rf"var\s+{name}\s*=\s*[\"']([^\"']+)[\"']", html)
    return m.group(1).strip() if m else ""


def _parse_time(html: str, soup: BeautifulSoup) -> datetime | None:
    m = re.search(r"var\s+ct\s*=\s*[\"'](\d{9,11})[\"']", html)
    if m:
        return datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc).replace(tzinfo=None)
    iso = _meta(soup, "article:published_time")
    if iso:
        try:
            return datetime.fromisoformat(iso).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def parse_article_html(html: str, url: str) -> dict:
    """从文章页 HTML 提取统一 item。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find(id="js_content")
    if content is None:
        raise ArticleImportError("未找到文章正文（可能链接失效或被风控拦截）")

    title = ""
    h1 = soup.find(id="activity-name")
    if h1:
        title = h1.get_text(strip=True)
    title = title or _meta(soup, "og:title")

    author_name = ""
    name_el = soup.find(id="js_name")
    if name_el:
        author_name = name_el.get_text(strip=True)
    author_name = author_name or _var(html, "nickname")

    # 正文里的图片补上 data-src（微信懒加载），保证导出可用
    for img in content.find_all("img"):
        if img.get("data-src") and not img.get("src"):
            img["src"] = img["data-src"]

    text = content.get_text("\n", strip=True)

    return {
        "external_id": article_external_id(url),
        "title": title or "未命名文章",
        "author_name": author_name,
        "author_id": _var(html, "biz"),
        "url": url,
        "cover_url": _meta(soup, "og:image"),
        "published_at": _parse_time(html, soup),
        "text": text,
        "html": str(content),
    }


async def fetch_article(url: str, *, cookie: str = "") -> dict:
    """抓取并解析单篇文章。拒绝重定向（防 SSRF）。"""
    url = normalize_article_url(url)
    headers = {
        "User-Agent": _UA,
        "Referer": "https://mp.weixin.qq.com/",
        "Origin": "https://mp.weixin.qq.com",
    }
    if cookie:
        headers["Cookie"] = cookie
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        resp = await client.get(url, headers=headers)
    if 300 <= resp.status_code < 400:
        raise ArticleImportError("目标链接发生重定向，已拒绝")
    resp.raise_for_status()
    item = parse_article_html(resp.text, url)
    logger.info("解析文章成功: %s", item["title"])
    return item
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd platform-api && uv run --extra dev pytest tests/test_article_import.py -q`
Expected: PASS — 5 passed。

- [ ] **Step 7: 提交**

```bash
cd platform-api
git add app/modules/article_import.py tests/fixtures/wechat_article.html tests/test_article_import.py pyproject.toml uv.lock
git commit -m "feat: add single WeChat article parser"
```

---

### Task 2: 导入编排服务 + API 端点

**Files:**
- Create: `platform-api/app/services/import_service.py`
- Create: `platform-api/app/api/imports.py`
- Modify: `platform-api/app/main.py`
- Modify: `platform-api/tests/test_article_import.py`（追加 API 测试）

**Interfaces:**
- Consumes: `article_import.fetch_article`（Task 1）、`ContentItem`/`MediaAsset`/`Transcript` 模型。
- Produces:
  - `async def import_wechat_article(db: Session, url: str) -> tuple[MediaAsset, bool]`（第二个值 = 是否新建）
  - `POST /api/imports/wechat-article` body `{"url": str}` → `{"asset_id", "content_id", "title", "author_name", "already_existed"}`

- [ ] **Step 1: 写失败测试（追加到 `tests/test_article_import.py`）**

```python
def test_import_endpoint_creates_asset_and_transcript(client, monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(url, cookie=""):
        from app.modules.article_import import parse_article_html

        return parse_article_html(html, "https://mp.weixin.qq.com/s/AbCdEf123456")

    monkeypatch.setattr("app.services.import_service.article_import.fetch_article", fake_fetch)

    r = client.post(
        "/api/imports/wechat-article",
        json={"url": "https://mp.weixin.qq.com/s/AbCdEf123456"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "测试文章标题"
    assert body["already_existed"] is False

    detail = client.get(f"/api/assets/{body['asset_id']}").json()
    assert detail["content"]["platform"] == "wechat_mp"
    assert "第一段正文" in detail["transcript"]["full_text"]


def test_import_endpoint_is_idempotent(client, monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(url, cookie=""):
        from app.modules.article_import import parse_article_html

        return parse_article_html(html, "https://mp.weixin.qq.com/s/AbCdEf123456")

    monkeypatch.setattr("app.services.import_service.article_import.fetch_article", fake_fetch)
    url = "https://mp.weixin.qq.com/s/AbCdEf123456"
    first = client.post("/api/imports/wechat-article", json={"url": url}).json()
    second = client.post("/api/imports/wechat-article", json={"url": url}).json()
    assert second["already_existed"] is True
    assert second["asset_id"] == first["asset_id"]


def test_import_endpoint_rejects_bad_url(client, monkeypatch):
    async def fake_fetch(url, cookie=""):
        from app.modules.article_import import fetch_article as real

        return await real(url, cookie=cookie)

    monkeypatch.setattr("app.services.import_service.article_import.fetch_article", fake_fetch)
    r = client.post("/api/imports/wechat-article", json={"url": "https://evil.example.com/s/x"})
    assert r.status_code == 422
    assert "微信" in r.text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd platform-api && uv run --extra dev pytest tests/test_article_import.py -q`
Expected: FAIL — `404`/`AttributeError`（`app.services.import_service` 不存在）。

- [ ] **Step 3: 写 `app/services/import_service.py`**

```python
"""单篇文章导入编排：解析结果 -> ContentItem + MediaAsset + Transcript。

设计说明：文章没有音视频，复用平台的"文本本体"存储 —— 正文写入 Transcript.full_text，
这样 AI 分析（handle_analyze 读 transcript）与导出（/api/assets/export）零改动即支持文章。
download_status 置 done 表示"无需下载"（文章的抓取就是它自己的下载）。
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import render_subdir
from app.models import ContentItem, MediaAsset, Transcript
from app.modules import article_import

logger = logging.getLogger("platform.import_service")


async def import_wechat_article(db: Session, url: str) -> tuple[MediaAsset, bool]:
    """导入单篇公众号文章，返回 (MediaAsset, 是否新建)。幂等：同 external_id 复用。"""
    item = await article_import.fetch_article(url)

    content = db.scalar(
        select(ContentItem).where(
            ContentItem.platform == "wechat_mp",
            ContentItem.external_id == item["external_id"],
        )
    )
    if content is not None:
        asset = db.scalar(select(MediaAsset).where(MediaAsset.content_id == content.id))
        if asset is not None:
            return asset, False

    if content is None:
        content = ContentItem(
            platform="wechat_mp",
            external_id=item["external_id"],
            content_type="article",
            title=item["title"],
            author_name=item["author_name"],
            author_id=item["author_id"],
            url=item["url"],
            cover_url=item["cover_url"],
            published_at=item["published_at"],
            source_kind="import",
            source_id=None,
            extra={"html": item["html"]},
        )
        db.add(content)
        db.flush()

    asset = MediaAsset(
        content_id=content.id,
        relative_path=render_subdir(
            "{platform}/{creator}/{date}/{content_id}",
            platform="wechat_mp",
            creator=item["author_name"],
            date=item["published_at"] or content.created_at,
            content_id=item["external_id"],
        ),
        download_status="done",   # 文章的抓取即下载
        transcribe_status="done",  # 正文已在 transcript，无需转录
        analyze_status="pending",
    )
    db.add(asset)
    db.flush()

    db.add(
        Transcript(
            asset_id=asset.id,
            language="zh",
            model="wechat_article",
            segments=[],
            full_text=item["text"],
        )
    )
    db.commit()
    db.refresh(asset)
    logger.info("文章已入库 asset_id=%s title=%s", asset.id, item["title"])
    return asset, True
```

- [ ] **Step 4: 写 `app/api/imports.py`**

```python
"""导入类 API：目前仅单篇公众号文章。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import security
from app.db import get_db
from app.models import ContentItem
from app.modules.article_import import ArticleImportError
from app.services.import_service import import_wechat_article

router = APIRouter(prefix="/api/imports", tags=["imports"], dependencies=[Depends(security.require_admin)])


class ArticleImportIn(BaseModel):
    url: str


@router.post("/wechat-article")
async def import_article(body: ArticleImportIn, db: Session = Depends(get_db)):
    """导入单篇微信公众号文章。重复导入同一篇返回既有素材。"""
    try:
        asset, created = await import_wechat_article(db, body.url)
    except ArticleImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    content = db.get(ContentItem, asset.content_id)
    return {
        "asset_id": asset.id,
        "content_id": asset.content_id,
        "title": content.title if content else "",
        "author_name": content.author_name if content else "",
        "already_existed": not created,
    }
```

- [ ] **Step 5: 注册路由**

在 `app/main.py` 的 import 列表里加 `imports`（按字母序放在 `crawl_tasks` 与 `pipeline` 之间），并加 `app.include_router(imports.router)`：

```python
from app.api import (
    accounts,
    ai_access,
    analytics,
    assets,
    auth,
    crawl_tasks,
    imports,
    pipeline,
    skills,
    subscriptions,
    system,
)
# ...
app.include_router(imports.router)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd platform-api && uv run --extra dev pytest tests/test_article_import.py -q`
Expected: PASS — 8 passed（含 Task 1 的 5 个）。

- [ ] **Step 7: 全量回归**

Run: `cd platform-api && uv run --extra dev pytest tests/ -q`
Expected: 全绿，无新增失败。

- [ ] **Step 8: 提交**

```bash
cd platform-api
git add app/services/import_service.py app/api/imports.py app/main.py tests/test_article_import.py
git commit -m "feat: import single WeChat article into asset library"
```

---

### Task 3: API Key（skills）+ MCP 工具

**Files:**
- Modify: `platform-api/app/api/skills.py`
- Modify: `platform-api/mcp_server/server.py`

**Interfaces:**
- Consumes: `import_wechat_article`（Task 2）。
- Produces: `POST /api/skills/import-article`（scope `operate`）；MCP 工具 `import_article(url)`。

- [ ] **Step 1: 加 skills 端点（追加到 `app/api/skills.py` 末尾）**

```python
@router.post("/import-article")
async def skill_import_article(
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(require_scope("operate", "admin")),
):
    """导入单篇公众号文章（API Key 通道，与前端能力对等）。"""
    from app.modules.article_import import ArticleImportError
    from app.services.import_service import import_wechat_article

    t0 = time.time()
    url = (body or {}).get("url", "")
    try:
        asset, _created = await import_wechat_article(db, url)
        _log(db, key.id, "import_article", url[:200], "ok", int((time.time() - t0) * 1000))
        return {"asset_id": asset.id, "content_id": asset.content_id}
    except ArticleImportError as exc:
        _log(db, key.id, "import_article", url[:200], "error", int((time.time() - t0) * 1000))
        raise HTTPException(status_code=422, detail=str(exc))
```

（`time`、`Request`、`HTTPException`、`Depends` 该文件顶部已 import；直接复用。）

- [ ] **Step 2: 加 MCP 工具（追加到 `mcp_server/server.py` 末尾）**

```python
@mcp.tool()
def import_article(url: str) -> dict:
    """导入单篇微信公众号文章到素材库（mp.weixin.qq.com/s... 链接）。"""
    return _post("/api/skills/import-article", {"url": url})
```

- [ ] **Step 3: 校验 skills 路由加载**

Run:
```bash
cd platform-api
uv run --extra dev python -c "from app.main import app; print([r.path for r in app.routes if 'import' in r.path])"
```
Expected: 输出含 `/api/skills/import-article` 与 `/api/imports/wechat-article`。

- [ ] **Step 4: MCP 语法校验**

Run: `cd platform-api && uv run --extra dev python -c "import ast;ast.parse(open('mcp_server/server.py').read());print('MCP_OK')"`
Expected: 输出 `MCP_OK`（不实际启动 MCP，避免依赖 `mcp` 包）。

- [ ] **Step 5: 提交**

```bash
cd platform-api
git add app/api/skills.py mcp_server/server.py
git commit -m "feat: expose article import via API key and MCP"
```

---

### Task 4: 前端"导入文章"对话框

**Files:**
- Modify: `platform-api/web/src/pages/Assets.vue`

- [ ] **Step 1: 加"导入文章"按钮与对话框**

在 `Assets.vue` 的 `.filters` 里、`刷新` 按钮后插入：

```html
      <el-button @click="importDialog = true">导入文章</el-button>
```

在 `<el-drawer ...>` 之前插入对话框：

```html
    <el-dialog v-model="importDialog" title="导入微信公众号文章" width="520px">
      <el-input
        v-model="importUrl"
        placeholder="https://mp.weixin.qq.com/s/..."
        clearable
      />
      <p class="hint">仅支持单篇文章链接。批量历史文章列表接口微信已关闭，无法导入整号历史。</p>
      <template #footer>
        <el-button @click="importDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">导入</el-button>
      </template>
    </el-dialog>
```

- [ ] **Step 2: 加脚本逻辑**

在 `<script setup>` 的 `const filters = reactive({ platform: '', transcribe_status: '' })` 之后加：

```ts
const importDialog = ref(false)
const importUrl = ref('')
const importing = ref(false)

async function doImport() {
  if (!importUrl.value.trim()) return
  importing.value = true
  try {
    await api.post('/api/imports/wechat-article', { url: importUrl.value.trim() })
    ElMessage.success('导入成功')
    importDialog.value = false
    importUrl.value = ''
    await load()
  } finally {
    importing.value = false
  }
}
```

在 `<style scoped>` 加：

```css
.hint { color: #909399; font-size: 12px; margin: 8px 0 0; }
```

- [ ] **Step 3: 构建校验（依赖 Plan A Task 5 的 node_modules）**

Run: `cd platform-api/web && npm run build`
Expected: 构建成功，无 TS/模板错误。

- [ ] **Step 4: 提交**

```bash
cd platform-api
git add web/src/pages/Assets.vue
git commit -m "feat: add article import dialog to assets page"
```

---

### Task 5: 文档修正（记录能力边界，避免后人误做）

**Files:**
- Create: `docs/plans/2026-10-05-wechat-mp-investigation.md`（调查报告）
- Modify: `docs/development-master-plan.md`（P6 重新定义）
- Modify: `docs/workbench-requirements-and-design-v1.md`（第 90 行去掉"公众号：已订阅的号"）
- Modify: `wechat-article-exporter/README.md`（顶部加停止维护说明）
- Modify: `platform-api/README.md`（能力边界）

- [ ] **Step 1: 落盘调查报告**

创建 `docs/plans/2026-10-05-wechat-mp-investigation.md`，正文见本文件末尾"附录：调查报告全文"（直接复制即可）。

- [ ] **Step 2: 改 master-plan P6**

把 `docs/development-master-plan.md` 第 85 行的 P6 行改为：

```markdown
| **P6** | 看板+分析 | 数据看板 + 大模型分析（公众号仅保留单篇 URL 导入，不做订阅同步） | 看板看走势，素材有 AI 摘要；单篇文章可导入 |
```

- [ ] **Step 3: 改 v1 设计第 90 行**

把 `docs/workbench-requirements-and-design-v1.md` 第 90 行里的 `公众号：已订阅的号` 删除，并在句末补：

```markdown
（公众号历史文章列表接口已于 2026-07 关闭，平台不支持公众号订阅同步，仅支持单篇 URL 导入）
```

- [ ] **Step 4: exporter README 加停维声明**

在 `wechat-article-exporter/README.md` 顶部标题后插入：

```markdown
> [!WARNING]
> **本副本为停止维护前的历史快照（commit 757e6bf，2026-06-02）。**
> 微信已于 2026-07 关闭跨公众号历史文章列表后台接口（ret=200013），上游项目随之停止维护。
> 本副本仅作协议/代码参考，**不要再照此实现公众号文章列表同步**。
```

- [ ] **Step 5: platform-api README 补边界**

在 `platform-api/README.md` 「协议来源与许可」小节前插入：

```markdown
## 公众号能力边界

- ✅ 登录态管理（扫码/探活）、✅ 单篇文章 URL 导入（`POST /api/imports/wechat-article`）。
- ❌ 不做公众号订阅同步 / 批量历史文章列表 / 公开索引发现：微信已于 2026-07 关闭相关后台接口。
  详见 `../docs/plans/2026-10-05-wechat-mp-investigation.md`。
```

- [ ] **Step 6: 校验**

Run: `cd /path/to/xsai-workbench && grep -n "P6" docs/development-master-plan.md | head`
Expected: 能看到修改后的 P6 行（含"单篇 URL 导入"）。

- [ ] **Step 7: 提交**

`docs/` 无 git（直接落盘）。`wechat-article-exporter/` 是独立 git 仓库，在其内提交；`platform-api/` 内提交 README：

```bash
cd platform-api && git add README.md && git commit -m "docs: record WeChat article capability boundary"
cd /path/to/xsai-workbench/wechat-article-exporter && git add README.md && git commit -m "docs: note upstream shutdown snapshot"
```

---

## Self-Review

- **Spec coverage:** 用户要的"单篇 URL 导入"由 Task 1–4 端到端实现（解析→入库→API→前端→MCP）；"不做公开发现"由 Task 5 明确写入文档并显式标注 ❌。
- **Placeholder scan:** 无 TBD；解析字段、测试断言、路由路径均为具体值。
- **Type consistency:** `fetch_article`/`parse_article_html`/`import_wechat_article`（返回 `tuple[MediaAsset, bool]`）在 Task 1–3 间一致；`ArticleImportError` 全程同名；`already_existed = not created`。
- **依赖:** 依赖 Plan A Task 1 的 `client` 夹具；若 Plan A 未执行，需先补测试夹具再跑 Task 2 的 API 测试。
- **边界:** 不含任何"列表/订阅/公开发现"实现；单篇外链一律 422。

---

## 附录：调查报告全文（Task 5 Step 1 直接复制）

```markdown
# 微信公众号内容能力调查报告（2026-10-05）

## 结论
- 微信已于 **2026-07 下旬**关闭"跨公众号历史文章列表"后台接口（`/cgi-bin/appmsgpublish`、
  `/cgi-bin/appmsg?action=list_ex`），故障形态为**第一页、零结果即返回 ret=200013**
  （频控码被复用为能力控制），而非以往的"跑几十页后才限流"。
- 上游 `wechat-article-exporter` 作者于 **2026-07-30** 发布停止维护公告；其在线站
  `down.mptext.top` 域名 **2026-10-30** 到期。
- 微信未发布公开公告，故严格表述为"证据充分的接口级调整"，功能性等价于关闭。
- 同一登录会话可出现"搜索成功（searchbiz）、单篇正文可打开、但列表失败"——说明登录健康、
  目标健康、列表能力受限三者并存。

## 证据
- 同期三个独立项目在 2026-07-30/31 集中报同一现象：exporter issue #199、
  wechat-download-api #22、we-mp-rss #440。
- 分析文：https://lovstudio.ai/blog/wechat-cross-account-index-ret-200013-2026
- 退场报道：https://techmoon.xyz/wechat-article-exporter/
- 本工作区 `wechat-article-exporter/` 停在 2026-06-02 的 `757e6bf`（关闭前快照，README 无警告）。

## 仍然有效 / 已失效
| 能力 | 状态 |
|---|---|
| 公众号登录态管理（扫码/探活 searchbiz） | 有效 |
| 按 URL 抓单篇文章（公开 mp.weixin.qq.com/s 页面） | 有效（本平台已支持） |
| 订阅同步 / 批量历史文章列表 | 已关闭，无可靠绕行 |
| 阅读量/评论 | 需 mitmproxy 截包，风险高，不采用 |
| 公开索引发现（搜狗等） | 可绕但属推断渠道、易失效 —— **本平台明确不做** |

## 对本平台的影响
- P1 账号中心的公众号**登录态管理**保留。
- P6 不再包含"公众号内容订阅同步"；公众号只作为**单篇导入**来源。
```

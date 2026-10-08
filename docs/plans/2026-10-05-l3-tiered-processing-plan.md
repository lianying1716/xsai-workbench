# 素材加工分档（L1/L2/L3）实施计划

> **⚠️ 已被取代（superseded）**：本计划提出的**三档**（l1 转录 / l2 抽帧 / l3 视频理解）
> 后来被
> [`2026-10-06-two-tier-simplification-brief.md`](2026-10-06-two-tier-simplification-brief.md)
> 简化为**两档**：`""` / `basic`（转录）/ `advanced`（视频理解）——中间的「抽帧 L2」档已删除。
>
> **当前代码以 `media_asset.process_tier ∈ {"", "basic", "advanced"}` 为准**
> （见 `platform-api/app/models.py`）。本文中所有 `l1/l2/l3` 取值与 `extract_frames` / ffmpeg
> 抽帧相关任务**均已不作数**，只作历史留痕，勿据此开发。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为素材引入分档加工：L1 转录（已有）、L2 ffmpeg 抽帧/关键帧、L3 多维度视频理解；是否升级到 L2/L3 由**动态热度门控**决定（阈值存 `system_setting`、可在线调、不写死），L3 采用「先判类型 → 再按视频类型选专属提示词 → 调 nexai 视频理解模型」的两遍式。

**Architecture:** 采集/同步产出内容与指标 → `process_gate.select_tier`（纯函数：热度分 + 分位 + 下限 + 预算）决定档位 → 入队 `extract_frames`（ffmpeg，零模型成本）→ 入队 `understand_video`（worker 内：`classify.classify` 判类型 → `process_settings` 取该类型提示词 → `vision.understand` 调 nexai `qwen3.8-flash`（OpenAI 兼容 `video_url`）或备用 `gemini-3.8-flash`（原生 `inlineData`）→ 写 `video_understanding`）→ API/前端展示。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / httpx / ffmpeg（外部二进制）/ pytest / Vue 3 + Element Plus。

> 前置调研与设计：`docs/plans/2026-10-05-video-understanding-tier-research.md`、
> `docs/plans/2026-10-05-l3-type-aware-prompting-design.md`、
> `docs/plans/evidence/2026-10-05-xsai-video-input-probe.md`。
> **核心实测事实**：nexai `qwen3.8-flash` 支持视频输入，OpenAI 兼容
> `content=[{"type":"video_url","video_url":{"url":"data:video/mp4;base64,..."}}]`；
> 判类 Pass 0 用纯文本实测 4/4 正确。

## Global Constraints

- 后端 = FastAPI；DB = PostgreSQL（开发/测试 SQLite）；单管理员；**API 即产品**（前端 / MCP / HTTP 同能力）。
- **本机永远局域网访问**：服务/接口按既有约定绑定，不得改成仅回环。
- **不写死阈值**：门控参数、类型目录、类型提示词全部存 `system_setting`（KV），有内置默认、可在线改、写入侧范围/结构校验（非法 422）。
- **供应商可换**：视频理解能力抽象为 provider 适配器（Base URL / Key / 模型名 / 协议），nexai 只是默认预设；**不硬编码模型名**（默认值可配，运行时可换）。
- **判类与理解分开**：判类只看文本（默认），失败回退通用模板且不阻断理解；`use_cover` 由用户可选（默认关闭）。
- **禁止编造**：提示词必须含「看不到的维度填 null」约束；结果记 `prompt_version`、`usage`（含 video_tokens）。
- 不落凭证明文；不新增对外绝对路径；无静默遥测。
- 只在 `platform-api/` 内提交；Conventional Commits（`feat:`/`fix:`/`test:`/`chore:`）。
- 复用既有夹具（`tests/conftest.py` 的 `client` / `session` / `_engine`）；**当前 62 个测试必须保持全绿**。
- 不改动既有 job handler 行为；新增 job_type 只扩展 `HANDLERS`。

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `app/models.py` | 新增 `AssetFrame`、`VideoUnderstanding`；`ContentItem` 加 `duration_sec`/`auto_category`/`category_confidence`；`MediaAsset` 加 `process_tier`/`frames_status`/`understand_status` | Modify |
| `alembic/versions/0003_tiered_processing.py` | 迁移：建两张表 + 加列 | Create |
| `app/core/process_settings.py` | 门控参数 + 类型目录 + 类型提示词 + 通用维度，KV 读写（带默认） | Create |
| `app/services/process_gate.py` | 纯函数 `select_tier`（热度分/分位/下限/预算） | Create |
| `app/modules/frames.py` | ffmpeg 场景切分/关键帧抽取（`extract`），产出文件 + 帧元数据 | Create |
| `app/modules/classify.py` | 判类 Pass 0（文本；可选封面），返回 `{type,confidence,reason,signals}` | Create |
| `app/modules/vision.py` | 视频理解 provider 适配器（qwen `video_url` / gemini `inlineData`）+ 结构化 JSON 解析 | Create |
| `app/services/understand_service.py` | 组合：判类 → 选提示词 → 调 vision → 写库；含预处理（压体积） | Create |
| `app/workers/handlers.py` | 新增 `handle_extract_frames`、`handle_understand_video` + 注册 | Modify |
| `app/api/assets.py` | `GET /assets/{id}/frames`、`GET /assets/{id}/understanding`、`POST /assets/{id}/process`、`POST /assets/{id}/reclassify` | Modify |
| `app/api/system.py` | `GET/PUT /api/system/process-settings` | Modify |
| `app/config.py` | 视觉模型默认配置项 | Modify |
| `web/src/pages/Assets.vue` | 详情「分档加工」区 | Modify |
| `web/src/pages/Settings.vue` | 「视频理解」tab（可编辑类型提示词） | Modify |
| `tests/test_process_gate.py` | 门控纯函数 | Create |
| `tests/test_process_settings.py` | 配置读写默认/校验 | Create |
| `tests/test_frames.py` | 抽帧（ffmpeg 存在时；否则 skip） | Create |
| `tests/test_classify.py` | 判类（mock httpx） | Create |
| `tests/test_vision.py` | provider 适配 + JSON 解析（mock httpx） | Create |
| `tests/test_understand_service.py` | 组合流程（mock classify+vision） | Create |
| `tests/test_understanding_api.py` | 新 API 鉴权/读写 | Create |
| `tests/test_tiered_handlers.py` | 两个 handler 幂等/状态 | Create |

---

### Task 1: 数据模型 + 迁移 `0003`

**Files:**
- Modify: `app/models.py`
- Create: `alembic/versions/0003_tiered_processing.py`
- Test: `tests/test_process_gate.py`（先加模型结构/唯一约束测试）

**Interfaces:**
- Produces:
  - `AssetFrame(id, asset_id, scene_index, timestamp_sec: float, path: str, is_keyframe: bool, created_at)`
  - `VideoUnderstanding(id, asset_id unique, category, category_confidence, category_reason, dimensions: JSON, summary, timeline: JSON, model, prompt_version, usage: JSON, status, error, created_at)`
  - `ContentItem.duration_sec: int`, `ContentItem.auto_category: str`, `ContentItem.category_confidence: float`
  - `MediaAsset.process_tier: str`（`""`/`l1`/`l2`/`l3`）、`MediaAsset.frames_status: str`、`MediaAsset.understand_status: str`

- [ ] **Step 1: 写失败测试**

```python
def test_tiered_models_exist(session):
    from app.models import AssetFrame, VideoUnderstanding, ContentItem, MediaAsset
    from sqlalchemy import inspect
    assert "asset_frame" in inspect(session.get_bind()).get_table_names()
    assert "video_understanding" in inspect(session.get_bind()).get_table_names()
    assert hasattr(ContentItem, "duration_sec") and hasattr(ContentItem, "auto_category")
    assert hasattr(MediaAsset, "process_tier")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_process_gate.py::test_tiered_models_exist -v`
Expected: FAIL（模型/表不存在）

- [ ] **Step 3: 实现模型与迁移**（按上方 Interfaces 定义字段；`asset_frame` 加 `UniqueConstraint("asset_id","scene_index")`；`video_understanding.asset_id` unique）

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_process_gate.py::test_tiered_models_exist -v`
Expected: PASS

- [ ] **Step 5: 迁移往返验证 + 提交**

Run: `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
Commit: `feat: add tiered-processing models and migration 0003`

---

### Task 2: 加工配置读取 `process_settings`

**Files:**
- Create: `app/core/process_settings.py`
- Test: `tests/test_process_settings.py`

**Interfaces:**
- Produces:
  - `PROCESS_KEYS: dict[str,str]`（短名→system_setting key）
  - `get_process_settings(db) -> dict`：门控数值参数（`l2_min_heat, l3_min_heat, min_likes_floor, budget, top_pct, weight_comment, weight_like, weight_play, frames_per_min, max_frames, video_max_mb, classify_enabled, use_cover, provider, vision_model, classify_model`）
  - `get_type_prompts(db) -> dict[str,dict]`：类型→`{"focus": str, "dimensions": [{"key","name","ask"}]}`
  - `get_taxonomy(db) -> dict[str,str]`：枚举→中文
  - `DEFAULT_TYPE_PROMPTS`, `DEFAULT_TAXONOMY`, `COMMON_DIMENSIONS` 常量（内置默认）

- [ ] **Step 1: 写失败测试**（默认值与覆盖）

```python
def test_process_defaults(session):
    from app.core.process_settings import get_process_settings
    s = get_process_settings(session)
    assert s["l2_min_heat"] >= 0 and s["l3_min_heat"] > s["l2_min_heat"]
    assert s["video_max_mb"] > 0 and s["provider"] in ("qwen","gemini")

def test_process_override(session):
    from app.models import SystemSetting
    from app.core.process_settings import get_process_settings
    session.add(SystemSetting(key="process_l3_min_heat", value="999"))
    session.commit()
    assert get_process_settings(session)["l3_min_heat"] == 999
```

- [ ] **Step 2: 跑测试确认失败** → Expected: FAIL（模块不存在）
- [ ] **Step 3: 实现**（沿用 `comment_settings.py` 的「KV 读取 + 类型归一 + 默认兜底」范式；类型提示词用 JSON 存单键 `process_type_prompts`，损坏时回退内置默认）
- [ ] **Step 4: 跑测试确认通过** → Expected: PASS
- [ ] **Step 5: 提交**：`feat: add process settings reader with defaults`

---

### Task 3: 动态门控 `select_tier`

**Files:**
- Create: `app/services/process_gate.py`
- Test: `tests/test_process_gate.py`（追加）

**Interfaces:**
- Consumes: `get_process_settings(db)`
- Produces: `select_tier(candidates: list[dict], s: dict) -> list[dict]`
  - 输入候选：`{"content_id", "like", "comment", "play", "existing_tier"}`
  - 输出：`{"content_id", "tier", "score", "reason"}`
  - 规则：`score = w_like*like + w_comment*comment + w_play*play`；`like < min_likes_floor` → 不高于 `l1`；
    `score >= l3_min_heat` → `l3`；`>= l2_min_heat` → `l2`；否则 `l1`；
    **取分位前 `top_pct`** 且**总入队数受 `budget` 约束**；已 `l3` 的不降级（`existing_tier`）。

- [ ] **Step 1: 写失败测试**（分位/下限/预算/不降级）

```python
def test_gate_tiers_and_budget():
    from app.services.process_gate import select_tier
    s = {"weight_like":1,"weight_comment":2,"weight_play":0,"min_likes_floor":100,
         "l2_min_heat":200,"l3_min_heat":1000,"top_pct":0.5,"budget":2}
    cands=[{"content_id":i,"like":l,"comment":0,"play":0,"existing_tier":""}
           for i,l in enumerate([5000,800,50,10])]
    out={r["content_id"]:r["tier"] for r in select_tier(cands,s)}
    assert out[0]=="l3" and out[1]=="l2" and out[2]=="l1" and out[3]=="l1"
    assert sum(1 for r in select_tier(cands,s) if r["tier"] in ("l2","l3")) <= s["budget"]
```

- [ ] **Step 2: 跑测试确认失败** → FAIL
- [ ] **Step 3: 实现纯函数**（不碰 DB；边界：空输入→`[]`；`top_pct` 用整数分位避免浮点 off-by-one）
- [ ] **Step 4: 跑测试确认通过** → PASS
- [ ] **Step 5: 提交**：`feat: add process tier gate (dynamic thresholds)`

---

### Task 4: L2 抽帧 `app/modules/frames.py`

**Files:**
- Create: `app/modules/frames.py`
- Test: `tests/test_frames.py`

**Interfaces:**
- Produces: `extract(video_path: str, out_dir: str, *, max_frames: int, per_min: float, scene_threshold: float = 0.3) -> dict`
  - 返回 `{"frames": [{"scene_index","timestamp_sec","path","is_keyframe"}], "count": int}`
  - 用 ffmpeg `select='gt(scene,THRESHOLD)'`（场景切换）取帧；若场景数不足则按 `per_min` 时间间隔均匀补帧；上限 `max_frames`
  - 缩略图：输出 JPEG（`-q:v 3`），文件名 `frame_%03d.jpg`
- Raises: `FileNotFoundError`（视频不存在）、`RuntimeError`（ffmpeg 失败，带 stderr 摘要）

- [ ] **Step 1: 写失败测试**（有 ffmpeg 才跑，否则 `pytest.skip`）

```python
import shutil, subprocess, pytest
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 未安装")
def test_extract_frames(tmp_path):
    from app.modules.frames import extract
    vid = tmp_path/"v.mp4"
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=3:size=160x120:rate=10",
                    "-pix_fmt","yuv420p",str(vid)],capture_output=True,check=True)
    out = extract(str(vid), str(tmp_path/"frames"), max_frames=6, per_min=10)
    assert out["count"] >= 1 and all(__import__("os").path.exists(f["path"]) for f in out["frames"])
```

- [ ] **Step 2: 跑测试确认失败** → FAIL（模块不存在）
- [ ] **Step 3: 实现**（subprocess 调 ffmpeg，禁用 shell；解析时间戳用 `ffprobe` 或按序号估算；不引入新依赖）
- [ ] **Step 4: 跑测试确认通过** → PASS
- [ ] **Step 5: 提交**：`feat: add ffmpeg keyframe extraction module`

---

### Task 5: 判类 Pass 0 `app/modules/classify.py`

**Files:**
- Create: `app/modules/classify.py`
- Test: `tests/test_classify.py`

**Interfaces:**
- Consumes: `get_taxonomy`, LLM 配置（DB `system_setting` 优先，回退 `settings`）
- Produces: `async classify(title, author, duration_sec, transcript, taxonomy: dict, *, cover_path: str|None, base_url, api_key, model, timeout=30) -> dict`
  - 返回 `{"type": <枚举>, "confidence": float, "reason": str, "signals": list[str]}`
  - 不在枚举内 → `type="other"`, `confidence=0`
  - 网络/解析失败 → 抛异常（调用方回退通用模板）
  - **测试注入点**：模块内定义 `async def _post_json(url, headers, body, timeout) -> dict`（内部用 `httpx.AsyncClient`），
    `classify` 只调用它。测试 monkeypatch `classify._post_json`，**不要 patch `httpx`**。

- [ ] **Step 1: 写失败测试**（mock httpx，断言解析与非法枚举回退）

```python
def test_classify_parses(monkeypatch):
    import asyncio, app.modules.classify as c
    async def fake_post(url, headers, body, timeout):
        return {"choices":[{"message":{"content":'{"type":"commerce","confidence":0.9,"reason":"x","signals":["链接"]}'}}]}
    monkeypatch.setattr(c,"_post_json",fake_post)
    out=asyncio.run(c.classify("标题","作者",30,"转录",{"commerce":"带货"},cover_path=None,
                               base_url="http://x",api_key="k",model="m"))
    assert out["type"]=="commerce" and out["confidence"]==0.9

def test_classify_unknown_enum(monkeypatch):
    import asyncio, app.modules.classify as c
    async def fake_post(url, headers, body, timeout):
        return {"choices":[{"message":{"content":'{"type":"nope","confidence":0.5}'}}]}
    monkeypatch.setattr(c,"_post_json",fake_post)
    out=asyncio.run(c.classify("t","a",10,"tr",{"commerce":"带货"},cover_path=None,
                               base_url="http://x",api_key="k",model="m"))
    assert out["type"]=="other"
```

- [ ] **Step 2: 跑测试确认失败** → FAIL
- [ ] **Step 3: 实现**（`response_format=json_object`；`use_cover` 时把封面转 base64 作为 `image_url` 一并送）
- [ ] **Step 4: 跑测试确认通过** → PASS
- [ ] **Step 5: 提交**：`feat: add video type classifier (pass 0)`

---

### Task 6: 视频理解 provider `app/modules/vision.py`

**Files:**
- Create: `app/modules/vision.py`
- Test: `tests/test_vision.py`

**Interfaces:**
- Produces:
  - `build_payload(provider, model, video_b64, prompt, *, mime="video/mp4") -> tuple[str, dict, dict]`（返回 `(url, headers, json_body)`）
  - `async understand(video_path, prompt, *, provider, base_url, api_key, model, max_mb=15, timeout=300) -> dict`
    - 返回 `{"text": str, "usage": dict, "model": str, "provider": str}`
    - 体积超 `max_mb` → 抛 `ValueError`（由 service 先压缩）
  - provider 适配：`qwen` → `POST {base}/chat/completions`，`content=[{"type":"text",...},{"type":"video_url","video_url":{"url":"data:video/mp4;base64,..."}}]`；
    `gemini` → `POST {base}/v1beta/models/{model}:generateContent`，`parts=[{"text":...},{"inlineData":{"mimeType":"video/mp4","data":b64}}]`
  - `parse_structured(text) -> dict`：容错解析模型返回的 JSON（去 ``` 围栏）

- [ ] **Step 1: 写失败测试**（两种 provider 的 payload 结构与 JSON 容错）

```python
def test_build_payload_qwen():
    from app.modules.vision import build_payload
    url, headers, body = build_payload("qwen","qwen3.8-flash","AAA","提示")
    c = body["messages"][0]["content"]
    assert c[1]["type"]=="video_url" and c[1]["video_url"]["url"].startswith("data:video/mp4;base64,AAA")

def test_build_payload_gemini():
    from app.modules.vision import build_payload
    url, headers, body = build_payload("gemini","gemini-3.8-flash","BBB","提示")
    assert url.endswith("/v1beta/models/gemini-3.8-flash:generateContent")
    assert body["contents"][0]["parts"][1]["inlineData"]["data"]=="BBB"

def test_parse_structured_fenced():
    from app.modules.vision import parse_structured
    assert parse_structured('```json\n{"a":1}\n```')["a"]==1
```

- [ ] **Step 2: 跑测试确认失败** → FAIL
- [ ] **Step 3: 实现**（`understand` 内部同样用模块级 `async def _post_json(...)`（`httpx.AsyncClient`）以便测试注入；
  `build_payload` / `parse_structured` 保持纯函数，测试不联网）
- [ ] **Step 4: 跑测试确认通过** → PASS
- [ ] **Step 5: 提交**：`feat: add video-understanding provider adapters`

---

### Task 7: 组合服务 `understand_service` + worker handlers

**Files:**
- Create: `app/services/understand_service.py`
- Modify: `app/workers/handlers.py`
- Test: `tests/test_understand_service.py`, `tests/test_tiered_handlers.py`

**Interfaces:**
- Consumes: `process_settings`, `classify`, `vision`, `frames`, `queue.enqueue`
- Produces:
  - `async run_understand(db, asset_id, *, force_category: str|None=None, use_cover: bool|None=None) -> VideoUnderstanding`
    1. 取 content + transcript；2. （未强制时）判类，失败→`other`+通用模板；3. 取该类型提示词；4. 体积超限先用 ffmpeg 压缩；5. `vision.understand`；6. `parse_structured`；7. upsert `VideoUnderstanding` + 更新 `content_item.auto_category` / `asset.understand_status`
  - `async run_extract_frames(db, asset_id) -> int`：调 `frames.extract`，幂等写 `AssetFrame`（按 `scene_index` upsert），更新 `asset.frames_status`/`process_tier`
  - `handle_extract_frames(db, payload)`、`handle_understand_video(db, payload)` + 注册到 `HANDLERS`

- [ ] **Step 1: 写失败测试**（mock classify/vision；断言写库字段与 prompt_version）

```python
def test_run_understand_writes(monkeypatch, session):
    import asyncio, app.services.understand_service as svc
    async def fake_classify(*a,**k): return {"type":"commerce","confidence":0.9,"reason":"x","signals":[]}
    async def fake_understand(*a,**k): return {"text":'{"summary":"s","dimensions":{"product":"裙子"}}',
                                              "usage":{"video_tokens":10},"model":"m","provider":"qwen"}
    monkeypatch.setattr(svc,"classify",fake_classify)
    monkeypatch.setattr(svc.vision,"understand",fake_understand)
    # 造 content/asset/transcript 后：
    # u = asyncio.run(svc.run_understand(session, asset.id)); assert u.category=="commerce"
```

- [ ] **Step 2: 跑测试确认失败** → FAIL
- [ ] **Step 3: 实现**（handler 抛异常即失败交给 runner 重试；`asset.understand_status` 置 doing/done/error）
- [ ] **Step 4: 跑测试确认通过** → PASS
- [ ] **Step 5: 提交**：`feat: add understand service and tiered handlers`

---

### Task 8: API（系统设置 + 素材分档）

**Files:**
- Modify: `app/api/system.py`, `app/api/assets.py`
- Test: `tests/test_understanding_api.py`, `tests/test_process_settings.py`（追加 422 用例）

**Interfaces:**
- Produces:
  - `GET /api/system/process-settings` → 门控参数 + 类型目录 + 类型提示词（**可读，用于设置页展示**）
  - `PUT /api/system/process-settings` → 校验范围/JSON 结构，非法 422，原子写
  - `GET /api/assets/{id}/frames` → 帧列表（含缩略图相对路径/URL）
  - `GET /api/assets/{id}/understanding` → 理解结果（无则 `{"status":"pending"}`）
  - `POST /api/assets/{id}/process` body `{tier: "l2"|"l3", force_category?: str, use_cover?: bool}` → 入队
  - `POST /api/assets/{id}/reclassify` → 重跑判类

- [ ] **Step 1: 写失败测试**（422 校验 + 鉴权 + 入队）

```python
def test_put_process_settings_rejects_bad(client):
    r = client.put("/api/system/process-settings", json={"l3_min_heat": -1})
    assert r.status_code == 422

def test_post_process_enqueues(client, session):
    # 造 asset 后
    r = client.post(f"/api/assets/{asset_id}/process", json={"tier":"l3"})
    assert r.status_code == 200
```

- [ ] **Step 2: 跑测试确认失败** → FAIL
- [ ] **Step 3: 实现**（复用 `security.require_admin` 依赖；写侧校验沿用 `_as_int`/`_as_float` 模式）
- [ ] **Step 4: 跑测试确认通过** → PASS
- [ ] **Step 5: 提交**：`feat: add process settings and asset tier APIs`

---

### Task 9: 前端 —— 素材详情「分档加工」+ 设置「视频理解」tab

**Files:**
- Modify: `web/src/pages/Assets.vue`, `web/src/pages/Settings.vue`
- Test: 前端无测试脚本，跑 `cd web && npm run build`

**Interfaces:**
- Consumes: 上述 API
- 素材详情新增：当前档位徽标、类型徽标 + 置信度 + 判类理由、维度卡片（JSON 美化）、帧墙（缩略图）、按钮「抽帧 / 视频理解 / 改类型重跑」、`use_cover` 勾选
- 设置新增「视频理解」tab：门控参数表单 + 类型目录/类型提示词**可查看可编辑**（textarea/JSON，保存前本地校验）

- [ ] **Step 1: 前端接线**（`api` 封装按既有 `Ht` axios 实例）
- [ ] **Step 2: 构建验证**

Run: `cd web && npm run build`
Expected: 构建成功

- [ ] **Step 3: 提交**：`feat: tiered-processing UI (asset detail + settings)`

---

## Self-Review

- **Spec 覆盖**：分档（T1/T4/T7）、动态门控不写死（T2/T3/T8）、视频理解可用（T6，已实测 provider）、**按类型区分提示词**（T2/T5/T6/T7）、设置页可看可编辑（T8/T9）、封面可选（T5/T8/T9）。
- **类型安全**：门控/配置全走 `system_setting` + 写侧校验；判类非法枚举回退 `other`。
- **不写死**：默认值可覆盖；模型名/协议可换 provider。
- **既有测试**：新增表/列用迁移；不改既有 handler 行为；每任务后跑全量 `uv run pytest`。
- **开放项（执行时确认）**：`analysis.py` 只读 config 的历史问题不在本计划范围；本计划的 vision/classify 走 DB 优先，保证设置页生效。

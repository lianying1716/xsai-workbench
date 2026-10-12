# 任务：把「素材加工分档」从三档简化为两档（删除抽帧档）

## 背景
已合并的 `feat/tiered-processing` 引入了三档：l1 转录 / l2 抽帧 / l3 视频理解。
用户要求**删掉中间的「抽帧」档，只保留两种**：
- **普通（basic）= 转录**（faster-whisper，已有能力）
- **高级（advanced）= 多维度视频理解**（判类 → 类型专属提示词 → 调 nexai 视频模型）

## 关键事实（已核实，可放心删）
- `run_understand`（视频理解）**完全不依赖抽帧**——不读 `AssetFrame`、不读 `frames_status`。
- 无 MCP / skills 引用抽帧。
- dev DB 里没有任何 `process_*` 配置行（无需清洗旧 KV）。
- `job_queue.payload`、`VideoUnderstanding` 等与本改动无关。

## 新的档位取值（全库统一）
`media_asset.process_tier` ∈ `""`（未加工） / `"basic"` / `"advanced"`。
删掉 `"l1"/"l2"/"l3"` 全部用法。

---

## 需要删除的东西（彻底删）
1. `app/modules/frames.py` —— 整个文件删除。
2. `app/models.py`：
   - 删除 `AssetFrame` 类。
   - `MediaAsset` 删除 `frames_status` 列。
   - `MediaAsset.process_tier` 注释改为 `# ""/basic/advanced`，并把 `String(8)` 放宽到 `String(16)`。
3. `app/services/understand_service.py`：
   - 删除 `run_extract_frames`。
   - 删除仅它使用的辅助函数（`_storage_root_path`、`_to_relative` 等，如无其它调用者）。
   - 删除 `AssetFrame` import。
   - `run_understand` 里 `asset.process_tier = "advanced"`（原为 "l3"）。
4. `app/workers/handlers.py`：删除 `handle_extract_frames` 与 `HANDLERS` 里的 `"extract_frames"` 注册；删除相应 import/docstring 文案。
5. `app/api/assets.py`：
   - 删除 `GET /assets/{id}/frames` 与 `GET /assets/{id}/frames/{scene_index}/image` 两个端点，及 `AssetFrame`/`_asset_storage_root_path` 等仅它们使用的辅助。
   - 素材详情返回里删除 `"frames": asset.frames_status`。
   - `POST /assets/{id}/process`：`tier` 只接受 `"basic"` 与 `"advanced"`：
     - `basic` → 入队 `transcribe`（复用既有 handler），并置 `asset.transcribe_status="pending"`；
     - `advanced` → 入队 `understand_video`（保留 `force_category` / `use_cover` 逻辑）；
     - 其它值 → 422（detail 写清只支持 basic / advanced）。
   - `reclassify` 端点的语义保持（重跑判类+理解 → advanced）。
6. `app/core/process_settings.py`：
   - `PROCESS_KEYS` 删除 `l2_min_heat`、`frames_per_min`、`max_frames`；把 `l3_min_heat` 改名为 `min_heat`（key `process_min_heat`）。
   - `_DEFAULTS` 相应删除/改名（`process_min_heat` 默认 1000，`_INT`）。
7. `app/api/system.py`：`_PROCESS_SPECS` 同步（删 3 项、改名 1 项）。
8. 前端 `web/src/pages/Assets.vue`：
   - 删除帧墙、`抽帧` 状态标签、`抽帧` 按钮、帧缩略图 blob 拉取、`frames_status` 相关 ref/轮询条件。
   - 档位按钮改为两个：**「转录（普通）」** 与 **「视频理解（高级）」**（`use_cover` 勾选保留给高级）。
   - 轮询条件只看 `understand_status`。
   - 档位徽标显示改为 basic/advanced 的中文（普通 / 高级）。
9. 前端 `web/src/pages/Settings.vue`：
   - 删除 `每分钟抽帧 frames_per_min`、`最多帧数 max_frames`、`l2_min_heat` 三个表单项（含默认值对象与保存请求体）。
   - `l3_min_heat` 改名 `min_heat`（标签如「高级档热度阈值」）。
10. 测试：
    - 删除 `tests/test_frames.py`。
    - `tests/test_process_gate.py`：删除 `AssetFrame` 相关用例与 l2→extract_frames 期望；档位断言改 basic/advanced。
    - `tests/test_understand_service.py`：删除 `run_extract_frames` 两用例。
    - `tests/test_tiered_handlers.py`：删除 `handle_extract_frames` 用例与 `"extract_frames" in HANDLERS` 断言。
    - `tests/test_understanding_api.py`：删除 `/frames`、`/frames/{i}/image` 全部用例；`/process` 断言改为 basic→transcribe、advanced→understand_video。
    - `tests/test_pipeline_e2e.py`：更新所有 l2/extract_frames/frames_status 期望。
    - `tests/test_process_settings.py`：更新键集合（min_heat，无 l2/frames）。

## 新增迁移 `alembic/versions/0005_two_tier.py`
- `revision="0005"`, `down_revision="0004"`。
- upgrade：
  - `op.drop_table("asset_frame")`
  - `op.drop_column("media_asset", "frames_status")`
  - 数据迁移：`UPDATE media_asset SET process_tier='advanced' WHERE process_tier='l3'`；`UPDATE media_asset SET process_tier='basic' WHERE process_tier IN ('l1','l2')`；`''` 保持 `''`。
  - `process_tier` 放宽到 `String(16)`（`op.alter_column`）。
- downgrade：完整逆向（重建 `asset_frame` 表 + `frames_status` 列 + 档位值映射回 l1/l2/l3；`basic→l1`、`advanced→l3`）。
- 必须通过 `alembic upgrade head` / `downgrade -1` / `upgrade head` 往返，且 `alembic check` 无漂移。

## 新档位语义（门控 `app/services/process_gate.py`）
- `_RANK = {"": 0, "basic": 1, "advanced": 2}`
- `_TIER_JOB = {"advanced": "understand_video"}`（basic 不自动入队：转录是既有独立管线，不在本门控范围）。
- `select_tier`：
  - `like < min_likes_floor` → `"basic"`
  - `score >= min_heat` 且在本批热度前 `top_pct` 名内 → `"advanced"`，否则 `"basic"`
  - `budget` 约束 advanced 条数（超出的从最低分降回 basic）
  - `existing_tier == "advanced"` → 保持 advanced（不降级）
  - reason 文案改 basic/advanced。
- `select_targets`：只产出 advanced 目标（basic 无 job）。
- `enqueue_process_jobs`：在途预算只统计 `understand_video`；入队时置 `understand_status="pending"`；**不再有任何 frames 状态**。
- 门控接线点（`handle_download` / crawl / sync）保持不变。

## 验证（必须真实跑）
- `uv run pytest tests/ -q` 全绿。
- `alembic upgrade head` / `downgrade -1` / `upgrade head` 往返 OK；`alembic check` 无漂移。
- `cd web && npm run build` 通过。
- 全仓不得再有 `AssetFrame` / `extract_frames` / `frames_status` / `app.modules.frames` / `l2_min_heat` / `frames_per_min` / `max_frames` 的残留引用（`grep` 证明，测试文件里也不许）。
- SQLite（测试）与 PG（dev 5433）两条路都要能建表/迁移。

## 红线
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 不写死阈值；供应商可换；不落凭证明文。
- 不破坏既有的转录、评论富集、采集/同步、判类/视频理解能力。

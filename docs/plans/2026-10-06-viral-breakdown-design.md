# 爆款拆解报告 + 对标账号拆解 · 设计

> 日期：2026-10-06
> 前置调研：`2026-10-06-viral-breakdown-competitor-research.md`（竞品都展示什么）
> 用户确认：① 单条拆解 + 对标账号拆解 一起做（可先后，同批交付）；② **不做受众画像**（拿不到平台完播/性别年龄，用互动数据 + 评论洞察替代）；③ 爆发提醒后置。
> **红线：本功能内不做任何星算 AI 宣传。** 星算的宣传只出现在「模型中心」与「MCP / skill」两处；拆解报告里只把模型名作为技术元数据记录，不做品牌露出、不做升级引导。

---

## 1. 两个功能，一个闭环

| 功能 | 形态 | 数据来源 |
|---|---|---|
| **A. 爆款拆解报告** | 一条作品 → 一份"为什么火 + 怎么复刻"的结构化报告 | 转录、视频理解(L3)、评论、互动快照、标题 |
| **B. 对标账号拆解** | 一个作者 → 一份账号级内容策略分析 | A 的聚合 + 内容元数据 + 互动快照 |

关系：B = A 在账号维度的聚合；A = B 的证据。**先做 A（LLM 重活、感官最强），再做 B（聚合、几乎零额外成本）。**

---

## 2. 功能 A：爆款拆解报告

### 2.1 报告结构（对齐竞品，见调研 §2）

```json
{
  "verdict": "一句话结论：这条为什么火",
  "score": 0-100,
  "hook": {
    "first_line": "前 3 秒台词",
    "first_frame": "首帧画面",
    "hook_type": "好奇缺口/反常识/清单体/转变叙事/痛点直呼/其他",
    "why": "为什么抓人"
  },
  "structure": [
    {"segment": "0-3s", "role": "钩子", "summary": "..."},
    {"segment": "3-15s", "role": "展开", "summary": "..."},
    {"segment": "...", "role": "转折/高潮/CTA", "summary": "..."}
  ],
  "pacing": {
    "pattern_interrupts": ["每 3-5 秒一个变化，举例"],
    "re_engagement_points": [8, 15],          // 二次拉回秒数（行业 8s / 12-18s）
    "emotion_curve": "情绪曲线描述"
  },
  "script": {
    "reusable_phrases": ["可复用句式"],
    "money_lines": ["金句/记忆点"]
  },
  "psych_triggers": ["好奇", "认同", "损失厌恶"],
  "cta": {"type": "引导方式", "placement": "位置"},
  "data_context": {                            // 确定性计算，不走 LLM
    "play": 0, "like": 0, "comment": 0,
    "play_vs_median": 0.0, "like_vs_median": 0.0,
    "engagement_rate": 0.0, "percentile": 0.0
  },
  "comment_insights": {                        // LLM 归纳评论
    "top_themes": ["观众最关心什么"],
    "controversies": ["争议点"],
    "questions": ["可回复/可做下一条的问题"]
  },
  "blueprint": ["复刻步骤：1... 2... 3..."],
  "replication_tips": ["给创作者的落地建议"]
}
```

- `data_context` 由后端**确定性**计算（相对该作者内容中位数的倍数、互动率、分位），不交给 LLM，保证数字可信。
- 其余字段由 LLM 产出，**必须严格 JSON**，看不到的字段填 null/空数组，禁止编造。

### 2.2 输入拼装（复用现有能力，不新增采集）
1. **转录**：`transcript.full_text` + 前若干 `segments`（用于拆钩子/时间轴）。
2. **视频理解**：`video_understanding.summary/dimensions/timeline`（若已跑过 L3，直接复用；它是画面+结构的可靠来源）。
3. **评论**：`comment` 表按 `like_count` 取 Top-N 正文（供 LLM 归纳观众洞察）。
4. **互动上下文**：最新 `content_metric_snapshot` + 该作者的历史中位数。
5. **元数据**：平台、标题、作者、时长、发布时间。

> 若没有 L3 理解：仍可用「转录 + 评论 + 指标」产出降级报告，并在结果里标 `understanding_available=false` 提示可先跑视频理解。**拆解不强制依赖 L3。**

### 2.3 触发与存储
- 新 job_type `breakdown`（worker 消费，走既有队列），`POST /assets/{id}/breakdown` 入队，`GET /assets/{id}/breakdown` 读取。
- 新表 `viral_breakdown`（一素材一行，asset_id 唯一），存 `score/verdict/sections/comment_insights/data_context/model/prompt_version/usage/status/error/created_at`。
- 提示词可配置：`system_setting` KV `breakdown_prompt`，有内置默认、可在线改（沿用既有范式，不写死）。

---

## 3. 功能 B：对标账号拆解

**纯聚合，实时计算（不新增表、不调 LLM）**，端点 `GET /api/analytics/creator/{author_id}/report?platform=`：

| 板块 | 内容 |
|---|---|
| **账号概览** | 发布量、时间跨度、平均/中位 播放·点赞·评论、平均互动率 |
| **发布节奏** | 按星期几分布、按小时分布（找出它的发文习惯） |
| **Top 作品** | 按最新播放量 Top10（标题/时间/互动） |
| **爆款规律** | 该账号中"爆款"（播放 ≥ 自身中位数 × 阈值，阈值可配默认为 3）= 这些爆款的共性：类型分布、时长、发布时段 |
| **内容支柱** | 该账号内容的类型分布（复用 `content_item.auto_category` / `video_understanding.category`） |
| **对标基准** | 该账号 vs 同平台全体中位数（谁更强、差多少） |
| **缺口提示** | 该平台整体高热度类型里，该账号没做的类型（内容缺口，来自分位对比） |

- 「爆款」判定用**相对该账号自身中位数**的倍数（避免大号普通内容误判），与成熟产品一致（调研 §3）。
- 不依赖粉丝数（我们拿不到），全部基于已采集内容的互动快照。
- 爆发提醒（定时多次刷新 + 通知）**本期不做**，记 backlog。

---

## 4. 与现有系统的接缝

| 层 | 改动 |
|---|---|
| 模型/迁移 | 新表 `viral_breakdown`；Alembic `0006` |
| 配置 | `app/core/breakdown_settings.py`：提示词 + 爆款阈值（KV + 默认，可在线改） |
| 模块 | `app/modules/breakdown.py`：提示词构造 + LLM 调用 + JSON 解析（复用 `analysis.py`/`vision.py` 的 OpenAI 兼容封装与 `_post_json` 测试注入点） |
| 服务 | `app/services/breakdown_service.py`：拼装输入 → 调 LLM → 算 data_context → 落库 |
| 队列 | `handlers.py` 新增 `breakdown` handler + 注册 |
| API | `POST/GET /api/assets/{id}/breakdown`；`GET /api/analytics/creator/{author_id}/report` |
| 前端 | 素材详情新增「爆款拆解」区（按钮 + 报告卡片：结论/评分/钩子/结构/节奏/文案/评论洞察/复刻蓝图）；数据看板新增「对标账号」入口与报告页 |
| MCP/Skill | 与 HTTP 对等：`breakdown_video(asset_id)`、`get_breakdown(asset_id)`、`creator_report(author_id, platform)` |

---

## 5. 红线

- **本功能内零星算宣传**：报告不出现"由星算提供"、不出现升级引导、不出现品牌 logo；只把模型名作为技术元数据（`model` 字段）记录。星算宣传只放「模型中心」与「MCP/skill」。
- 供应商可换、模型名来自配置、不硬编码。
- 数字（data_context / 对标）由后端确定性计算，LLM 只负责定性分析，避免编造。
- 不新增采集渠道、不依赖平台未开放数据（完播率/画像）。
- 复用既有转录、视频理解、评论、指标快照；缺失时优雅降级并如实标注。

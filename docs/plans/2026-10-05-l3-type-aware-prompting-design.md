# L3 视频理解 · 按视频类型区分的提示词体系（设计）

> 日期：2026-10-05
> 前置：`2026-10-05-video-understanding-tier-research.md`（已确认 nexai `qwen3.8-flash` 支持视频输入理解）
> 本文只解决用户提出的第 3 点：**提示词要按视频类型区分，不能一刀切**。
> 用户已拍板：第 1、2 点按前文建议（保守可调门控 + 超限先压缩/切片）。

---

## 1. 问题陈述

同一个「多维度理解」提示词，套到所有视频上会出两类问题：

- **该看的没看**：带货视频最该拆「卖点/价格/钩子/转化号召」，知识视频最该拆「论点/论据/结论」，
  剧情视频最该拆「人物关系/冲突/反转/笑点」——用一套通用维度，等于每条都问了一堆不痛不痒的问题。
- **不该看的看了**：对纯剧情/娱乐视频追问「商业转化要素」，模型只能硬编，产出噪声。

**结论：先判类型，再按类型给专属的“关注点 + 维度集 + JSON schema”。**

---

## 2. 设计目标

1. **类型驱动**：判类 → 选类型专属提示词 → 产出该类型该有的维度。
2. **可扩展**：新增类型 / 调整某类型的维度，只改配置，不改业务代码。
3. **可覆盖**：运营可改某类型的提示词/维度，也可对单条手动指定类型后重跑。
4. **可纠错**：分类可能出错，必须能看理由、能人工改、能按新类型重跑。
5. **可校验**：模型输出结构化 JSON，按 schema 解析；分类与理解分两次调用，互不阻塞。

---

## 3. 两遍式架构

```
                    ┌─ metadata: platform / title / author / duration / 互动
ContentItem ────────┤
                    └─ L1 转录 full_text（若已有）
                            │
                  ① 判类 Pass 0（文本模型，便宜）
                            │  {type, confidence, reason, signals}
                            ▼
                  ② 选类型专属提示词（维度集 + Focus + schema）
                            │
                  ③ 视频理解 Pass 1（视频模型 qwen3.8-flash）
                    输入：视频 + 该类型提示词 +（可选）转录文本
                            │
                            ▼
              video_understanding.dimensions (JSON) + 类型元数据
```

- **为什么分两遍**：判类只看文本，极便宜（~几百 token）；理解才花视频 token（较贵）。
  先判类再决定怎么问，避免用错模板浪费一次视频调用。
- **为什么判类用文本就够**：标题 + 转录前几百字 + 时长，实测足以高准确率分型（见 §9）。
- **失败隔离**：判类失败 → 回退「通用 spec」并标记 `type=other`，不阻断理解；理解失败 → 可单独重试，不重跑判类。

---

## 4. 分类器设计（Pass 0）

**输入信号**（有就用，缺就跳过）：
`platform`、`title`、`author_name`、`duration_sec`、`transcript` 前 ~600 字、互动量级（可选）。

**输出**：
```json
{"type":"<枚举>","confidence":0.0~1.0,"reason":"简短理由","signals":["命中的线索"]}
```

**规则**：
- `response_format=json_object` + 低温度，只允许枚举值；不在枚举内 → 归 `other`。
- `confidence < 阈值`（默认 0.6，可配）→ 用**通用 spec** 或**最接近的父类**，并在结果里标 `low_confidence=true` 供人工复核。
- 分类结果**单独存**：`content_item.auto_category`（或新表），与 `video_understanding` 解耦，便于只重跑分类。

**枚举 v1（16 类 + other）**：

| 枚举 | 中文 | 枚举 | 中文 |
|---|---|---|---|
| `knowledge` | 知识科普 | `news` | 新闻资讯/纪实 |
| `opinion` | 观点评论/热点解读 | `vlog` | 日常 vlog/生活记录 |
| `commerce` | 带货/种草/开箱 | `performance` | 才艺/舞蹈/音乐 |
| `drama` | 剧情/段子/情景 | `game` | 游戏 |
| `tutorial` | 教程/技能教学 | `film_tv` | 影视解说/剪辑混剪 |
| `review` | 测评/探店 | `food` | 美食制作/吃播 |
| `emotion` | 情感/鸡汤/励志 | `pet` | 萌宠 |
| `interview` | 访谈/对话 | `sports` | 体育赛事 |
| `other` | 其他/无法归类 | | |

> 该枚举可按需增删；平台差异（如 B 站更偏知识/影视，抖音更偏剧情/带货）可在提示词里提示先验，但不写死。

---

## 5. 维度库（共用 + 类型专属）

每个维度 = `key` + `中文名` + `问什么`。类型 = 有序维度子集 + 专属 Focus。

**通用维度（多数类型都会有）**

| key | 名称 | 问什么 |
|---|---|---|
| `visual` | 画面内容 | 主体、场景、动作、画面风格 |
| `speech` | 语音/文案 | 口播要点、字幕、旁白（可与 L1 转录互补） |
| `structure` | 内容结构 | 开头钩子→展开→转折→结尾的段落划分 |
| `emotion` | 情绪与节奏 | 情绪基调、节奏快慢、情绪曲线 |
| `highlights` | 可复用点 | 金句、名场面、可二创的画面 |
| `scene_count` | 场景数 | 大致的场景/镜头切换数 |

**类型专属维度（示例）**

| 类型 | 追加维度 |
|---|---|
| `commerce` | `product`（商品与卖点）、`price_offer`（价格/优惠/规格）、`cta`（转化号召）、`trust`（信任背书） |
| `knowledge` / `tutorial` | `thesis`（核心论点/目标）、`steps`（步骤/论据）、`takeaway`（结论/要点） |
| `drama` | `characters`（人物关系）、`conflict`（冲突）、`twist`（反转/笑点） |
| `review` | `target`（测评对象）、`pros_cons`（优缺点）、`verdict`（结论/是否推荐） |
| `emotion` | `theme`（主题情绪）、`turning_point`（情绪转折）、`quotes`（共鸣金句） |
| `film_tv` | `source`（原片/素材来源）、`plot_summary`（剧情概述）、`editing_style`（剪辑风格/解说话术） |
| `news` | `event`（事件要素 5W）、`timeline`（时间线）、`stance`（立场/来源） |
| `performance` | `act_type`（才艺类型）、`highlights`、`tempo`（节奏/卡点） |
| `food` | `dish`（菜品）、`ingredients`（食材）、`process`（制作过程/口感） |
| `game` | `game_title`（游戏）、`moment`（高光操作/剧情）、`commentary`（解说风格） |
| `sports` | `match`（赛事/对阵）、`key_moment`（关键瞬间）、`result`（结果） |
| `interview` | `guest`（嘉宾）、`topics`（话题）、`notable_qa`（代表问答） |
| `vlog` | `location`（地点）、`activity`（活动线）、`mood`（生活氛围） |
| `pet` | `animals`（宠物）、`cute_moments`（萌点/名场面） |

> 维度是「问什么」的清单，不是死字段：模型看不到的维度填 `null`，**禁止编造**（写进约束）。

---

## 6. 提示词模板结构（单条模板长这样）

```
【角色】你是<平台>短视频内容分析师，专长<类型中文>类视频。
【任务】观看视频，输出该类型的内容理解结果。
【本类型关注点】<该类型的 Focus 段落：这类视频最该抓什么、最容易漏什么>
【维度定义】逐条列出本类型维度 key + 中文名 + 问什么。
【输出格式】严格输出如下 JSON（只输出 JSON，不要解释）：
{
  "type": "<枚举>",
  "summary": "<100字内整体概括>",
  "dimensions": { "<key>": <值>, ... },
  "timeline": [ {"t": <秒>, "event": "<发生了什么>"} ],   // 可选，长视频/剧情类更有用
  "confidence": 0~1
}
【约束】只依据视频与给定转录；不确定的字段填 null；不要编造品牌/人名/价格。
```

- **Focus 段落**是「类型区分」的灵魂：它比维度名更能改变模型注意力。
  例：`commerce` 的 Focus 是「重点捕捉商品外观、卖点话术、价格与优惠、下单引导、限时/稀缺感」；
  `knowledge` 的 Focus 是「重点提炼论点与论据链、关键数据、可复述的结论」。
- 维度是**建议而非硬模板**：允许模型在 `dimensions` 里补充它发现的额外要点（放 `extras`）。

---

## 7. 配置与存储

- **提示词与维度目录**：存 `system_setting`（KV，JSON）——
  `process_type_taxonomy`（枚举+说明）、`process_type_prompts`（类型→Focus+维度+schema）、
  `process_prompt_common`（通用维度）。有内置默认值，运营可在系统设置页改。
- **单条覆盖**（后续版本）：`prompt_template` 表支持自定义命名模板 + 绑定到类型/具体内容。
- **版本**：结果里记 `prompt_version`（如 `v1:commerce`），便于回溯与 A/B。
- **写侧校验**：改配置时校验 JSON 结构合法、枚举不重复、维度 key 合法，非法 → 422（沿用评论设置的做法）。

---

## 8. 数据落库

`video_understanding`（新增表）：
`asset_id`、`category`（类型枚举）、`category_confidence`、`category_reason`、
`dimensions`(JSON)、`summary`、`timeline`(JSON, 可空)、`model`、`prompt_version`、
`usage`(JSON：video_tokens/成本)、`status`、`error`、`created_at`。

`content_item` 增列：`auto_category`、`category_confidence`（便于筛选/看板，不必每次都 join）。

---

## 9. 实测验证（2026-10-05，qwen3.8-flash）

用真实标题+转录样本跑判类 Pass 0：

| 样本 | 判类结果 | 置信度 | 关键信号 |
|---|---|---|---|
| 「3个方法让手机多撑2年」（口播教方法） | `tutorial` ✅ | 0.98 | 「教你三招」「第一步关掉后台刷新」 |
| 「这条裙子我回购5次，评论区扣1链接」 | `commerce` ✅ | 0.99 | 「回购」「显瘦」「下单送腰带」 |
| 「当老板问我为什么迟到…沉默了」（段子） | `drama` ✅ | 0.92 | 情景对话、反转笑点 |
| 「iPhone17 Pro 深度测评」 | `review` ✅ | 0.98 | 「深度测评」「值不值得买」 |

→ **4/4 正确、耗时短、纯文本、成本可忽略**，证明「文本判类 → 类型专属提示词」两遍式可行。
（完整脚本与输出为 2026-10-05 本机临时验证，未入库。）

---

## 10. 成本

- Pass 0 判类：文本 ~300 in + ~200 out token，按 qwen3.8-flash ≈ 忽略级（< ¥0.001）。
- Pass 1 理解：一次视频调用（视频 token 计入输入，样例 5s≈2590、30s≈数千~1.5万）。
- 合计仍是**每条视频一条视频调用 + 一次文本调用**，与「一刀切」方案同量级。

---

## 11. 实现落点（供实施计划）

| 层 | 改动 |
|---|---|
| 模块 | `app/modules/vision.py`：视频理解 provider 适配器（qwen `video_url` / gemini `inlineData`）；`app/modules/classify.py`：判类 |
| 配置 | `app/core/process_settings.py`：门控 + 类型目录 + 类型提示词默认值 |
| 服务 | `app/services/process_gate.py`：热度门控 + 档位决策 + 选类型提示词 |
| 队列 | `extract_frames`、`understand_video` 两个 handler |
| 数据 | `video_understanding` 表、`asset_frame` 表、`content_item.auto_category`；Alembic `0003` |
| API | `GET/PUT /api/system/process-settings`；`GET /api/assets/{id}/understanding`；`POST /api/assets/{id}/process {tier, force_category?}`；`POST /api/assets/{id}/reclassify` |
| 前端 | 素材详情「分档加工」区：类型徽标 + 置信度 + 判类理由、维度卡片、帧墙、手动改类型/重跑、门控理由；设置页可编辑类型提示词 |
| MCP/Skills | 与 HTTP 对等：`understand_video`、`get_understanding`、`reclassify` |

---

## 12. 用户确认（2026-10-05）

| # | 问题 | 决定 |
|---|---|---|
| 1 | 类型目录（16 类） | **够用**，按现状；不做按平台拆分 |
| 2 | 类型专属维度（§5） | **按本文设计执行** |
| 3 | 提示词配置 | **内置默认 + 设置页可查看内容、可在线编辑调整** |
| 4 | 判类是否用封面图 | **由用户手动选择**（默认不用；作为可选开关，开启才额外调用图片模型） |

> 决策 3 的含义：类型提示词/维度目录存 `system_setting`（内置默认值），
> 设置页「视频理解」tab 以可编辑表单/JSON 暴露，保存时做结构校验（422）。
> 决策 4 的含义：判类默认只用文本（标题/作者/时长/转录）；
> 提供 `use_cover` 开关（全局默认 + 单条可覆盖），开启时把封面图一并送入分类器。


---

## 13. 实施计划

已按本设计写成可执行计划：**`docs/plans/2026-10-05-l3-tiered-processing-plan.md`**
（9 个任务，含 TDD 步骤与提交点；覆盖 L2 抽帧、L3 两遍式视频理解、动态门控、设置页可编辑、封面可选）。

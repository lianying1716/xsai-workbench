# 素材加工分档 · 视频理解实现调研

> 日期：2026-10-05
> 范围：`platform-api`（统一素材采集管理平台）的「素材加工等级」设计前置调研
> 结论定位：**先调研、先定方案，再动模型接入代码**（用户明确要求）
> 关联文档：`workbench-requirements-and-design-v1.md`（场景 A/9 系统设置、场景 A/5 素材库）、
> `2026-10-05-douyin-comment-enrichment-design.md`（已落地的「动态门控」范式，本文复用同一思路）

---

## 1. 背景与目标

用户提出：素材加工应分成等级，越高级越贵，按需触发：

| 档位 | 名称 | 加工内容 | 成本量级 | 现状 |
|---|---|---|---|---|
| L1 | 普通 | 音频转文字（ASR） | 低（本地 CPU/GPU 一次过） | 已实现 |
| L2 | 高级 | 抽帧 / 关键帧 / 场景切分 | 中（ffmpeg，几乎零模型成本） | 待建 |
| L3 | 最高级 | 多维度视频理解（画面+语音+结构+情绪…） | 高（多模态大模型，按 token/帧计费） | 待建 |

本文先回答一个问题：**L2/L3 到底怎么实现，有没有云端/开源模型能真正理解视频？**
结论分两层：
1. **云端现成可用（已逐个实测）**：nexai 的 `qwen3.8-flash`（首选）和 `gemini-3.8-flash`（备选）
   **真的支持视频输入理解**——详见 §3 与证据文件。**L3 不需要自托管、不需要等新模型。**
2. **开源可自托管**：Qwen3-VL / InternVideo / VideoLLaMA3 / SmolVLM2 等（§5），作为离线或省费升级项。
> 注意：初版本节曾基于文档标签误判“nexai 没有视频理解”，**已按实测更正**，见 §3 更正说明。

---

## 2. 平台现状盘点（调研的事实基础）

### 2.1 已具备的能力

- **下载**：`app/modules/media_download.py`（yt-dlp 安全封装），产出 `video_file` / `audio_file`。
- **L1 转录**：`app/modules/transcription.py`（faster-whisper），`handle_transcribe` 写 `transcript` 表
  （`segments` 带 `start/end/text`，`full_text`）。**已有时间轴，是 L2/L3 的天然输入。**
- **文本分析**：`app/modules/analysis.py` 走 OpenAI 兼容 `chat/completions`，写 `analysis_result`。
- **任务队列**：`job_queue`（PG `FOR UPDATE SKIP LOCKED`），handler 表：
  `download / transcribe / analyze / sync / crawl / fetch_comments`。
- **动态门控范式**：`app/services/comment_gate.py` + `app/core/comment_settings.py`
  （参数存 `system_setting` KV、有默认值、可在线改、写入侧做范围校验 -> 422）。
  **本文的「触发门槛智能化、不写死」直接复用这套范式。**
- **系统设置**：`GET/PUT /api/system/settings`（大模型 Base URL / Key / 模型名 / 代理）。
- **诊断**：`GET /api/system/diagnostics`（已逐项检查 Python / DB / …，可扩展到 ffmpeg / GPU / VLM）。

### 2.2 关键缺口

1. `media_asset` 只有 `download_status / transcribe_status / analyze_status` 三个状态，
   **没有「加工等级」这个概念**，也没有帧/场景/视频理解的存储表。
2. `JobQueue.job_type` 注释与实现只覆盖到 `fetch_comments`，需要新增 `extract_frames` / `understand_video` 之类。
3. 系统设置里只有「一个」LLM（文本用），**没有「视觉/视频模型」独立配置项**。

---

## 3. 星算 nexai 视频理解能力（实测更正 —— 关键发现）

> ⚠️ 本节推翻了初版基于文档标签的结论。**线上真实模型经过逐个实测**后发现：
> **nexai 已经具备可用的视频理解模型。**

初版只看了 `model-api-reference.md` 的能力标签（全是「图片输入」）就下了“没有视频理解”的结论，
但那是错的——**文档标签不可信**：`qwen3.8-flash` 连「图片输入」都没标，实际却支持视频输入。

### 3.1 实测方法

构造**时序可验证**的测试视频：前段红底白字 `KMX7`，后段蓝底黄字 `QZP2`。
只有真正读进视频的模型才能同时答对；纯文本模型会说“没有收到视频”。逐个探测线上全部对话模型。
（完整证据见 `evidence/2026-10-05-xsai-video-input-probe.md`。）

### 3.2 实测结论

| 模型 | 视频输入 | 正确协议/字段 | 备注 |
|---|---|---|---|
| **qwen3.8-flash** | ✅ **支持** | OpenAI 兼容 `POST /v1/chat/completions`，content 项 `{"type":"video_url","video_url":{"url":"data:video/mp4;base64,..." 或 "https://..."}}` | 4/4 通过；返回 `video_tokens`；支持 `response_format=json_object`；**单价最便宜** |
| **gemini-3.8-flash** | ✅ **支持** | **仅** Gemini 原生 `POST /v1beta/models/gemini-3.8-flash:generateContent`，part `{"inlineData":{"mimeType":"video/mp4","data":<base64>}}` | 5/5 通过；**OpenAI 兼容路径不支持视频，会静默幻觉** |
| qwen3.8-max | ✅ 支持 | 同 flash | 质量更高但输入 ¥12/M，是 flash 的 100 倍 |
| 其余 30+ 个（GPT / Claude / Grok / Kimi / GLM / MiniMax / MiMo / DeepSeek） | ❌ | — | 拒绝或看不到视频 |

**其他要点**
- **内联 base64 可用**：局域网/私网部署无法给上游公开 URL，实测 qwen3.8-flash 直接收
  `data:video/mp4;base64,...`，1.1MB / 6.8MB / 13.5MB 均成功（27MB 触发过一次 502，需控体积）。
- **抽帧回退可用**：qwen3.8-flash 同样能接多张图片帧，正确回答两帧内容 → 无视频输入时的保底方案。
- **文档标签与“视频模型”都会误导**：`omni`/`seedance*`/`minimax-h3` 是视频**生成**；
  能力标签里「图片输入」≠ 有/无视频能力。
- **计费**：qwen3.8-flash 输入 ¥0.113/M、输出 ¥0.382/M；样例 5s 视频 ≈ 2590 video_tokens，
  单条 1 分钟视频理解成本约 ¥0.002 级。

> **更正后的结论：L3 可以直接用 nexai 的 `qwen3.8-flash`（首选）或 `gemini-3.8-flash`（备选）做真正的视频理解，
> 不必自托管、也不必“等模型上线”。** 仍需按供应商写适配器，因为字段/协议不同。

---

## 4. 本机硬件现实（2026-10-05 实测）

```
nvidia-smi: 2 x NVIDIA GeForce RTX 3060 - 12288 MiB/卡, 驱动 595.84, CUDA 13.2
  GPU0: 10359 MiB 已用; GPU1: 10359 MiB 已用
  占用者: /www/wwwroot/local-llm/runtime/kvmem/.../llama-kvmem-server（每卡约 10GB）
CPU: 32 vCPU; RAM: 59 GiB; ffmpeg 6.1.1 已装
```

- **两张卡当前都被本地 LLM 服务占掉约 10GB，只剩约 2GB/卡**，装不下一个 7B+ 的视频 MLLM。
- 但**这一点已不再是阻碍**：nexai 的 `qwen3.8-flash` 可直接做视频理解（见 §3），推理在云端，本机零显存占用。
- 自托管视频 MLLM 仅作为「想完全离线/想省调用费」时的可选升级，不再是必需路径。
- ffmpeg 可用 -> **L2 抽帧今天就能零成本落地**。

---

## 5. 开源方案调研

### 5.1 路线 A：直接用「视频理解 MLLM」（端到端吃视频）

这类模型本身就能输入视频（多帧序列），一次前向完成时序理解。

| 项目 | 规模 | 能力 / 特点 | 许可 | 自托管门槛（实测口径） |
|---|---|---|---|---|
| **Qwen3-VL**（阿里，2025-09） | Dense 2B/4B/8B/32B，MoE 30B-A3B/235B-A22B | 原生交错上下文至 256K，**原生视频理解**，动态帧率采样（vLLM 默认 fps=2，可 `extra_body` 调；支持小时级长视频、时间戳对齐、帧级索引） | Apache-2.0（Qwen 系通常如此，落地前复核） | 8B BF16 约 17GB；**8B Q4/AWQ 约 6~9GB，可进单张 12GB**（Ollama `qwen3-vl:8b` 需 Ollama >= 0.12.7）；32B 需 24GB+；MoE 旗舰需 8x80GB |
| **InternVideo2.5**（OpenGVLab，2025-01） | 8B / 2B 级别 | 长视频 MLLM，**可记忆 6x 于原模型**，擅长目标跟踪/分割等密集视觉任务；MVBench / VideoMME 表现强 | 见仓库（各权重分别声明） | 8B 量级，单卡 24GB 更稳；12GB 需量化 |
| **InternVideo3**（2026-06） | 多模态基础模型 | **长时程视频理解 + 具身/agentic 推理**（工具调用、证据累积、验证），偏研究前沿 | 见仓库 | 偏重，先观望 |
| **VideoLLaMA3**（DAMO，2025-01） | 7B / 2B | 图像+视频统一，前沿开源视频理解，HuggingFace Transformers 原生支持 | Apache-2.0 | 7B BF16 需 24GB 更稳；量化可进 12GB |
| **SmolVLM2**（HuggingFace，2025-02） | 256M / 500M / 2.2B | **为端侧而生**，2.2B 约 5GB 显存即可跑视频；Video-MME 上以小博大 | Apache-2.0 | **最低门槛：单张 12GB 轻松，甚至 CPU/端侧** |

**路线 A 的取舍**：质量最高、一次调用完成时序理解。**好消息：nexai 已经能提供这条路**——
`qwen3.8-flash` / `gemini-3.8-flash` 就是云端视频理解模型（见 §3），无需自托管。
自托管（Qwen3-VL-8B Q4 / SmolVLM2）只在「完全离线」或「调用量极大想省费」时才值得。

### 5.2 路线 B：「抽帧 + 图像 VLM」组合管线（把视频拆成图片）

不依赖视频理解模型，用现有的图片输入模型逐帧/逐场景理解，再用文本模型汇总。

```
视频 -> ffmpeg 场景切分/关键帧 -> 每帧转 base64/URL -> 图像输入模型 -> 逐帧描述
                                                        |
                              结合 L1 转录文本 -> 文本模型汇总 -> 多维度理解结果
```

- **优点**：nexai 今天就能用（图片模型 + 文本模型，或直接 `qwen3.8-flash`）；
  显存零占用（推理在云端）；成本随帧数线性可控；**帧多帧少、要不要理解，完全由门控决定**。
- **定位**：在 §3 已确认有原生视频模型后，本路线降级为
  **(a) 抽帧产物本身的用途（缩略图/剪辑取图/检索）** 与 **(b) 视频输入不可用时的保底方案**。
- **缺点**：丢失精确时序（帧间运动/快慢节奏靠采样近似）；调用次数多（每帧一次或一批多图一次）；
  视频越长 token 越贵。
- **成熟先例**：开源 CLI **`byjlw/video-analyzer`**（Whisper 转录 + 关键帧喂 Llama 视觉模型，
  本地 Ollama / OpenAI 兼容 API 皆可）——**和我们已有的 transcribe + 图片模型能力几乎同构**，
  说明这条管线是被生产验证过的。
- 变体优化：一次请求塞多张图（多图交错上下文），摊薄调用开销；用 `Qwen3-VL-Embedding-8B`
  做帧级语义向量，支持「按画面检索素材」。

### 5.3 路线 C：现成开源「视频理解管线 / 平台」

| 项目 | 类型 | 说明 |
|---|---|---|
| **byjlw/video-analyzer** | CLI 管线 | Whisper + 关键帧 + 视觉 LLM，最贴合我们，**可直接借鉴其流程而非依赖它** |
| **NVIDIA NeMo Curator**（视频管线） | 数据工程框架 | 10s 切片 -> clip 向量 -> 自动打标/字幕，面向「大规模视频数据集治理」，重 |
| **PySceneDetect** | 场景检测库 | 内容感知切分 + 自适应检测，可调阈值，能直接 `ffmpeg` 导出关键帧；**L2 首选** |
| **AKS / GenS / AdaRD-Key** 等（CVPR/ACL 2025 论文+代码） | 关键帧采样算法 | 「该看哪几帧」的学术最优解，训练无关、可插拔；**L2 的进阶选项**，非一期必需 |

### 5.4 路线选择矩阵（更正后）

| 维度 | 路线 A1 nexai 云端视频模型（qwen3.8-flash / gemini-3.8-flash） | 路线 A2 自托管视频 MLLM | 路线 B 抽帧+图片VLM | 路线 C 现成管线 |
|---|---|---|---|---|
| 今天可用 | ✅ | ❌（本机无显存） | ✅ | ✅（需自建） |
| 时序理解 | ★★★★ | ★★★★ | ★★★ | ★★★ |
| 成本 | 按 token（极低） | 硬件一次性 | 按帧 token | 同 B |
| 部署复杂度 | **最低** | 高 | 中 | 高 |
| 与 nexai 契合 | **最优** | 一般 | 好 | 一般 |
| 结论 | **L3 首选** | 离线/省费的升级项 | L2 产物 + 保底 | 借鉴流程 |

---

## 6. 推荐方案

### 6.1 总原则

1. **分档触发，动态智能，绝不写死**——沿用 `comment_gate` 范式：阈值存 `system_setting`，
   有默认值、可在线调、写入侧校验。
2. **L2 独立于 L3**：抽帧本身不花钱、不依赖大模型，应**永远可以先做**（也顺带产出缩略图/封面）。
   是否**进一步**理解由门控决定。
3. **供应商可换**：图片/视频理解能力抽象成 provider 配置（Base URL / Key / 模型名 / 协议），
   nexai 只是默认预设之一。符合「开源、默认明确、可换供应商」红线。
4. **成本可见**：每档记录实际消耗（帧数、调用次数、估算 token），避免「偷偷花钱」。

### 6.2 推荐落地顺序

**第一步（L2，无模型成本，先做）**
- 新增 `extract_frames` job：`PySceneDetect` 或 ffmpeg `select`/`scdet` 场景切分 ->
  每场景取代表帧 -> 存 `asset_frame` 表（`timestamp, path, scene_index, is_keyframe`）+ 缩略图。
- 产出的帧既服务缩略图/剪辑取图/检索，也可作为视频输入不可用时的保底输入。

**第二步（L3，直接调 nexai 视频理解模型 —— 已实测可用）**
- 新增 `understand_video` job：
  - **主路径**：把素材视频按供应商适配器送进视觉模型——
    - 首选 `qwen3.8-flash`（OpenAI 兼容 + `video_url`，最便宜）
    - 备选 `gemini-3.8-flash`（Gemini 原生 `inlineData`）
  - **预处理**：局域网素材用**内联 base64** 上传（实测 1~13MB 可行）；
    过大视频先用 ffmpeg 降码率/降分辨率/切片（例如 360p、6~10fps、按需分段）再送。
  - **提示词**：要求返回**结构化 JSON**，覆盖多维：画面内容 / 语音文案 / 内容结构（钩子-转折-卖点）/
    情绪节奏 / 可复用金句与画面 / 场景数。可叠加 L1 转录文本一起送，效果更全。
- 结果写 `video_understanding` 表（JSON 多维 + model + usage/成本元数据）。

**第三步（可选升级）**
- 想完全离线/想省海量调用费：自托管 Qwen3-VL-8B（Q4）或 SmolVLM2 —— **仅换 provider，业务层不变**。
- 想增强「按画面找素材」：用 nexai 的 `Qwen3-VL-Embedding-8B` / `Reranker` 建帧级向量检索。

---

## 7. 待用户决策的开放问题

> 2026-10-05 用户已拍板：**第 1 点（门控）与第 2 点（超限先压缩/切片）按本文建议执行**；
> **第 3 点（多维度）要求“提示词按视频类型区分，不能一刀切”**。
> 对应的详细设计见 `2026-10-05-l3-type-aware-prompting-design.md`（两遍式：先判类，再选类型专属提示词）。

1. **L3 视频理解的默认触发门槛**：用哪套热度指标（播放/点赞/评论/新颖度）与阈值？
   建议先给保守默认、系统设置页可调、并支持手动强制。
2. **单条视频送模型的体积策略**：是否接受「超过约 10~15MB 先 ffmpeg 压缩/切片再送」？
   （可用更高质量换更慢/更贵的多段调用，也可只送压缩版。）
3. **多维度的「维度」清单**：默认用（画面/语音/内容结构/情绪节奏/金句/场景数），
   是否还要「带货要素识别」「品牌 logo」「人物识别」「违规/风险元素」等？
4. **L2 抽帧是否需要**：既然有原生视频模型，抽帧是否仍作为「缩略图 + 剪辑取图 + 保底」保留？
   （建议保留，成本极低。）

---

## 8. 参考来源

- nexai 模型目录（本地生成）：`/www/wwwroot/nexai/docs/reference/model-api-reference.md`
- nexai 品牌图标规范：`/www/wwwroot/nexai/docs/reference/ai-brand-icons.md`
- Qwen3-VL 技术报告：https://arxiv.org/abs/2511.21631 ；仓库 https://github.com/QwenLM/Qwen3-VL
- Qwen3-VL 视频理解/vLLM 采样：https://deepwiki.com/QwenLM/Qwen3-VL/5.4-video-understanding ；
  https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html
- InternVideo2.5：https://github.com/OpenGVLab/InternVideo/tree/main/InternVideo2.5 ；
  https://arxiv.org/abs/2501.12386
- InternVideo3：https://github.com/OpenGVLab/InternVideo/tree/main/InternVideo3
- VideoLLaMA3：https://github.com/damo-nlp-sg/videollama3 ；https://arxiv.org/abs/2501.13106
- SmolVLM2：https://huggingface.co/blog/smolvlm2
- video-analyzer（Whisper+关键帧+视觉LLM）：https://github.com/byjlw/video-analyzer
- PySceneDetect：https://github.com/Breakthrough/PySceneDetect
- 关键帧采样研究：AKS https://github.com/ncTimTang/AKS ；GenS https://arxiv.org/abs/2503.09146
- 本机硬件：`/www/wwwroot/local-llm/hardware.md` + 2026-10-05 `nvidia-smi` 实测
- **xsai5.xyz 视频输入逐模型实测证据：`evidence/2026-10-05-xsai-video-input-probe.md`**

> 说明：VRAM/许可等数字来自公开资料与实测，量级可信，**具体以落地前的复核为准**。

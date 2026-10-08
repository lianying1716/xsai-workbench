# xsai5.xyz 视频输入能力实测证据（2026-10-05）

> 方法：构造一段**时序可验证**的测试视频——前 1.5s 红底白字 `KMX7`，后 1.5s 蓝底黄字 `QZP2`。
> 只有真正“看了视频”的模型才能同时答对两段的颜色与文字；纯文本模型会否认收到视频。
> 端点：`https://api.xsai5.xyz/v1`。测试脚本见同目录说明（本机 /tmp 临时脚本，未入库）。

## 测试视频

`seq.mp4`：0–1.5s 红底白字 KMX7 → 1.5–3s 蓝底黄字 QZP2（320x240, 9.5KB）。
另用真实的 `flower.mp4`（延时开花，5s）与 `out60.mp4`（30s，360p/6fps，156KB）做鲁棒性与结构化验证。

## 结果总表

| 模型 | 视频输入 | 可用协议/字段 | 实测结论 |
|---|---|---|---|
| **qwen3.8-flash** | **是** | OpenAI 兼容 `POST /v1/chat/completions`，content 项 `{"type":"video_url","video_url":{"url": <"data:video/mp4;base64,…" 或 "https://…">}}` | **4/4 通过**；正确说出 KMX7/QZP2；返回 `usage.prompt_tokens_details.video_tokens`；`response_format=json_object` 可用 |
| **gemini-3.8-flash** | **是** | **仅** Gemini 原生 `POST /v1beta/models/gemini-3.8-flash:generateContent`，part `{"inlineData":{"mimeType":"video/mp4","data":<base64>}}` | **5/5 通过**；同样能答 KMX7/QZP2。**OpenAI 兼容路径不支持视频**（见下） |
| gemini-3.8-flash（OpenAI 兼容路径） | 否（会幻觉） | `video_url` / `file_data` | `video_url` 被静默忽略 → 模型编造内容；`file_data` 报 `downloaded content is not an image` |
| qwen3.8-max | 是（同 flash 字段） | 同 qwen3.8-flash | 能描述公开视频；但 ¥12/M 输入，成本是 flash 的 100 倍，且本次有超时/502 |
| gpt-5.5 / gpt-5.6-sol / gpt-6-sol / gpt-6.1-sol | 否 | — | `image_url` 传视频 → 502 “image format illegal / invalid base64” |
| claude-opus-5 / claude-opus-4-8 / claude-sonnet-5 | 否 | — | “I don't have access to any video” |
| grok-4.6 / grok-4.7 | 否 | — | 502 `Invalid base64` |
| kimi-k3 / glm-5.3 / glm-5.3-flash / MiniMax-M3 / mimo-v2.5* / deepseek-v4.1-flash(-free) | 否 | — | 拒绝或看不到视频 |

## 关键细节

- **字段名是陷阱**：Qwen 认 `video_url`；Gemini（OpenAI 兼容层）认 `image_url` 但**不真读视频**（会幻觉）。
  → 视频理解必须按“供应商适配器”分别处理，不能用一套通用 payload。
- **内联 base64 可用**（局域网/私网平台的关键）：qwen3.8-flash 对 `data:video/mp4;base64,…` 实测通过，
  1.1MB / 6.8MB / 13.5MB 均成功；27MB 触发过一次 502（网关体积/超时上限，需降码率或分段）。
- **抽帧回退可用**：qwen3.8-flash 也能接多张 `image_url` 帧，正确回答两帧的 KMX7/QZP2 → 无视频输入时的保底方案。
- **能力标签不可信**：`model-api-reference.md` 对 `qwen3.8-flash` 只标了「流式/工具调用」，**连图片输入都没标**，
  但它实际支持视频输入。→ 结论：以**实测/运行时探测**为准，不要照抄文档标签。
- **文档里的 “视频模型” 不是理解**：`omni`/`seedance*`/`minimax-h3` 是视频**生成**。

## 计费（来自 nexai 模型目录）

| 模型 | 输入 | 输出 | 视频 token 计费 |
|---|---|---|---|
| qwen3.8-flash | ¥0.113 / 百万 | ¥0.382 / 百万 | 计入输入（`video_tokens`） |
| gemini-3.8-flash | ¥0.75 / 百万 | ¥3.75 / 百万 | 计入输入 |
| qwen3.8-max | ¥12 / 百万 | ¥36 / 百万 | 计入输入 |

样例：5s 视频约 2590 video_tokens；30s/360p/6fps 约数千~1.5万 video_tokens。
按 qwen3.8-flash 计价，**单条 1 分钟视频理解约 ¥0.002 级**（视频 token 数受上游抽帧策略影响，以实际返回为准）。

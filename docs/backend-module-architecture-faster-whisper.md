# faster-whisper 后端架构审查与本地转录模块设计

## 1. 文档目标

本文档基于对 `/www/wwwroot/xsai-workbench/faster-whisper` 的源码审查，整理其现有能力、运行流程、模型加载、音频解码、VAD、批处理、测试、Docker、许可与部署限制，并定义其并入统一平台时的后端模块设计、数据模型、统一 API、前端配置页面和实施路线。

本文档只覆盖 `faster-whisper`。它在统一平台中的定位是“本地视频/音频转录引擎适配层”，负责把已下载视频或音频资产转成结构化文字、分段、词级时间戳和导出文档，再交给后续分析模块处理。

## 2. 总体结论

- `faster-whisper` 是 Python 推理库，不是后端服务；当前没有数据库、任务队列、Web API、权限、前端或文件资产管理。
- 核心实现基于 `CTranslate2`，通过 `WhisperModel` 和 `BatchedInferencePipeline` 完成转录，支持 CPU/GPU、量化、VAD、词级时间戳、热词、语言检测、翻译任务和批处理。
- 当前项目适合直接作为统一平台 `transcription` 模块的底层适配库；不能把其源码结构直接暴露给其他业务模块。
- 统一平台必须自建模型管理、任务队列、运行日志、转录结果落库、NAS 路径管理、导出文件、硬件诊断、失败重试和前端配置。
- 跨平台部署可支持 Linux/macOS/Windows 单机；CPU 是最稳妥基线，NVIDIA GPU 需要严格匹配 CUDA/cuDNN/CTranslate2 版本。
- 项目源码许可证是 MIT，适合并入；但 Whisper 模型、CTranslate2、PyAV、Silero VAD ONNX、Hugging Face 模型仓库各自的许可与模型使用条款需要单独归档。

## 3. 现有项目结构

关键目录：

```text
faster-whisper/
  faster_whisper/
    transcribe.py              # WhisperModel、BatchedInferencePipeline、转录主流程
    audio.py                   # PyAV 解码、重采样、立体声拆分
    vad.py                     # Silero VAD ONNX、语音片段检测、时间戳还原
    feature_extractor.py       # log-Mel 特征提取
    tokenizer.py               # Whisper tokenizer 包装、多语言、词切分
    utils.py                   # 模型下载、模型清单、时间格式化
    assets/silero_vad_v6.onnx  # 内置 VAD 模型
  tests/                       # 单元测试与音频样本
  benchmark/                   # 速度、显存、内存、WER 基准脚本
  docker/                      # NVIDIA CUDA 示例镜像
  setup.py                     # Python 包定义
  setup.cfg                    # black/isort/flake8 配置
```

公开入口在 `faster_whisper/__init__.py`：

```text
WhisperModel
BatchedInferencePipeline
decode_audio
download_model
available_models
format_timestamp
```

并入时应只依赖这些稳定入口，避免让业务代码直接调用内部函数。

## 4. 依赖、版本与许可

当前本地版本：

- 包版本：`1.2.1`
- Git 远端：`https://github.com/SYSTRAN/faster-whisper`
- 当前提交：`ed9a06cd8`
- Python：`>=3.9`
- 源码许可证：MIT

核心依赖：

```text
ctranslate2>=4.0,<5
huggingface_hub>=0.23
tokenizers>=0.13,<1
onnxruntime>=1.14,<2
av>=11
tqdm
```

转换模型额外依赖：

```text
transformers[torch]>=4.23
```

代码风格与 CI：

- `black==23.*`
- `isort==5.*`
- `flake8==6.*`
- `pytest==7.*`
- CI 使用 Python 3.9，执行 `black --check .`、`isort --check-only .`、`flake8 .`、`pytest -v tests/`。

并入要求：

- 统一平台主项目继续使用自己的锁版本文件，`faster-whisper` 作为第三方依赖或 vendor 适配来源。
- 必须建立 `third_party_licenses/` 归档：`faster-whisper` MIT、CTranslate2、PyAV、ONNX Runtime、tokenizers、Hugging Face Hub、Silero VAD、所选 Whisper 模型。
- 如果未来开源，模型文件不应默认随仓库发布，只记录下载来源、模型 ID、版本、校验值和许可链接。

## 5. 运行与模型加载机制

`WhisperModel` 初始化支持：

- `model_size_or_path`：模型尺寸名、本地 CTranslate2 模型目录、Hugging Face 模型 ID。
- `device`：`cpu`、`cuda`、`auto`。
- `device_index`：单 GPU 编号或多个 GPU 编号列表。
- `compute_type`：`default`、`float16`、`int8`、`int8_float16` 等 CTranslate2 支持类型。
- `cpu_threads`：CPU 线程数，非 0 时覆盖 `OMP_NUM_THREADS`。
- `num_workers`：多线程调用时的推理 worker 数，提升吞吐但增加内存占用。
- `download_root`：模型下载目录。
- `local_files_only`：只使用本地缓存，适合离线 NAS/单机部署。
- `revision`、`use_auth_token`：Hugging Face 模型版本和私有模型 token。

内置模型别名包括：

```text
tiny, tiny.en, base, base.en, small, small.en,
medium, medium.en,
large-v1, large-v2, large-v3, large,
distil-small.en, distil-medium.en, distil-large-v2, distil-large-v3, distil-large-v3.5,
large-v3-turbo, turbo
```

模型下载使用 `huggingface_hub.snapshot_download`，只下载：

```text
config.json
preprocessor_config.json
model.bin
tokenizer.json
vocabulary.*
```

统一平台设计要求：

- 模型缓存目录必须可配置，例如 `/mnt/nas/xsai/models/faster-whisper`、`D:\xsai\models` 或 Windows UNC 路径。
- 前端必须支持“预下载模型”“校验模型”“仅本地模式”“删除模型缓存”“查看模型占用空间”。
- 生产转录任务不能在任务运行中隐式下载大模型；应先通过模型管理页完成下载和校验。
- 私有模型 token 必须加密保存，日志中不能输出。

## 6. 音频解码与预处理

`audio.py` 使用 PyAV 解码音频：

- 输入支持文件路径或 file-like 对象。
- 默认重采样为 16 kHz。
- 默认输出 mono `float32` numpy 数组。
- `split_stereo=True` 时返回左右声道，可用于手工双声道分离转录。
- 会忽略部分无效音频帧。
- PyAV 包内携带 FFmpeg 库，转录解码本身不要求系统安装 FFmpeg。

需要注意：

- 统一平台下载的视频文件可能仍需要 FFmpeg 做视频抽音频、容器修复、分片合并、格式转换和媒体信息探测；不能因为 PyAV 可解码就删除全局 FFmpeg 依赖。
- 长视频不应一次性把所有中间文件写到 NAS 再处理；建议本地临时目录抽音频，完成后只保留需要的转录文档和可选音频副本。
- 所有输入文件必须来自统一 `media_asset`，不能让外部 API 任意传服务器绝对路径。

## 7. 转录能力审查

### 7.1 普通转录

`WhisperModel.transcribe()` 是基础转录入口，返回：

```text
segments: Iterable[Segment]
info: TranscriptionInfo
```

重要行为：

- `segments` 是 generator，只有迭代时才真正开始转录。
- 默认 `vad_filter=False`。
- 默认 `without_timestamps=False`，即保留时间戳相关生成逻辑。
- 默认 30 秒窗口处理，窗口内通过 token 时间戳切分 segment。
- 支持温度 fallback：默认 `[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]`。
- 通过 `compression_ratio_threshold`、`log_prob_threshold`、`no_speech_threshold` 控制重复、低置信、静音跳过。

统一平台必须在 worker 内完整消费 generator，并持续写入进度与分段结果；不能把 generator 返回给 API 层。

### 7.2 批处理转录

`BatchedInferencePipeline.transcribe()` 是批量推理入口：

- 默认 `vad_filter=True`。
- 默认 `batch_size=8`。
- 默认 `without_timestamps=True`。
- 对长音频必须有 VAD 或传入 `clip_timestamps`；否则超过 chunk 长度会报错。
- 会先通过 VAD 切出语音片段，再合并为不超过 `chunk_length` 的批处理输入。
- 完成后可把 VAD 后的时间戳恢复到原始音频时间线。

统一平台建议：

- 第一阶段默认使用 `BatchedInferencePipeline`，适合大量视频转录。
- 默认启用 VAD，避免长静音浪费时间。
- `word_timestamps` 默认关闭，用户在 Profile 中开启；开启后速度和内存开销更高。
- 对播客、访谈、长视频提供“高准确度 Profile”：`beam_size=5`、`word_timestamps=True`、较保守 VAD。
- 对批量热点视频提供“快速 Profile”：`turbo` 或 `distil-large-v3`、`batch_size` 可调、词级时间戳关闭。

### 7.3 语言检测与多语言

能力：

- 未传 `language` 时，多语言模型会自动检测语言。
- 英文专用模型只支持 `en`，传其他语言会回退到 `en`。
- `multilingual=True` 时可对每个 segment 做语言检测。
- `language_detection_threshold` 和 `language_detection_segments` 控制检测阈值与检测窗口数量。

平台要求：

- 前端提供 `自动检测`、`中文 zh`、`英文 en`、`日文 ja` 等常用语言选择。
- 保存 `language`、`language_probability`、`all_language_probs`。
- 中文、日文、泰文、粤语等无空格语言的词级切分来自 tokenizer Unicode 分割，不应承诺等同自然语言分词。

### 7.4 热词、提示词和翻译

支持项：

- `hotwords`：提示模型关注特定词，例如品牌名、账号名、技术名词。
- `initial_prompt`：首个窗口提示。
- `prefix`：首个窗口前缀。
- `task`：`transcribe` 或 `translate`。

平台要求：

- 每个转录 Profile 支持热词列表。
- 每个账号、博主或关键词任务可继承自己的热词，例如产品名、人名、专业术语。
- 翻译任务先作为高级选项，不作为第一期核心承诺；后续分析模块可以使用外部 LLM API 做更可控的翻译和摘要。

### 7.5 词级时间戳

`word_timestamps=True` 时：

- 通过 cross-attention 与动态时间规整生成词级时间戳。
- 输出 `Word(start, end, word, probability)`。
- 会对中英文标点做前后合并。
- 有 hallucination silence 处理逻辑，可跳过疑似幻觉前后的静音。

限制：

- 词级时间戳不是强对齐模型，不等同 WhisperX 那类二次对齐。
- 中文等无空格语言按 token/Unicode 可解码边界切分，不能直接当作精确词语。
- 开启后会增加推理时间和内存。

统一平台第一期建议保存 segment 级时间戳为必选，word 级时间戳为可选。

## 8. VAD 审查

`vad.py` 内置 Silero VAD ONNX：

- 模型文件：`faster_whisper/assets/silero_vad_v6.onnx`
- Runtime：`onnxruntime`
- Provider：`CPUExecutionProvider`
- `get_vad_model()` 使用 `lru_cache` 缓存模型实例。
- `get_speech_timestamps()` 返回语音片段样本范围。
- `collect_chunks()` 把语音片段合并为最大时长内的 chunk。
- `SpeechTimestampsMap` 把 VAD 后时间戳还原到原始音频时间线。

`VadOptions` 配置：

```text
threshold
neg_threshold
min_speech_duration_ms
max_speech_duration_s
min_silence_duration_ms
speech_pad_ms
min_silence_at_max_speech
use_max_poss_sil_at_max_speech
```

默认差异：

- 普通 `WhisperModel.transcribe(vad_filter=True)` 默认 `min_silence_duration_ms=2000`。
- 批处理 `BatchedInferencePipeline.transcribe()` 默认会把 `min_silence_duration_ms` 调整为 `160`，并把 `max_speech_duration_s` 设为 chunk 长度。

并入要求：

- 前端 Profile 必须能配置 VAD 开关、静音阈值、最小静音、语音 padding。
- 日志必须记录 VAD 移除了多少音频、保留了哪些片段。
- 长视频默认启用 VAD，但允许“音乐/混剪/非连续人声”场景关闭或放宽 VAD。

## 9. Docker 与跨平台部署

项目自带 Docker 示例：

```text
FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04
RUN pip3 install faster-whisper
CMD ["python3", "infer.py"]
```

GPU 关键约束：

- 最新 `ctranslate2` 需要 CUDA 12 和 cuDNN 9。
- CUDA 11/cuDNN 8 需要降级 `ctranslate2==3.24.0`。
- CUDA 12/cuDNN 8 需要降级 `ctranslate2==4.4.0`。
- Docker GPU 需要宿主机安装 NVIDIA 驱动和 NVIDIA Container Toolkit。

跨平台建议：

- Linux：首选 Docker Compose；有 NVIDIA GPU 时提供 GPU compose profile。
- macOS：第一期按 CPU 推理支持，不承诺 Apple Metal 加速。
- Windows：支持本机 Python/CPU、Windows 路径、UNC 路径；GPU 需单独验证 CUDA/cuDNN/PATH，Docker GPU 更建议走 WSL2/NVIDIA 方案。
- 所有平台默认提供 CPU `int8` Profile 作为可启动基线。

## 10. 测试与基准审查

现有测试覆盖：

- 支持语言列表。
- JFK 示例转录、语言检测、词级时间戳。
- 批处理转录。
- 空音频。
- prefix。
- VAD 参数。
- 立体声拆分转录。
- 多语言转录。
- hotwords。
- 普通转录与批处理转录签名一致性。
- 时间戳单调性。
- 手工 `clip_timestamps`。
- 模型下载到指定目录和 cache。
- suppressed tokens 与 Unicode 切分。

Benchmark 覆盖：

- `speed_benchmark.py`：单次推理速度。
- `memory_benchmark.py`：CPU 内存和 GPU 显存/功耗。
- `wer_benchmark.py`：LibriSpeech WER。
- `evaluate_yt_commons.py`：YouTube Commons ASR 评估。

统一平台验收测试应新增：

- 使用本地小音频样本验证 CPU `tiny` 模型可转录。
- 使用配置的模型缓存目录，不访问网络。
- 生成 `txt`、`srt`、`vtt`、`json` 导出。
- 失败任务可重试，取消任务能停止 worker 并释放模型引用。
- NAS 路径、Windows 路径、Docker volume 映射路径均能写入。
- 转录完成后自动触发分析任务。

## 11. 统一数据模型设计

建议新增表：

```text
transcription_model
  id, provider, model_key, display_name, source_repo, local_path,
  revision, size_bytes, language_scope, supports_translation,
  supports_word_timestamps, license_note, checksum, status

transcription_profile
  id, name, model_id, device, device_index, compute_type,
  cpu_threads, num_workers, batch_enabled, batch_size,
  language, task, beam_size, best_of, temperature,
  vad_enabled, vad_options_json, word_timestamps,
  hotwords, initial_prompt, max_new_tokens, chunk_length,
  is_default, created_at, updated_at

transcription_job
  id, media_asset_id, content_item_id, profile_id, status,
  priority, source_module, requested_by, progress,
  duration_seconds, duration_after_vad_seconds,
  language, language_probability, error_code, error_message,
  started_at, finished_at, created_at

transcript_document
  id, job_id, media_asset_id, language, full_text,
  text_path, json_path, srt_path, vtt_path,
  segment_count, word_count, created_at

transcript_segment
  id, document_id, segment_index, start_seconds, end_seconds,
  text, avg_logprob, compression_ratio, no_speech_prob,
  temperature, token_ids_json

transcript_word
  id, segment_id, word_index, start_seconds, end_seconds,
  word, probability

transcription_log
  id, job_id, level, message, event_type, payload_json, created_at

hardware_profile
  id, host_id, os, python_version, ctranslate2_version,
  cuda_available, cuda_version, cudnn_version,
  gpu_name, gpu_memory_total, cpu_threads, memory_total,
  last_checked_at
```

与统一资产库关系：

- 输入来自 `media_asset`，类型可能是 `video`、`audio`。
- 输出仍登记为 `media_asset` 或 `transcript_document`，路径指向 NAS/本地存储。
- `content_item` 通过 `content_item_id` 关联转录文档，后续分析模块读取 `transcript_document`。

## 12. 后端模块抽离设计

建议统一平台新增：

```text
platform-api/app/modules/transcription/
  schemas.py
  models.py
  service.py
  worker.py
  queue.py
  profile_service.py
  model_registry.py
  model_cache.py
  faster_whisper_adapter.py
  media_preprocessor.py
  result_writer.py
  exporters.py
  diagnostics.py
  hardware.py
  cleanup.py
```

模块职责：

- `model_registry.py`：维护支持模型清单、模型来源、能力、许可备注。
- `model_cache.py`：下载、校验、删除、离线模式、本地路径扫描。
- `profile_service.py`：管理转录 Profile，限制非法组合。
- `media_preprocessor.py`：从视频资产抽取音频、检查时长、采样率、格式、临时文件。
- `faster_whisper_adapter.py`：唯一直接调用 `WhisperModel` 和 `BatchedInferencePipeline` 的地方。
- `queue.py`：任务入队、优先级、并发限制、取消标记。
- `worker.py`：加载模型、执行转录、消费 generator、更新进度、捕获异常。
- `result_writer.py`：写入 `transcript_document`、segment、word、日志和资产索引。
- `exporters.py`：生成 `txt`、`json`、`srt`、`vtt`，后续可加 `lrc`。
- `diagnostics.py`：检测模型目录、PyAV、ONNX Runtime、CTranslate2、CUDA、NAS 写入。
- `hardware.py`：采集 CPU/GPU/内存信息，辅助前端推荐 Profile。
- `cleanup.py`：清理临时音频、失败残留、过期导出文件。

统一适配接口：

```text
TranscriptionEngine
  load_model(profile)
  transcribe(input_audio, profile, progress_callback)
  unload_model(model_key)
  detect_language(input_audio, profile)

TranscriptionJobService
  create_job(media_asset_id, profile_id)
  start_job(job_id)
  cancel_job(job_id)
  retry_job(job_id)
  list_jobs(filters)

TranscriptResultWriter
  write_info(job_id, info)
  write_segment(job_id, segment)
  write_word(segment_id, word)
  write_artifacts(document_id)
```

## 13. 统一 API 草案

```text
GET    /api/transcription/models
POST   /api/transcription/models/download
POST   /api/transcription/models/scan-local
POST   /api/transcription/models/{id}/verify
DELETE /api/transcription/models/{id}

GET    /api/transcription/profiles
POST   /api/transcription/profiles
GET    /api/transcription/profiles/{id}
PUT    /api/transcription/profiles/{id}
DELETE /api/transcription/profiles/{id}
POST   /api/transcription/profiles/{id}/set-default

POST   /api/transcription/jobs
GET    /api/transcription/jobs
GET    /api/transcription/jobs/{id}
POST   /api/transcription/jobs/{id}/cancel
POST   /api/transcription/jobs/{id}/retry

GET    /api/transcription/jobs/{id}/segments
GET    /api/transcription/jobs/{id}/words
GET    /api/transcription/jobs/{id}/logs
GET    /api/transcription/documents/{id}
GET    /api/transcription/documents/{id}/export/{format}

GET    /api/transcription/diagnostics
POST   /api/transcription/diagnostics/run
GET    /api/transcription/events
```

外部 skill/API 应只开放高层能力：

```text
POST /api/skills/transcription/jobs
GET  /api/skills/transcription/jobs/{id}
GET  /api/skills/transcription/documents/{id}
```

外部调用只传 `media_asset_id` 或受控上传文件 ID，不允许传任意服务器路径。

## 14. 必须进入统一前端的页面

### 14.1 转录任务队列

- 显示等待中、运行中、成功、失败、已取消。
- 展示来源平台、视频标题、账号/博主、模型、Profile、进度、耗时。
- 支持取消、重试、提高优先级、批量重跑。

### 14.2 转录详情页

- 左侧视频/音频播放器，右侧 transcript。
- segment 按时间线显示，可点击跳转播放位置。
- 展示语言、置信度、VAD 后时长、模型、耗时、错误日志。
- 支持导出 `txt/json/srt/vtt`。

### 14.3 模型管理页

- 模型列表：tiny/base/small/medium/large/distil/turbo。
- 显示本地状态、大小、路径、来源、revision、校验状态。
- 支持下载、暂停、删除、扫描本地目录、仅本地模式。
- 模型缓存目录支持本机和 NAS。

### 14.4 转录 Profile 页

- 设备：CPU/GPU、GPU 编号、compute type、CPU 线程数、worker 数。
- 推理：beam、temperature、batch size、chunk length、语言、任务类型。
- VAD：启停、阈值、最小静音、语音 padding。
- 文本：热词、初始提示词、词级时间戳。
- 保存为默认 Profile 或按来源平台指定 Profile。

### 14.5 硬件与诊断页

- 操作系统、Python、CTranslate2、PyAV、ONNX Runtime。
- CUDA/cuDNN、GPU 名称、显存、驱动可用性。
- 模型目录可写性、NAS 写入测试、临时目录空间。
- 给出建议：CPU int8、GPU float16、降低 batch size 等。

### 14.6 存储与清理页

- 转录文档保存路径模板。
- 临时音频目录。
- 是否保留抽取后的音频。
- 失败任务残留清理、过期导出清理、模型缓存空间查看。

### 14.7 分析联动配置页

- 转录完成后是否自动进入分析。
- 分析类型：摘要、关键词、人物/品牌、选题、爆款指标、时间轴。
- 失败时是否重试、是否通知前端工作台。

## 15. 与其他模块的关系

统一数据流：

```text
Douyin/Bilibili/MediaCrawler/yt-dlp
  -> media_asset(video/audio)
  -> transcription_job
  -> faster_whisper_adapter
  -> transcript_document + transcript_segment + transcript_word
  -> analysis_job
  -> dashboard / external skill API
```

边界：

- 抖音/B 站模块负责下载和账号同步。
- `MediaCrawler` 负责公开内容抓取和部分媒体下载。
- `yt-dlp` 后续可作为通用下载器补充。
- `faster-whisper` 只负责本地 ASR，不负责下载视频、不负责账号、不负责内容分析。
- 分析模块读取转录结果，不直接调用 `faster-whisper`。

## 16. 风险与处理

- 模型下载风险：Hugging Face 访问可能失败，必须支持预下载和离线模式。
- GPU 版本风险：CUDA/cuDNN/CTranslate2 不匹配会导致启动失败，必须在诊断页提前发现。
- 内存风险：large 模型、batch、word timestamps 会显著增加 RAM/VRAM，必须有并发限制。
- generator 风险：转录只有迭代时执行，worker 必须负责完整消费和异常捕获。
- 长视频风险：一次性加载超长音频会占用内存，后续需要分片预处理和任务切分。
- VAD 风险：强 VAD 可能删除音乐、低声、多人讨论中的有效内容，Profile 必须可调。
- 词级时间戳风险：中文和无空格语言并非真实分词，前端文案不能误导。
- 说话人分离风险：当前库没有 diarization，只能双声道拆分；真正说话人识别需后续引入 WhisperX/pyannote/NeMo 等。
- 许可证风险：源码 MIT 不等于模型和内置 ONNX 权利全部自动满足开源发布，需要逐项归档。
- 路径风险：NAS、Docker volume、Windows UNC、macOS/Linux 挂载路径必须经过统一存储模块校验。
- 任务取消风险：CTranslate2 推理过程不一定能即时中断，需要用 worker 进程级取消或分段检查取消标记。

## 17. 实施顺序

### P0：依赖与合规

- 建立第三方依赖和模型许可清单。
- 确定默认模型：建议 `small` 或 `turbo` 作为推荐，`tiny` 作为诊断模型。
- 建立模型缓存目录和离线模式配置。

### P1：最小可用转录

- 新增 `transcription` 模块、Profile、Job、Document、Segment 表。
- CPU `tiny` 本地转录跑通。
- 支持从 `media_asset` 创建任务、写入 segment、导出 txt/json/srt/vtt。

### P2：批处理与 NAS

- 接入 `BatchedInferencePipeline`。
- 支持 VAD、batch size、热词、语言选择。
- 支持本地/NAS 保存路径和临时目录清理。

### P3：前端工作台

- 完成任务队列、模型管理、Profile、详情页、硬件诊断。
- 支持任务日志流和失败重试。

### P4：自动联动分析

- 抖音/B 站/MediaCrawler 下载完成后自动创建转录任务。
- 转录完成后自动创建分析任务。
- 数据看板可按账号、博主、关键词、平台查看转录覆盖率。

### P5：性能与高级能力

- GPU Profile、显存检测、并发限流。
- 长视频分片、断点续跑。
- 可选说话人分离、强制对齐、字幕编辑器。

## 18. 最终架构设计

最终形态：

```text
Unified Workbench Frontend
  -> platform-api (FastAPI)
      -> media_asset module
      -> transcription module
          -> model registry/cache
          -> profile service
          -> job queue
          -> worker
          -> faster-whisper adapter
          -> result writer
          -> exporters
          -> diagnostics
      -> analysis module
      -> external skill API
  -> PostgreSQL
  -> Local/NAS Storage
      -> original videos
      -> temp audio
      -> transcript txt/json/srt/vtt
      -> model cache
  -> CTranslate2 / faster-whisper
  -> Optional NVIDIA CUDA Runtime
```

用户只看到统一工作台。`faster-whisper` 不作为独立应用存在，也不暴露原始 Python API；它成为 `platform-api` 内部可替换的 ASR 引擎。后续如果要替换为 OpenAI API、whisper.cpp 或其他本地模型，只需要新增 `TranscriptionEngine` 实现，不影响任务、结果、前端和外部 skill/API。

## 19. 本轮复盘

本轮已完成：

- 审查 `faster-whisper` 目录结构、包入口、依赖、许可证、CI、Docker。
- 审查 `WhisperModel`、`BatchedInferencePipeline`、音频解码、VAD、模型下载、tokenizer、feature extractor。
- 审查测试与 benchmark，提炼统一平台需要继承的验收点。
- 确认该项目应作为本地转录引擎适配库，而不是独立后端服务。
- 复核本地提交 `ed9a06cd8`、包版本 `1.2.1`、Python `>=3.9`、MIT 许可和公开入口 `WhisperModel/BatchedInferencePipeline/decode_audio/download_model`。
- 确认 PyAV 可解码音频但不替代平台级 FFmpeg；统一平台仍需要 FFmpeg 处理视频抽音频、容器修复、合并和媒体信息。
- 确认普通转录默认 `vad_filter=False`，批处理默认 `vad_filter=True`、`batch_size=8`、`without_timestamps=True`；前端 Profile 必须明确展示这些差异。

最终落地要求：

- 先完成 `media_asset` 统一表、NAS 路径模板和转录任务表，再接入 `faster_whisper_adapter`。
- 模型下载、离线模式、硬件诊断、任务取消、导出文件必须由统一平台实现。
- `faster-whisper` 不暴露原始 Python API 给前端或外部 skill，只通过受控任务队列调用。

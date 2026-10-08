# yt-dlp 后端架构审查与通用媒体下载模块设计

## 1. 文档目标

本文档基于对 `/www/wwwroot/xsai-workbench/yt-dlp` 的源码审查，整理其现有能力、运行流程、核心模块、下载与后处理机制、Cookie/代理/网络能力、测试、打包、许可与安全风险，并定义其并入统一平台时的后端模块设计、数据模型、统一 API、前端配置页面和实施路线。

本文档只覆盖 `yt-dlp`。它在统一平台中的定位是“通用媒体 URL 解析与下载模块”，用于处理任意公开视频/音频 URL、非重点平台的下载、微信文章内嵌媒体下载、专用平台模块失败时的兜底下载，以及未来外部 skill 的通用媒体下载能力。

## 2. 总体结论

- `yt-dlp` 是成熟的命令行音视频下载器，同时提供可嵌入的 Python API：`yt_dlp.YoutubeDL`。
- 当前仓库是完整上游项目，不是薄封装；包含 CLI、API、约 1022 个 extractor 文件、下载器、后处理器、网络层、Cookie 管理、插件、缓存、自更新、测试和 PyInstaller 打包链。
- 统一平台不应把 `yt-dlp` CLI 直接暴露给前端用户。应在 `platform-api` 中封装 `media_download` 模块，只开放受控的下载 Profile、Cookie Profile、网络 Profile、存储 Profile 和后处理 Profile。
- `yt-dlp` 不能替代 `dysync.net`、`bili-sync` 和 `MediaCrawler`：它擅长“已知 URL 的解析/下载”，不负责我们的关键词任务编排、账号关注列表同步、热门排序抓取和长期资产库。
- `yt-dlp` 下载得到的视频、音频、字幕、缩略图和 infojson 应进入统一 `media_asset` 体系，并触发后续本地 `faster-whisper` 转录与分析。
- 源码许可证是 Unlicense，适合复用；但 PyInstaller 发布二进制包含 GPLv3+ 组件，若未来开源/分发应优先依赖源码或 PyPI wheel，不直接并入上游打包产物。

## 3. 仓库基线

本地审查信息：

```text
路径: /www/wwwroot/xsai-workbench/yt-dlp
远端: https://github.com/yt-dlp/yt-dlp
当前本地提交: 5faffa999
version.py RELEASE_GIT_HEAD: 04d6974f502bbdfaed72c624344f262e30ad9708
版本: 2026.03.17
Python: >=3.10
包名: yt-dlp
入口: yt-dlp = "yt_dlp:main"
许可证: Unlicense
```

本轮复盘确认该仓库仍是完整上游项目：`yt_dlp/extractor` 顶层 extractor 文件 1022 个，`test/test_*.py` 文件 33 个。统一平台需要建立版本锁定和升级验证流程，不能随意自动更新。

## 4. 现有项目结构

关键目录：

```text
yt-dlp/
  yt_dlp/
    __init__.py              # CLI 入口、参数解析、CLI -> YoutubeDL params 映射
    YoutubeDL.py             # 核心编排器：提取、格式选择、下载、后处理、归档
    options.py               # CLI 参数定义
    extractor/               # 站点 extractor，约 1022 个文件
    downloader/              # HTTP、HLS、DASH、RTMP、WebSocket、外部下载器
    postprocessor/           # FFmpeg、字幕、缩略图、元数据、SponsorBlock、Exec
    networking/              # urllib/requests/websockets/curl_cffi 请求层
    cookies.py               # Cookie 文件和浏览器 Cookie 读取
    cache.py                 # 本地缓存
    plugins.py               # extractor/postprocessor 插件加载
    update.py                # 自更新逻辑
    jsinterp.py              # JS 解释与站点签名相关能力
  test/                      # 33 个 test_*.py
  bundle/                    # PyInstaller 与 Docker 打包脚本
  devscripts/                # 文档、版本、lazy extractor、工具脚本
  pyproject.toml             # 包、依赖、hatch、ruff、autopep8、pytest
  README.md                  # CLI、依赖、嵌入 API、插件说明
  THIRD_PARTY_LICENSES.txt   # 二进制打包第三方许可证
```

并入时应只依赖 `yt_dlp.YoutubeDL`、`yt_dlp.postprocessor` 中必要类和稳定公开行为，避免让业务代码直接耦合 CLI 参数解析和自更新/插件机制。

## 5. 构建、测试与开发命令

上游常用命令：

```text
python -m yt_dlp URL
python -m pytest -Werror
make test
make offlinetest
make codetest
make lazy-extractors
python -m bundle.pyinstaller
```

`pyproject.toml` 中的工具：

- 静态检查：`ruff check .`
- 格式检查：`autopep8 --diff .`
- 测试：`pytest`、`pytest-rerunfailures`、`pytest-randomly`、`pytest-xdist`
- Hatch 环境：`hatch-static-analysis`、`hatch-test`

统一平台不需要复用上游 Makefile 和 PyInstaller 构建链。后续只需要为 `media_download` 适配层建立我们自己的单元测试、集成测试和少量真实 URL 诊断测试。

## 6. 依赖与许可

`yt-dlp` 默认依赖为空，能力通过可选依赖增强。主要可选依赖：

```text
brotli / brotlicffi      # Brotli 内容编码
certifi                 # CA 证书
mutagen                 # 媒体元数据、缩略图嵌入
pycryptodomex           # HLS AES-128 等解密
requests / urllib3      # HTTP 请求增强
websockets              # WebSocket 下载
yt-dlp-ejs              # YouTube 完整支持相关 JS 组件
curl-cffi               # TLS/浏览器指纹模拟
secretstorage           # Linux 浏览器 Cookie keyring
deno                    # JS runtime，可用于 YouTube 相关能力
```

外部二进制依赖：

- `ffmpeg`、`ffprobe`：合并音视频、转码、抽音频、嵌字幕、嵌元数据、修复容器等核心后处理需要。
- `aria2c`、`curl`、`wget`、`httpie`、`axel`：可选外部下载器。
- `rtmpdump`、`mplayer`、`mpv`：部分旧协议可选。
- JavaScript runtime：Deno/Node/Bun/QuickJS，YouTube 复杂场景需要。

许可判断：

- 源码、sdist、PyPI wheel 为 Unlicense。
- PyInstaller 打包二进制包含 GPLv3+ 代码，不能在未来开源分发中无脑打包进我们的项目。
- `mutagen`、`AtomicParsley`、`rtmpdump`、`mpv/mplayer` 等带 GPL 系许可证；是否随镜像分发需要单独归档。
- `ffmpeg` 许可证取决于构建参数。平台 Docker 镜像若内置 ffmpeg，必须记录来源和 license 配置。

并入建议：以 Python 依赖形式使用 `yt-dlp` 源码/wheel；Docker 镜像中单独安装 `ffmpeg`，并在 `third_party_licenses/` 记录 `yt-dlp`、`yt-dlp-ejs`、`curl-cffi`、`ffmpeg`、`mutagen` 等来源。

## 7. 核心入口与嵌入方式

官方推荐从 Python 嵌入：

```python
import yt_dlp

ydl_opts = {
    "quiet": True,
    "noprogress": True,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)
    info = ydl.sanitize_info(info)
```

下载时：

```python
ydl_opts = {
    "paths": {"home": storage_root, "temp": temp_root},
    "outtmpl": {"default": "%(extractor_key)s/%(id)s/%(title).120S.%(ext)s"},
    "writeinfojson": True,
    "writethumbnail": True,
    "writesubtitles": True,
    "progress_hooks": [progress_hook],
    "postprocessor_hooks": [postprocess_hook],
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
```

统一平台必须注意：

- 不解析普通 stdout；使用 `logger`、`progress_hooks`、`postprocessor_hooks`、`extract_info()` 返回值和生成的文件。
- `extract_info()` 返回值不保证天然 JSON 可序列化，必须用 `YoutubeDL.sanitize_info()`。
- API 默认 `ignoreerrors=False`，CLI 默认行为与 API 有差异，适配层要显式设置。
- 不让前端用户直接填写任意 CLI 参数；CLI 参数只能由后端受控映射。

## 8. 核心运行流程

典型流程：

```text
URL
  -> YoutubeDL.extract_info()
  -> 选择第一个 suitable extractor
  -> extractor.extract() 返回 info_dict / playlist / url_transparent
  -> process_ie_result()
  -> process_video_result()
  -> 清洗 metadata、formats、subtitles、thumbnails
  -> 格式排序与格式选择
  -> process_info()
  -> prepare_filename() 生成临时路径和最终路径
  -> 写 description / subtitles / thumbnails / info.json / link
  -> get_suitable_downloader()
  -> HTTP/HLS/DASH/FFmpeg/External downloader 下载
  -> FFmpeg merge/fixup/postprocessors
  -> MoveFilesAfterDownload
  -> record_download_archive()
  -> progress/postprocessor hooks
  -> 返回 sanitized info + artifacts
```

播放列表流程会递归处理 `entries`，支持 `playlist_items`、随机/反序、懒加载、失败计数、下载归档和 playlist 级 metadata。统一平台第一期应避免默认下载超大播放列表，必须设置最大条数、最大总大小和可取消任务。

## 9. YoutubeDL 编排器审查

`yt_dlp/YoutubeDL.py` 是核心编排器，主要职责：

- 管理 `params` 配置字典。
- 注册默认 extractor 和 plugin extractor。
- 加载 Cookie、代理、HTTP headers、JS runtime、remote components。
- 输出模板校验与文件名生成。
- 调度 extractor，处理 `video`、`playlist`、`multi_video`、`url`、`url_transparent`。
- 清洗 info dict，填充通用字段和数值字段。
- 处理字幕、缩略图、格式排序、格式选择。
- 调用 downloader 下载文件。
- 调用 postprocessor 处理合并、转码、元数据、缩略图、字幕、章节等。
- 写入 download archive。
- 通过 hook 汇报下载和后处理进度。

重要参数类别：

- 账号认证：`username`、`password`、`twofactor`、`netrc`、`cookiefile`、`cookiesfrombrowser`。
- 下载选择：`format`、`format_sort`、`playlist_items`、`match_filter`、`min/max_filesize`、`date`、`min/max_views`。
- 存储：`paths`、`outtmpl`、`restrictfilenames`、`windowsfilenames`、`trim_file_name`、`overwrites`、`continuedl`、`download_archive`。
- 网络：`proxy`、`socket_timeout`、`source_address`、`impersonate`、`nocheckcertificate`、`geo_bypass`。
- 下载器：`ratelimit`、`retries`、`fragment_retries`、`concurrent_fragment_downloads`、`http_chunk_size`。
- 媒体副产物：`writeinfojson`、`writethumbnail`、`writesubtitles`、`writeautomaticsub`、`getcomments`。
- 后处理：`postprocessors`、`ffmpeg_location`、`merge_output_format`、`extractaudio`、`remuxvideo`、`recodevideo`、`embedsubtitles`、`embedthumbnail`、`sponsorblock_*`。

统一平台应将这些参数收敛成 Profile，而不是暴露原始参数。

## 10. Extractor 模块审查

`yt_dlp/extractor/common.py` 定义 `InfoExtractor` 协议。单视频结果必须有：

- `id`
- `title`
- `url` 或 `formats`

常见附加字段：

- 作者：`uploader`、`uploader_id`、`channel`、`channel_id`
- 时间：`timestamp`、`upload_date`、`duration`
- 互动：`view_count`、`like_count`、`comment_count`
- 媒体：`formats`、`thumbnails`、`subtitles`、`automatic_captions`
- 直播：`is_live`、`live_status`、`was_live`
- DRM：`has_drm`
- HTTP：`http_headers`、`cookies`、`impersonate`

平台相关观察：

- `bilibili.py` 支持视频、番剧、课程、空间投稿、收藏夹、稍后再看、播放列表、动态、直播、搜索等，但部分能力需要 `SESSDATA` 登录 Cookie。
- `tiktok.py` 包含 `TikTokIE`、用户、标签、音乐、合集、直播，以及 `DouyinIE`。Douyin 部分明确提示需要新鲜 Cookie，适合作为兜底，不应替代 `dysync.net`。
- `generic.py` 可解析网页中嵌入的视频、OpenGraph、播放器 iframe 等，适合微信文章/网页里的嵌入媒体发现。
- `youtube.py` 复杂度很高，依赖 JS runtime、PO token、不同 client、Cookie、Visitor Data 等。若开启 YouTube 下载，需要单独做诊断和版本更新流程。

统一平台策略：

- 第一阶段允许 `Generic`、`Bilibili`、`Youtube`、`Twitter/X`、`TikTok/Douyin` 等常见 extractor，但必须可配置启停。
- 抖音/哔哩哔哩账号同步仍以专用模块为主，`yt-dlp` 只做已知 URL 下载和兜底。
- 不承诺所有 extractor 长期稳定；任务失败应记录 extractor 名称、版本、错误码和上游建议。

## 11. 下载器模块审查

下载器入口是 `yt_dlp/downloader/__init__.py` 的 `get_suitable_downloader()`。它根据 `protocol`、`requested_formats`、是否 stdout、是否分片、是否直播、外部下载器配置选择具体下载器。

主要下载器：

```text
HttpFD                 # 普通 HTTP/HTTPS/FTP 下载
HlsFD                  # 原生 m3u8/HLS 分片下载
DashSegmentsFD         # DASH 分片下载
FFmpegFD               # ffmpeg 下载、合并、流处理
RtmpFD / RtspFD        # RTMP/RTSP
WebSocketFragmentFD    # WebSocket fragment -> ffmpeg stdin
YoutubeLiveChatFD      # YouTube live chat/replay
ExternalFD             # aria2c/curl/wget/httpie/axel/ffmpeg 等外部下载器
```

关键能力：

- 普通 HTTP 支持断点续传、Range、`.part` 临时文件、限速、重试、最小/最大文件大小、HTTP chunk。
- HLS/DASH 分片支持 `.ytdl` 状态文件、断点恢复、跳过坏分片、并发分片、AES-128 HLS 解密、广告片段跳过、外部下载器接管。
- 多格式合并时会先下载音频和视频分轨，再通过 `FFmpegMergerPP` 合并。
- 直播 HLS/DASH 更依赖 FFmpeg，原生 HLS 对部分直播能力有限。
- 外部下载器会生成命令行并可能写临时 cookies 文件。

统一平台默认建议：

- 默认使用内置下载器 + FFmpeg，不默认启用外部下载器。
- `concurrent_fragment_downloads` 初始为 3 或 4，不要让用户随意设很高。
- 所有临时文件写入本地 temp root，完成后移动到 NAS/root，降低 NAS 上碎片写入和中断风险。
- 每个任务必须支持取消；对外部下载器和 FFmpeg 需要 worker 进程级取消。

## 12. 后处理模块审查

`yt_dlp/postprocessor` 提供以下核心能力：

```text
FFmpegMerger              # 合并音视频
FFmpegExtractAudio        # 抽音频
FFmpegVideoRemuxer        # 不重编码换封装
FFmpegVideoConvertor      # 转码
FFmpegEmbedSubtitle       # 嵌字幕
FFmpegMetadata            # 写 metadata / chapters / infojson
FFmpegSplitChapters       # 分章节切分
FFmpegSubtitlesConvertor  # 字幕格式转换
FFmpegThumbnailsConvertor # 缩略图转换
EmbedThumbnail            # 嵌入封面
ModifyChapters            # 删除/调整章节
SponsorBlock              # 查询并标记/移除 YouTube SponsorBlock 片段
XAttrMetadata             # 写扩展属性
Exec                      # 下载后执行任意命令
MoveFilesAfterDownload    # 移动临时文件到最终目录
```

统一平台第一期建议开放：

- 合并音视频。
- 保存 `info.json`。
- 保存缩略图。
- 保存字幕/自动字幕。
- 可选抽音频给转录模块。
- 可选 remux 到 `mp4/mkv`。

暂不开放或默认关闭：

- `ExecPP`：即使上游已限制模板转换，本质仍可执行 shell 命令，平台不应开放给前端和外部 skill。
- `SponsorBlock remove`：会修改原视频内容，第一期最多保存标记，不默认裁剪。
- `XAttrMetadata`：跨平台差异大，NAS 上意义有限。
- 任意 `postprocessor_args`：会变成后门级命令注入入口。

## 13. 网络层审查

`yt_dlp/networking` 提供统一 `RequestDirector`，按偏好选择可用请求处理器：

- `urllib`：基础请求处理器。
- `requests`：增强代理、连接复用、HTTPS 代理。
- `websockets`：WebSocket 支持。
- `curl_cffi`：浏览器 TLS/HTTP 指纹模拟。

支持能力：

- 全局 headers。
- Cookie jar。
- 全局代理和系统代理。
- SOCKS/HTTP/HTTPS 代理，具体能力取决于 handler。
- 客户端证书。
- SSL 校验开关。
- source address、IPv4/IPv6 强制。
- `impersonate` 浏览器模拟，例如 chrome/safari/firefox/edge。
- `file://` 默认禁用。

统一平台策略：

- 网络 Profile 中提供代理、超时、重试、限速、浏览器模拟开关。
- `nocheckcertificate` 只做高级选项，并在日志中标记。
- `enable_file_urls` 永远关闭，除非后续做内部安全审计。
- 默认不继承宿主机系统代理，除非管理员明确开启，避免部署环境隐式影响抓取。
- 记录每个任务使用的代理、handler、impersonate target 和失败原因。

## 14. Cookie 与登录态审查

`cookies.py` 支持：

- Netscape 格式 Cookie 文件。
- `--cookies-from-browser` 从浏览器读取 Cookie。
- 浏览器支持：Chrome、Chromium、Brave、Edge、Opera、Vivaldi、Whale、Firefox、Safari。
- Linux Chromium keyring 支持：需要 `secretstorage` 或相应 keyring。
- Firefox container 支持。
- Windows/macOS/Linux Chromium Cookie 解密逻辑。
- 合并多个 CookieJar。

关键风险：

- 浏览器 Cookie 读取依赖宿主机用户目录、桌面环境、keyring、浏览器 profile，Docker 内通常不可直接访问。
- Cookie 属于高敏感凭证，日志、infojson 和错误输出都要脱敏。
- 上游也明确避免把未限定域的 Cookie 直接传给所有域；平台要继续保持域限制。
- 外部下载器可能把 Cookie 写入临时文件，临时文件必须在任务结束后删除。

统一平台设计：

- 建立 `download_cookie_profile`，保存 Cookie 文件内容或加密后的 Cookie Jar。
- 支持手动导入 Netscape Cookie 文件、浏览器自动读取、账号模块生成的 Cookie 复用。
- 浏览器读取只在本机非 Docker 或明确挂载 profile 时启用；Docker 部署首选扫码/浏览器自动登录模块导入 Cookie。
- Cookie Profile 必须绑定平台/域名范围，不允许通用 Cookie 被任意 URL 使用。

## 15. 存储与路径机制

`yt-dlp` 原生支持：

- `paths.home`：最终输出根目录。
- `paths.temp`：临时文件目录。
- 各类型目录：subtitle、thumbnail、description、infojson、chapter、pl_infojson 等。
- `outtmpl.default`：主文件名模板。
- `outtmpl` 按类型覆盖，例如字幕和缩略图放不同目录。
- Windows 文件名安全：`windowsfilenames`。
- ASCII 限制：`restrictfilenames`。
- 文件名长度裁剪：`trim_file_name`。
- `.part`、`.ytdl`、download archive。

统一平台映射：

```text
storage_root/{source_platform}/{creator_slug}/{publish_date}/{content_id}/
  video.{ext}
  audio.{ext}
  subtitles/{lang}.{ext}
  thumbnails/{id}.{ext}
  metadata.info.json
  transcript.md
  transcript.json
  analysis.json
```

必须支持：

- Linux/macOS 路径，例如 `/mnt/nas/xsai-content`。
- Windows 盘符，例如 `D:\xsai-content`。
- Windows UNC，例如 `\\NAS\xsai-content`。
- 本地 temp 目录与 NAS 最终目录分离。
- 路径可用性、写入权限、剩余容量、长路径和非法字符诊断。

禁止：

- 外部 API 直接传服务器绝对输出路径。
- URL 或标题决定上级目录跳转。
- 使用不受控的 `outtmpl` 原样来自用户输入。

## 16. 插件、自更新与缓存

插件系统：

- 支持 `yt_dlp_plugins.extractor` 和 `yt_dlp_plugins.postprocessor`。
- 默认从用户配置目录、系统配置目录、可执行文件目录、`PYTHONPATH`、zip/egg/whl 加载。
- 插件可以覆盖内置 extractor。

自更新：

- `update.py` 支持 stable/nightly/master channel 和 GitHub release 查询。
- 对不同二进制 variant 有不同更新策略。
- 从 source 运行时提示不能自更新。

缓存：

- 默认 `${XDG_CACHE_HOME}/yt-dlp`。
- 保存站点签名、client ids 等 JSON。
- 可禁用或清理。

统一平台策略：

- 默认设置 `YTDLP_NO_PLUGINS=1`，并将 `plugin_dirs=[]`。
- 不开放自更新；版本升级由平台依赖锁和发布流程完成。
- 缓存目录放到平台配置目录，例如 `{data_root}/cache/yt-dlp`，可在前端诊断页清理。
- 如果未来支持自定义 extractor，必须做管理员上传、代码审查、版本签名和隔离执行。

## 17. 测试覆盖审查

上游 `test/` 覆盖面较广：

- `test_YoutubeDL.py`：格式选择、筛选、playlist、输出模板等核心逻辑。
- `test_download.py`：动态生成真实 extractor 下载测试。
- `test_downloader_http.py`、`test_downloader_external.py`：下载器和外部下载器命令。
- `test_postprocessors.py`：Exec 安全、FFmpeg 缩略图转换、SponsorBlock/章节处理等。
- `test_cookies.py`、`test_YoutubeDLCookieJar.py`：Cookie 解析和浏览器 Cookie 解密。
- `test_networking.py`、`test_http_proxy.py`、`test_socks.py`、`test_websockets.py`：网络层。
- `test_plugins.py`：插件加载、覆盖、zip 插件、禁用目录。
- `test_config.py`、`test_update.py`、`test_subtitles.py`、`test_overwrites.py`。

统一平台需要新增的测试：

- `YtDlpAdapter` 参数白名单与默认 Profile。
- URL probe 返回 formats/subtitles/thumbnails 的标准化。
- 下载进度 hook 写入任务状态。
- 后处理 hook 写入日志。
- Cookie Profile 脱敏和域名限制。
- NAS 路径映射和非法路径拦截。
- 任务取消、失败重试、断点恢复。
- 外部 skill API 权限和限流。

## 18. 与现有模块的边界

### 18.1 与 dysync.net

`dysync.net` 负责抖音账号、关注/收藏/合集等账号内同步能力。`yt-dlp` 只适合：

- 已知抖音 URL 兜底下载。
- 非账号同步来源的单条公开视频下载。
- 专用模块失败时作为备选解析器。

不应使用 `yt-dlp` 重建抖音关注列表同步。

### 18.2 与 bili-sync

`bili-sync` 仍是 B 站账号收藏夹、UP 主选择、同步任务的主模块。`yt-dlp` 可用于：

- B 站单 URL 下载。
- 公开收藏夹/播放列表的临时导入。
- `bili-sync` 已得到 URL 后由统一下载模块执行媒体下载。

对于私密收藏夹、稍后再看、账号内状态，仍由账号同步模块管理 Cookie 和同步范围。

### 18.3 与 MediaCrawler

`MediaCrawler` 负责关键词、热门内容、搜索结果和公共内容数据抓取。`yt-dlp` 负责把抓取结果中的视频 URL 变成实际媒体文件。两者关系：

```text
MediaCrawler 抓取内容元数据
  -> content_item / media_candidate
  -> media_download job
  -> media_asset
```

### 18.4 与 wechat-article-exporter

微信文章模块负责文章 HTML、阅读量、评论、资源归档。`yt-dlp` 可用于：

- 解析文章内嵌视频 URL。
- 下载 `mpvideo`、第三方播放器或网页嵌入媒体。
- 把下载结果归入文章关联 `media_asset`。

### 18.5 与 faster-whisper

`yt-dlp` 产生视频/音频资产，`faster-whisper` 负责转录。建议流程：

```text
media_download 完成
  -> media_asset(video/audio)
  -> optional audio_extract
  -> transcription_job
  -> transcript + analysis
```

抽音频可由 `yt-dlp` 后处理或统一媒体处理模块执行，但任务状态必须归入统一流水线。

## 19. 统一平台模块设计

建议新增模块：

```text
platform-api/app/modules/media_download/
  router.py                 # FastAPI 路由
  schemas.py                # 请求/响应模型
  models.py                 # SQLAlchemy ORM
  service.py                # 业务编排
  ytdlp_adapter.py          # 封装 yt_dlp.YoutubeDL
  profile_service.py        # 下载/网络/存储/后处理 Profile
  format_probe.py           # download=False 探测 formats/subs/thumbs
  cookie_service.py         # Cookie Profile 解密、导入、域名限制
  storage_mapper.py         # NAS/本地路径映射、模板生成
  progress_sink.py          # hooks -> 任务进度/日志
  postprocess_policy.py     # 后处理白名单
  network_policy.py         # 代理、headers、impersonate、安全策略
  archive_service.py        # 下载归档、去重
  diagnostics.py            # ffmpeg、js runtime、依赖、网络、路径诊断
  worker.py                 # 下载 worker
  queue.py                  # 任务入队、取消、重试、并发控制
  safety.py                 # URL、路径、命令、插件、文件大小限制
```

设计原则：

- `media_download` 不直接保存业务平台账号密码，只引用统一 `platform_account` 或 `credential_profile`。
- 所有 `ydl_opts` 由后端生成，前端不能提交任意 dict。
- 任务结果必须写入统一资产库，而不是只写本地文件。
- 任务可取消、可重试、可查看日志、可定位产物。
- 下载和后处理在 worker 中执行，API 请求只负责入队和查询状态。

## 20. Profile 抽象

### 20.1 Download Profile

面向用户的下载配置：

```text
name
format_policy          # best, best_720p, audio_only, custom_safe
max_resolution
preferred_container    # mp4, mkv, webm
write_infojson
write_thumbnail
write_subtitles
write_auto_subtitles
subtitle_languages
extract_audio
audio_format
merge_output_format
max_filesize
playlist_limit
retry_count
fragment_retry_count
concurrent_fragments
rate_limit
```

### 20.2 Storage Profile

```text
name
storage_root
temp_root
path_template
windows_safe_filenames
trim_filename_length
overwrite_policy
keep_part_files
download_archive_enabled
```

### 20.3 Cookie Profile

```text
name
platform
allowed_domains
source_type             # manual_file, browser, account_module
encrypted_cookie_blob
browser_name
browser_profile
expires_at
last_validated_at
status
```

### 20.4 Network Profile

```text
name
proxy_url
use_system_proxy
socket_timeout
impersonate_target
force_ipv4_or_ipv6
geo_proxy
geo_bypass_country
retry_sleep_policy
custom_headers_safe
```

### 20.5 Postprocess Profile

```text
name
enable_ffmpeg_merge
remux_video
extract_audio_for_transcription
embed_subtitles
embed_thumbnail
write_metadata
sponsorblock_mark_only
disabled_unsafe_exec
```

## 21. 数据模型建议

第一批 PostgreSQL 表：

```text
media_download_profile
  id, name, format_policy, max_resolution, preferred_container,
  write_infojson, write_thumbnail, write_subtitles, write_auto_subtitles,
  subtitle_languages, extract_audio, audio_format, merge_output_format,
  max_filesize, playlist_limit, retries, fragment_retries,
  concurrent_fragments, rate_limit, created_at, updated_at

media_storage_profile
  id, name, storage_root, temp_root, path_template,
  windows_safe_filenames, trim_filename_length, overwrite_policy,
  archive_enabled, created_at, updated_at

media_network_profile
  id, name, proxy_url_encrypted, use_system_proxy, socket_timeout,
  impersonate_target, geo_policy, rate_limit, headers_json_encrypted,
  created_at, updated_at

media_cookie_profile
  id, name, platform, allowed_domains, source_type,
  encrypted_cookie_blob, browser_name, browser_profile,
  expires_at, last_validated_at, status, created_at, updated_at

media_download_job
  id, source_type, source_ref_id, url, title_hint,
  profile_id, storage_profile_id, network_profile_id, cookie_profile_id,
  status, priority, requested_by, scheduled_at, started_at, finished_at,
  error_code, error_message, created_at, updated_at

media_download_run
  id, job_id, ytdlp_version, extractor_key, extractor,
  effective_opts_json, started_at, finished_at, status,
  progress_percent, downloaded_bytes, total_bytes,
  speed, eta, retry_count, error_code, error_message

media_download_item
  id, job_id, parent_item_id, url, webpage_url,
  extractor_key, platform, content_id, title, creator_name,
  duration, upload_time, view_count, like_count, comment_count,
  is_playlist, playlist_id, playlist_index, raw_info_json

media_download_format
  id, item_id, format_id, ext, protocol, width, height, fps,
  vcodec, acodec, tbr, filesize, filesize_approx, has_drm,
  language, raw_format_json

media_download_artifact
  id, job_id, item_id, artifact_type, path, relative_path,
  file_ext, mime_type, size_bytes, sha256, storage_profile_id,
  created_at

media_download_subtitle
  id, item_id, language, ext, is_auto, url, path, status

media_download_thumbnail
  id, item_id, thumbnail_id, width, height, url, path, status

media_download_archive
  id, extractor_key, content_id, archive_key, first_job_id,
  last_seen_at, created_at

media_download_log
  id, job_id, run_id, level, message, event_type, payload_json, created_at
```

`media_download_artifact` 中的视频和音频最终应同步写入统一 `media_asset`，不要形成两个互不相干的资产系统。

## 22. 统一 API 设计

管理 API：

```text
POST   /api/media-download/probe
GET    /api/media-download/probe/{probe_id}

POST   /api/media-download/jobs
GET    /api/media-download/jobs
GET    /api/media-download/jobs/{job_id}
POST   /api/media-download/jobs/{job_id}/cancel
POST   /api/media-download/jobs/{job_id}/retry
DELETE /api/media-download/jobs/{job_id}

GET    /api/media-download/jobs/{job_id}/logs
GET    /api/media-download/jobs/{job_id}/artifacts

GET    /api/media-download/profiles
POST   /api/media-download/profiles
PUT    /api/media-download/profiles/{id}

GET    /api/media-download/storage-profiles
POST   /api/media-download/storage-profiles
POST   /api/media-download/storage-profiles/{id}/diagnose

GET    /api/media-download/network-profiles
POST   /api/media-download/network-profiles

GET    /api/media-download/cookie-profiles
POST   /api/media-download/cookie-profiles/import
POST   /api/media-download/cookie-profiles/{id}/validate

GET    /api/media-download/diagnostics
POST   /api/media-download/diagnostics/run
```

外部 skill/API：

```text
POST /api/skills/media-download/probe-url
POST /api/skills/media-download/download-url
GET  /api/skills/media-download/jobs/{job_id}
GET  /api/skills/media-download/artifacts/{artifact_id}
```

Skill API 必须：

- 使用 API Key。
- 记录调用日志。
- 限制可用 Profile。
- 禁止提交任意输出路径。
- 默认禁用 Cookie Profile，除非管理员明确授权。

## 23. 前端配置页面

统一前端必须增加以下页面或功能区：

### 23.1 下载队列

- 任务列表：状态、平台、标题、URL、进度、速度、剩余时间、大小、创建来源。
- 操作：暂停/取消、重试、查看日志、打开资产、重新转录。
- 过滤：状态、平台、来源模块、日期、失败原因。

### 23.2 URL 探测与新建下载

- 输入一个或多个 URL。
- 后端 `probe` 后展示标题、平台、作者、时长、缩略图、可用格式、字幕、是否 DRM、是否需要 Cookie。
- 选择 Download Profile、Storage Profile、Network Profile、Cookie Profile。
- 支持播放列表预览和条目选择，默认限制数量。

### 23.3 下载 Profile

- 清晰选项：最佳质量、最高 1080p、最高 720p、仅音频、保存字幕、保存缩略图、保存 infojson。
- 高级选项：格式排序、容器、并发分片、限速、最大文件大小、重试次数。
- 不显示原始 `-f`、`-S` 等 CLI 语法，除非管理员高级模式。

### 23.4 存储 Profile

- 根目录、临时目录、路径模板、文件名规则、覆盖策略。
- 路径诊断：是否存在、可写、剩余空间、NAS 延迟、长路径风险。
- 展示最终目录预览。

### 23.5 Cookie / 登录态

- Cookie Profile 列表：平台、域名范围、来源、状态、过期时间、最近验证。
- 导入 Netscape Cookie 文件。
- 从浏览器读取 Cookie 的引导和限制说明。
- 与账号模块关联：B 站/抖音/YouTube 等。

### 23.6 网络与代理

- 代理地址、超时、重试、限速、浏览器模拟、IPv4/IPv6。
- 诊断目标 URL 连通性。
- 显示当前可用 request handler：urllib、requests、websockets、curl_cffi。

### 23.7 任务详情

- 基础信息、提取器、格式选择、文件产物、字幕、缩略图、infojson。
- 实时日志和下载进度。
- 后处理步骤和耗时。
- 失败堆栈脱敏显示。

### 23.8 依赖诊断

- Python、yt-dlp 版本、ffmpeg/ffprobe 版本。
- Deno/Node/Bun/QuickJS 可用性。
- curl_cffi、requests、websockets、pycryptodomex、mutagen、secretstorage 是否安装。
- 缓存目录、临时目录、存储根目录状态。

## 24. 安全与合规风险

必须默认关闭或严格限制：

- `ExecPP` 和任意 shell 命令。
- `netrc_cmd`。
- `enable_file_urls`。
- 任意 `postprocessor_args` 和 `external_downloader_args`。
- 插件自动加载。
- 自更新。
- 任意 headers 注入。
- 任意输出路径和输出模板。
- 任意外部下载器路径。

必须控制：

- URL SSRF：限制内网地址、metadata 地址、本机地址，除非管理员白名单。
- 文件大小：设置单文件和单任务总大小上限。
- 播放列表：设置最大条数，避免一次下载整个频道。
- Cookie：加密存储、域名绑定、日志脱敏、临时文件清理。
- infojson：可能包含个人信息，前端展示和导出要提示。
- DRM：不绕过 DRM，遇到 DRM 只记录失败或选择其他格式。
- 版权和平台条款：平台只提供用户自持账号和公开内容归档能力，不承诺绕过访问限制。
- SponsorBlock：如调用外部 API，应在网络和隐私设置中可关闭。

## 25. 跨平台部署要求

基础要求：

- Python `>=3.10`。
- Docker Compose 首选，但本机开发也要可启动。
- Linux/macOS/Windows 均支持单机部署。
- FFmpeg/ffprobe 可配置路径。
- 存储根目录和临时目录使用平台配置，不硬编码 Linux 路径。
- Windows 下启用 `windowsfilenames`，避免生成非法文件名。

Docker 注意：

- Docker 容器读取宿主机浏览器 Cookie 很困难，除非显式挂载 profile 和 keyring，第一期不作为默认能力。
- NAS 路径应由宿主机先挂载后再映射到容器。
- ffmpeg、ca-certificates、字体不是全部下载场景都必须，但应作为推荐基础镜像依赖。

## 26. 任务队列与并发策略

建议第一期：

- 全局下载 worker 并发：1-2。
- 单任务分片并发：3-4。
- 同一平台/同一 Cookie Profile 串行或低并发，降低账号风控。
- 大播放列表拆分为子任务，便于取消、重试和进度展示。
- 下载失败按错误类型分级：网络重试、Extractor 失败、Cookie 失效、格式不可用、DRM、路径错误、FFmpeg 错误。
- 任务取消通过 worker 进程/线程标记和子进程终止实现。

## 27. 实施路线

### P0：基线和合规

- 锁定 `yt-dlp` 版本。
- 建立第三方许可证记录。
- 完成 ffmpeg、Python 依赖、缓存目录、存储目录诊断。
- 默认禁用插件、自更新、Exec、file URLs。

### P1：URL 探测

- 实现 `probe_url(download=False)`。
- 标准化返回标题、平台、作者、时长、缩略图、formats、subtitles。
- 前端完成 URL 探测页和格式预览。

### P2：下载任务

- 实现任务表、run 表、日志表和 worker。
- 接入 `progress_hooks`、`postprocessor_hooks`。
- 下载视频、infojson、缩略图、字幕。
- 产物写入 `media_asset`。

### P3：存储与 NAS

- 实现 Storage Profile。
- 本地 temp -> NAS final move。
- 路径诊断、容量诊断、Windows/UNC 路径兼容。

### P4：账号与 Cookie

- 实现 Cookie Profile。
- 支持 Netscape Cookie 导入和账号模块 Cookie 复用。
- 实现域名限制、过期验证、脱敏日志。

### P5：后处理与转录衔接

- 支持抽音频、remux、字幕转换。
- 下载完成后创建转录任务。
- 统一资产详情展示视频、音频、字幕、缩略图和 infojson。

### P6：外部 skill/API

- 提供 `probe-url`、`download-url`、`job-status`、`artifact-read`。
- 增加 API Key、权限范围、限流和调用日志。

### P7：高级平台支持

- YouTube 诊断、JS runtime、PO token/Cookie 状态展示。
- Twitter/X、TikTok/Douyin、Bilibili 的 extractor 参数白名单。
- 可选 SponsorBlock 标记。

## 28. 不并入或暂缓能力

不保留：

- 原命令行作为最终用户入口。
- 上游 PyInstaller 打包产物。
- 自更新能力。
- 默认插件加载。
- 任意命令执行。

暂缓：

- 任意 extractor 参数编辑器。
- 任意外部下载器参数。
- 自动从 Docker 内读取宿主机浏览器 Cookie。
- SponsorBlock 自动裁剪。
- 直播长时间录制和 live chat 下载。
- 付费/私密内容的通用支持，除非专用账号模块明确可合法访问。

## 29. 最终架构图

```text
统一前端工作台
  -> 下载队列 / URL 探测 / Profile / Cookie / 网络 / 存储 / 诊断
  -> platform-api (FastAPI)
      -> media_download.router
      -> media_download.service
      -> queue / worker
      -> ytdlp_adapter
          -> yt_dlp.YoutubeDL
             -> extractor
             -> downloader
             -> postprocessor
             -> networking
             -> cookies
      -> storage_mapper
      -> progress_sink
      -> media_asset service
      -> transcription service
  -> PostgreSQL
      -> jobs / runs / profiles / artifacts / logs / archive
  -> 本地或 NAS 存储
      -> video / audio / subtitles / thumbnails / infojson / transcript / analysis
```

## 30. 本次复盘结论

`yt-dlp` 最适合成为统一平台的“通用媒体下载内核”，而不是一个独立服务或前端功能页。它的价值在于 extractor 覆盖广、格式选择成熟、HLS/DASH/FFmpeg 下载链完整、Cookie/代理/浏览器模拟能力丰富、hook 能接入任务进度。

并入时的关键不是复制所有 CLI 功能，而是建立严格的安全外壳：统一任务、统一存储、统一凭证、统一日志、统一资产、统一诊断。第一期只开放稳定、可解释、可审计的下载能力；高风险能力必须默认关闭，并通过管理员配置逐项解锁。

本轮最终复盘已确认：

- 统一平台只能调用受控 `yt_dlp.YoutubeDL` opts，不暴露任意 CLI 参数或 Python dict。
- `media_download` 产物必须同步写入统一 `media_asset`，并衔接 `transcription`。
- 插件、自更新、`ExecPP`、`enable_file_urls`、任意后处理参数、任意外部下载器参数默认禁用。
- 外部 skill/API 只允许 URL 探测、下载任务创建、任务状态和产物读取，不允许提交服务器输出路径。

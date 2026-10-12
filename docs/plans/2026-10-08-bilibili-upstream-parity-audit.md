# B站能力对照审计：bili-sync 上游 vs 我们

> 日期：2026-10-08 · 范围：`platform-api` 的 B站（bilibili）能力 vs 上游 `bili-sync`
> 目的：看清「上游有、我们还没做」的功能，作为后续迭代的候选清单。
>
> 数据来源：`bili-sync/`（Rust，v2.11.x）与 `platform-api/` 实际代码，逐项核对。

---

## 0. 先说定位差异（决定"要不要做"）

两个项目**目标不同**，不是谁替代谁：

| | bili-sync | platform-api（我们） |
|---|---|---|
| 定位 | **单平台**下载器，服务 NAS 媒体库 | **多平台**素材采集/管理平台 |
| 平台 | 只有 B站 | B站 / 抖音 / 小红书 / 快手 / 知乎 / 公众号 |
| 输出 | 媒体文件（喂 Emby/Jellyfin/infuse） | 素材库 + 转录 + AI 分析 + 看板 |
| 强项 | B站细节做到极致（画质/弹幕/字幕/NFO/分P） | 跨平台统一、账号中心、AI 接入、MCP |

**结论**：我们不是要复刻 bili-sync。下面区分「**值得补**」和「**按定位不需要**」。

---

## 1. 我们已对齐的（✅ 已做）

| 能力 | bili-sync | 我们 | 备注 |
|---|---|---|---|
| Cookie 认证 | ✅ | ✅ | 我们支持扫码 + 手填 |
| 扫码登录 | ✅ | ✅ | `x/passport-login/web/qrcode/*` |
| 收藏夹同步 | ✅ | ✅ | `/x/v3/fav/resource/list` |
| 合集/系列同步 | ✅ | ⚠️ 仅列源 | 能列出合集，但 `fetch_source` 还没取合集内容 |
| UP 主投稿同步 | ✅ 自动扫描 | ✅ | 走 WBI 签名 `/x/space/wbi/arc/search` |
| 关注列表 | ✅ | ✅ | 我们带 24h 缓存补粉丝数 |
| 风控识别/冷却 | ✅ | ✅ | 我们 -352/-412/412 走 cooldown |
| 下载并发/限速 | ✅ 可配 | ⚠️ 走 yt-dlp | yt-dlp 内部并发，我们未暴露配置 |
| 失败重试 | ✅ 次数上限丢弃 | ✅ | 我们的 job 队列 max_attempts=3 |
| 服务名/元数据落库 | ✅ | ✅ | 我们 content_item + snapshot |
| Web UI 管理 | ✅ | ✅ | 我们多平台统一 UI |

---

## 2. 上游有、我们没有（⚠️ 逐项判定）

### 2.1 媒体加工（B站特色，**建议补**）

| 缺的功能 | bili-sync 做法 | 我们的影响 | 建议 |
|---|---|---|---|
| **弹幕下载** | 拉 protobuf 弹幕 → 转 **ASS 字幕**（`danmaku/*.rs` 525 行，含 canvas 渲染） | 完全没做 | ⚠️ **中优先**：做「弹幕采集 → 入库」比转 ASS 更贴我们「素材分析」定位 |
| **字幕下载** | `subtitle.rs`（75 行）拉 B站 CC 字幕 | 没做；但我们要的是**转录**（whisper），CC 字幕其实更准更快 | ⚠️ **建议补**：有 CC 时直接取，省一次 whisper |
| **NFO 刮削文件** | 生成 `tvshow.nfo`/`episode.nfo`（`workflow.rs` generate_*_nfo） | 没做 | ❌ **不需要**：NFO 是喂 Emby/Jellyfin 的，我们不面向媒体库 |
| **分P（多P）下载** | 支持按分P 展开、单独命名 | 没做（只取单视频） | ⚠️ **低-中优先**：多P教程/合集常见，但可先不做 |
| **画质/编码选择** | `FilterOption`：8K/4K/HDR/Dolby/Hi-Res/编码白名单/上下限 | 没做（yt-dlp 自动 best） | ⚠️ **低优先**：我们是为转录/分析，画质够用即可 |

### 2.2 媒体库形态（**按定位不需要**）

| 缺的功能 | bili-sync | 为什么我们可不做 |
|---|---|---|
| **媒体服务器命名** | `video_name`/`page_name` 模板 + 时间格式 | 我们存 `{platform}/{creator}/{date}/{id}`，不是媒体库拓扑 |
| **上传者目录/NFO 时间类型** | `upper_path`、`nfo_time_type` | 同上 |
| **CDN 排序优选** | `cdn_sorting` | yt-dlp 自带选源 |
| **UP 主自动建目录** | ✅ | 我们按订阅源建 |

### 2.3 通知（**建议补，跨平台通用**）

| 缺的功能 | bili-sync | 我们的影响 | 建议 |
|---|---|---|---|
| **Telegram 通知** | ✅ | 没做 | ⚠️ 通用价值高 |
| **Webhook 通知** | ✅ 可模板化 | 没做 | ⚠️ **建议补**：Webhook 最通用，一个就够覆盖 Bark/飞书/钉钉 |
| **忽略常见错误** | `ignore_common_errors` | 没做 | ⚠️ 低优先 |

### 2.4 凭据维护（**建议补，稳定性关键**）

| 缺的功能 | bili-sync | 我们的影响 | 建议 |
|---|---|---|---|
| **Cookie 自动刷新** | ✅ 完整实现：`need_refresh()` → `get_refresh_csrf` → `cookie/refresh` → `confirm_refresh`（`credential.rs`） | ❌ **我们只在体检时提示"建议刷新"，从不真正刷新** | ⚠️ **高优先**：B站 Cookie 会过期，能自动续期就不用反复扫码 |

> **这是我们最明显的一处能力缺口**：我们有 `ac_time_value`（refresh_token）字段，也在扫码时存了，
> 但**没有用它去刷新**。bili-sync 的 `credential.rs` 是现成的参照实现。

### 2.5 其他

| 缺的功能 | bili-sync | 我们 |
|---|---|---|
| 稍后再看（watch later） | ✅ | ❌ 没做（抖音侧做了 like/favorite，B站侧没查 watch later） |
| 视频状态手动重置/改 | ✅ `/videos/{id}/reset-status` | ⚠️ 有 job 重试，但没有「单个素材重置状态」按钮 |
| 任务并行度/请求频率可配 | ✅ `ConcurrentLimit` + `RateLimit` | ⚠️ 只有固定 cooldown，不可配 |
| 配置版本迁移 | ✅ `version` 字段 + 迁移校验 | ⚠️ 我们靠 alembic 管 schema，业务配置无版本 |

---

## 3. 反过来：我们有、bili-sync 没有（我们的相对优势）

- **跨平台统一**：一个账号中心管 6 个平台，bili-sync 只有 B站
- **转录 + AI 分析**：whisper 转录 + 视频理解 + 爆款拆解（bili-sync 只下载）
- **API Key / MCP**：外部 AI 可直接调（bili-sync 只有 Web UI）
- **内容指标快照**：`content_metric_snapshot` 趋势（bili-sync 只存下载状态）
- **多平台采集**：关键词采集覆盖 5 平台（bili-sync 无采集概念）

---

## 4. 建议的补齐优先级（若要做）

| 优先级 | 功能 | 理由 | 参照 |
|---|---|---|---|
| **P1** | B站 **Cookie 自动刷新** | 直接决定"能不能长期无人值守"，我们现在会静默过期 | `bili-sync/.../credential.rs:161-262` |
| **P1** | **Webhook 通知** | 通用、一个覆盖所有 IM；失败/完成能第一时间知道 | `bili-sync/.../notifier/mod.rs` |
| **P2** | **CC 字幕优先** | 有官方字幕时跳过 whisper，省算力又快 | `bili-sync/.../subtitle.rs` |
| **P2** | **合集内容同步** | 我们只能"列出"合集，不能"同步"其内容，是功能断点 | `bili-sync/.../collection.rs` |
| **P3** | 弹幕采集入库 | 贴素材分析定位；不必转 ASS | `bili-sync/.../danmaku/*` |
| **P3** | 稍后再看同步 | 补齐 B站侧订阅源类型 | `bili-sync/.../watch_later.rs` |
| **P4** | 分P、画质选择、媒体库命名 | 按我们定位可暂不做 | — |

---

## 5. 结论

- **必须补的只有 2 项**：Cookie 自动刷新（稳定性硬伤）、通知（可观测性）。
- **值得补的 2 项**：CC 字幕优先、合集内容同步（当前是功能断点）。
- **按定位不该抄的**：NFO、媒体库命名、画质档位、CDN 优选 —— 那些是 NAS 下载器的活，不是素材平台的活。

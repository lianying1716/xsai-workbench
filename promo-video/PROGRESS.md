# 宣传片 v2 · 进度

## 已完成

### 1. 演示站数据全真化（方案 1）
- 清空 `seed_demo.py` 的假内容（改为 `PLATFORM_DEMO_FAKE_CONTENT=1` 才启用）
- 演示站 = **17 条真实素材**：7 真视频 + 10 真文章，**零假数据**
- 每条都有：真实封面、真实转录、真实 AI 分析
- 7 个视频全部可点击播放（实测 `readyState=4`、正在播）

### 2. 真实内容生产管线（可重跑）
| 脚本 | 作用 |
|---|---|
| `scripts/seed_demo_real.py` | 把真实内容注入演示库（含超大视频过滤，默认 >20MB 跳过） |
| `/tmp/demo-build/transcribe_batch.py` | faster-whisper 真实转录 |
| `/tmp/demo-build/analyze_batch.py` | deepseek-v4.1-flash-free 分析 + 爆款拆解 |
| `/tmp/demo-build/fetch_articles.py` | 公众号文章抓取 |
| `/tmp/demo-build/gen_covers2.py` | qwen-image-2.1 封面生成 |

模型统一：分析/拆解用 **deepseek-v4.1-flash-free**，封面用 **qwen-image-2.1**。

### 3. 素材来源
- 真实视频：`data/demo_storage`（10 个文件，7 个已入演示）
- 真实文章：10 篇公众号（MCP / Graph Engineering / 大模型安全 / 空间智能 等）
- 封面：85 张（qwen-image 生成 34 + 真实下载 51）

### 4. 片子 v3（已渲染 + 已验收）
- `videos/stargather-promo/renders/stargather-promo-v3.mp4` — 59.9s / 1920×1080 / 30fps / 51.3MB
- 8 镜：痛点洪流 → 数字对撞 → 品牌反转 → 账号中心 → 关键词采集 → 素材库真播放 → 转录+拆解 → 数据+CTA
- BGM 裁到真实下降拍（`assets/bgm-v3.mp3`），真实脉冲 69.84 BPM（`assets/beat-grid-v3.json`）
- 原创音效层 `assets/sfx-v1.mp3`（`scripts/gen_sfx.py`），全部吸附真实重拍
- 真实性：真实界面截图（Playwright dsf=2）+ **真实视频真的播放**（`assets/clips/real-demo.mp4`）
- 交互感：可见光标 + 点击涟漪 + 真打字 + 平台指示灯逐个点亮 + 4 处强推近（1.34–1.78x）
- 验收报告：`G3-REPORT-v3.md`（**94 分**，无硬否决）；静帧审阅页 `g2v3/storyboard.html`

## 对抗性复检修掉的真实缺陷（v2 → v3）

1. BGM 前 6.4s 近乎静音，正压在开场钩子上 → 裁到真实下降拍，开场能量比 0.40 → 0.96
2. 节拍网格是错的（写 92.29，实际 69.84 BPM）→ 重建网格并重排所有卡点
3. 全片 66% 帧无运动，品牌镜静止 5.6s → 加环境律动，活跃帧 37% → 81.3%，≥1s 静止段 0
4. 主功能点缩放不足 → 4 处 1.34–1.78x 推近
5. 只有图片没有点击 → 光标 + 涟漪 + 真打字 + 真视频播放

## 片子 v4（按用户 6 条反馈重做）

- 成片：`videos/stargather-promo/renders/stargather-promo-v4.mp4`（59.9s，51.8MB）
- 验收：`videos/stargather-promo/G3-REPORT-v4.md`（**97 分**，0 error / 0 warning，对比度 55/55，静止段 0）

| 用户反馈 | 处理 |
|---|---|
| 文案太抽象看不懂 | 改为「收藏夹里堆了一大堆，再也没打开过」+ 副文案；接入落地页原词 |
| 右上角全程固定 star logo | 新增固定品牌角标，10/10 采样点在线 |
| 第二帧做时间线 + 跳动数字 | 时间线逐拍推进 + 刻度 + 落点；收藏与「打开过」**都是**动态数字 |
| 第三画面缺主 logo、信息太少 | 加大号主 logo + 定位 + 三件事 + 底部平台条（logo+中文名） |
| 第四画面不要 DOUYIN/XHS 字样 | 改为真实平台 logo + 中文名（B站/抖音/小红书/快手/知乎/公众号） |
| 落地页内容可直接用 | 主张、平台清单、能力描述均取自 `capture/extracted/visible-text.txt` |

## 片子 v5（修正 logo + 重做数字动画）

- 成片：`videos/stargather-promo/renders/stargather-promo-v5.mp4`（59.9s，51.9MB）
- 静帧审阅：`videos/stargather-promo/g2v5/storyboard.html`

### 1) Logo 严重错误（已修）
**问题**：我用了 `platform-api/docs/brand/logo/dist/stargather-symbol-*.svg`——
那是 2026-10-08 第一轮「四角托 + 中心星」的概念稿，**早已淘汰**。

**正确资产**：2026-10-09 正式选型的 **M3「月碗托星」**，产品实际在用
`platform-api/web/public/logo-symbol.svg`（源文件 `docs/brand/logo/m3/stargather-m3.svg`）。

处理：删掉全部旧概念稿副本 → 换成 M3（`assets/brand/stargather-m3.svg`）→ 全片右上角固定 + 场景 3 主 logo。
程序化验证：角标 logo 与官方 M3 同尺寸 **NCC 0.856**；场景 3 主 logo **NCC 0.926**（砖红小星可检出）。

### 2) 数字跳动生硬（已重做）
**问题**：旧实现是「每 2 拍 `tl.set()` 一次」，本质是跳字；而且建立在
「seek 渲染不会触发 `onUpdate`」这个**错误假设**上。

**实测结论**：`onUpdate` 在 seek 下**是生效的**（单独做了 seek 探针：1s→1043、3s→2043、5s→2410）。

改法（对齐 `hyperframes-animation/rules/counting-dynamic-scale.md` 的标准做法）：
- proxy 对象 + `tl.to()` + `onUpdate` 逐帧插值，`Math.round().toLocaleString()`
- 计数 ease `power2.out`（先快后缓，像在不断累积）
- `tabular-nums` + `font-feature-settings:'tnum'` + **JS 实测最宽字符串来定槽宽**（位数 1→4 不推挤布局）
- 数字自身 scale `0.55→1` 与计数同段；落定后只在结束时回弹一次
- 「打开过的」也连续累加（0→3）

程序化验证：6.4→9.6s 逐帧 **95/95 帧都有变化（0 帧冻结）**；DOM 实测
`89→636→1,377→1,834→2,185→2,444→2,624→2,741→2,818→2,844→2,847`。

## 片子 v7（真实页面 + 抖小云→抖音 + 片尾官网）

- 成片：`videos/stargather-promo/renders/stargather-promo-v7.mp4`（59.9s，59.3MB）
- 静帧审阅：`videos/stargather-promo/g2v7/storyboard.html`
- 基准：在 v5 之上改（v5 的角标样式是用户选定保留的）

### 1) 关键词采集 / 转录 / 爆款拆解 → 全部换成真实页面
- **S5 关键词采集**：改用真实「新建采集任务」对话框截图（Playwright 真机、dsf=2），
  含真打进去的关键词与光标点击反馈；不再是自造输入框。
- **S7 转录 + 拆解**：左侧换真实「转录」页（457 字真实 faster-whisper 转录，缓慢滚读），
  右侧换真实「爆款拆解」报告页（87% 评分 + 真实 deepseek 结论 + 开场钩子/内容结构/复刻蓝图）。
- 顺带修掉一个真实产品缺陷：`seed_demo_real.py` 把拆解写进了不存在的 `result` 列，
  导致**演示站里拆解报告一直是空的**。已改为产品真实列（`verdict` / `sections` /
  `data_context` / `score`），并按 `Assets.vue` 实际读取的结构（hook/structure/psych_triggers/
  blueprint/replication_tips）做映射。现在演示站打开素材详情能看到完整报告。

### 2) 演示站「抖小云」→「抖音」
清掉了仓库里所有残留（`scripts/seed_demo.py`、`web/src/pages/DesignPreview.vue`、
`web/public/demo-data/snapshot.json`、构建产物），重新导出快照 + 重新构建 `dist-demo`，
并重抓了片中用到的账号页截图。全仓库检索 `抖小云` 为 0。

### 3) 片尾加落地页地址
最后一帧在主张之下加了 `cai.xsai5.xyz` 地址条（与墨色硬边/偏移影同语言），片尾保持到结束。

## 线上演示站已重新部署（2026-10-12）

- 目标：`https://cai.xsai5.xyz/demo/`（香港服务器 `/var/www/cai/demo/`）
- 方式：`rsync -az --delete platform-api/web/dist-demo/ nexai-hk:/var/www/cai/demo/`
- 回滚备份：`/var/www/cai/demo.prev3`（部署前的旧版，8.2M）
- 结果核对：
  - 素材 **33 → 17**（旧的假内容清空，7 真视频 + 10 真文章）
  - 账号 `[DEMO] 抖小云·主号` → `[DEMO] 抖音·主号`，全量检索 `抖小云` 为 0
  - 爆款拆解报告从**空**变为**7 条真实报告**（87% + deepseek 结论 + 完整板块），浏览器实测渲染正常
  - 真实视频可播（`readyState=4`，`currentTime` 正常推进）
  - 9 个页面全部加载，无 JS 报错、无 4xx

> 部署前线上是 10-11 的旧版（33 条含假内容、仍叫"抖小云"），与片子片尾的官网入口不一致；
> 现已一致。

## 关键文件
- 创作稿：`CREATIVE-BRIEF.md`
- 验收标准：`ACCEPTANCE.md`（90 分线）
- 演示站：`platform-api/web/dist-demo/`（`/demo/` 路径）

## 流程沉淀 + 验收器复算（2026-10-12）

这轮不体检仓库，只把「这次怎么做片的」变成下次能重跑的东西：

### 1. 新增可执行验收器 `scripts/audit_video.py`
把 SOP §二·⑥ 的检测表从描述变成命令。一条命令输出可留档 JSON，退出码 0/1 表示过没过线。
覆盖：规格、开场能量比、分块差分（frozen / low-motion 分开报）、空黑帧、
节拍对齐偏移、镜头推近倍数、真视频播放、数字连续、逐字打字。

### 2. 复算旧报告，发现一处不一致（如实记录）
- 旧报告（v4 §二）写「连续静止 ≥1.0s：**0 处**」。
- 用真实逐帧差分复算 v7：**53.4s 起 2.3s、58.5s 起 1.4s** 两段「低运动」。
- 判定：**不是像素级冻结**（逐帧平均差 0.2–0.5 灰度级，环境层仍在动），
  但**内容层几乎不动**。旧报告用单一「静止」口径把这层差别抹掉了。
- 处理：审计器拆成 **frozen**（整幅平均差 < 0.15）与 **low-motion**（活跃块 < 2%）两个口径，都在证据里。

### 3. 修掉验收器自己的三个 bug（否则它在生产「看起来专业的数字」）
1. 尺度探针：整帧交叉相关 + 形状不匹配静默 `continue` → 所有窗口假报 1.0x；改为区域内模板匹配，并输出 NCC。
2. 真视频探针：整框平均差被播放器描边稀释，比值只有 1.9 → 改为「热点子块占比」，得到 0.438 vs 0.000。
3. 节拍探针：一度拿渲染成片做 onset 分析（混音 + 编码位移）→ 改用 BGM 源文件，17 个 downbeat 平均偏移 **4.1ms**。

### 4. 新增 `scripts/make_beat_grid.py`
BPM 检测会在真值/2 倍/无关候选间飘（同一首曲子：librosa 给 143.55，自相关给 69.84）。
工具用自相关锁定基频 + 显式 `--align-to` 解决「4 倍相位歧义」，复算本次 BGM = **69.83742 BPM**，与冻结网格一致。

### 5. v7 审计证据
`evidence/audit-v7.json`（本次审计器输出，PASS=true）。


## 片子 v9（MiMo-V2.6 多模态拆解驱动 + 封面修复）

- 成片：`videos/stargather-promo/renders/stargather-promo-v9.mp4`（59.9s，70.1MB）
- 静帧审阅：`videos/stargather-promo/snap-v9/contact-sheet.jpg`
- 审计：`evidence/audit-v9.json`（PASS）

### 1) 首帧卡片封面：占位文字 → 真实封面（用户直接反馈）
- 48 张真实封面（`platform-api/web/public/demo-data/media/*.png`，864×1152）压缩为 480×640 JPEG
  （58MB → 2.2MB）落到 `assets/ui/covers/`，替换 S1 卡片里写死的 `<div class="fm">封面</div>`。
- 程序化验证：首帧卡片区裁剪 std 65.6→93.9、平均饱和度 12.2→28.1、独立颜色数大幅上升；
  逐块差分显示卡片区无纯色块。MiMo 复看确认是真实照片。

### 2) MiMo-V2.6 多模态拆解（5 部大厂参考片 + 我们）
- 报告：`reference/vlm-analysis/MIMO-REPORT.md`；逐片 7 视角证据：`reference/vlm-analysis/mimo/`。
- 拆出四条跨片共识：主角是人/人的一次操作（不是 UI）；一屏一个主张；快慢要呼吸；
  色彩是封闭系统（低饱和底 + 单一强调色）。
- v9 据此落地：S1 卡片改「生长式入场」（scale+blur，替换四面硬滑入）；
  S1 副文案砍到一行；「真实演示数据」水印统一改弱化 `DEMO`；S8 结尾加 1.2s 呼吸留白。

### 3) v9 相对 v7 的运动指标（audit_video.py 复算）
| 指标 | v7 | v9 |
|---|---|---|
| 活跃帧占比 | 0.774 | **0.938** |
| 冻结帧占比 | 0.005 | **0.000** |
| 平均块差分 | 3.86 | **5.33** |
| 节拍平均偏移 | 4.1ms | 4.1ms |

### 4) 顺手修掉一个真实回归
卡片从浅灰占位换成真实照片后，深色照片压到 S1 底部元数据行，触发对比度不足（2.19:1）；
给该行加奶油底衬后恢复达标（check 0 error / 0 warning）。

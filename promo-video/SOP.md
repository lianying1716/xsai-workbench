# 星采宣传片 · 制作流程 SOP

> 这份文档记录 **2026-10-11 ~ 10-12 这次做片的完整流程**，目的是下一次（换产品、换版本、换平台）
> 能照着重跑，而不是重新摸一遍。
>
> 它不是工作报告（那是 `PROGRESS.md`），也不是验收标准（那是 `ACCEPTANCE.md`），
> 而是**「怎么做」的操作手册 + 「为什么这样做」的判据**。
>
> 五份文档的分工见 `README.md`。

---

## 一、流程总览

```
① 定验收线  →  ② 写创作稿  →  ③ 备真实素材  →  ④ 搭合成  →  ⑤ 渲染
                                                    ↑              ↓
                                                    └── ⑥ 对抗性验收 ──┘
                                                          （不通过就回到 ④）
```

每一步的产出物都是下一步的输入，且**每步都有可机器检验的关卡**。

---

## 二、六步操作

### ① 定验收线（最容易被跳过，但最贵）

**先写 `ACCEPTANCE.md`，再动任何代码。** 内容包括：

- 一句话定义「优秀的产品宣传片是什么」
- 加权评分维度（本片 6 项，总分 100，通过线 90）
- **硬否决项**（触犯任意一条直接不通过，不看总分）
- 本片特定的验证点（主张、结构、必现元素、卡点基准）

**为什么**：没有验收线，「改得好不好」就只剩主观感觉，会陷入无限返工。
本片 9 条硬否决里有 3 条（无假 UI、素材许可、时长画幅）在后期真的拦下过东西。

### ② 写创作稿（`CREATIVE-BRIEF.md`）

产出：**核心主张 1 句 + 逐镜文案表 + 视觉语言 + 分镜表**。

关键判据（对应验收线 A 项）：

- 一句话主张，不是功能清单
- 开场 0–3s 用**观众的语言**回答「我为什么要在乎」，不用产品内部词汇
- 每个镜头只干一件事，追溯不到主张的镜头直接砍
- 结尾一句像人话的 CTA

**踩过的坑**：初版开场是「你又存了一条 / 上次打开是什么时候」——描述现象，观众点头但无感。
改成用户原话后才成立（「收藏夹里堆了一大堆，再也没打开过」）。**这条反馈来自用户，不是自检出来的。**

### ③ 备真实素材（本流程最重的一段，也是最容易做假的）

**铁律：能用真界面就不造图，能用真数据就不编数字。** 本片的素材全部来自演示站真实抓取。

素材来源三条路径：

| 素材类型 | 来源 | 方式 |
|---|---|---|
| 界面截图 | 演示站 `platform-api/web/dist-demo/` | Playwright 真机截图，`deviceScaleFactor=2` → 3840×2160 |
| 视频内容 | 演示库真实视频 | `ffmpeg` 截片段（本片 6.2s 竖版） |
| 封面 | qwen-image-2.1 生成 / 真实下载 | 见「生成管线」 |

**演示站数据必须先全真**，否则片子里全是占位图。本片为此专门做了一轮演示站改造
（清假数据 + 批量补真实内容），详见 `PROGRESS.md`。

### ④ 搭合成（HyperFrames）

工程：`videos/stargather-promo/`，入口 `index.html`。

- 逐场景 `<section data-start data-duration>`，一条主时间线
- **卡点必须用真实脉冲**，不能用理论 BPM
- 数字动画用 `proxy + onUpdate` 逐帧插值，不用「每隔几拍 set 一次」
- 每镜要有环境律动（网格漂移 / 幽灵字视差），否则整片大半是静止帧

### ⑤ 渲染

```bash
npx hyperframes@0.8.147 check                       # 关卡：必须 0 error
npx hyperframes@0.8.147 render -o renders/xxx.mp4 --crf 20
```

> 用 `--crf 20`：默认 CRF 16 在「全屏缓慢缩放」的片子上会到 150MB+，CRF 20 约 50MB，观感无差。

### ⑥ 对抗性验收（这是本流程真正的核心）

**不看图，全靠量。** 每一条结论都要有命令输出支撑。这些检测已固化成审计器
`../scripts/audit_video.py`，一条命令跑完并输出可留档 JSON：

```bash
cd videos/stargather-promo
python3 ../../scripts/audit_video.py renders/xxx.mp4 \
  --total 59.9 --grid-json assets/beat-grid-v3.json --bgm assets/bgm-v3.mp3 \
  --countup "6.4:9.6:380:180:260:150" \
  --playback "35.5:38.5:193:179:285:160:640:300:280:160" \
  --scale-windows "26.0:27.7:38:86:596:335" \
  --json ../../evidence/audit-xxx.json   # 退出码 0=通过，1=未过线
```

| 检查项 | 手段 | 对应参数 |
|---|---|---|
| 时长/画幅/音轨 | `ffprobe` | （默认跑） |
| 开场是否静音 | 逐段 RMS，算「0–3s / 全片」比值（<0.6 即开场偏弱） | `--head-seconds` |
| 那一段是死的 | 960×540 @10fps 切 12×6 块逐块差分；分开报 **frozen**（真冻结）和 **low-motion** | `--static-threshold` |
| 空/黑帧 | 同上，看 `std<8` / `mean<12` | （默认跑） |
| 节拍是否真对齐 | BGM 源文件算 onset 包络，检查每个 downbeat 的偏移 | `--grid-json --bgm` |
| 镜头推近倍数 | **区域内模板匹配**（不是整帧交叉相关），报 median/max | `--scale-windows` |
| 真视频是否在播 | 播放区「热点子块占比」vs 静态区 | `--playback` |
| 数字是否连续 | 数字区逐帧差分，统计「完全没变的帧对」（应为 0） | `--countup` |
| 打字是否真逐字 | 输入区差分里的离散跳变簇计数 | `--typing` |
| 对比度 / 排版溢出遮挡 | `hyperframes check` 的 Contrast / Layout 段 | （框架自带） |

> **工作目录**：脚本在 `promo-video/scripts/`，要 `cd` 到 `videos/stargather-promo/` 再跑，
> 这样 `assets/...` 与 `renders/...` 的相对路径才成立。

**发现问题的正确姿势**：不要问「哪里不好看」，要问「哪一帧可以证明它是死的 / 假的 / 错的」。

---

## 三、卡片：本次踩过的坑（下次直接避开）

| # | 坑 | 怎么发现的 | 怎么修 |
|---|---|---|---|
| 1 | BGM 前 6.4s 几乎静音，正压在开场钩子上 | 逐段 RMS | 把音乐裁到**真实下降拍**，开场能量比 0.40→0.96 |
| 2 | 节拍网格写 92.29 BPM，实际是 69.84 | tempogram + 自相关 | 重建网格，场景边界重排（原本偏 0.4–0.57s） |
| 3 | 全片 66% 的帧零运动，品牌镜静止 5.6s | 分块差分 | 每镜加环境律动，活跃帧 37%→88%，≥1s 静止段归零 |
| 4 | 上轮判定「seek 下 `onUpdate` 不触发」→ 数字只能跳字 | 写 seek 探针实测 | **该假设是错的**；改用 `onUpdate` 逐帧累加 |
| 5 | logo 用错（拿的是已淘汰的第一轮概念稿） | 读 `m3/README.md` 的品牌决策记录 | 换成当前在用的 M3「月碗托星」，并用像素比对验证 |
| 6 | 演示站拆解报告一直是空的 | 比对 DB schema 与 `Assets.vue` 读取结构 | `seed_demo_real` 写进了不存在的 `result` 列 → 改为真实列 + 结构映射 |
| 7 | 品牌角标用 `.clip`（`inset:0`）盖住整屏 | `check` 报 text_occluded | 角标改 `inset:auto` |

> **第 4 条最值得记**：一个错误假设会让整段实现走偏。**遇到「做不到」时，先写最小探针验证假设，别信文档和记忆。**

### 卡片之外：三条「指标本身会说谎」的教训

做验收器时踩到的，比片子本身的问题更值得沉淀：

1. **同一个词，两个口径，会互相掩盖。**
   最早只报一个「静止段」。复算时发现：旧报告写「≥1s 静止段 0 处」，但用真实逐帧差分一算，
   S8 收尾有 **53.4s 起 2.3s、58.5s 起 1.4s** 两段低运动。
   真相是——那里逐帧平均差约 0.2–0.5 灰度级，**不是像素级冻结，但内容几乎不动**。
   现在审计器把 **frozen**（整幅平均差 < 0.15）和 **low-motion**（活跃块 < 2%）分开报，
   两者都写进证据，不再用一个「静止」把差别抹平。

2. **指标参数写错会静默给出「合格」。**
   尺度探针第一版用整帧交叉相关，形状对不齐就 `continue`，结果**所有窗口都返回 1.0x**——
   看起来「镜头没推近」，实际是探针失效。改法：区域内模板匹配 + 打印 NCC，
   没有可信匹配就报 `error` 而不是猜一个数。**一个永远返回「正常」的探针，比没有探针更危险。**

3. **基准要用源文件，不能用成品。**
   测节拍对齐时，一度拿**渲染成片**做 onset 分析——成片混了音效、还有编码位移，
   偏移量算出来是脏的。改成用 `assets/bgm-v3.mp3` 做基准后，
   17 个 downbeat 的平均偏移从「看似有偏差」收敛到 **4.1 ms**（最大 23 ms）。

> 一句话：**验收器本身也要被验收。** 每个探针都要能在一个已知为真的样本上给出真值，
> 在一个已知为假的样本上给出假值；否则它只是在生产看起来专业的数字。

---

## 四、生成管线（当前状态 + 待沉淀）

本次真实素材的生产脚本**有 13 个，但只在 `data/demo_pipeline/`，机子一清就没了**。它们靠约定文件名串联：

```
transcripts.json → analysis.json → real_pack.json → 注入演示库
article_urls.json → fetch_articles → import_articles ┐
need_covers.json  → gen_covers2    → cover_cache     ┘
```

其中有复用价值的 7 个：

| 脚本 | 作用 | 依赖 |
|---|---|---|
| `transcribe_batch.py` | faster-whisper 批量转录真实视频 | CPU int8（GPU 被占用会 OOM） |
| `analyze_batch.py` | deepseek-v4.1-flash-free 分析 + 爆款拆解 | `~/.codex/auth.json` 的 key |
| `fetch_articles.py` | 抓真实公众号文章 | `app.modules.article_import` |
| `gen_covers2.py` | qwen-image-2.1 生成封面 | （本地网关的环境变量文件） |
| `export_real_pack.py` | 从 Postgres 导出内容包 | 本地 PG :5433 |
| `import_articles.py` | 文章入库（走平台 import 服务，与线上同构） | 同上 |
| `fetch_article_covers.py` | 下载真实文章封面 | — |

**待做**：把这批脚本移进 `platform-api/scripts/demo_pipeline/`，去掉硬编码路径、改成 CLI 参数。

---

## 五、下次开新片的最短路径

```bash
# 0. 读这三份，别跳过
#    ACCEPTANCE.md（验收线）· CREATIVE-BRIEF.md（怎么写）· 本文件（怎么做）

# 1. 演示站数据先全真（片子的素材质量由这里决定）
cd platform-api
uv run python scripts/export_demo_snapshot.py     # 会自动关掉假内容
cd web && npm run build:demo

# 2. 版面/界面截图（真机、2 倍图）
#    Playwright：deviceScaleFactor=2，viewport 1920×1080

# 3. 改 index.html：文案 / 场景 / 卡点（卡点用真实脉冲）

# 4. 过关 + 渲染
cd ../promo-video/videos/stargather-promo
npx hyperframes@0.8.147 check
npx hyperframes@0.8.147 render -o renders/xxx.mp4 --crf 20

# 5. 对抗性验收（见 §二·⑥ 的检测表），逐条留证据
python3 ../../scripts/audit_video.py renders/xxx.mp4 --total 59.9 \
  --grid-json assets/beat-grid-v3.json --bgm assets/bgm-v3.mp3 \
  --countup "..." --playback "..." --scale-windows "..." \
  --json ../../evidence/audit-xxx.json
```

---

## 六、一句话总结

**这个流程的价值不在「做出一个片子」，而在「片子上的每个判断都能被一条命令证伪」。**

看不到图不是障碍——只要把「好看」拆成可测量的量（能量比、活跃帧率、尺度倍数、差分比），
就能在不看图的情况下把片子做到 90 分以上，而且每一处修改都有据可查。

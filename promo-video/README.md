# promo-video — 星采宣传片工程

纯代码 + 录屏制作的产品宣传片（不用剪辑软件），基于 HyperFrames。

## 先读哪份

| 文档 | 角色 | 什么时候看 |
|---|---|---|
| **`SOP.md`** | **怎么做**（操作手册 + 判据 + 踩坑卡片） | **开工前必读** |
| `ACCEPTANCE.md` | 好的标准是什么、硬否决项、90 分线 | 动代码之前先定 |
| `CREATIVE-BRIEF.md` | 文案 / 分镜 / 视觉语言（当前片子的创作稿） | 写内容时 |
| `THIRD_PARTY_NOTICES.md` | 音乐、字体、平台图标、素材署名 | 对外发布前必查 |
| `PROGRESS.md` | 本次实际做了什么、修了哪些缺陷（工作报告） | 复盘时 |

一句话分工：**SOP 讲方法，ACCEPTANCE 讲标准，BRIEF 讲内容，NOTICES 讲合规，PROGRESS 讲历史。**

## 成片

| 版本 | 文件 | 说明 |
|---|---|---|
| **v9（当前交付）** | `videos/stargather-promo/renders/stargather-promo-v9.mp4` | 59.9s / 1920×1080 / 30fps · 真实封面 + 生长式入场 + 留白结尾 |
| v7 | `videos/stargather-promo/renders/stargather-promo-v7.mp4` | 59.9s / 1920×1080 / 30fps · 真实页面 + M3 标志 + 片尾官网 |
| v1–v6 | 同目录 | 历史版本，留作对比 |

配套产出：

- `videos/stargather-promo/g2v7/storyboard.html` — 8 镜静帧审阅页
- `videos/stargather-promo/snap-v7/contact-sheet.jpg` — 全片接触表
- `videos/stargather-promo/index.html` — 合成源文件（唯一真源）

## 快速跑通（改片后）

```bash
cd videos/stargather-promo
npx hyperframes@0.8.147 check                       # 必须 0 error
npx hyperframes@0.8.147 render -o renders/xxx.mp4 --crf 20
```

验片方法（不看图也能验收）见 `SOP.md` §二·⑥，命令如下：

```bash
python3 ../../scripts/audit_video.py renders/xxx.mp4 --total 59.9 \
  --grid-json assets/beat-grid-v3.json --bgm assets/bgm-v3.mp3 \
  --countup "..." --playback "..." --scale-windows "..." \
  --json ../../evidence/audit-xxx.json
```

脚本说明见 `scripts/README.md`。

## 目录结构

```
promo-video/
├── SOP.md / ACCEPTANCE.md / CREATIVE-BRIEF.md
├── THIRD_PARTY_NOTICES.md / PROGRESS.md / README.md（本文件）
├── scripts/                  可重跑工具（验收器 + 节拍网格）
└── videos/stargather-promo/
    ├── index.html              合成源（所有场景 + 时间线）
    ├── assets/                 音乐、音效、界面截图、品牌标志、真视频片段
    ├── scripts/gen_sfx.py      原创音效生成（可重跑）
    ├── renders/                成片（不进版本库）
    ├── g2v7/ snap-v7/          静帧审阅页与接触表
    └── capture/ capture-demo/  落地页 & 演示站的抓取产物
```

> 演示素材的生产脚本（转录 / AI 分析 / 封面 / 导出）在
> `platform-api/scripts/demo_pipeline/`，状态与改造清单见该目录 README。

## 不进版本库的东西

见 `.gitignore`：`renders/`、`snapshots*/`、`verify/`、`capture*/`、`.hyperframes/`、`node_modules/`。
成片和抓取产物体积大且可重生成，需要交付时单独传。

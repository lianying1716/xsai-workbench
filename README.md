<div align="center">

<img src="site/assets/logo-symbol.svg" width="84" alt="星采 Stargather">

# xsai-workbench · 星采 Stargather 设计工作台

**星采 Stargather 的设计文档、品牌资产与宣传片工程。**
产品代码在独立仓库：[**lianying1716/platform-api**](https://github.com/lianying1716/platform-api)。

[![Product](https://img.shields.io/badge/product-platform--api-009688.svg)](https://github.com/lianying1716/platform-api)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Film](https://img.shields.io/badge/film-%E5%AE%A3%E4%BC%A0%E7%89%87%20v9-CC2823.svg)](https://github.com/lianying1716/platform-api/blob/main/README.md)

[在线演示](https://cai.xsai5.xyz/demo/) · [官网](https://cai.xsai5.xyz/) · [产品仓库](https://github.com/lianying1716/platform-api)

</div>

---

## 这个仓库是什么

星采把「刷到就收藏、却再也没打开过」的视频，变成一套本地、结构化、可被 AI 调用的内容知识库
——做了这个产品之后，它的**设计过程**留在这个仓库里：

- **需求与设计文档**（`docs/`）：需求、架构、分期总纲、账号中心设计，以及逐功能的
  `docs/plans/` 设计与实施记录。
- **品牌资产**（`logo-gen/`）：最终选定的 **M3「月碗托星」** 标志的矢量母版、生成与矢量化脚本。
- **官网**（`site/`）：静态落地页（PC + H5），部署在 `cai.xsai5.xyz`。
- **宣传片工程**（`promo-video/`）：用「纯代码 + 真实界面录屏」做宣传片的方法与验收工具
  ——SOP、验收标准、创作稿、**可重跑的视频审计器**。
- **做片管线技能**（`promo-video-pipeline/`）：把上面这套方法沉淀成一个可复用的技能
  （含 `audit_video.py`、多模态拆解脚本、起始模板）。

产品本身（后端 + 前端 + MCP）在 **[platform-api](https://github.com/lianying1716/platform-api)** 仓库，
支持抖音 / B站 / 小红书 / 快手 / 知乎 / 公众号 的采集、下载、转录、AI 分析与 API/MCP 接入，
开源、可私有化部署。

## 宣传片

星采宣传片 v9（1080p / 60s）就在产品仓库的首页里：见
[platform-api → 宣传片](https://github.com/lianying1716/platform-api#宣传片)。
片中用到的真实界面、真实数据与真视频播放，制作与验收方法见本仓库 `promo-video/`。

## 目录结构

```
xsai-workbench/
├── docs/                 # 需求 / 架构 / 分期总纲 / 逐功能设计与实施记录
│   └── plans/            # 每个功能的 design + plan（历史留痕）
├── logo-gen/             # 品牌标志生成与矢量化脚本（M3「月碗托星」为最终选型）
│   ├── vectorize.py      # 位图概念图 → 矢量（扁平化 + potrace）
│   ├── m3_assets.py      # 从矢量母版导出全套位图
│   └── build_frontend_brand.py  # 生成前端品牌文件
├── site/                 # 静态官网（index.html / mobile.html，本地打包 GSAP）
└── promo-video/          # 宣传片工程
    ├── SOP.md            # 怎么做（操作手册 + 判据 + 踩坑）
    ├── ACCEPTANCE.md     # 好的标准（硬否决项 / 90 分线）
    ├── CREATIVE-BRIEF.md # 文案 / 分镜 / 视觉语言
    └── scripts/          # audit_video.py（可重跑的视频审计器）等
└── promo-video-pipeline/ # 可复用的「代码 + 录屏做宣传片」技能（MIT）
```

## 视频审计器（这套方法的重点）

`promo-video/scripts/audit_video.py` 把「片子好不好」变成**可被命令证伪**的指标：
规格、开场能量比、分块运动（区分 *冻结* 与 *低运动*）、空黑帧、节拍偏移、
推近倍数（区域模板匹配）、真视频播放、数字连续、逐字打字——一条命令输出 JSON，退出码 0/1。

```bash
python3 promo-video/scripts/audit_video.py <render.mp4> --total 59.9 \
  --grid-json <beat-grid.json> --bgm <bgm.mp3> --json report.json
```

## 许可

本仓库代码与文档采用 **Apache-2.0**（见 [`LICENSE`](LICENSE)）。
`promo-video-pipeline/` 为 MIT（见其自身 `LICENSE`）。
第三方素材的来源与许可（音乐、字体、平台图标、参考片）见
`promo-video/THIRD_PARTY_NOTICES.md` 与 `promo-video-pipeline/THIRD_PARTY_NOTICES.md`。

## 关于星算 AI

星采（本工作台与 `platform-api`）由 **[星算 AI](https://xsai5.xyz)** 的作者开发。
星算是**闭源**的大模型服务（`https://xsai5.xyz`），与开源项目星采相互独立：星采可私有化部署、
不依赖星算也能完整运行；星算只是可选的模型来源之一。

---

<div align="center"><sub>星采 Stargather · 把收藏，变成你的内容知识库 · 由 <a href="https://xsai5.xyz">星算 AI</a> 的作者开发</sub></div>

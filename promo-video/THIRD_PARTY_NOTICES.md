# 第三方素材署名（宣传片项目）

## 音乐

- **ElectroHouse Cheesy.wav** — 作者 RutgerMuller
- 来源：Freesound #51278 — https://freesound.org/people/RutgerMuller/sounds/51278
- 许可：**CC0 1.0 Universal（公共领域奉献）** — https://creativecommons.org/publicdomain/zero/1.0/
- 用途：`videos/stargather-promo/assets/bgm-v3.mp3`
  - 由原曲裁切至真实下降拍（原曲 6.906s），得到 60.0s 的成片用床；
  - 真实脉冲 **69.84 BPM**（1 拍 = 0.859s），节拍网格 `assets/beat-grid-v3.json`。

## 音效

- `videos/stargather-promo/assets/sfx-v1.mp3` — **本项目原创**，由 `scripts/gen_sfx.py` 用正弦/噪声合成。
  所有转场 whoosh、重拍 impact、点击 click、打字 tick 均落在 `assets/beat-grid-v3.json` 的真实节拍上。
  无第三方采样，可自由使用。

## 字体

- **Noto Sans CJK SC**（正文）— SIL Open Font License 1.1
- **Smiley Sans 得意黑**（标题）— SIL Open Font License 1.1
- **JetBrains Mono**（标签/等宽）— SIL Open Font License 1.1

## 品牌与界面素材

- 落地页视觉与工作台界面截图均为本项目自有素材（`capture/`、`capture-demo/`）。
- **星采主标志（M3「月碗托星」）**：`assets/brand/stargather-m3.svg`，取自产品实际在用的品牌资产
  （`platform-api/web/public/logo-symbol.svg`，源文件 `platform-api/docs/brand/logo/m3/stargather-m3.svg`，
  2026-10-09 正式选型）。用于全片右上角固定角标与场景 3 主 logo。
  早期 `docs/brand/logo/dist/stargather-symbol-*.svg` 为已淘汰的第一轮概念稿，**本片不再使用**。
  - **版本选择（已定）**：角标与场景 3 均使用 **完整版**（深蓝底 + 米白 + 砖红小星）。
    M3 文档提到「完整版 16px 会糊、小尺寸另用简化版」，本片最小使用尺寸为 **38px**（MP4 像素），
    高于该阈值，故不启用简化版；简化版 `stargather-m3-small.svg` 仅随资产留存备用。
  - 角标不做反白/透明替换：完整版的深蓝方块在米白纸品底上是「品牌徽章」，与正片的包豪斯硬边描边语言一致；
    已实测八幕底色下角标墨色描边与奶油底占比稳定（描边 0.21–0.24，底 0.59–0.65），可辨识度不受场景影响。
- **第三方平台图标**：B站 / 抖音 / 小红书 / 快手 / 知乎 / 公众号 的几何路径取自
  **simple-icons（CC0-1.0 公共领域）**，登记表见 `platform-api/web/src/brand/platforms.ts`。
  仅用于标识「这是哪个平台」，商标归各平台所有，不作为星采自身标志、不暗示官方背书。

## 录屏素材（演示内容）

- `assets/ui/*.png`：星采演示站（`platform-api/web/dist-demo/`）的真实界面截图，由 Playwright 以
  deviceScaleFactor=2 采集（3840×2160）。
- `assets/clips/real-demo.mp4`：演示站素材库中一条**真实可播视频**的 6.2s 片段（演示数据），
  用于「素材库 → 点开 → 真的开始播」这一镜头。
- 所有演示内容均为**演示数据**，片中已标注「真实演示数据 / 演示数据 · 只读展示」。

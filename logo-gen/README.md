# logo-gen · 品牌标志生成脚本

「星采 / Stargather」品牌标志的**探索与生成脚本**留痕。最终选定方案是
**「轨道 Orbit」**（四角星 + 倾斜环带），正式资产已产出到 `platform-api/docs/brand/` 与
`platform-api/web/public/brand/`。

## 正式交付管线（改标志时跑这几个）

```bash
python3 logo-gen/orbit_final.py     # 烘焙母版 SVG（真实路径，无 mask）
python3 logo-gen/orbit_assets.py    # 生成网页图标 / APP 图标 / 横版组合
python3 logo-gen/orbit_gallery.py   # 生成交付画廊 HTML
```

依赖：`shapely`、`cairosvg`、`Pillow`。脚本按自身位置反推工作台根目录，
不写死绝对路径，clone 到任意路径都能跑（前提是 `logo-gen/` 与 `platform-api/` 仍是同级目录）。

> **不要手改产物**：`platform-api/docs/brand/` 下的 SVG/PNG 均由上述脚本生成，改标志请重跑脚本。

## 目录说明

| 路径 | 内容 |
|------|------|
| `orbit_*.py` | 「轨道」正式管线（上面三个 + `orbit_master` 几何定义 / `orbit_bake` mask 烘焙 / `orbit_sheet` 对比表） |
| `raw/` … `raw5/` | 四轮生图探索的候选（共 24 款），存 512px 缩略图 |
| `tiny/` | 三款最高分候选的 16px 可辨识度验证图 |
| `run*.py` + `prompts*.py` | 调星算生图 API 的探索脚本（每轮一份） |
| `judge*.py` / `see.py` | 把图发给视觉模型评审 / 描述（生图阶段本环境"看不了图"的替代方案） |
| `scratch/` | 一次性试验脚本，非正式管线 |
| `trace*.py` | 第三方 logo 形状溯源实验（对照 MediaCrawler webui 资源） |

探索过程的完整记录见 `platform-api/docs/brand/logo/GENERATED.md` 与
`platform-api/docs/brand/logo/README.md`。

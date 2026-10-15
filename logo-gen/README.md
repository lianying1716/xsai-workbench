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

## M3（现行）交付管线

当前正式标志是 **M3「月碗托星」**（矢量母版在 `platform-api/docs/brand/logo/m3/`）。
改标志时跑这几个：

```bash
python3 logo-gen/vectorize.py <concept.png> <out.svg> \          # 位图概念图 -> 矢量（扁平化+potrace）
    --palette "13,25,55;243,236,221;204,40,35" [--flat 已有中间图]
python3 logo-gen/m3_assets.py            # 从矢量母版导出 dist/ 全套位图
python3 logo-gen/build_frontend_brand.py # 生成前端 web/public 品牌文件（favicon/侧栏/登录）
```

方法说明与踩坑见 `logo-gen/trace-lab/README.md`；标志选型与规范见
`platform-api/docs/brand/logo/m3/README.md`、`platform-api/docs/brand/logo/GENERATED.md`。

## 目录说明

| 路径 | 内容 |
|------|------|
| `orbit_*.py` | 「轨道」旧管线（历史，已被 M3 取代，见下） |
| `raw/` … `raw5/` | 四轮生图探索的候选（共 24 款），存 512px 缩略图 |
| `raw6/` … `raw12/` | 2026-10-09 各轮生图候选（`BRIEF.md` + `prompts6|…|12.py`）；**m3 是最终选型** |
| `m3-pipeline/` | **M3 矢量化中间产物**（扁平化结果），`vectorize.py --flat` 离线复现用 |
| `tiny/` | 三款最高分候选的 16px 可辨识度验证图 |
| `run*.py` + `prompts*.py` | 调星算生图 API 的探索脚本（每轮一份） |
| `judge*.py` / `see.py` | 把图发给视觉模型评审 / 描述（生图阶段本环境"看不了图"的替代方案） |
| `scratch/` | 一次性试验脚本，非正式管线 |
| `trace*.py` | 第三方 logo 形状溯源实验（对照 MediaCrawler webui 资源） |

探索过程的完整记录见 `platform-api/docs/brand/logo/GENERATED.md` 与
`platform-api/docs/brand/logo/README.md`。

> **探索脚本含绝对路径**：`run*.py` / `prompts*.py` / `gallery*.py` / `judge*.py` / `see.py` /
> `scratch/` / `trace*.py` 是当时一次性运行的探索脚本，其中的绝对路径已脱敏。
> 它们只作历史留痕，**不要直接复用**；需要重跑时请自行把路径改成本机路径。
> 真正需要长期维护的只有上面「正式交付管线」里的 `orbit_*.py`（已改为相对路径）。

> **与 `platform-api/docs/brand/logo/tools/` 的关系**：那边的 `gallery.py` / `judge2.py` /
> `prompts4.py` / `run4.py` / `see.py` 是本目录同名探索脚本的副本（为让 `platform-api` 仓库
> 自包含品牌资产复现流程）。**改探索脚本时两处需同步**；正式管线以本目录 `orbit_*.py` 为准。

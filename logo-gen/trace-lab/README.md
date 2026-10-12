# trace-lab · 位图转矢量的方法实验

这里是「把 AI 概念图变成可用矢量」的方法实验区。**结论已固化**在
`../vectorize.py`（可复用管线），本目录保留各方案的脚本与对照结果。

## 实验过的方案与结论（针对 M3，同一张图）

| 方案 | 脚本 | 结果 |
|---|---|---|
| vtracer 彩色描摹（多参数/分层/4 色量化） | `_tests/`、`img2svg.py` | 边缘毛刺、丢光晕 · 2–5 分 |
| potrace 直接描原图 | `img2svg2.py` | 渐变被切成碎色块 · 6 分 |
| 视觉大模型直接生成 SVG | `llm_svg.py` | 结构走形、悬空线 · 4 分 |
| **扁平化 + potrace（采用）** | `flatten.py` + `potrace_svg.py` → `../vectorize.py` | 干净平滑无噪点 · **9 分** |

## 关键坑（踩过，记下来）

1. **potracer 的 `Bitmap.__init__` 会内部 `invert()`**——必须传 `~mask`，
   否则描出来永远是整幅画布的外框（我们一开始就中招，SVG 只有 800 字节）。
2. **不能对带渐变的图直接描摹**：任何阈值/量化都会把光晕切成碎块。
   先让生图模型"扁平化"成纯色平涂，再描摹，质量才达标。
3. **`vtracer` 与 `potrace` 用途不同**：前者适合照片/复杂图，后者适合 logo 这类扁平形状。

## 目录

- `potrace_svg.py` —— 修好的 potrace 封装（mask → 平滑贝塞尔 path）
- `flatten.py` —— 调 gpt-image-2.5 把图扁平化
- `img2svg.py` / `img2svg2.py` —— 分层描摹实验脚本（kmeans / 指定调色板）
- `llm_svg.py` —— 让视觉大模型直接输出 SVG 的实验
- `_tests/` —— 各方案的渲染结果与对照图（`_tests/FINAL-cmp.png` 是最终对照）

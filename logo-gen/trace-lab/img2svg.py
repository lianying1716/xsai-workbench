#!/usr/bin/env python3
"""图片 -> 多色 SVG 的通用管线（分层 potrace）。

思路：
1. 读图，按主色做 k-means 量化 -> N 个色层（比"彩色描摹"稳定得多）；
2. 每个非背景色层单独二值化，去噪；
3. 每层用 potrace 描摹成平滑贝塞尔路径；
4. 合成：背景色矩形 + 各层 path（evenodd 处理孔洞）。

用法：
  python3 img2svg.py in.png out.svg --colors 6 [--crop x0,y0,x1,y1] [--blur 1.0] \
      [--minpx 60] [--turd 30] [--upscale 2]
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from potrace_svg import mask_to_paths


def kmeans(a, k, iters=30, seed=7):
    px = a.reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(seed)
    # k-means++ 初始化
    idx = [int(rng.integers(len(px)))]
    for _ in range(k-1):
        d = np.min(((px[:, None] - px[idx][None]) ** 2).sum(-1), 1)
        idx.append(int(np.argmax(d)))
    C = px[idx].copy()
    for _ in range(iters):
        lab = ((px[:, None] - C[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            sel = lab == j
            if sel.any():
                C[j] = px[sel].mean(0)
    lab = ((px[:, None] - C[None]) ** 2).sum(-1).argmin(1).reshape(a.shape[:2])
    return C.round().astype(int), lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--colors", type=int, default=6)
    ap.add_argument("--crop", default=None)
    ap.add_argument("--blur", type=float, default=1.0)
    ap.add_argument("--minpx", type=int, default=60)
    ap.add_argument("--turd", type=int, default=30)
    ap.add_argument("--upscale", type=int, default=2)
    ap.add_argument("--alphamax", type=float, default=1.0)
    args = ap.parse_args()

    im = Image.open(args.src).convert("RGB")
    if args.crop:
        x0, y0, x1, y1 = [int(v) for v in args.crop.split(",")]
        im = im.crop((x0, y0, x1, y1))
    if args.upscale > 1:
        im = im.resize((im.width*args.upscale, im.height*args.upscale), Image.LANCZOS)
    if args.blur:
        im = im.filter(ImageFilter.GaussianBlur(args.blur))
    a = np.asarray(im)
    h, w, _ = a.shape
    pal, lab = kmeans(a, args.colors)
    counts = np.bincount(lab.ravel(), minlength=args.colors)
    bg = int(counts.argmax())

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
           f'<rect width="{w}" height="{h}" fill="rgb{tuple(int(v) for v in pal[bg])}"/>']
    nlayers = 0
    for j in range(args.colors):
        if j == bg:
            continue
        m = lab == j
        if m.sum() < args.minpx:
            continue
        # 去噪：只保留 >= minpx 的连通块
        l2, n2 = ndimage.label(m)
        if n2:
            sizes = ndimage.sum(m, l2, range(1, n2+1))
            keep = np.zeros_like(m)
            for i in range(n2):
                if sizes[i] >= args.minpx:
                    keep |= (l2 == i+1)
            m = keep
        if not m.any():
            continue
        ds = mask_to_paths(m, turd=args.turd, alphamax=args.alphamax)
        col = f"rgb{tuple(int(v) for v in pal[j])}"
        for d in ds:
            svg.append(f'<path d="{d}" fill="{col}" fill-rule="evenodd"/>')
        nlayers += 1
    svg.append("</svg>")
    Path(args.out).write_text("\n".join(svg), encoding="utf-8")
    print(f"ok colors={args.colors} used_layers={nlayers} bg=rgb{tuple(int(v) for v in pal[bg])} size={w}x{h} -> {args.out}")


if __name__ == "__main__":
    main()

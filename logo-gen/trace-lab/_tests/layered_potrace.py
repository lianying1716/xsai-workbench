#!/usr/bin/env python3
"""分层 potrace 矢量化：把位图按主色拆成若干二值层，逐层用 potrace 描摹出平滑贝塞尔曲线，
再合成一个多色 SVG。比 vtracer 的彩色描摹干净得多。

用法: python3 layered_potrace.py <in.png> <out.svg> [--colors 4] [--crop x0,y0,x1,y1]
"""
import argparse, io, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
from potrace import Bitmap


def kmeans_palette(a, k, iters=25, seed=0):
    """简易 k-means，返回 (palette[k,3], labels[h,w])。"""
    rng = np.random.default_rng(seed)
    px = a.reshape(-1, 3).astype(np.float32)
    # init: k-means++ light
    idx = [int(rng.integers(len(px)))]
    for _ in range(k - 1):
        d = np.min(((px[:, None, :] - px[idx][None, :, :]) ** 2).sum(-1), axis=1)
        idx.append(int(np.argmax(d)))
    C = px[idx].copy()
    for _ in range(iters):
        d = ((px[:, None, :] - C[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                C[j] = px[m].mean(0)
    d = ((px[:, None, :] - C[None, :, :]) ** 2).sum(-1)
    lab = d.argmin(1).reshape(a.shape[:2])
    return C.round().astype(int), lab


def mask_to_d(mask, turd=100, alphamax=1.0, opttolerance=0.2):
    """二值 mask -> potrace 路径的 d 字符串（含孔洞，evenodd）。"""
    m = np.ascontiguousarray(mask.astype(np.uint8))
    bm = Bitmap(m)
    paths = bm.trace(turdsize=turd, alphamax=alphamax, opttolerance=opttolerance)
    ds = []
    for curve in paths:
        # potrace 的 y 轴：像素中心偏移 0.5
        pts = curve
        d = _curve_to_d(pts)
        if d:
            ds.append(d)
    return ds


def _curve_to_d(curve):
    # potracer Curve: 子路径列表，每段有 start_point / control1 / control2 / end_point
    out = []
    for seg in curve:
        sp = seg.start_point
        out.append(f"M {sp.x:.2f} {sp.y:.2f}")
        for c in seg:
            c1, c2, ep = c.c1, c.c2, c.end_point
            out.append(f"C {c1.x:.2f} {c1.y:.2f} {c2.x:.2f} {c2.y:.2f} {ep.x:.2f} {ep.y:.2f}")
        out.append("Z")
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--colors", type=int, default=4)
    ap.add_argument("--crop", default=None)
    ap.add_argument("--blur", type=float, default=1.2)
    ap.add_argument("--minpx", type=int, default=60)
    ap.add_argument("--turd", type=int, default=40)
    args = ap.parse_args()

    im = Image.open(args.src).convert("RGB")
    if args.crop:
        x0, y0, x1, y1 = [int(v) for v in args.crop.split(",")]
        im = im.crop((x0, y0, x1, y1))
    if args.blur:
        im = im.filter(ImageFilter.GaussianBlur(args.blur))
    a = np.asarray(im)
    h, w, _ = a.shape
    pal, labels = kmeans_palette(a, args.colors)

    # 背景 = 面积最大的颜色
    counts = np.bincount(labels.ravel(), minlength=args.colors)
    bg = int(counts.argmax())

    layers = []
    for j in range(args.colors):
        if j == bg:
            continue
        m = labels == j
        if m.sum() < args.minpx:
            continue
        # 清理小噪点
        lab, n = ndimage.label(m)
        if n:
            sizes = ndimage.sum(m, lab, range(1, n + 1))
            keep = np.zeros_like(m)
            for i in range(n):
                if sizes[i] >= args.minpx:
                    keep |= (lab == i + 1)
            m = keep
        layers.append((j, m, tuple(int(v) for v in pal[j])))

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">']
    svg.append(f'<rect width="{w}" height="{h}" fill="rgb{tuple(int(v) for v in pal[bg])}"/>')
    for j, m, rgb in layers:
        ds = mask_to_d(m, turd=args.turd)
        fill = f"rgb{rgb}"
        for d in ds:
            svg.append(f'<path d="{d}" fill="{fill}" fill-rule="evenodd"/>')
    svg.append("</svg>")
    Path(args.out).write_text("\n".join(svg), encoding="utf-8")
    print(f"colors={args.colors} bg={tuple(int(v) for v in pal[bg])} layers={len(layers)} -> {args.out}")


if __name__ == "__main__":
    main()

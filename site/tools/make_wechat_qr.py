#!/usr/bin/env python3
"""把微信个人名片原图裁成适合网页展示的二维码素材。

原图来自微信「保存图片」，四周留白很大、底部带一行小字说明，直接放网页里
二维码会显得很小、文字也不可读。这里只裁出二维码本体并保留安全留白
（quiet zone），文字说明由网页自己写，便于做「长按识别」的提示。

输入：仓库根目录的 微信图片_*.jpg
输出：assets/wechat-qr.png / .webp
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def find_source() -> Path:
    explicit = ROOT.parent.glob("微信图片_*.jpg")
    for p in explicit:
        return p
    raise SystemExit("找不到微信二维码原图（微信图片_*.jpg）")


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else find_source()
    im = Image.open(src).convert("L")
    a = np.array(im)

    # 二维码是整张图里唯一的大块深色区域，取它的黑点包围盒
    dark = a < 128
    # 只在下半部分找，避开顶部昵称
    h, w = a.shape
    region = dark[int(h * 0.25):, :]
    ys, xs = np.where(region)
    y0, y1 = ys.min() + int(h * 0.25), ys.max() + int(h * 0.25)
    x0, x1 = xs.min(), xs.max()

    # 二维码本体 + 安全留白（quiet zone）。取边长的 12%，留足识别余量。
    size = max(x1 - x0, y1 - y0)
    pad = int(size * 0.12)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    half = size // 2 + pad
    left, top = cx - half, cy - half
    right, bottom = cx + half, cy + half

    # 裁到图像范围内，不足的部分用白色补，保证正方形
    box = Image.new("L", (right - left, bottom - top), 255)
    sx0, sy0 = max(0, left), max(0, top)
    sx1, sy1 = min(w, right), min(h, bottom)
    box.paste(im.crop((sx0, sy0, sx1, sy1)), (sx0 - left, sy0 - top))

    # 输出为纯黑白的 RGB（网页上哪怕被纸纹底色盖住也要清晰）
    box = box.convert("RGB")
    out_png = ASSETS / "wechat-qr.png"
    out_webp = ASSETS / "wechat-qr.webp"
    box.save(out_png)
    # 二维码对压缩伪影很敏感：不缩放、不用有损 WebP，保持原生尺寸无损输出。
    # 尺寸够用（540 模块区 + 64 留白），放大交给浏览器做。
    box.save(out_webp, "WEBP", lossless=True, method=6)

    print(f"source: {src}")
    print(f"QR bbox: x {x0}..{x1}, y {y0}..{y1}  (size {size}px)")
    print(f"saved: {out_png.name} {box.size}, {out_webp.name} {box.size} (lossless)")


if __name__ == "__main__":
    main()

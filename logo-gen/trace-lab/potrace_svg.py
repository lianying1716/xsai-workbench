#!/usr/bin/env python3
"""把二值 mask 用 potrace 描摹成 SVG path（处理后端差异）。
potracer 的 Curve 提供 start_point 与 segments；segment 可能是 CornerSegment
（用 .c 作为二次曲线控制点）或 BezierSegment（.c1/.c2 三次）。
"""
import numpy as np
from potrace import Bitmap, BezierSegment, CornerSegment
from scipy import ndimage
from PIL import Image, ImageFilter


def _fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def curve_to_d(curve, dy=0.0, dx=0.0):
    sp = curve.start_point
    parts = [f"M {_fmt(sp.x+dx)} {_fmt(sp.y+dy)}"]
    for seg in curve.segments:
        ep = seg.end_point
        if isinstance(seg, BezierSegment):
            c1, c2 = seg.c1, seg.c2
            parts.append(f"C {_fmt(c1.x+dx)} {_fmt(c1.y+dy)} "
                         f"{_fmt(c2.x+dx)} {_fmt(c2.y+dy)} "
                         f"{_fmt(ep.x+dx)} {_fmt(ep.y+dy)}")
        else:  # CornerSegment: .c 是二次贝塞尔控制点
            c = getattr(seg, "c", None)
            if c is None:
                parts.append(f"L {_fmt(ep.x+dx)} {_fmt(ep.y+dy)}")
            else:
                parts.append(f"Q {_fmt(c.x+dx)} {_fmt(c.y+dy)} "
                             f"{_fmt(ep.x+dx)} {_fmt(ep.y+dy)}")
    parts.append("Z")
    return " ".join(parts)


def mask_to_paths(mask, turd=30, alphamax=1.0, opttol=0.2, ox=0.0, oy=0.0):
    # 注意：potracer 的 Bitmap.__init__ 会 invert()，所以传 ~mask 才得到该形状本身
    bm = Bitmap(np.ascontiguousarray(~mask.astype(bool)))
    paths = bm.trace(turdsize=turd, alphamax=alphamax, opttolerance=opttol)
    return [curve_to_d(c, dx=ox, dy=oy) for c in paths]


if __name__ == "__main__":
    # quick self-test
    yy, xx = np.mgrid[0:100, 0:100]
    m = (((xx-50)**2+(yy-50)**2) < 35**2)
    ds = mask_to_paths(m, turd=2)
    print("paths:", len(ds))
    print(ds[0][:160])

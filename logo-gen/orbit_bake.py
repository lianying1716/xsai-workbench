"""把「轨道」标记的 mask 烘焙成真实路径几何（evenodd 孔洞）。

生图/探索阶段用 <mask> 很方便，但印刷、切割、刺绣、单色化都需要
真实轮廓路径。这里用 shapely 做布尔运算，输出不带 mask 的纯路径 SVG。
"""
import math, os, sys
from shapely.geometry import Polygon, Point
from shapely.affinity import rotate, translate
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orbit_master as M

CX = CY = M.CX, M.CY
CXV, CYV = M.CX, M.CY


def star_poly(r_out, ratio, n=8):
    r_in = r_out * ratio
    pts = []
    for i in range(n):
        ang = math.radians(-90 + i * 45)
        r = r_out if i % 2 == 0 else r_in
        pts.append((CXV + r * math.cos(ang), CYV + r * math.sin(ang)))
    return Polygon(pts)


def ellipse_poly(a, b, rot, n=256):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = a * math.cos(t), b * math.sin(t)
        th = math.radians(rot)
        pts.append((CXV + x * math.cos(th) - y * math.sin(th),
                    CYV + x * math.sin(th) + y * math.cos(th)))
    return Polygon(pts)


def half_plane(rot, sign):
    """y_local sign>=0 的半平面（大矩形），用于把环带切成前后两半。"""
    th = math.radians(rot)
    # local y 的单位方向（global）
    ux, uy = -math.sin(th), math.cos(th)
    # local x 的单位方向
    vx, vy = math.cos(th), math.sin(th)
    L = 800
    p = lambda s, t: (CXV + sign * ux * L * s + vx * t * L,
                      CYV + sign * uy * L * s + vy * t * L)
    return Polygon([p(0, -1), p(0, 1), p(1, 1), p(1, -1)])


def rnd(poly, nd=2):
    """把 shapely 几何转成 SVG path（evenodd）。"""
    def ring(coords):
        return "M " + " L ".join(f"{x:.{nd}f} {y:.{nd}f}" for x, y in coords) + " Z"
    def one(p):
        parts = [ring(p.exterior.coords)]
        for hole in p.interiors:
            parts.append(ring(hole.coords))
        return "".join(parts)
    if poly.is_empty:
        return ""
    if poly.geom_type == "Polygon":
        return one(poly)
    if poly.geom_type == "MultiPolygon":
        return "".join(one(g) for g in poly.geoms)
    if poly.geom_type == "GeometryCollection":
        return "".join(rnd(g, nd) for g in poly.geoms if g.geom_type in ("Polygon", "MultiPolygon"))
    return ""


def build(fill, fill2=None, gap=M.GAP, r_out=M.R_OUT, ratio=M.RATIO,
          a=M.A, b=M.B, band=M.BAND, theta=M.THETA, gap_scale=1.0,
          title="星采 Stargather"):
    band_fill = fill if fill2 is None else fill2
    star = star_poly(r_out, ratio)
    half = band / 2.0
    ring_outer = ellipse_poly(a + half, b + half, theta)
    ring_inner = ellipse_poly(max(a - half, 1e-3), max(b - half, 1e-3), theta)
    ring = ring_outer.difference(ring_inner)
    front = ring.intersection(half_plane(theta, +1))
    back = ring.intersection(half_plane(theta, -1))

    star_cut = star.difference(front.buffer(gap, join_style=2))
    back_cut = back.difference(star.buffer(gap * 0.45, join_style=2))

    d_back = rnd(back_cut)
    d_star = rnd(star_cut)
    d_front = rnd(front)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" '
        f'role="img" aria-label="{title}"><title>{title}</title>'
        f'<path d="{d_back}" fill="{band_fill}" fill-rule="evenodd"/>'
        f'<path d="{d_star}" fill="{fill}" fill-rule="evenodd"/>'
        f'<path d="{d_front}" fill="{band_fill}" fill-rule="evenodd"/>'
        '</svg>')


SMALL = dict(r_out=92, ratio=0.50, a=70, b=30, band=20, theta=-25, gap=11)

if __name__ == "__main__":
    import cairosvg
    from PIL import Image
    import numpy as np
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/baked"
    os.makedirs(out, exist_ok=True)
    for slug, kw, bg in [("primary", dict(fill=M.INK, fill2=M.RED), M.CREAM),
                         ("inverse", dict(fill=M.CREAM, fill2=M.RED), M.INK)]:
        svg = build(**kw)
        p = os.path.join(out, f"{slug}.svg")
        open(p, "w").write(svg)
        cairosvg.svg2png(url=p, write_to=os.path.join(out, f"{slug}.png"), output_width=512,
                         output_height=512, background_color=bg)
        print("wrote", p, len(svg), "bytes")
    # 与 mask 版逐像素比对
    import cairosvg
    a1 = np.array(Image.open(os.path.join(out, "primary.png")).convert("RGBA"))
    cairosvg.svg2png(url="/tmp/orb5/primary.svg", write_to="/tmp/_mask.png", output_width=512, output_height=512,
                     background_color=M.CREAM)
    a2 = np.array(Image.open("/tmp/_mask.png").convert("RGBA"))
    diff = np.abs(a1[:, :, :3].astype(int) - a2[:, :, :3].astype(int)).max()
    frac = (np.abs(a1[:, :, :3].astype(int) - a2[:, :, :3].astype(int)).max(axis=2) > 24).mean()
    print(f"baked vs mask: max channel diff {diff}, differing pixels {frac*100:.2f}%")

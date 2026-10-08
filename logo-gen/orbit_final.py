"""星采 Stargather ·「轨道 Orbit」最终交付管线。

产出：
  docs/brand/logo/orbit/      母版 SVG（烘焙真实路径，无 mask）
  web/public/brand/orbit/     画廊用的 PNG（多尺寸 + 反白）
  web/public/brand/orbit-gallery.html

几何来自视觉评审选优：
  主标  g2  星尖 80 / 内比 0.44，轨道 82×30 带宽 15 倾角 -22°
  小尺寸 s4 星尖 92 / 内比 0.50，轨道 70×30 带宽 20 倾角 -25°（加宽缝，16px 不糊）
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import Polygon
import orbit_master as M

REPO = "/www/wwwroot/xsai-workbench/platform-api"
MASTER_DIR = f"{REPO}/docs/brand/logo/orbit"
WEB_DIR = f"{REPO}/web/public/brand/orbit"

G2 = dict(r_out=80, ratio=0.5176, a=82, b=30, band=15, theta=-22)
S4 = dict(r_out=92, ratio=0.5176, a=70, b=30, band=20, theta=-25)

CXV = CYV = 128.0


def _star(r_out, ratio):
    r_in = r_out * ratio
    pts = []
    for i in range(8):
        ang = math.radians(-90 + i * 45)
        r = r_out if i % 2 == 0 else r_in
        pts.append((CXV + r * math.cos(ang), CYV + r * math.sin(ang)))
    return Polygon(pts)


def _ellipse(a, b, rot, n=48):
    pts = []
    th = math.radians(rot)
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = a * math.cos(t), b * math.sin(t)
        pts.append((CXV + x * math.cos(th) - y * math.sin(th),
                    CYV + x * math.sin(th) + y * math.cos(th)))
    return Polygon(pts)


def _half(rot, sign):
    th = math.radians(rot)
    ux, uy = -math.sin(th), math.cos(th)   # 局部 y 方向
    vx, vy = math.cos(th), math.sin(th)    # 局部 x 方向
    L = 900
    return Polygon([(CXV + sign * ux * L * s + vx * t * L, CYV + sign * uy * L * s + vy * t * L)
                    for s, t in ((0, -1), (0, 1), (1, 1), (1, -1))])


def _path(geom, nd=2):
    def ring(cs):
        return "M " + " L ".join(f"{x:.{nd}f} {y:.{nd}f}" for x, y in cs) + " Z"
    def one(p):
        return ring(p.exterior.coords) + "".join(ring(h.coords) for h in p.interiors)
    if geom.is_empty:
        return ""
    if geom.geom_type == "Polygon":
        return one(geom)
    if geom.geom_type == "MultiPolygon":
        return "".join(one(g) for g in geom.geoms)
    return "".join(_path(g, nd) for g in getattr(geom, "geoms", []) if g.geom_type.startswith("Poly"))


def build(star_fill, band_fill, gap=4.0, star_gap_scale=1.0, geo=None, title="星采 Stargather"):
    g = dict(G2 if geo is None else geo)
    r_out, ratio, a, b, band, theta = g["r_out"], g["ratio"], g["a"], g["b"], g["band"], g["theta"]
    star = _star(r_out, ratio)
    half = band / 2.0
    ring = _ellipse(a + half, b + half, theta).difference(_ellipse(max(a - half, 1e-3), max(b - half, 1e-3), theta))
    front = ring.intersection(_half(theta, +1))
    back = ring.intersection(_half(theta, -1))
    star_cut = star.difference(front.buffer(gap * star_gap_scale, join_style=2))
    back_cut = back.difference(star.buffer(gap * 0.5, join_style=2))
    # 采样折线留了冗余顶点，简化到亚像素精度（0.25/256 ≈ 0.1%）
    tol = 0.15
    star_cut = star_cut.simplify(tol, preserve_topology=True)
    back_cut = back_cut.simplify(tol, preserve_topology=True)
    front = front.simplify(tol, preserve_topology=True)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" '
            f'role="img" aria-label="{title}"><title>{title}</title>'
            f'<path d="{_path(back_cut)}" fill="{band_fill}" fill-rule="evenodd"/>'
            f'<path d="{_path(star_cut)}" fill="{star_fill}" fill-rule="evenodd"/>'
            f'<path d="{_path(front)}" fill="{band_fill}" fill-rule="evenodd"/>'
            '</svg>')


# ---- 交付清单 ----
ITEMS = [
    # slug, 名称, 说明, star_fill, band_fill, 背景, geo
    ("primary",  "墨星 · 红轨", "主标。星用墨，轨道用品牌砖红，两层对比最强。", M.INK, M.RED, M.CREAM, G2),
    ("inverse",  "米白星 · 红轨", "深底 / 深色模式主标。星改米白，缝改墨色。", M.CREAM, M.RED, M.INK, G2),
    ("blue",     "墨星 · 蓝轨", "辅助。轨道换辅助蓝，用于需要与红区分的信息图。", M.INK, M.BLUE, M.CREAM, G2),
    ("small",    "小尺寸版", "16×16 专用：星放大、轨道加宽、缝加宽，缩到 16px 仍分得清两层。", M.INK, M.RED, M.CREAM, S4),
    ("mono-ink",   "单色 · 墨", "所有同色场景（一份黑白印刷、雕刻、水印）。", M.INK, M.INK, M.CREAM, G2),
    ("mono-cream", "单色 · 米白", "深底单色。", M.CREAM, M.CREAM, M.INK, G2),
]


def main():
    os.makedirs(MASTER_DIR, exist_ok=True)
    os.makedirs(WEB_DIR, exist_ok=True)
    import cairosvg
    from PIL import Image
    for slug, name, desc, sf, bf, bg, geo in ITEMS:
        mono = sf == bf
        gap = 8.0 if mono else 4.0
        svg = build(sf, bf, gap=gap, geo=geo)
        open(f"{MASTER_DIR}/stargather-orbit-{slug}.svg", "w", encoding="utf-8").write(svg)
    # 干净的大师母版 = 单色墨（用于派生 favicon / 单色）
    open(f"{MASTER_DIR}/stargather-orbit-master.svg", "w", encoding="utf-8").write(
        build(M.INK, M.INK, gap=8.0, geo=G2))
    print("master svg ->", MASTER_DIR)


if __name__ == "__main__":
    main()

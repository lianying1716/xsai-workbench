"""星采 Stargather ·「轨道 / Orbit」标志母版生成器。

选定几何（视觉评审选优，代号 g2）：
    四角星（尖半径 80 / 内比 0.44） + 倾斜椭圆环带（82×30，带宽 15，倾角 -22°）
环带在星前 / 星后交错穿插 —— 用 mask 打出**透明缝**（真 knock-out），
因此标记不带任何背景色，放在深底/浅底/图片上都成立，且单色化后仍保留前后层次。

全部为纯矢量：无渐变、无滤镜、无位图、无文本。
"""
import math, os

CX = CY = 128.0
R_OUT, RATIO = 80.0, 0.44
A, B, BAND, THETA = 82.0, 30.0, 15.0, -22.0
GAP = 4.0          # 双色版缝宽（相对值）
GAP_MONO = 8.0     # 单色版缝宽（同色时需更宽才读得出穿插）

# ---- 品牌色（对齐 web/src/styles/tokens.css 的 V3 令牌）----
INK   = "#1A1512"
RED   = "#CC2823"
CREAM = "#F3F0E7"
BLUE  = "#0B58BB"


def star_path(cx=CX, cy=CY, r_out=R_OUT, ratio=RATIO):
    r_in = r_out * ratio
    pts = []
    for i in range(8):
        ang = math.radians(-90 + i * 45)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"


def _ept(t, a, b, cx, cy, rot):
    th = math.radians(rot)
    x, y = a * math.cos(t), b * math.sin(t)
    return (cx + x * math.cos(th) - y * math.sin(th),
            cy + x * math.sin(th) + y * math.cos(th))


def arc(t0, t1, a=A, b=B, rot=THETA, cx=CX, cy=CY, n=72):
    """椭圆弧 → 采样折线。

    刻意不用 SVG 的椭圆弧命令：在掩膜里大弧标志与描边宽度的组合
    容易把弧线画到画布之外（实测会溢出 viewBox），采样折线在任何
    渲染器里都稳定，且 72 段对 256 画布远低于像素精度。
    """
    pts = [_ept(t0 + (t1 - t0) * i / n, a, b, cx, cy, rot) for i in range(n + 1)]
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts)


def symbol(fill, fill2=None, gap=GAP, mono=False, node_fill=None,
           r_out=R_OUT, ratio=RATIO, a=A, b=B, band=BAND, theta=THETA,
           title="星采 Stargather"):
    """轨道标记。

    fill  : 星的颜色
    fill2 : 环带的颜色（None 表示与星同色 = 单色版）
    mono  : True 时使用更宽的缝以在同色下保住穿插层次
    """
    band_fill = fill if fill2 is None else fill2
    if mono:
        gap = max(gap, GAP_MONO)
    star = star_path(r_out=r_out, ratio=ratio)
    front = arc(0.0, math.pi, a, b, theta)
    back = arc(math.pi, 2 * math.pi, a, b, theta)
    # 星上的槽：前环外扩 gap → 在星上打出缝
    slot_w = band + 2 * gap
    # 环被星压住：星外扩 gap/2 → 在环上打出缝
    occl_w = gap * 0.9

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" '
        f'role="img" aria-label="{title}">'
        f'<title>{title}</title>'
        '<defs>'
        '<mask id="slot" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256">'
        '<rect width="256" height="256" fill="#fff"/>'
        f'<path d="{front}" fill="none" stroke="#000" stroke-width="{slot_w:.2f}"/>'
        '</mask>'
        '<mask id="occl" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256">'
        '<rect width="256" height="256" fill="#fff"/>'
        f'<path d="{star}" fill="#000" stroke="#000" stroke-width="{occl_w:.2f}"/>'
        '</mask>'
        '</defs>'
        # 1) 后半环（被星遮挡，留缝）
        f'<path d="{back}" fill="none" stroke="{band_fill}" stroke-width="{band:.2f}" mask="url(#occl)"/>'
        # 2) 星（前环位置开槽）
        f'<path d="{star}" fill="{fill}" mask="url(#slot)"/>'
        # 3) 前半环（压在星上）
        f'<path d="{front}" fill="none" stroke="{band_fill}" stroke-width="{band:.2f}"/>'
        # 4) 可选：轨道上的运行节点（小圆点），让"轨道"读成"有物在跑"
        + (node_svg(node_fill, a, b, band, theta) if node_fill else '')
        + '</svg>'
    )


def node_svg(color, a=A, b=B, band=BAND, theta=THETA, t=0.72 * math.pi, r=None):
    """在环带上放一个实心圆节点（默认落在前半环右上段）。"""
    x, y = _ept(t, a, b, CX, CY, theta)
    r = r if r is not None else band * 0.62
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{color}"/>'


def node_pos(t=0.72 * math.pi):
    return _ept(t, A, B, CX, CY, THETA)


# ---- 交付配色 ----
PRIMARY = dict(fill=INK, fill2=RED)                 # 墨星 · 红轨（主用）
INVERSE = dict(fill=CREAM, fill2=RED)               # 米白星 · 红轨（深底）
BLUE_BAND = dict(fill=INK, fill2=BLUE)                # 墨星 · 蓝轨（辅助）
MONO_INK   = dict(fill=INK,   mono=True)            # 单色 · 墨
MONO_RED   = dict(fill=RED,   mono=True)            # 单色 · 砖红
MONO_CREAM = dict(fill=CREAM, mono=True)            # 单色 · 米白（深底）

RED_STAR = dict(fill=RED, fill2=INK)             # 砖红星 · 墨轨
NODE     = dict(fill=INK, fill2=RED, node_fill=BLUE)   # 墨星 · 红轨 · 蓝节点

COLORWAYS = {
    "primary":    ("墨星 · 红轨",     PRIMARY,    CREAM),
    "inverse":    ("米白星 · 红轨",   INVERSE,    INK),
    "blue":       ("墨星 · 蓝轨",     BLUE_BAND,  CREAM),
    "red-star":   ("砖红星 · 墨轨",   RED_STAR,   CREAM),
    "node":       ("墨星 · 红轨 · 蓝节点", NODE,  CREAM),
    "mono-ink":   ("单色 · 墨",       MONO_INK,   CREAM),
    "mono-red":   ("单色 · 砖红",     MONO_RED,   CREAM),
    "mono-cream": ("单色 · 米白",     MONO_CREAM, INK),
}


def write_all(root):
    os.makedirs(root, exist_ok=True)
    for slug, (label, kw, bg) in COLORWAYS.items():
        open(os.path.join(root, f"stargather-orbit-{slug}.svg"), "w", encoding="utf-8").write(symbol(**kw))
    return list(COLORWAYS)


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "/www/wwwroot/xsai-workbench/logo-gen/orbit"
    print("wrote", root, write_all(root))

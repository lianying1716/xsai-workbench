"""E「轨道」精确矢量母版生成器。
四角星 + 倾斜椭圆环带，上下交错穿插（真矢量 weave）。
"""
import math

V = 256.0
CX = CY = 128.0
R_OUT = 78.0
R_RATIO = 0.355
A, B = 88.0, 36.0        # 环带椭圆半长轴 / 半短轴
BAND = 20.0              # 环带宽度
THETA = -24.0            # 环带倾斜角（负 = 右端上翘）
GAP = 5.0


def star_path(cx, cy, r_out, ratio):
    r_in = r_out * ratio
    pts = []
    for i in range(8):
        ang = math.radians(-90 + i * 45)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"


def ellipse_pt(t, a, b, cx, cy, rot_deg):
    th = math.radians(rot_deg)
    x, y = a * math.cos(t), b * math.sin(t)
    return (cx + x * math.cos(th) - y * math.sin(th),
            cy + x * math.sin(th) + y * math.cos(th))


def arc(a, b, cx, cy, rot_deg, t0, t1, sweep=1):
    p0 = ellipse_pt(t0, a, b, cx, cy, rot_deg)
    p1 = ellipse_pt(t1, a, b, cx, cy, rot_deg)
    return (f"M {p0[0]:.2f} {p0[1]:.2f} A {a:.2f} {b:.2f} {rot_deg:.2f} 0 0 {sweep} "
            f"{p1[0]:.2f} {p1[1]:.2f}")


def build(star_fill, band_fill, gap=GAP, small=False, star=None, band=None):
    star = star or star_path(CX, CY, R_OUT, R_RATIO)
    band = band or f'<path d="{arc(A,B,CX,CY,THETA,0,math.pi)}" fill="none" stroke="{{b}}" stroke-width="{BAND:.2f}"/>'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">',
           '<defs>']
    out.append('<mask id="m_slot" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256">'
               '<rect width="256" height="256" fill="#fff"/>'
               f'<path d="{arc(A,B,CX,CY,THETA,0,math.pi)}" fill="none" stroke="#000" '
               f'stroke-width="{BAND + 2*gap:.2f}"/></mask>')
    out.append('<mask id="m_occl" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256">'
               '<rect width="256" height="256" fill="#fff"/>'
               f'<path d="{star}" fill="#000" stroke="#000" stroke-width="{gap*0.8:.2f}"/></mask>')
    out.append('</defs>')
    # 1) 后半环（被星遮挡，留缝）
    out.append(f'<path d="{arc(A,B,CX,CY,THETA,math.pi,2*math.pi)}" fill="none" stroke="{band_fill}" '
               f'stroke-width="{BAND:.2f}" mask="url(#m_occl)"/>')
    # 2) 星（前环处开槽，除非小尺寸）
    out.append(f'<path d="{star}" fill="{star_fill}"'
               + ('' if small else ' mask="url(#m_slot)"') + '/>')
    # 3) 前半环（压在星上）
    out.append(f'<path d="{arc(A,B,CX,CY,THETA,0,math.pi)}" fill="none" stroke="{band_fill}" '
               f'stroke-width="{BAND:.2f}"/>')
    out.append('</svg>')
    return ''.join(out)


if __name__ == "__main__":
    import sys
    s = build("#1A1512", "#CC2823")
    open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/orbit.svg", "w").write(s)
    print("ok", len(s))

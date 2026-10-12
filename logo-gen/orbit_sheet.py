"""生成「轨道」几何变体对比表，用视觉模型评审。"""
import math, os, sys
sys.path.insert(0, "/path/to/xsai-workbench/logo-gen")
from PIL import Image, ImageDraw
import cairosvg

V = 256.0

def star_path(cx, cy, r_out, ratio):
    r_in = r_out * ratio
    pts = []
    for i in range(8):
        ang = math.radians(-90 + i * 45)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"

def ellipse_pt(t, a, b, cx, cy, rot):
    th = math.radians(rot); x, y = a*math.cos(t), b*math.sin(t)
    return (cx + x*math.cos(th) - y*math.sin(th), cy + x*math.sin(th) + y*math.cos(th))

def arc(a,b,cx,cy,rot,t0,t1):
    p0 = ellipse_pt(t0,a,b,cx,cy,rot); p1 = ellipse_pt(t1,a,b,cx,cy,rot)
    return f"M {p0[0]:.2f} {p0[1]:.2f} A {a:.2f} {b:.2f} {rot:.2f} 0 0 1 {p1[0]:.2f} {p1[1]:.2f}"

def build(star_fill="#1A1512", band_fill="#CC2823", A=88, B=36, BAND=20, THETA=-24,
          R_OUT=78, RATIO=0.355, gap=5.0, small=False):
    cx = cy = 128.0
    star = star_path(cx, cy, R_OUT, RATIO)
    front = arc(A,B,cx,cy,THETA,0,math.pi)
    back  = arc(A,B,cx,cy,THETA,math.pi,2*math.pi)
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">','<defs>']
    if gap > 0 and not small:
        o.append(f'<mask id="s" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256">'
                 f'<rect width="256" height="256" fill="#fff"/>'
                 f'<path d="{front}" fill="none" stroke="#000" stroke-width="{BAND+2*gap:.2f}"/></mask>')
        o.append(f'<mask id="o" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256">'
                 f'<rect width="256" height="256" fill="#fff"/>'
                 f'<path d="{star}" fill="#000" stroke="#000" stroke-width="{gap*0.9:.2f}"/></mask>')
    o.append('</defs>')
    o.append(f'<path d="{back}" fill="none" stroke="{band_fill}" stroke-width="{BAND:.2f}"'
             + (f' mask="url(#o)"' if gap>0 and not small else '') + '/>')
    o.append(f'<path d="{star}" fill="{star_fill}"' + (f' mask="url(#s)"' if gap>0 and not small else '') + '/>')
    o.append(f'<path d="{front}" fill="none" stroke="{band_fill}" stroke-width="{BAND:.2f}"/>')
    o.append('</svg>')
    return ''.join(o)

def render(svg, out, size, bg="#F3F0E7"):
    open("/tmp/_t.svg","w").write(svg)
    cairosvg.svg2png(url="/tmp/_t.svg", write_to=out, output_width=size, output_height=size,
                     background_color=bg)

VARIANTS = [
 ("v1-narrow",  dict(A=86,  B=32, BAND=18, THETA=-28, R_OUT=78, RATIO=0.36, gap=4)),
 ("v2-wide",    dict(A=102, B=42, BAND=18, THETA=-24, R_OUT=72, RATIO=0.36, gap=4)),
 ("v3-chunky",  dict(A=94,  B=40, BAND=26, THETA=-22, R_OUT=72, RATIO=0.36, gap=4)),
 ("v4-nogap",   dict(A=96,  B=38, BAND=24, THETA=-24, R_OUT=76, RATIO=0.36, gap=0)),
 ("v5-shallow", dict(A=100, B=30, BAND=22, THETA=-14, R_OUT=78, RATIO=0.36, gap=4)),
 ("v6-steep",   dict(A=88,  B=44, BAND=22, THETA=-38, R_OUT=76, RATIO=0.36, gap=4)),
 ("v7-hug",     dict(A=76,  B=28, BAND=18, THETA=-25, R_OUT=80, RATIO=0.36, gap=4)),
 ("v8-fattilt", dict(A=100, B=52, BAND=22, THETA=-25, R_OUT=70, RATIO=0.36, gap=4)),
]

if __name__ == "__main__":
    from PIL import ImageFont
    cell, pad, cols = 300, 34, 4
    rows = (len(VARIANTS)+cols-1)//cols
    W = cols*(cell+pad)+pad; H = rows*(cell+pad+40)+pad
    sheet = Image.new("RGB",(W,H),(255,255,255)); d = ImageDraw.Draw(sheet)
    for i,(name,kw) in enumerate(VARIANTS):
        r,c = divmod(i,cols)
        x = pad + c*(cell+pad); y = pad + r*(cell+pad+40)
        png = f"/tmp/var_{name}.png"
        render(build(**kw), png, cell, bg="#F3F0E7")
        im = Image.open(png).convert("RGB"); sheet.paste(im,(x,y))
        small = f"/tmp/var_{name}_16.png"
        render(build(**kw, small=True), small, 16, bg="#F3F0E7")
        s = Image.open(small).convert("RGB").resize((96,96), Image.NEAREST)
        sheet.paste(s,(x+cell-100,y+cell-100))
        d.rectangle([x,y,x+cell-1,y+cell-1], outline=(180,180,180))
        d.text((x+4, y+cell+6), name, fill=(0,0,0))
    sheet.save("/tmp/orbit_variants.png")
    print("sheet", sheet.size)

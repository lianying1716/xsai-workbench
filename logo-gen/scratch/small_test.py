import sys, os, math
sys.path.insert(0,'/www/wwwroot/xsai-workbench/logo-gen')
import orbit_master as M
import cairosvg
from PIL import Image, ImageDraw

CANDS = [
 ("s1", dict(r_out=88, ratio=0.50, a=78, b=30, band=20, theta=-20, gap=9)),
 ("s2", dict(r_out=90, ratio=0.52, a=74, b=32, band=22, theta=-18, gap=10)),
 ("s3", dict(r_out=86, ratio=0.48, a=80, b=34, band=24, theta=-22, gap=9)),
 ("s4", dict(r_out=92, ratio=0.50, a=70, b=30, band=20, theta=-25, gap=11)),
 ("s5", dict(r_out=88, ratio=0.46, a=82, b=30, band=18, theta=-20, gap=8)),
]
out='/tmp/small'; os.makedirs(out, exist_ok=True)
rows=[]
for name,kw in CANDS:
    svg=M.symbol(fill=M.INK, fill2=M.RED, **kw)
    p=f"{out}/{name}.svg"; open(p,'w').write(svg)
    shots=[]
    for s in (16,24,32):
        cairosvg.svg2png(url=p, write_to=f"{out}/{name}-{s}.png", output_width=s, output_height=s, background_color=M.CREAM)
        shots.append((s,f"{out}/{name}-{s}.png"))
    rows.append((name,shots))

cell=200; pad=18
W=len(rows)*(3*cell+40+pad)+pad
H=cell+2*pad+80
sheet=Image.new("RGB",(W,H),(255,255,255)); dr=ImageDraw.Draw(sheet)
x=pad
for name,shots in rows:
    y=pad
    for s,p in shots:
        im=Image.open(p).convert("RGB").resize((cell,cell), Image.NEAREST)
        sheet.paste(im,(x,y)); 
        dr.text((x+4,y+cell+4), f"{name}@{s}", fill=(0,0,0))
        y+=cell+26
    x+=cell+40+pad
sheet.save(f"{out}/sheet.png"); print(sheet.size)

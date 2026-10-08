import sys, os
sys.path.insert(0,'/www/wwwroot/xsai-workbench/logo-gen')
import orbit_sheet as O
from PIL import Image, ImageDraw
import cairosvg

CANDS = [
  ("g1",  dict(A=78, B=26, BAND=14, THETA=-20, R_OUT=80, RATIO=0.46, gap=4)),
  ("g2",  dict(A=82, B=30, BAND=15, THETA=-22, R_OUT=80, RATIO=0.44, gap=4)),
  ("g3",  dict(A=74, B=34, BAND=15, THETA=-18, R_OUT=82, RATIO=0.46, gap=4)),
  ("g4",  dict(A=86, B=32, BAND=16, THETA=-26, R_OUT=78, RATIO=0.42, gap=4)),
]

def render(kw, out, size, bg="#F3F0E7"):
    open('/tmp/_g.svg','w').write(O.build(star_fill="#1A1512", band_fill="#CC2823", **kw))
    cairosvg.svg2png(url='/tmp/_g.svg', write_to=out, output_width=size, output_height=size, background_color=bg)

cell=340; pad=26; cols=4
W=cols*(cell+pad)+pad; H=cell+2*pad+60
sheet=Image.new("RGB",(W,H),(255,255,255)); dr=ImageDraw.Draw(sheet)
for i,(name,kw) in enumerate(CANDS):
    x=pad+i*(cell+pad); y=pad
    render(kw, '/tmp/gc.png', cell)
    sheet.paste(Image.open('/tmp/gc.png').convert("RGB"),(x,y))
    # 16px blown up
    render(kw, '/tmp/gc16.png', 16, bg="#F3F0E7")
    s=Image.open('/tmp/gc16.png').convert("RGB").resize((96,96), Image.NEAREST)
    sheet.paste(s,(x+cell-100,y+cell-100))
    # dark reversed
    render(kw, '/tmp/gcd.png', cell, bg="#1A1512")
    dr.rectangle([x,y,x+cell-1,y+cell-1], outline=(120,120,120))
    dr.text((x+4,y+cell+8), name, fill=(0,0,0))
sheet.save('/tmp/geo_judge.png'); print(sheet.size)

import sys, math
sys.path.insert(0,'/www/wwwroot/xsai-workbench/logo-gen')
import orbit_sheet as O
from PIL import Image
import cairosvg

def ascii_show(svg, tag, size=56):
    open('/tmp/_m.svg','w').write(svg)
    cairosvg.svg2png(url='/tmp/_m.svg', write_to='/tmp/_m.png', output_width=224, output_height=224,
                     background_color='#F3F0E7')
    im = Image.open('/tmp/_m.png').convert('RGB').resize((size,size//2+ size//2//1))
    im = Image.open('/tmp/_m.png').convert('RGB').resize((size,size//2))
    chars=' .:-=+*#%@'
    print('==', tag, '==')
    for y in range(size//2):
        row=''
        for x in range(size):
            r,g,b = im.getpixel((x,y))
            if r>140 and g<115 and b<115: row+='R'
            else:
                lum=0.3*r+0.59*g+0.11*b
                row+=chars[min(9,int((255-lum)/256*10))]
        print(row)

for tag,kw in [
  ("thick r.42 tuned", dict(A=84,B=30,BAND=15,THETA=-22,R_OUT=80,RATIO=0.42,gap=4)),
  ("thick r.50 tuned", dict(A=80,B=28,BAND=14,THETA=-20,R_OUT=80,RATIO=0.50,gap=4)),
  ("cross a80 b34",    dict(A=80,B=34,BAND=15,THETA=-18,R_OUT=80,RATIO=0.44,gap=4)),
  ("cross a74 b36",    dict(A=74,B=36,BAND=15,THETA=-16,R_OUT=82,RATIO=0.46,gap=4)),
]:
    ascii_show(O.build(**kw), tag)

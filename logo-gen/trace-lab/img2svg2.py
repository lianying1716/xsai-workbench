#!/usr/bin/env python3
"""图片 -> 多色 SVG（分层 potrace，支持指定调色板 + 平滑控制）。

改进点（相对 img2svg.py）：
- 可传 --palette 固定调色板（用品牌色而不是 kmeans 混出的脏色）；
- 高倍上采样 + 高斯模糊 -> potrace，得到更平滑的曲线；
- --clean 做形态学开闭，去掉分层残留的碎块；
- 支持 --gradient 时给最大层加线性渐变（保留一点原图光影）。
"""
import argparse, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
sys.path.insert(0, str(Path(__file__).resolve().parent))
from potrace_svg import mask_to_paths


def parse_palette(s):
    cols=[]
    for part in s.split(";"):
        part=part.strip()
        if not part: continue
        r,g,b=[int(v) for v in part.split(",")]
        cols.append((r,g,b))
    return np.array(cols, np.int32)


def nearest_palette(a, pal):
    d=((a[:,:,None,:].astype(np.int32)-pal[None,None,:,:])**2).sum(-1)
    return d.argmin(-1)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--palette", default=None, help='"r,g,b;r,g,b;..." 不传则 kmeans')
    ap.add_argument("--colors", type=int, default=6)
    ap.add_argument("--crop", default=None)
    ap.add_argument("--blur", type=float, default=2.0)
    ap.add_argument("--minpx", type=int, default=400)
    ap.add_argument("--turd", type=int, default=120)
    ap.add_argument("--upscale", type=int, default=3)
    ap.add_argument("--alphamax", type=float, default=1.0)
    ap.add_argument("--clean", type=int, default=1, help="形态学开闭次数")
    args=ap.parse_args()

    im=Image.open(args.src).convert("RGB")
    if args.crop:
        x0,y0,x1,y1=[int(v) for v in args.crop.split(",")]
        im=im.crop((x0,y0,x1,y1))
    if args.upscale>1:
        im=im.resize((im.width*args.upscale, im.height*args.upscale), Image.LANCZOS)
    if args.blur:
        im=im.filter(ImageFilter.GaussianBlur(args.blur))
    a=np.asarray(im); h,w,_=a.shape

    if args.palette:
        pal=parse_palette(args.palette)
        lab=nearest_palette(a, pal)
        k=len(pal)
    else:
        from img2svg import kmeans
        p,lab=kmeans(a,args.colors); pal=p; k=args.colors

    cnt=np.bincount(lab.ravel(), minlength=k)
    bg=int(cnt.argmax())
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
         f'<rect width="{w}" height="{h}" fill="rgb{tuple(int(v) for v in pal[bg])}"/>']
    used=0
    # 层顺序：面积大的先画，小的后画（避免被盖）
    order=[j for j in np.argsort(-cnt) if j!=bg]
    for j in order:
        if cnt[j] < args.minpx: continue
        m=(lab==j)
        if args.clean:
            m=ndimage.binary_opening(m, np.ones((3,3)), iterations=args.clean)
            m=ndimage.binary_closing(m, np.ones((5,5)), iterations=args.clean)
        l2,n2=ndimage.label(m)
        if n2:
            sizes=ndimage.sum(m,l2,range(1,n2+1)); keep=np.zeros_like(m)
            for i in range(n2):
                if sizes[i]>=args.minpx: keep|=(l2==i+1)
            m=keep
        if not m.any(): continue
        ds=mask_to_paths(m, turd=args.turd, alphamax=args.alphamax)
        col=f"rgb{tuple(int(v) for v in pal[j])}"
        for d in ds:
            svg.append(f'<path d="{d}" fill="{col}" fill-rule="evenodd"/>')
        used+=1
    svg.append("</svg>")
    Path(args.out).write_text("\n".join(svg),encoding="utf-8")
    print(f"ok k={k} used={used} bg=rgb{tuple(int(v) for v in pal[bg])} {w}x{h} -> {args.out}")

if __name__=="__main__":
    main()

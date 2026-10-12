#!/usr/bin/env python3
"""把 M3 矢量母版做成前端要用的全套品牌文件，写入 platform-api/web/public/。

产物：
  logo-symbol.svg        登录页用（带夜空底，浅底上显示）
  logo-symbol-dark.svg   侧栏用（透明底，深底上显示）
  logo-symbol-small.svg  小尺寸简化版（带底）
  favicon.svg / favicon.ico / favicon-16/32/48.png
  icon-192.png / icon-512.png / maskable-512.png / apple-touch-icon.png
"""
import re, io
from pathlib import Path
import cairosvg
from PIL import Image
from scipy import ndimage
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
M3 = ROOT / "platform-api" / "docs" / "brand" / "logo" / "m3"
FULL_SVG = M3 / "stargather-m3.svg"
SMALL_SVG = M3 / "small" / "stargather-m3-small.svg"
OUT = ROOT / "platform-api" / "web" / "public"
NAVY = "#0D1937"
CREAM = "#F3ECDD"


def read_parts(svg_path):
    """返回 (viewBox, [ (d, fill) ... ])"""
    s = Path(svg_path).read_text(encoding="utf-8")
    vb = re.search(r'viewBox="([^"]+)"', s).group(1)
    parts = re.findall(r'<path d="([^"]+)" fill="([^"]+)"', s)
    return vb, parts


def write_svg(path, vb, parts, bg=None, title="星采 Stargather"):
    body = []
    if bg:
        x, y, w, h = [float(v) for v in vb.split()]
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}"/>')
    for d, fill in parts:
        body.append(f'<path d="{d}" fill="{fill}" fill-rule="evenodd"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="256" height="256" '
           f'role="img" aria-label="{title}"><title>{title}</title>' + "".join(body) + "</svg>")
    Path(path).write_text(svg, encoding="utf-8")
    return svg


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vb_f, parts_f = read_parts(FULL_SVG)
    vb_s, parts_s = read_parts(SMALL_SVG)

    # 1) 登录页：夜空底（浅色卡片上）
    write_svg(OUT / "logo-symbol.svg", vb_f, parts_f, bg=NAVY)
    # 2) 侧栏：透明底（深色侧栏上）
    write_svg(OUT / "logo-symbol-dark.svg", vb_f, parts_f, bg=None)
    # 3) 小尺寸简化版（带底）
    write_svg(OUT / "logo-symbol-small.svg", vb_s, parts_s, bg=NAVY)
    # 4) favicon.svg = 简化版带底
    fav_svg = write_svg(OUT / "favicon.svg", vb_s, parts_s, bg=NAVY)

    # 位图：favicon 用简化版（16px 才认得出）
    def render(svg_text, size, bg):
        png = cairosvg.svg2png(bytestring=svg_text.encode(), output_width=size, output_height=size,
                               background_color=bg)
        return Image.open(io.BytesIO(png)).convert("RGBA")

    small_svg_text = (OUT / "logo-symbol-small.svg").read_text(encoding="utf-8")
    full_svg_text = (OUT / "logo-symbol.svg").read_text(encoding="utf-8")

    for s in (16, 32, 48):
        render(small_svg_text, s, NAVY).convert("RGB").save(OUT / f"favicon-{s}.png")
    render(small_svg_text, 256, NAVY).convert("RGB").save(
        OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    # PWA 图标用完整版（大尺寸，细节好看）
    render(full_svg_text, 192, NAVY).convert("RGB").save(OUT / "icon-192.png")
    render(full_svg_text, 512, NAVY).convert("RGB").save(OUT / "icon-512.png")

    # maskable：安全边距（内容缩到 64%）
    for name, size, pad in (("maskable-512", 512, 0.18), ("apple-touch-icon", 180, 0.10)):
        inner = int(size * (1 - 2 * pad))
        canvas = Image.new("RGB", (size, size), NAVY)
        canvas.paste(render(full_svg_text, inner, NAVY).convert("RGB"),
                     ((size - inner) // 2, (size - inner) // 2))
        canvas.save(OUT / f"{name}.png")

    print("frontend brand assets written ->", OUT)


if __name__ == "__main__":
    main()

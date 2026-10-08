"""星采「轨道」全套交付：网页图标 / APP 图标 / 横版组合 / 画廊。"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orbit_final as F
import orbit_master as M
import cairosvg
from PIL import Image

WORKBENCH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(WORKBENCH, "platform-api")
MASTER = f"{REPO}/docs/brand/logo/orbit"
OUT = f"{REPO}/docs/brand/logo/orbit/dist"
WEB = f"{REPO}/web/public"
BRAND = f"{WEB}/brand/orbit"
os.makedirs(OUT, exist_ok=True)
os.makedirs(BRAND, exist_ok=True)


def png(svg_text, path, size, bg=None):
    tmp = "/tmp/_a.svg"
    open(tmp, "w").write(svg_text)
    cairosvg.svg2png(url=tmp, write_to=path, output_width=size, output_height=size,
                     background_color=bg)
    return path


def icon_tile(svg_text, size, bg, fg_pad=0.20, radius=0.22):
    """圆角方块底 + 居中标，用于 app icon / maskable。"""
    inner = int(size * (1 - 2 * fg_pad))
    png(svg_text, "/tmp/_inner.png", inner, bg=None)
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(tile)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * radius), fill=bg)
    ch = Image.open("/tmp/_inner.png").convert("RGBA")
    tile.alpha_composite(ch, ((size - ch.width) // 2, (size - ch.height) // 2))
    tile.save("/tmp/_tile.png")
    return "/tmp/_tile.png"


PRIMARY = F.build(M.INK, M.RED, gap=4.0, geo=F.G2)
SMALL = F.build(M.INK, M.RED, gap=4.0, geo=F.S4)
MONO_INK = F.build(M.INK, M.INK, gap=8.0, geo=F.G2)
MONO_CREAM = F.build(M.CREAM, M.CREAM, gap=8.0, geo=F.G2)

# 自然留白（画布 256，图形 bbox 约 48..208）
def main():
    # --- 网页图标（透明背景，用于 index.html）---
    for name, svg, size, bg in [
        ("favicon-16.png", SMALL, 16, None),
        ("favicon-32.png", SMALL, 32, None),
        ("favicon-48.png", SMALL, 48, None),
        ("apple-touch-icon.png", PRIMARY, 180, M.CREAM),
        ("icon-192.png", PRIMARY, 192, M.CREAM),
        ("icon-512.png", PRIMARY, 512, M.CREAM),
    ]:
        png(svg, f"{OUT}/{name}", size, bg=bg)
    # maskable：四周留 20% 安全区
    tile = icon_tile(MONO_CREAM, 512, M.INK, fg_pad=0.22, radius=0.0)
    Image.open(tile).save(f"{OUT}/maskable-512.png")
    # APP 图标：品牌色圆角方块
    Image.open(icon_tile(MONO_CREAM, 512, M.RED, fg_pad=0.22)).save(f"{OUT}/app-icon-512.png")
    Image.open(icon_tile(MONO_INK, 512, M.CREAM, fg_pad=0.22)).save(f"{OUT}/app-icon-light-512.png")
    Image.open(icon_tile(MONO_CREAM, 512, M.INK, fg_pad=0.22)).save(f"{OUT}/app-icon-dark-512.png")
    # favicon.ico
    im = Image.open(f"{OUT}/favicon-48.png").convert("RGBA")
    im.save(f"{OUT}/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # 单色 SVG
    open(f"{OUT}/favicon.svg", "w").write(SMALL)
    open(f"{MASTER}/stargather-orbit-favicon.svg", "w").write(SMALL)
    print("web icons ->", OUT)


if __name__ == "__main__":
    main()

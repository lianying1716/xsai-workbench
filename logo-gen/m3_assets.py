#!/usr/bin/env python3
"""星采 Stargather · M3 资产导出（从矢量母版渲染）。

母版：platform-api/docs/brand/logo/m3/stargather-m3.svg（由 vectorize.py 管线生成）
输出：dist/ 全套位图 + 网页副本。

由矢量渲染的好处：任意尺寸都锐利，favicon 不会模糊。
"""
from pathlib import Path
import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
M3 = ROOT / "platform-api" / "docs" / "brand" / "logo" / "m3"
SVG = M3 / "stargather-m3.svg"
DIST = M3 / "dist"
WEB = ROOT / "platform-api" / "web" / "public" / "brand" / "m3"
ICONS = (1024, 512, 256, 192, 180, 128, 64, 48, 32, 16)


def render(size: int) -> Image.Image:
    png = cairosvg.svg2png(url=str(SVG), output_width=size, output_height=size)
    import io
    return Image.open(io.BytesIO(png)).convert("RGB")


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)

    for s in ICONS:
        render(s).save(DIST / f"symbol-{s}.png")
    render(1024).save(DIST / "symbol-master.png")

    # favicon.ico（多尺寸）
    ico = render(256)
    ico.save(DIST / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    # apple-touch / maskable：在深蓝底上加安全边距
    for name, size, pad in (("apple-touch-icon", 180, 0.10), ("maskable-512", 512, 0.18)):
        inner = int(size * (1 - 2 * pad))
        canvas = Image.new("RGB", (size, size), (13, 25, 55))
        canvas.paste(render(inner), ((size - inner) // 2, (size - inner) // 2))
        canvas.save(DIST / f"{name}.png")

    # 网页副本
    for p in DIST.glob("*.png"):
        (WEB / p.name).write_bytes(p.read_bytes())
    (WEB / "favicon.ico").write_bytes((DIST / "favicon.ico").read_bytes())
    (WEB / "stargather-m3.svg").write_bytes(SVG.read_bytes())
    print("done ->", DIST)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""绘制「素材墙」插画（纯代码，中文精确渲染）。

生图模型无法可靠渲染中文，会把卡片里的文字画成拉丁伪文字。
这张图的文字区域本来就由我们自己控制，因此改用 Pillow 精确绘制：
暖米白底 + 砖红/钴蓝/芥末黄 + 粗描边，与站点其余插画同风格。

输出：assets/art/media-wall.png（再由 build 流程转 webp）
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1344, 768
OUT = Path(__file__).resolve().parent.parent / "assets" / "art" / "media-wall.png"

PAPER = (245, 240, 230)
CARD = (255, 253, 248)
INK = (22, 21, 26)
RED = (193, 58, 44)
BLUE = (34, 73, 201)
YELLOW = (238, 181, 27)
GREEN = (30, 122, 77)
MUTED = (109, 104, 95)
SOFT = (236, 229, 214)

FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def f(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


T_TITLE = f(FONT_BOLD, 26)
T_CARD = f(FONT_BOLD, 21)
T_SMALL = f(FONT_REG, 17)
T_TINY = f(FONT_REG, 15)
T_PANEL = f(FONT_BOLD, 22)
T_STAT = f(FONT_BOLD, 30)


def rounded(d: ImageDraw.ImageDraw, box, r, fill, outline=INK, width=3):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def text(d, xy, s, font, fill=INK, anchor="la"):
    d.text(xy, s, font=font, fill=fill, anchor=anchor)


def bar(d, x, y, w, h, color):
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=color)


def thumb(d, box, color):
    """卡片缩略图：一个抽象几何图形，不含任何文字。"""
    x0, y0, x1, y1 = box
    rounded(d, box, 10, color, INK, 3)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d.polygon(
        [(cx, cy - 26), (cx + 26, cy), (cx, cy + 26), (cx - 26, cy)],
        fill=CARD,
        outline=INK,
        width=3,
    )


def main() -> None:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # 细网格底纹
    for x in range(0, W, 48):
        d.line([(x, 0), (x, H)], fill=(238, 233, 222), width=1)
    for y in range(0, H, 48):
        d.line([(0, y), (W, y)], fill=(238, 233, 222), width=1)

    # 标题
    text(d, (64, 56), "素材库", f(FONT_BOLD, 40))
    text(d, (64, 112), "每条素材都带着元数据、转录与分析结果", T_SMALL, MUTED)
    d.line([(64, 150), (620, 150)], fill=INK, width=3)

    # ---- 左侧：素材卡片网格 2 列 x 3 行 ----
    cards = [
        ("影视飓风", "B站 · 已完成转录", RED),
        ("科普研究所", "抖音 · 已 AI 分析", BLUE),
        ("对标账号合集", "小红书 · 已判类", YELLOW),
        ("露营装备测评", "关键词采集 · 已入库", GREEN),
        ("产品发布会回放", "快手 · 待分析", BLUE),
        ("个人收藏夹", "知乎 · 已完成转录", RED),
    ]
    cw, ch, gap = 302, 168, 22
    ox, oy = 64, 186
    for i, (title, meta, color) in enumerate(cards):
        r, c = divmod(i, 2)
        x = ox + c * (cw + gap)
        y = oy + r * (ch + gap)
        rounded(d, [x, y, x + cw, y + ch], 12, CARD, INK, 3)
        thumb(d, [x + 16, y + 16, x + 110, y + 110], color)
        text(d, (x + 128, y + 30), title, T_CARD)
        text(d, (x + 128, y + 64), meta, T_TINY, MUTED)
        bar(d, x + 128, y + 96, 150, 10, (222, 216, 203))
        bar(d, x + 128, y + 114, 112, 10, (222, 216, 203))
        # 状态点
        d.ellipse([x + cw - 36, y + 26, x + cw - 20, y + 42], fill=GREEN, outline=INK, width=2)

    # ---- 右侧：分析面板 ----
    px, py, pw, ph = 748, 186, 532, 506
    rounded(d, [px, py, px + pw, py + ph], 14, CARD, INK, 3)

    # 面板标题
    d.rectangle([px, py, px + pw, py + 58], fill=INK)
    text(d, (px + 22, py + 28), "内容分析", T_PANEL, (255, 255, 255), "lm")
    d.ellipse([px + pw - 42, py + 22, px + pw - 20, py + 44], fill=YELLOW, outline=(255, 255, 255), width=2)

    text(d, (px + 22, py + 82), "自动摘要", T_CARD)
    d.rounded_rectangle([px + 22, py + 116, px + pw - 22, py + 208], radius=8, fill=SOFT, outline=INK, width=2)
    bar(d, px + 38, py + 136, 400, 11, (206, 199, 185))
    bar(d, px + 38, py + 158, 440, 11, (206, 199, 185))
    bar(d, px + 38, py + 180, 300, 11, (206, 199, 185))

    text(d, (px + 22, py + 228), "内容标签", T_CARD)
    tags = ["教程", "科普", "对标", "口播", "测评"]
    tx = px + 22
    for i, t in enumerate(tags):
        tw = d.textlength(t, font=T_TINY) + 30
        fill = [RED, BLUE, YELLOW, GREEN, SOFT][i]
        rounded(d, [tx, py + 262, tx + tw, py + 300], 8, fill, INK, 2)
        text(d, (tx + tw / 2, py + 281), t, T_TINY, (255, 255, 255) if fill != YELLOW else INK, "mm")
        tx += tw + 12

    text(d, (px + 22, py + 322), "转录进度", T_CARD)
    prog = [("已完成", 96, GREEN), ("处理中", 62, BLUE), ("待处理", 24, YELLOW)]
    for i, (label, pct, color) in enumerate(prog):
        yy = py + 360 + i * 44
        text(d, (px + 22, yy), label, T_TINY, MUTED)
        bx, bw = px + 118, 300
        d.rounded_rectangle([bx, yy - 4, bx + bw, yy + 16], radius=10, fill=SOFT, outline=INK, width=2)
        d.rounded_rectangle([bx, yy - 4, bx + int(bw * pct / 100), yy + 16], radius=10, fill=color, outline=INK, width=2)
        text(d, (px + pw - 26, yy + 6), f"{pct}%", T_TINY, INK, "rm")

    # 底部统计
    stats = [("128", "素材"), ("96", "已转录"), ("41", "已分析")]
    sy = py + 442
    for i, (n, label) in enumerate(stats):
        sx = px + 22 + i * 162
        text(d, (sx, sy), n, T_STAT)
        text(d, (sx, sy + 36), label, T_TINY, MUTED)

    img.save(OUT)
    print(f"saved {OUT} {img.size}")


if __name__ == "__main__":
    main()

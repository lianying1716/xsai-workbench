"""生成「轨道」logo 交付画廊（局域网可看）+ 横版组合。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orbit_final as F
import orbit_master as M
import cairosvg
from PIL import Image

REPO = "/www/wwwroot/xsai-workbench/platform-api"
BRAND = f"{REPO}/web/public/brand/orbit"
os.makedirs(BRAND, exist_ok=True)

PRIMARY = F.build(M.INK, M.RED, gap=4.0, geo=F.G2)
SMALL   = F.build(M.INK, M.RED, gap=4.0, geo=F.S4)
INV     = F.build(M.CREAM, M.RED, gap=4.0, geo=F.G2)
BLUE    = F.build(M.INK, M.BLUE, gap=4.0, geo=F.G2)
MONO_I  = F.build(M.INK, M.INK, gap=8.0, geo=F.G2)
MONO_C  = F.build(M.CREAM, M.CREAM, gap=8.0, geo=F.G2)


def png(svg_text, name, size, bg=None, resample=Image.LANCZOS):
    p = f"{BRAND}/{name}"
    open("/tmp/_g.svg", "w").write(svg_text)
    cairosvg.svg2png(url="/tmp/_g.svg", write_to=p, output_width=size, output_height=size, background_color=bg)
    return name


VARIANTS = [
    ("primary", "主标 · 墨星红轨", PRIMARY, M.CREAM, "默认使用。米白底、墨色星、砖红轨道，两层对比最强。"),
    ("inverse", "深底版 · 米白星红轨", INV, M.INK, "深色背景与深色模式使用。"),
    ("blue", "辅助 · 墨星蓝轨", BLUE, M.CREAM, "需要与砖红区分时（图表、分类标签）。"),
    ("small", "小尺寸版 · 16px 专用", SMALL, M.CREAM, "星更大、轨道更粗、缝更宽，缩到 16px 仍分得清两层。"),
    ("mono-ink", "单色 · 墨", MONO_I, M.CREAM, "黑白印刷、雕刻、水印等只有一个颜色的场景。"),
    ("mono-cream", "单色 · 米白", MONO_C, M.INK, "深底单色。"),
]

cards = []
for slug, name, svg, bg, desc in VARIANTS:
    big = png(svg, f"{slug}-big.png", 300, bg)
    s64 = png(svg, f"{slug}-s64.png", 64, bg)
    s32 = png(svg, f"{slug}-s32.png", 32, bg)
    s16 = png(svg, f"{slug}-s16.png", 16, bg)
    inv_bg = M.INK if bg == M.CREAM else M.CREAM
    inv = png(svg, f"{slug}-check.png", 56, inv_bg)
    cards.append(f'''
  <article class="card">
    <div class="art" style="background:{bg}"><img src="/brand/orbit/{big}" alt="{name}"></div>
    <h2>{name}</h2>
    <p class="desc">{desc}</p>
    <div class="ladder">
      <figure><img src="/brand/orbit/{s64}"><figcaption>64</figcaption></figure>
      <figure><img src="/brand/orbit/{s32}"><figcaption>32</figcaption></figure>
      <figure><img src="/brand/orbit/{s16}" class="px16"><figcaption>16</figcaption></figure>
      <figure class="inv" style="background:{inv_bg}"><img src="/brand/orbit/{inv}"><figcaption>反底</figcaption></figure>
    </div>
  </article>''')

# 横版组合（标 + 字）
def wordmark(bg, ink, accent, name):
    p = f"{BRAND}/{name}"
    src_svg = INV if ink != M.INK else PRIMARY
    MARK = 168
    open("/tmp/_g.svg","w").write(src_svg)
    cairosvg.svg2png(url="/tmp/_g.svg", write_to="/tmp/_mk.png", output_width=MARK, output_height=MARK)
    mark = Image.open("/tmp/_mk.png").convert("RGBA")
    from PIL import ImageDraw, ImageFont
    fp_zh = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    fp_en = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    f_zh = ImageFont.truetype(fp_zh, 96)
    f_en = ImageFont.truetype(fp_en, 40)
    # 量文字宽度
    tmp = Image.new("RGB",(10,10)); dt = ImageDraw.Draw(tmp)
    w_zh = dt.textlength("星采", font=f_zh)
    w_en = dt.textlength("STARGATHER", font=f_en)
    # 让两行宽度接近：以中文宽为准缩放英文
    scale = w_zh / w_en
    f_en = ImageFont.truetype(fp_en, max(18, int(40*scale)))
    w_en = dt.textlength("STARGATHER", font=f_en)
    gap = 24
    text_w = max(w_zh, w_en)
    H = 240
    W = int(28 + MARK + gap + text_w + 32)
    canvas = Image.new("RGB",(W,H),bg)
    canvas.paste(mark, (30, (H-MARK)//2), mark)
    d = ImageDraw.Draw(canvas)
    x0 = 30 + MARK + gap
    # 中文与英文组成一个垂直居中的文字块
    zh_h = 96; en_h = f_en.size
    total = zh_h + 6 + en_h
    y = (H - total)//2
    d.text((x0, y), "星采", font=f_zh, fill=ink)
    d.text((x0, y + zh_h + 6), "STARGATHER", font=f_en, fill=accent)
    canvas.save(p)
    return name

wm_light = wordmark(M.CREAM, M.INK, M.RED, "lockup-light.png")
wm_dark = wordmark(M.INK, M.CREAM, M.RED, "lockup-dark.png")

html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>星采 · 轨道 logo 交付</title><style>
:root {{ --ink:#1A1512; --red:#CC2823; --bg:#F3F0E7; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:36px; background:var(--bg); color:var(--ink);
  font-family:-apple-system,"PingFang SC","Noto Sans CJK SC",system-ui,sans-serif; }}
header {{ border-bottom:3px solid var(--ink); padding-bottom:16px; margin-bottom:26px; }}
h1 {{ margin:0 0 8px; font-size:32px; letter-spacing:-.01em; }}
.sub {{ color:#6b6257; font-size:14px; line-height:1.75; }}
.sub b {{ color:var(--red); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:18px; }}
.card {{ background:#fff; border:2px solid var(--ink); box-shadow:4px 4px 0 var(--ink); padding:16px; }}
.art {{ display:grid; place-items:center; min-height:180px; }}
.art img {{ width:150px; height:150px; object-fit:contain; }}
h2 {{ margin:10px 0 4px; font-size:16px; }}
.desc {{ margin:0 0 12px; font-size:13px; line-height:1.55; color:#4b463e; min-height:40px; }}
.ladder {{ display:flex; align-items:flex-end; gap:16px; border-top:1px solid #e4ddd0; padding-top:12px; }}
.ladder figure {{ margin:0; text-align:center; }}
.ladder img {{ display:block; margin:0 auto 4px; }}
.ladder .px16 {{ image-rendering:pixelated; width:32px; height:32px; }}
.ladder figcaption {{ font-size:10px; color:#8a8177; }}
.ladder .inv {{ margin-left:auto; padding:6px; }}
.lockups {{ margin-top:30px; border-top:3px solid var(--ink); padding-top:22px; }}
.lockups h2 {{ font-size:20px; margin:0 0 14px; }}
.lockups img {{ width:100%; max-width:560px; border:2px solid var(--ink); display:block; margin-bottom:14px; }}
</style></head><body>
<header>
  <h1>星采 Stargather ·「轨道 Orbit」</h1>
  <div class="sub">
    你选的 <b>E 轨道</b> 已经矢量重绘并补齐配色。<br>
    现在是<b>墨 + 砖红</b>双色系统（不再是纯黑），另有深底版 / 辅助蓝 / 单色版 / 16px 专用版。<br>
    每张都带 64 / 32 / 16 px 缩放和反底测试 —— 关键看 <b>16px</b> 那格。
  </div>
</header>
<div class="grid">{''.join(cards)}</div>
<div class="lockups">
  <h2>横版组合</h2>
  <img src="/brand/orbit/{wm_light}" alt="横版 浅底">
  <img src="/brand/orbit/{wm_dark}" alt="横版 深底">
</div>
<p style="margin-top:26px;color:#6b6257;font-size:13px;line-height:1.75">
  确认配色后我就把它接进侧栏、登录页、favicon / APP 图标，并重出品牌规范页。
</p>
</body></html>'''
open("/www/wwwroot/xsai-workbench/platform-api/web/public/brand/orbit-gallery.html","w",encoding="utf-8").write(html)
print("gallery written")

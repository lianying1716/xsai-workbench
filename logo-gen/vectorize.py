#!/usr/bin/env python3
"""位图 logo -> 干净矢量 SVG 的通用管线（本仓库验证可用）。

两段式，解决"AI 概念图带渐变/颗粒，直接描摹必崩"的问题：

  阶段1  扁平化 flatten：调星算 gpt-image-2.5 把带渐变光晕的图重画成**纯色平涂**版本
                        （构图/元素/比例不变，只去掉光影质感）。可用 --flat 跳过复用已有结果。
  阶段2  矢量化 trace  ：按调色板分层二值化 -> potrace 描摹成平滑贝塞尔 ->
                        合成多色 SVG，并归一化到指定 viewBox。

为什么不能一步到位：
  · vtracer 彩色描摹  -> 边缘毛刺、丢光晕（实测 2-5 分）
  · potrace 直接描原图 -> 渐变被切成碎色块（实测 6 分）
  · LLM 直接生成 SVG  -> 结构走形、悬空线（实测 4 分）
  · 本管线（扁平化+potrace）-> 干净平滑（实测 9 分）

用法：
  python3 vectorize.py <in.png> <out.svg> \
      [--palette "13,25,55;243,236,221;204,40,35"] [--crop x0,y0,x1,y1] \
      [--viewbox 256] [--flat flat.png] [--skip-flatten]
"""
import argparse, base64, json, os, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "trace-lab"))
from potrace_svg import mask_to_paths   # noqa: E402

API = "https://api.xsai5.xyz/v1/images/generations"
FLATTEN_PROMPT = (
    "Redraw this logo as a clean FLAT vector design. Keep the EXACT same composition, shapes, "
    "positions and proportions. Remove ALL gradients, glows, texture, shadows and noise - use only "
    "a few solid flat colors with crisp clean edges. No extra elements, no text, no watermark."
)


def flatten_via_api(src: Path, out: Path, model="gpt-image-2.5") -> bool:
    key = Path("/tmp/xk").read_text().strip()
    b64 = base64.b64encode(src.read_bytes()).decode()
    body = json.dumps({"model": model, "prompt": FLATTEN_PROMPT,
                       "size": "1024x1024", "n": 1,
                       "image": f"data:image/png;base64,{b64}"})
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    fh.write(body); fh.close()
    try:
        r = subprocess.run(["curl", "-s", "-m", "300", API,
                            "-H", f"Authorization: Bearer {key}",
                            "-H", "Content-Type: application/json",
                            "--data-binary", f"@{fh.name}"],
                           capture_output=True, text=True)
    finally:
        os.unlink(fh.name)
    try:
        d = json.loads(r.stdout)
    except Exception:
        print("  flatten: bad json", r.stdout[:160]); return False
    if "error" in d:
        print("  flatten: api error", json.dumps(d["error"], ensure_ascii=False)[:160]); return False
    url = d["data"][0].get("url")
    if not url:
        print("  flatten: no url"); return False
    subprocess.run(["curl", "-s", "-m", "300", "-o", str(out), url], check=True)
    return True


def kmeans(a, k, iters=30, seed=7):
    px = a.reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(seed)
    idx = [int(rng.integers(len(px)))]
    for _ in range(k - 1):
        d = np.min(((px[:, None] - px[idx][None]) ** 2).sum(-1), 1)
        idx.append(int(np.argmax(d)))
    C = px[idx].copy()
    for _ in range(iters):
        lab = ((px[:, None] - C[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            sel = lab == j
            if sel.any():
                C[j] = px[sel].mean(0)
    lab = ((px[:, None] - C[None]) ** 2).sum(-1).argmin(1).reshape(a.shape[:2])
    return C.round().astype(int), lab


def trace_to_svg(img: Path, palette, upscale, blur, minpx, turd, clean):
    im = Image.open(img).convert("RGB")
    if upscale > 1:
        im = im.resize((im.width * upscale, im.height * upscale), Image.LANCZOS)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im)
    if palette is not None:
        pal = np.array(palette, np.int32)
        lab = ((a[:, :, None, :].astype(np.int32) - pal[None, None]) ** 2).sum(-1).argmin(-1)
    else:
        pal, lab = kmeans(a, 5)
    k = len(pal)
    cnt = np.bincount(lab.ravel(), minlength=k)
    bg = int(cnt.argmax())
    from scipy import ndimage
    layers = []
    for j in np.argsort(-cnt):
        if j == bg or cnt[j] < minpx:
            continue
        m = (lab == j)
        if clean:
            m = ndimage.binary_opening(m, np.ones((3, 3)), iterations=clean)
            m = ndimage.binary_closing(m, np.ones((5, 5)), iterations=clean)
        l2, n2 = ndimage.label(m)
        if n2:
            sizes = ndimage.sum(m, l2, range(1, n2 + 1))
            keep = np.zeros_like(m)
            for i in range(n2):
                if sizes[i] >= minpx:
                    keep |= (l2 == i + 1)
            m = keep
        if m.any():
            layers.append((j, mask_to_paths(m, turd=turd)))
    return pal, bg, layers, im.size


def build_svg(bg_rgb, layers, pal, out_svg, viewbox=256, pad=0.06, size=(1, 1)):
    w, h = size
    xs, ys = [], []
    for _, ds in layers:
        for d in ds:
            nums = [float(v) for v in re.findall(r"-?\d*\.?\d+", d)]
            xs += nums[0::2]; ys += nums[1::2]
    if not xs:
        x0, y0, x1, y1 = 0, 0, w, h
    else:
        x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
    cw, ch = max(x1 - x0, 1), max(y1 - y0, 1)
    side = max(cw, ch) * (1 + 2 * pad)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    vx, vy = cx - side / 2, cy - side / 2

    def hexof(rgb):
        return "#%02X%02X%02X" % tuple(int(v) for v in rgb)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx:.1f} {vy:.1f} {side:.1f} {side:.1f}" '
             f'width="{viewbox}" height="{viewbox}" role="img" aria-label="星采 Stargather">',
             f'<title>星采 Stargather</title>',
             f'<rect x="{vx:.1f}" y="{vy:.1f}" width="{side:.1f}" height="{side:.1f}" fill="{hexof(bg_rgb)}"/>']
    for j, ds in layers:
        col = hexof(pal[j])
        for d in ds:
            parts.append(f'<path d="{d}" fill="{col}" fill-rule="evenodd"/>')
    parts.append("</svg>")
    Path(out_svg).write_text("\n".join(parts), encoding="utf-8")
    return Path(out_svg).stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--palette", default="13,25,55;243,236,221;204,40,35")
    ap.add_argument("--crop", default=None)
    ap.add_argument("--flat", default=None, help="复用已有的扁平化结果，跳过 API 调用")
    ap.add_argument("--skip-flatten", action="store_true")
    ap.add_argument("--upscale", type=int, default=2)
    ap.add_argument("--blur", type=float, default=1.2)
    ap.add_argument("--minpx", type=int, default=500)
    ap.add_argument("--turd", type=int, default=120)
    ap.add_argument("--clean", type=int, default=1)
    ap.add_argument("--viewbox", type=int, default=256)
    ap.add_argument("--pad", type=float, default=0.06)
    args = ap.parse_args()

    src = Path(args.src)
    work = Path(tempfile.mkdtemp(prefix="vec_"))
    img = src
    if args.crop:
        x0, y0, x1, y1 = [int(v) for v in args.crop.split(",")]
        tmp = work / "crop.png"
        Image.open(src).convert("RGB").crop((x0, y0, x1, y1)).save(tmp)
        img = tmp

    if args.skip_flatten:
        flat = img
        print("skip flatten")
    elif args.flat and Path(args.flat).exists():
        flat = Path(args.flat); print("reuse flat", flat)
    else:
        flat = work / "flat.png"
        print("flattening via gpt-image-2.5 ...")
        if not flatten_via_api(img, flat):
            print("flatten failed"); return 1

    palette = [[int(v) for v in p.split(",")] for p in args.palette.split(";")] if args.palette else None
    pal_used, bg, layers, size = trace_to_svg(flat, palette, args.upscale, args.blur,
                                              args.minpx, args.turd, args.clean)
    n = build_svg(pal_used[bg], layers, pal_used, args.out, args.viewbox, args.pad, size)
    print(f"ok -> {args.out} ({n} bytes, {len(layers)} layers, bg=#{int(pal_used[bg][0]):02X}{int(pal_used[bg][1]):02X}{int(pal_used[bg][2]):02X})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

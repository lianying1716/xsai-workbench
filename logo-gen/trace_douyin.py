"""从抖音参考位图描出干净的音符矢量（升采样 + 形态学清理 + RDP 简化）。"""
import sys, numpy as np
sys.path.insert(0, '/path/to/xsai-workbench/logo-gen')
from PIL import Image, ImageFilter
from scipy import ndimage
from trace import moore_trace, rdp, holes


def clean_note(im, box=16, dark_thr=320, up=6):
    a = np.array(im.convert('RGB')).astype(int)
    dark = a.sum(axis=2) < dark_thr
    ys, xs = np.where(dark)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
    crop = a[y0:y1 + 1, x0:x1 + 1]
    h, w, _ = crop.shape
    inner = crop[box:h - box, box:w - box]
    note = (inner.sum(axis=2) >= dark_thr)
    # 升采样 + 闭运算去毛刺
    m = Image.fromarray((note * 255).astype('uint8')).resize(
        (note.shape[1] * up, note.shape[0] * up), Image.LANCZOS)
    m = m.filter(ImageFilter.GaussianBlur(up * 0.6))
    mm = np.array(m) > 110
    mm = ndimage.binary_closing(mm, np.ones((up * 3, up * 3)))
    mm = ndimage.binary_opening(mm, np.ones((up * 2, up * 2)))
    lab, n = ndimage.label(mm)
    if n > 1:                        # 取最大连通块
        sizes = ndimage.sum(mm, lab, range(1, n + 1))
        mm = lab == (1 + int(np.argmax(sizes)))
    return mm, up


def to_path(mask, up, target=100.0, eps=0.35, ox=0.0, oy=0.0):
    """把升采样掩膜描成 path，并归一化到 target x target 的正方形（保留长宽比）。"""
    c = moore_trace(mask)
    c = rdp(c, eps * up)
    ys, xs = np.where(mask)
    # 以掩膜 bbox 为基准做等比缩放，居中放入 target 方框
    bh, bw = (ys.max() - ys.min() + 1), (xs.max() - xs.min() + 1)
    s = target / max(bh, bw)
    pts = []
    for y, x in c:
        X = (x - xs.min()) * s + ox
        Y = (y - ys.min()) * s + oy
        pts.append((X, Y))
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z", s, (bw * s, bh * s)


if __name__ == "__main__":
    ref = "/path/to/xsai-workbench/MediaCrawler/api/webui/logos/douyin.png"
    im = Image.open(ref)
    mm, up = clean_note(im)
    print("cleaned mask", mm.shape, "px", mm.sum(), "holes", len(holes(mm)))
    d, s, size = to_path(mm, up)
    print("path points", d.count("L") + 1, "normalized size", size)
    open("/tmp/dy2.txt", "w").write(d)

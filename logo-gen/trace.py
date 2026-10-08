"""从位图描出外轮廓并简化成 SVG path（Moore 邻域边界跟踪 + Douglas-Peucker）。"""
import numpy as np


def moore_trace(mask, start=None):
    """返回外轮廓点列（像素坐标，y 向下）。mask: bool 2D。"""
    h, w = mask.shape
    if start is None:
        ys, xs = np.where(mask)
        # 取最上、最左的点作起点
        i = np.lexsort((xs, ys))[0]
        start = (int(ys[i]), int(xs[i]))
    # 8 邻域，顺时针
    nbr = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]

    def get(p):
        y, x = p
        return 0 <= y < h and 0 <= x < w and mask[y, x]

    contour = [start]
    prev_dir = 6  # 从左侧进入
    cur = start
    for _ in range(200000):
        found = False
        for k in range(8):
            d = (prev_dir + 1 + k) % 8
            ny, nx = cur[0] + nbr[d][0], cur[1] + nbr[d][1]
            if get((ny, nx)):
                contour.append((ny, nx))
                prev_dir = (d + 4) % 8  # 回指方向
                cur = (ny, nx)
                found = True
                break
        if not found:
            break
        if cur == start and len(contour) > 3:
            break
    return np.array(contour, float)


def rdp(points, eps):
    """Douglas-Peucker 简化（迭代实现，避免递归深度）。"""
    if len(points) < 3:
        return points
    keep = np.zeros(len(points), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        p, q = points[i], points[j]
        seg = q - p
        L = np.hypot(*seg)
        if L == 0:
            d = np.hypot(*(points[i + 1:j] - p).T)
        else:
            rel = points[i + 1:j] - p
            d = np.abs(seg[0] * rel[:, 1] - seg[1] * rel[:, 0]) / L
        k = np.argmax(d)
        if d[k] > eps:
            m = i + 1 + k
            keep[m] = True
            stack.append((i, m))
            stack.append((m, j))
    return points[keep]


def mask_to_path(mask, eps=1.2, scale=1.0, ox=0.0, oy=0.0):
    c = moore_trace(mask)
    c = rdp(c, eps)
    pts = [((x + 0.5) * scale + ox, (y + 0.5) * scale + oy) for y, x in c]
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"


def holes(mask):
    """返回内部孔洞的掩膜列表（简单 flood fill）。"""
    from scipy import ndimage
    filled = ndimage.binary_fill_holes(mask)
    h = filled & ~mask
    lab, n = ndimage.label(h)
    out = []
    for i in range(1, n + 1):
        m = lab == i
        if m.sum() > 4:
            out.append(m)
    return out

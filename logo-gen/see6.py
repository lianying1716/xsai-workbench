import os, sys
sys.path.insert(0, "/path/to/platform-api/docs/brand/logo/tools")
from see import ask
Q = """你是资深品牌设计总监。评审这张 logo 概念图，用于产品「星采 Stargather」
（中文自媒体创作者的自动化素材采集与管理加工工具）。标准：简洁、几何、包豪斯硬边、
有力量感、缩到 16px 仍辨识、不花哨、不能像通用图标库或常见符号。

严格按格式，每项一句话：
1. 实际画的是什么：（客观描述形状+颜色）
2. 像不像现成符号/通用图标：（比如警示标志/放射/靶心/快门等）是/否 + 理由
3. 简洁度：好/一般/差 + 理由
4. 16px 辨识度：强/中/弱 + 理由
5. 小瑕疵：具体指出
6. 总分(1-10)：只给数字
7. 一句话结论：值不值得深化
"""
d = "raw6"
for f in sorted(os.listdir(d)):
    if not f.endswith(".png"): continue
    print(f"\n{'='*58}\n{f}\n{'='*58}")
    print(ask(os.path.join(d, f), Q, max_side=760))

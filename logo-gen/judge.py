"""按 logo 设计标准逐张评审（视觉模型当设计评委）。"""
import sys, os
sys.path.insert(0, "/path/to/xsai-workbench/logo-gen")
from see import ask

Q = """你是资深品牌设计总监。请评审这张 logo 概念图，用于一个叫"星采"的产品：
自媒体创作的自动化素材管理加工工具，面向中文创作者。
视觉调性要求：简洁、几何、有力量感、能缩到 16px 仍可辨识、不要花哨。

请严格按以下格式回答，每项一句话，不要客套：
1. 实际画的是什么：（客观描述）
2. 辨识度（16px 是否还认得出）：强/中/弱 + 理由
3. 简洁度：好/一般/差 + 理由
4. 是否像现成模板或常见 cliché：是/否 + 理由
5. 小瑕疵（对齐/比例/对称/留白问题）：具体指出
6. 总分（1-10）：只给数字
7. 一句话结论：这个方向值不值得继续深化
"""

for f in sorted(os.listdir("raw")):
    if not f.endswith(".png"): continue
    print(f"\n{'='*60}\n{f}\n{'='*60}")
    print(ask(os.path.join("raw", f), Q, max_side=700))

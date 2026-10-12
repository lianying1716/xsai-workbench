import os, sys
sys.path.insert(0, "/path/to/platform-api/docs/brand/logo/tools")
from see import ask
Q = """你是资深品牌设计总监，评审一款中文创作者工具「星采 Stargather」的品牌 logo 概念图。
品牌内涵：星采 = 采星（把散落的星光采集收拢）。调性：星空、诗意、浪漫、精致。
用途：产品内品牌标 / 手机 APP 图标 / 浏览器 favicon（很小）/ 登录页 / 印刷周边。

请严格按格式，每项一句话：
1. 实际画的是什么：客观描述（图形、文字、颜色、背景、有无渐变或光影）
2. 若有汉字，逐个念出你看到的字（无关写「无文字」）
3. 有没有明显缺陷（错字/糊字/破形/构图失衡/元素冲突）：具体指出，没有写「无」
4. 设计感与原创性：强/中/弱 + 理由（是否像现成图标或 emoji）
5. 诗意浪漫感：强/中/弱 + 理由
6. 缩小到 16-24px 是否还能用：强/中/弱 + 理由
7. 总分(1-10)：只给数字
8. 一句话结论：值不值得深化
"""
d="raw12"
for f in sorted(os.listdir(d)):
    if not f.endswith(".png"): continue
    print(f"\n{'='*58}\n{f}\n{'='*58}")
    print(ask(os.path.join(d,f), Q, max_side=820))

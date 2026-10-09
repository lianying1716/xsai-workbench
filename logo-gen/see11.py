import os, sys
sys.path.insert(0, "/www/wwwroot/xsai-workbench/platform-api/docs/brand/logo/tools")
from see import ask
Q = """你是资深品牌设计总监，正在评审一款名为「星采 Stargather」的中文创作者工具的品牌 logo 概念图。
品牌内涵：星采 = 采星（把散落的星光采集收拢），调性要求：星空、诗意、浪漫、精致、克制。

请严格按格式回答，每项一句话：
1. 实际画的是什么：（客观描述形状、文字、颜色、背景）
2. 如果图中有汉字，请逐字念出你看到的字（无关就写「无文字」）
3. 文字/图形是否有明显错误（错字、糊字、断裂、破形）：具体指出；没有就写「无」
4. 诗意与浪漫感：强/中/弱 + 理由
5. 简洁度：好/一般/差 + 理由
6. 小尺寸（16-24px）可用性：强/中/弱 + 理由（若是纯字标，说明几字的笔画会不会糊）
7. 像不像现成的通用图标或 emoji：是/否 + 理由
8. 总分(1-10)：只给数字
9. 一句话结论：值不值得深化
"""
d="raw11"
for f in sorted(os.listdir(d)):
    if not f.endswith(".png"): continue
    print(f"\n{'='*58}\n{f}\n{'='*58}")
    print(ask(os.path.join(d,f), Q, max_side=820))

#!/usr/bin/env python3
"""方案 C：让视觉大模型直接把 logo 图重建成干净 SVG。
用法: python3 llm_svg.py <img.png> <out.svg> [model]
"""
import base64, json, subprocess, sys, os, tempfile, re
KEY=open("/path/to/api-key").read().strip()
API="https://api.xsai5.xyz/v1/chat/completions"

PROMPT = """你是矢量图形工程师。请把这张 LOGO 图重建为一份**干净的 SVG**（viewBox 用原图比例）。

要求：
1. 只输出 SVG 代码，从 <svg 开始、到 </svg> 结束，不要任何解释、不要 markdown 代码块。
2. 造型用平滑的贝塞尔曲线（C/Q）或圆/椭圆，**不要**大量短直线（L）堆出的锯齿。
3. 忠实还原：主体形状的轮廓、各元素的位置与大小比例、颜色（用 #RRGGBB）。
4. 把渐变/光晕简化为干净的平面色块（这是要做正式 logo，平面更适合）。
5. 背景色也画上（用一个大 rect）。
6. 路径要简洁——每个形状用尽量少的锚点，锚点转角要顺滑。

现在请输出这张图的 SVG："""

def ask(img_path, model="gpt-5.6-sol", max_side=1024):
    from PIL import Image
    im=Image.open(img_path).convert("RGB")
    if max(im.size)>max_side: im.thumbnail((max_side,max_side),Image.LANCZOS)
    t=tempfile.NamedTemporaryFile(suffix=".png",delete=False); im.save(t.name); 
    b64=base64.b64encode(open(t.name,"rb").read()).decode(); os.unlink(t.name)
    payload={"model":model,"messages":[{"role":"user","content":[
        {"type":"text","text":PROMPT},
        {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}}]}],
        "max_tokens":8000}
    with tempfile.NamedTemporaryFile("w",suffix=".json",delete=False) as fh:
        json.dump(payload,fh); body=fh.name
    out=subprocess.run(["curl","-s","-m","300",API,"-H",f"Authorization: Bearer {KEY}",
        "-H","Content-Type: application/json","--data-binary",f"@{body}"],
        capture_output=True,text=True)
    os.unlink(body)
    try:
        d=json.loads(out.stdout)
        if "error" in d: return "ERR: "+json.dumps(d["error"],ensure_ascii=False)[:300]
        return d["choices"][0]["message"]["content"]
    except Exception as e:
        return f"PARSE-ERR {e}: {out.stdout[:300]}"

if __name__=="__main__":
    img,out=sys.argv[1],sys.argv[2]
    model=sys.argv[3] if len(sys.argv)>3 else "gpt-5.6-sol"
    txt=ask(img,model)
    open(out+".raw.txt","w").write(txt)
    m=re.search(r"<svg.*?</svg>", txt, re.S)
    if m:
        svg=m.group(0)
        if "xmlns" not in svg.split(">")[0]:
            svg=svg.replace("<svg",'<svg xmlns="http://www.w3.org/2000/svg"',1)
        open(out,"w").write(svg)
        print("OK wrote",out,len(svg),"bytes")
    else:
        print("NO SVG FOUND; raw saved to",out+".raw.txt"); print(txt[:400])

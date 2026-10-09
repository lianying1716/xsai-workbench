#!/usr/bin/env python3
"""方案 D（混合）：先用生图模型把带渐变/质感的 logo 概念图"扁平化"，
再用 potrace 描摹成干净 SVG。
星算的 images/generations 支持 image 字段（图生图）；这里直接把参考图以 base64 传入。"""
import base64,json,os,subprocess,sys,tempfile
KEY=open("/tmp/xk").read().strip()
API="https://api.xsai5.xyz/v1/images/generations"

PROMPT=("Redraw this logo as a clean FLAT vector design. Keep the exact same composition, shapes, "
        "positions and proportions. Remove ALL gradients, glows, texture, shadows and noise - use only "
        "a few solid flat colors (deep navy background, cream-white bowl and stars, one brick-red accent "
        "star). Crisp clean edges, no anti-aliasing haze, no extra elements, no text.")

def flatten(img_path,out,model="gpt-image-2.5",size="1024x1024"):
    b64=base64.b64encode(open(img_path,"rb").read()).decode()
    body=json.dumps({"model":model,"prompt":PROMPT,"size":size,"n":1,
                     "image":f"data:image/png;base64,{b64}"})
    import tempfile as _tf
    fh=_tf.NamedTemporaryFile("w",suffix=".json",delete=False); fh.write(body); fh.close()
    r=subprocess.run(["curl","-s","-m","300",API,"-H",f"Authorization: Bearer {KEY}",
        "-H","Content-Type: application/json","--data-binary",f"@{fh.name}"],capture_output=True,text=True)
    os.unlink(fh.name)
    try: d=json.loads(r.stdout)
    except Exception: print("bad json",r.stdout[:200]); return False
    if "error" in d: print("ERR",json.dumps(d["error"],ensure_ascii=False)[:220]); return False
    url=d["data"][0].get("url") or ""
    if not url: print("no url",json.dumps(d)[:200]); return False
    subprocess.run(["curl","-s","-m","300","-o",out,url],check=True)
    return True

if __name__=="__main__":
    src,out=sys.argv[1],sys.argv[2]
    model=sys.argv[3] if len(sys.argv)>3 else "gpt-image-2.5"
    print("OK" if flatten(src,out,model) else "FAIL")

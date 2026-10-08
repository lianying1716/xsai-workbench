import time
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:9501"
reqs=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":950})
    pg.on("request", lambda r: reqs.append((time.time(), r.url)))
    pg.goto(BASE+"/#/login"); pg.wait_for_timeout(700)
    pg.fill("input[type=password]","test1234"); pg.click("button:has-text('登录')"); pg.wait_for_timeout(1000)
    pg.goto(BASE+"/#/assets"); pg.wait_for_timeout(1000)
    pg.click("button:has-text('详情')"); pg.wait_for_timeout(1500)
    t0=time.time(); reqs.clear()
    pg.wait_for_timeout(7000)   # ~2-3 poll cycles while "doing"
    frames_req=[u for t,u in reqs if u.endswith('/frames')]
    img_req=[u for t,u in reqs if '/frames/' in u and u.endswith('/image')]
    print(f"over 7s of active polling: /frames calls={len(frames_req)}, frame image calls={len(img_req)}")
    print("distinct image URLs:", len(set(img_req)), "->", sorted(set(img_req)))
    b.close()

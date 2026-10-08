import time, json, re
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:9612"; OUT="/www/wwwroot/xsai-workbench/docs/plans/evidence/2026-10-06-final-review-v2"
ce, pe, posts = [], [], []
def log(*a): print(*a, flush=True)
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={"width":1440,"height":900}); page=ctx.new_page()
    page.on("console", lambda m: ce.append(f"{m.type}: {m.text}") if m.type=="error" else None)
    page.on("pageerror", lambda e: pe.append(str(e)))
    page.on("request", lambda r: posts.append(r.post_data) if ("/process" in r.url and r.method=="POST") else None)
    page.goto(BASE+"/#/login"); page.wait_for_timeout(1500)
    pws=page.locator("input[type=password]"); pws.nth(0).fill("v2pass123")
    if pws.count()>1: pws.nth(1).fill("v2pass123")
    page.get_by_role("button", name=re.compile("设置密码并进入|登录")).click(); page.wait_for_timeout(1800)
    page.goto(BASE+"/#/assets"); page.wait_for_timeout(1500); page.screenshot(path=f"{OUT}/01_list.png")
    page.locator("tr", has_text="v2 爆款测试").first.get_by_role("button", name="详情").click(); page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT}/02_detail.png")
    cb=page.locator(".tier-actions .el-checkbox")
    log("use_cover checked:", "is-checked" in (cb.first.get_attribute("class") or ""), "| tier:", page.locator(".tier-row").inner_text().replace("\n","/"))
    page.locator(".tier-actions button", has_text="抽帧").first.click(); page.wait_for_timeout(1200)
    log("POST after L2:", posts[-1])
    open("/tmp/v2_live/flag","w").write("go")
    for _ in range(50):
        time.sleep(0.5); t=page.locator(".tier-row").inner_text()
        if "完成" in t: break
    log("after worker L2:", t.replace("\n","/"), "| frame imgs:", page.locator(".frame-wall img").count())
    page.screenshot(path=f"{OUT}/03_after_l2_done.png")
    page.locator(".tier-actions button", has_text="视频理解").first.click(); page.wait_for_timeout(1200)
    log("POST after L3:", posts[-1]); open("/tmp/v2_live/flag","w").write("go")
    for _ in range(30):
        time.sleep(0.5); t=page.locator(".tier-row").inner_text()
        if "失败" in t: break
    log("after worker L3:", t.replace("\n","/"))
    page.screenshot(path=f"{OUT}/04_after_l3.png")
    page.goto(BASE+"/#/system"); page.wait_for_timeout(1500)
    page.get_by_role("tab", name="视频理解").click(); page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT}/05_settings.png")
    log("checked switches:", page.locator(".el-switch.is-checked").count())
    page.get_by_role("button", name="保存").first.click(); page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT}/06_settings_saved.png")
    log("console errors:", json.dumps(ce, ensure_ascii=False)); log("page errors:", json.dumps(pe, ensure_ascii=False))
    b.close()

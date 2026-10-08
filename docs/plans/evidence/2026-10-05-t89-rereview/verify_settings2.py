import sqlite3
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:9501"; DB="/tmp/t89_rr/data/rr.db"; SHOTS="/tmp/t89_rr/shots"
def get_uc():
    r=sqlite3.connect(DB).execute("select value from system_setting where key='process_use_cover'").fetchone()
    return r[0] if r else None
puts=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1500,"height":1000})
    def on_req(req):
        if req.method=="PUT" and "process-settings" in req.url:
            puts.append(req.post_data)
    pg.on("request", on_req)
    pg.goto(BASE+"/#/login"); pg.wait_for_timeout(700)
    pg.fill("input[type=password]","test1234"); pg.click("button:has-text('登录')"); pg.wait_for_timeout(1000)
    pg.goto(BASE+"/#/system"); pg.wait_for_timeout(2000)
    pg.click(".el-tabs__item:has-text('视频理解')"); pg.wait_for_timeout(1000)
    print("use_cover switch checked state:", pg.eval_on_selector_all(".el-switch.is-checked","els=>els.length"), "checked switches")
    print("before db:", get_uc())
    pg.locator("button:has-text('保存')").locator("visible=true").click(); pg.wait_for_timeout(1500)
    print("PUT bodies:", puts)
    import json
    for bd in puts:
        try: print("  use_cover in body:", json.loads(bd).get("use_cover"))
        except Exception as e: print("  parse err", e)
    print("after db:", get_uc())
    b.close()

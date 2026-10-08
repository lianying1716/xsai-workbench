import sqlite3
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:9501"; DB="/tmp/t89_rr/data/rr.db"
def latest_payload():
    r=sqlite3.connect(DB).execute("select payload from job_queue where job_type='understand_video' order by id desc limit 1").fetchone()
    return r[0] if r else None
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":950})
    pg.goto(BASE+"/#/login"); pg.wait_for_timeout(700)
    pg.fill("input[type=password]","test1234"); pg.click("button:has-text('登录')"); pg.wait_for_timeout(1000)
    pg.goto(BASE+"/#/assets"); pg.wait_for_timeout(1000)
    pg.click("button:has-text('详情')"); pg.wait_for_timeout(1600)
    # do NOT touch checkbox; click L3
    pg.click("button:has-text('视频理解（L3）')"); pg.wait_for_timeout(1200)
    print("global default=True, checkbox untouched -> L3 job payload:", latest_payload())
    b.close()

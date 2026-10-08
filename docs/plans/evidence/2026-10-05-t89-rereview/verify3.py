import json, sqlite3, os
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:9501"; DB="/tmp/t89_rr/data/rr.db"; SHOTS="/tmp/t89_rr/shots"
def db_exec(sql,args=()):
    con=sqlite3.connect(DB,timeout=10); con.execute(sql,args); con.commit(); con.close()
# restore understanding row (verify.py deleted it)
db_exec("DELETE FROM video_understanding WHERE asset_id=1")
db_exec("""INSERT INTO video_understanding
 (asset_id,category,category_confidence,category_reason,low_confidence,dimensions,summary,timeline,model,prompt_version,usage,status,error,created_at)
 VALUES (1,'commerce',0.87,'含商品展示',0,?,'演示','[]','qwen3.8-flash','v1','{}','done','',datetime('now'))""",
 (json.dumps({"product":"裙子","dish":"红烧肉","visual":"红绿蓝"}, ensure_ascii=False),))
db_exec("UPDATE media_asset SET process_tier='l3', understand_status='done', error='' WHERE id=1")
errors=[]; res=[]
def check(n,c,d=""):
    res.append(c); print(("PASS " if c else "FAIL ")+n+((" — "+d) if d else ""))
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":950})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE+"/#/login"); pg.wait_for_timeout(700)
    pg.fill("input[type=password]","test1234"); pg.click("button:has-text('登录')"); pg.wait_for_timeout(1000)
    pg.goto(BASE+"/#/assets"); pg.wait_for_timeout(1000); pg.click("button:has-text('详情')"); pg.wait_for_timeout(1600)
    body=pg.inner_text("body"); pg.screenshot(path=SHOTS+"/04c_dims.png", full_page=True)
    check("T9#4 菜品 (type-specific dish)", "菜品" in body)
    check("T9#4 商品与卖点 (product)", "商品与卖点" in body)
    check("T9#4 画面内容 (visual)", "画面内容" in body)
    check("no pageerror", not errors, str(errors[:2]))
    print("passed", sum(res), "/", len(res)); b.close()

import json, sqlite3, os
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:9501"; DB="/tmp/t89_rr/data/rr.db"; SHOTS="/tmp/t89_rr/shots"
def db_exec(sql,args=()):
    con=sqlite3.connect(DB,timeout=10); con.execute(sql,args); con.commit(); con.close()
def reopen(pg):
    pg.click(".el-drawer__close-btn"); pg.wait_for_timeout(400)
    pg.click("button:has-text('详情')"); pg.wait_for_timeout(1400)
errors=[]
res=[]
def check(n,c,d=""):
    res.append(c); print(("PASS " if c else "FAIL ")+n+((" — "+d) if d else ""))
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":950})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE+"/#/login"); pg.wait_for_timeout(700)
    pg.fill("input[type=password]","test1234"); pg.click("button:has-text('登录')"); pg.wait_for_timeout(1000)
    pg.goto(BASE+"/#/assets"); pg.wait_for_timeout(1000); pg.click("button:has-text('详情')"); pg.wait_for_timeout(1400)

    # ensure understanding row done with type-specific dish dim
    db_exec("UPDATE video_understanding SET dimensions=?, status='done' WHERE asset_id=1",
            (json.dumps({"product":"裙子","dish":"红烧肉","visual":"红绿蓝"}, ensure_ascii=False),))
    db_exec("UPDATE media_asset SET process_tier='l3', understand_status='done' WHERE id=1")
    reopen(pg)
    body=pg.inner_text("body"); pg.screenshot(path=SHOTS+"/04b_dim_labels_reopen.png", full_page=True)
    check("T9#4 菜品 (type-specific dish) label", "菜品" in body)
    check("T9#4 商品与卖点 (product) label", "商品与卖点" in body)
    check("T9#4 画面内容 (visual) label", "画面内容" in body)

    # error with no understanding row
    db_exec("DELETE FROM video_understanding WHERE asset_id=1")
    db_exec("UPDATE media_asset SET understand_status='error', error='上传视频超过 15MB 上限' WHERE id=1")
    reopen(pg)
    body=pg.inner_text("body"); pg.screenshot(path=SHOTS+"/05b_error_reopen.png", full_page=True)
    check("T9#3 failure text from /understanding.error", "上传视频超过 15MB 上限" in body, body[body.find("理解失败"):][:90] if "理解失败" in body else "no block")
    check("T9#3 no pageerror", not errors, str(errors[:2]))
    print("passed", sum(res), "/", len(res))
    b.close()

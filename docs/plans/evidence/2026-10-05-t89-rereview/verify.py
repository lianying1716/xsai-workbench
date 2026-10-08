import json, sqlite3, time, os
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:9501"
DB = "/tmp/t89_rr/data/rr.db"
TOKEN = open("/tmp/t89_rr/token.sh").read().split("TOKEN=")[1].strip()
SHOTS = "/tmp/t89_rr/shots"
os.makedirs(SHOTS, exist_ok=True)

def db_exec(sql, args=()):
    con = sqlite3.connect(DB, timeout=10)
    con.execute(sql, args); con.commit(); con.close()

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ((" — " + detail) if detail else ""))

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 950})
    pg.on("pageerror", lambda e: errors.append(("pageerror", str(e))))
    pg.on("console", lambda m: errors.append(("console." + m.type, m.text)) if m.type == "error" else None)

    # --- real login ---
    pg.goto(BASE + "/#/login"); pg.wait_for_timeout(800)
    pg.fill("input[type=password]", "test1234")
    pg.click("button:has-text('登录')")
    pg.wait_for_timeout(1200)
    tok = pg.evaluate("localStorage.getItem('token')")
    check("login via real events -> token stored", bool(tok), tok[:10] if tok else "")

    # --- open assets detail via real clicks ---
    pg.goto(BASE + "/#/assets"); pg.wait_for_timeout(1200)
    pg.click("button:has-text('详情')"); pg.wait_for_timeout(1500)
    body = pg.inner_text("body")
    pg.screenshot(path=SHOTS + "/01_detail_initial.png", full_page=True)
    check("drawer shows tier l3", "当前档位：l3" in body, "当前档位：l3" if "当前档位：l3" in body else body[:120])
    check("drawer shows 判类 带货", "带货" in body)
    check("dimension label 商品与卖点 (type-specific product)", "商品与卖点" in body)
    check("dimension label 画面内容 (common visual)", "画面内容" in body)
    check("frame wall rendered 3 imgs",
          pg.eval_on_selector_all(".frame-wall img", "els => els.length") == 3)

    # --- T9#1: action refreshes state (frames_status) + tier from refresh point ---
    db_exec("UPDATE media_asset SET process_tier='l2' WHERE id=1")
    pg.click("button:has-text('抽帧（L2）')")
    pg.wait_for_timeout(1500)
    body = pg.inner_text("body")
    pg.screenshot(path=SHOTS + "/02_after_l2_click.png", full_page=True)
    fs = sqlite3.connect(DB).execute("select frames_status from media_asset where id=1").fetchone()[0]
    check("T9#1 frames_status pending in DB after click", fs == "pending", "db=" + fs)
    check("T9#1 DOM reflects 抽帧 待处理 after action", "抽帧 待处理" in body, body[body.find("分档加工"):][:80] if "抽帧 待处理" not in body else "")
    check("T9#1 '当前档位' reloaded from refresh point (l2)", "当前档位：l2" in body)

    # --- T9#2: poll picks up external worker state change within ~3s ---
    db_exec("UPDATE media_asset SET frames_status='done', process_tier='l3' WHERE id=1")
    pg.wait_for_timeout(4200)
    body = pg.inner_text("body")
    pg.screenshot(path=SHOTS + "/03_after_poll.png", full_page=True)
    check("T9#2 poll picked up external DB change (抽帧 完成, tier l3)",
          "抽帧 完成" in body and "当前档位：l3" in body)

    # --- T9#4: type-specific dim 'dish' -> 菜品 ---
    dims = {"product":"裙子","dish":"红烧肉","visual":"红绿蓝"}
    db_exec("UPDATE video_understanding SET dimensions=? WHERE asset_id=1", (json.dumps(dims, ensure_ascii=False),))
    db_exec("UPDATE media_asset SET process_tier='l3' WHERE id=1")
    pg.wait_for_timeout(4200)
    body = pg.inner_text("body")
    pg.screenshot(path=SHOTS + "/04_dim_labels.png", full_page=True)
    check("T9#4 type-specific dim label 菜品 (dish)", "菜品" in body)
    check("T9#4 dim label 商品与卖点 (product)", "商品与卖点" in body)
    check("T9#4 dim label 画面内容 (visual)", "画面内容" in body)

    # --- T9#3: error text from /understanding surfaced when no row result ---
    db_exec("UPDATE media_asset SET understand_status='error', error='缺少 ffmpeg，无法抽帧' WHERE id=1")
    db_exec("DELETE FROM video_understanding WHERE asset_id=1")
    pg.wait_for_timeout(4200)
    body = pg.inner_text("body")
    pg.screenshot(path=SHOTS + "/05_error.png", full_page=True)
    check("T9#3 failure detail shows /understanding.error", "缺少 ffmpeg，无法抽帧" in body,
          body[body.find("理解失败"):][:80] if "理解失败" in body else "no 理解失败 block")

    # --- T9#7: reopen drawer repeatedly, no leak/pageerror ---
    db_exec("UPDATE media_asset SET understand_status='done' WHERE id=1")
    for i in range(3):
        pg.click(".el-drawer__close-btn"); pg.wait_for_timeout(400)
        pg.click("button:has-text('详情')"); pg.wait_for_timeout(1200)
    check("T9#7/9 no pageerror after reopen cycle", not [e for e in errors if e[0] == "pageerror"],
          str([e for e in errors if e[0]=="pageerror"][:2]))

    # --- Settings page: use_cover persistence on save (prior Minor #5) ---
    pg.goto(BASE + "/#/assets"); pg.wait_for_timeout(500)
    pg.goto(BASE + "/#/system"); pg.wait_for_timeout(1500)
    # enable use_cover switch then save
    sw = pg.locator(".el-switch").filter(has_text="")  # fallback: locate by form item
    body = pg.inner_text("body")
    # Set API-side to True first, reload, then save and confirm retained
    db_exec("UPDATE system_setting SET value='true' WHERE key='process_use_cover' OR key LIKE '%use_cover%'")
    pg.wait_for_timeout(300)
    pg.reload(); pg.wait_for_timeout(1500)
    pg.screenshot(path=SHOTS + "/06_settings.png", full_page=True)
    check("settings page loaded", "视频理解" in pg.inner_text("body"))

    b.close()

print("\n--- ERRORS ---")
for e in errors: print(e)
npass = sum(1 for _,c,_ in results if c)
print(f"\n{ npass }/{len(results)} checks passed")

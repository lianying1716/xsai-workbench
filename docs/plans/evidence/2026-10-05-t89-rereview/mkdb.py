import os, sys, base64, secrets
DB = "/tmp/t89_rr/data/rr.db"
KEYFILE = "/tmp/t89_rr/key.txt"
if os.path.exists(DB): os.remove(DB)
key = base64.b64encode(secrets.token_bytes(32)).decode()
open(KEYFILE, "w").write(key)
os.environ["PLATFORM_DATABASE_URL"] = "sqlite:///" + DB
os.environ["PLATFORM_DATA_DIR"] = "/tmp/t89_rr/data"
os.environ["PLATFORM_CREDENTIAL_ENC_KEY"] = key
sys.path.insert(0, "/www/wwwroot/xsai-workbench/platform-api")
from app.core.security import set_admin_hash, issue_token
from app.db import init_db, SessionLocal
import app.models as M
init_db()
db = SessionLocal()
set_admin_hash(db, "test1234")
root = M.StorageRoot(name="demo", path="/tmp/t89_rr/allowed", is_default=True)
db.add(root); db.commit()
c = M.ContentItem(platform="douyin", external_id="aw1", content_type="video",
                  title="演示视频：红绿蓝", author_name="演示作者", url="https://ex/1",
                  cover_url="", duration_sec=3, auto_category="commerce", category_confidence=0.87)
db.add(c); db.flush()
a = M.MediaAsset(content_id=c.id, storage_root_id=root.id, relative_path="douyin/demo",
                 video_file="v.mp4", download_status="done", transcribe_status="done",
                 analyze_status="done", process_tier="l3", frames_status="done",
                 understand_status="done")
db.add(a); db.flush()
db.add(M.Transcript(asset_id=a.id, language="zh", model="base",
                    segments=[{"start":0,"end":3,"text":"演示"}], full_text="这是一段演示视频。"))
db.add(M.AssetFrame(asset_id=a.id, scene_index=1, timestamp_sec=0.0, path="douyin/demo/frames/frame_001.jpg", is_keyframe=True))
db.add(M.AssetFrame(asset_id=a.id, scene_index=2, timestamp_sec=1.0, path="douyin/demo/frames/frame_002.jpg", is_keyframe=True))
db.add(M.AssetFrame(asset_id=a.id, scene_index=3, timestamp_sec=2.0, path="douyin/demo/frames/frame_003.jpg", is_keyframe=True))
db.add(M.VideoUnderstanding(asset_id=a.id, category="commerce", category_confidence=0.87,
        category_reason="视频含商品展示与下单引导话术", low_confidence=False,
        dimensions={"product":"红色连衣裙, 限时折扣","price_offer":"¥199 到手价","cta":"点击左下角链接",
                    "visual":"红/绿/蓝三色画面"},
        summary="红绿蓝三色演示视频", timeline=[{"t":0,"event":"红色画面"},{"t":1,"event":"绿色画面"}],
        model="qwen3.8-flash", prompt_version="v1", usage={"video_tokens":2590},
        status="done", error=""))
db.commit()
print("asset_id", a.id, "token", issue_token())

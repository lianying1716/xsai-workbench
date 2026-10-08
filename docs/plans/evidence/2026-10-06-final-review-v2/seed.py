import os, sys, base64, subprocess
os.environ.setdefault("PLATFORM_DATABASE_URL", sys.argv[1])
os.environ.setdefault("PLATFORM_CREDENTIAL_ENC_KEY", base64.b64encode(os.urandom(32)).decode())
from app.db import SessionLocal, Base, engine
import app.models as M
Base.metadata.create_all(engine)
db = SessionLocal()
store = sys.argv[2]; os.makedirs(store, exist_ok=True)
root = M.StorageRoot(name="tmp", path=store, is_default=True); db.add(root); db.flush()
vp = os.path.join(store, "video.mp4")
subprocess.run(["ffmpeg","-hide_banner","-nostdin","-y","-f","lavfi","-i","testsrc=duration=6:size=320x240:rate=10","-pix_fmt","yuv420p",vp],capture_output=True)
c = M.ContentItem(platform="douyin", external_id="v2hot", content_type="video", title="v2 爆款测试", author_name="tester", url="https://example.com/v", source_kind="crawl", duration_sec=6)
db.add(c); db.flush(); db.add(M.ContentMetricSnapshot(content_id=c.id, like=5000, comment=300))
a = M.MediaAsset(content_id=c.id, storage_root_id=root.id, relative_path="", video_file="video.mp4", download_status="done", process_tier="", frames_status="", understand_status="")
db.add(a)
db.add(M.SystemSetting(key="process_use_cover", value="true"))
db.commit(); print("SEED ok asset", a.id); db.close()

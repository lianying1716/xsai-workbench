import os, base64, tempfile
os.environ["PLATFORM_DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["PLATFORM_CREDENTIAL_ENC_KEY"] = base64.b64encode(os.urandom(32)).decode()
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.models  # noqa
from app.db import Base
from app.models import ContentItem, ContentMetricSnapshot, MediaAsset, JobQueue, SystemSetting
from app.workers import handlers
eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(eng)
db = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)()
async def fake_download(url, target_dir, **kw): return {"video_file":"video.mp4","audio_file":"audio.wav"}
import app.modules.media_download as md
md.download = fake_download
db.add(SystemSetting(key="process_budget", value="2")); db.commit()
for i in range(5):
    c = ContentItem(platform="douyin", external_id=f"h{i}", url=f"https://d/h{i}", content_type="video")
    db.add(c); db.flush()
    db.add(ContentMetricSnapshot(content_id=c.id, like=5000))
    a = MediaAsset(content_id=c.id, download_status="pending"); db.add(a); db.commit()
    asyncio.run(handlers.handle_download(db, {"asset_id": a.id}))
qs = db.query(JobQueue).filter_by(job_type="understand_video").all()
print("jobs:", [(j.id, j.payload["asset_id"], j.status) for j in qs])
for j in qs: j.status = "done"
db.commit()
from app.services.process_gate import enqueue_process_jobs, select_targets
from app.core.process_settings import get_process_settings
s = get_process_settings(db)
t = select_targets(db, db.query(ContentItem).all(), settings=s)
print("re-touch select_targets ->", [(a.id, tier) for a,tier,_ in t])
n = enqueue_process_jobs(db, db.query(ContentItem).all(), settings=s)
print("created =", n)
print("now jobs:", [(j.payload["asset_id"], j.status) for j in db.query(JobQueue).filter_by(job_type="understand_video").all()])

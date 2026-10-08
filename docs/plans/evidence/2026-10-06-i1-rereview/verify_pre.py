"""在 PRE-fix 工作树(28f42f4)上运行：证明修复前 50 条逐条 → 50 job。"""
import os, base64, tempfile, sys
os.environ["PLATFORM_DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["PLATFORM_CREDENTIAL_ENC_KEY"] = base64.b64encode(os.urandom(32)).decode()
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.models  # noqa
from app.db import Base
from app.models import ContentItem, ContentMetricSnapshot, MediaAsset, JobQueue
from app.services.process_gate import enqueue_process_jobs
from app.core.process_settings import get_process_settings
print("process_gate from:", __import__("app.services.process_gate", fromlist=["x"]).__file__)

eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(eng)
db = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)()

def mk(ext, like):
    c = ContentItem(platform="douyin", external_id=ext, content_type="video", source_kind="crawl")
    db.add(c); db.flush()
    db.add(ContentMetricSnapshot(content_id=c.id, like=like))
    a = MediaAsset(content_id=c.id, video_file="v.mp4", download_status="done")
    db.add(a); db.commit()
    return c, a

def settings(**kw):
    s = get_process_settings(db); s.update(kw); return s

n = 0
for i in range(50):
    c, a = mk(f"hot{i}", 5000)
    n += enqueue_process_jobs(db, [c], settings=settings())  # default budget=20
jobs = db.query(JobQueue).filter_by(job_type="understand_video").count()
print(f"PRE-FIX: batch=1 x50 hot, default budget=20 -> created={n}, jobs={jobs}")

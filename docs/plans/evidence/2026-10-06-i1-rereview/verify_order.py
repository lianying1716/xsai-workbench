"""决定性对抗：剩余额度 < 批内合格数时，保留按「分数优先」还是「输入顺序」？"""
import os, base64, tempfile
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

# 输入顺序 [low, high]，budget=1 → 分数优先应保留 high；输入顺序应保留 low
clow, alow = mk("low", 800)     # l2
chigh, ahigh = mk("high", 5000) # l3
enqueue_process_jobs(db, [clow, chigh], settings=settings(budget=1, top_pct=1.0))
rows = db.query(JobQueue).all()
kept = [r.payload["asset_id"] for r in rows]
print("kept asset ids:", kept, "| low=%s high=%s" % (alow.id, ahigh.id))
print("RESULT:", "high(分数优先)" if ahigh.id in kept else "low(输入顺序)")

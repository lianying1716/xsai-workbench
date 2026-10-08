"""对抗：输入顺序 [low, mid, high] + 外部占位令 remaining < 批内合格数，看丢谁。"""
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

# 外部占位 1 条（手动 API 入队，占用 1 额度）。budget=3 → remaining=2
cocc, aocc = mk("occupier", 5000)
enqueue_process_jobs(db, [cocc], settings=settings(budget=3, top_pct=1.0))

# 批内按输入顺序 low, mid, high（分数递增），top_pct=1/budget=3 → select_tier 三条全过
clow, alow = mk("low", 800)     # l2
cmid, amid = mk("mid", 3000)    # l3
chigh, ahigh = mk("high", 5000) # l3
enqueue_process_jobs(db, [clow, cmid, chigh], settings=settings(budget=3, top_pct=1.0))

rows = db.query(JobQueue).filter(JobQueue.payload["asset_id"] != aocc.id).all()
kept = {r.payload["asset_id"] for r in rows}
print("low=%s mid=%s high=%s" % (alow.id, amid.id, ahigh.id))
print("kept:", sorted(kept))
print("high kept?", ahigh.id in kept, "| mid kept?", amid.id in kept, "| low kept?", alow.id in kept)

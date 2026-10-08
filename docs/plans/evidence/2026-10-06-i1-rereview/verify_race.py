"""对抗：两个并发调用者交错读取在途计数 → 是否可能突破 budget？"""
import os, base64, tempfile
d = tempfile.mkdtemp()
os.environ["PLATFORM_DATABASE_URL"] = "sqlite:///" + os.path.join(d, "t.db")
os.environ["PLATFORM_CREDENTIAL_ENC_KEY"] = base64.b64encode(os.urandom(32)).decode()
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app.models  # noqa
from app.db import Base
from app.models import ContentItem, ContentMetricSnapshot, MediaAsset, JobQueue
from app.services import process_gate
from app.core.process_settings import get_process_settings

eng = create_engine("sqlite:///" + os.path.join(d, "t.db"))
Base.metadata.create_all(eng)
S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)

def mk(db, ext, like):
    c = ContentItem(platform="douyin", external_id=ext, content_type="video", source_kind="crawl")
    db.add(c); db.flush()
    db.add(ContentMetricSnapshot(content_id=c.id, like=like))
    a = MediaAsset(content_id=c.id, video_file="v.mp4", download_status="done")
    db.add(a); db.commit()
    return c, a

setup = S()
cA, aA = mk(setup, "A", 5000)
cB, aB = mk(setup, "B", 5000)
settings = get_process_settings(setup); settings.update(budget=1, top_pct=1.0)
setup.close()

# 手动交错：模拟两个 worker 槽同时处理两条下载完成
dbA = S(); dbB = S()
# 两个会话都在「已用=0」时算 remaining=1
usedA, _ = process_gate._budget_counts(dbA)
usedB, _ = process_gate._budget_counts(dbB)
print("usedA=%s usedB=%s (both 0 -> each sees remaining=1)" % (usedA, usedB))
# A 先入队提交
from app.core.queue import enqueue
enqueue(dbA, "understand_video", {"asset_id": aA.id}, priority=120, commit=True)
# B 仍按旧读数入队（未重新计数）
enqueue(dbB, "understand_video", {"asset_id": aB.id}, priority=120, commit=True)
chk = S()
n = chk.query(JobQueue).filter_by(job_type="understand_video").count()
print("final understand_video jobs =", n, "(budget=1)  -> 若=2 则并发下为软上限（TOCTOU）")

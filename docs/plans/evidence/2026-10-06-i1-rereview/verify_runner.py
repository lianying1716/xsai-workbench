"""独立复核：真实 runner 领取 + 预算跨 job 生命周期 + 批内排序对抗。"""
import asyncio, os, base64, tempfile
os.environ["PLATFORM_DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["PLATFORM_CREDENTIAL_ENC_KEY"] = base64.b64encode(os.urandom(32)).decode()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.models  # noqa
from app.db import Base
from app.models import ContentItem, ContentMetricSnapshot, MediaAsset, JobQueue, SystemSetting
from app.services.process_gate import enqueue_process_jobs
from app.core.process_settings import get_process_settings
import app.workers.runner as runner
from app.core import queue

def fresh():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    runner.SessionLocal = S
    return eng, S()

def mk(db, ext, like, comment=0):
    c = ContentItem(platform="douyin", external_id=ext, content_type="video", source_kind="crawl")
    db.add(c); db.flush()
    db.add(ContentMetricSnapshot(content_id=c.id, like=like, comment=comment))
    a = MediaAsset(content_id=c.id, video_file="v.mp4", download_status="done")
    db.add(a); db.commit()
    return c, a

def settings(db, **kw):
    s = get_process_settings(db); s.update(kw); return s

# 1) 真实 runner：入队 N 个 understand_video（budget 已封顶），逐个 claim+complete
#    完成后额度释放，为后续入队腾出空间 → 证明「done 释放额度」在真实队列语义下成立。
eng, db = fresh()
db.add(SystemSetting(key="process_budget", value="2")); db.commit()
for i in range(10):
    c, a = mk(db, f"h{i}", 5000)
    enqueue_process_jobs(db, [c], settings=settings(db))
print("1) after 10 batch=1, jobs =", db.query(JobQueue).filter_by(job_type="understand_video").count(), "(expect 2)")
# 领一条置 running：额度仍占，不加新
j = queue.claim(db, ["understand_video"])
print("1) claimed job status ->", j.status)
c, a = mk(db, "h_new", 5000)
enqueue_process_jobs(db, [c], settings=settings(db))
print("1) after claim(running), jobs =", db.query(JobQueue).count(), "(expect 2, running 仍占额度)")
# 完成该 job → 额度释放 → 新入队可成功
queue.complete(db, j)
enqueue_process_jobs(db, [c], settings=settings(db))
print("1) after complete, jobs =", db.query(JobQueue).count(), "(expect 3: done 释放 1)")

# 2) 对抗：批内剩余额度受限时，保留的是按分数还是按输入顺序？
eng, db = fresh()
# batch: [mid(3000), high(5000), low2(800)]，budget=3 → 三条都够；再制造 1 条在途占位
cocc, aocc = mk(db, "occupier", 5000)
enqueue_process_jobs(db, [cocc], settings=settings(db, budget=3, top_pct=1.0))  # used=1
cmid, amid = mk(db, "mid", 3000)
chigh, ahigh = mk(db, "high", 5000)
clow, alow = mk(db, "low", 800)
# 现在 remaining = 3-1 = 2；批内 3 条（top_pct=1, budget=3 → select_tier 全保留）
enqueue_process_jobs(db, [cmid, chigh, clow], settings=settings(db, budget=3, top_pct=1.0))
rows = db.query(JobQueue).filter_by(job_type="understand_video").all()
kept = {}
for r in rows:
    kept[r.payload["asset_id"]] = True
print("2) kept asset ids:", sorted(r.payload["asset_id"] for r in rows))
print("2) occupier=%s mid=%s high=%s low=%s" % (aocc.id, amid.id, ahigh.id, alow.id))
print("   -> high kept? %s   mid kept? %s   low kept? %s" % (
    ahigh.id in kept, amid.id in kept, alow.id in kept))
print("   NOTE: 若 low 入而 high 被丢，则批内截断按输入顺序而非分数优先")

# 3) batch 路径整体仍受 budget（一次调用）
eng, db = fresh()
cs = [mk(db, f"b{i}", 5000)[0] for i in range(30)]
enqueue_process_jobs(db, cs, settings=settings(db, budget=5, top_pct=1.0))
print("3) batch=30 once, budget=5, top_pct=1 ->", db.query(JobQueue).count(), "(expect 5)")
db.close()

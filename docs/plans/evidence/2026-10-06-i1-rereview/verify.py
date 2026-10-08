"""独立复核 I1 修复：在途预算（全局）是否真的封顶。"""
import asyncio, os, base64, tempfile
os.environ["PLATFORM_DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["PLATFORM_CREDENTIAL_ENC_KEY"] = base64.b64encode(os.urandom(32)).decode()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa
from app.db import Base

def fresh():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng, sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)()

from app.models import ContentItem, ContentMetricSnapshot, MediaAsset, JobQueue, SystemSetting
from app.services.process_gate import enqueue_process_jobs, _budget_counts

def mk(db, ext, like, comment=0, status="done"):
    c = ContentItem(platform="douyin", external_id=ext, content_type="video", source_kind="crawl")
    db.add(c); db.flush()
    db.add(ContentMetricSnapshot(content_id=c.id, like=like, comment=comment))
    a = MediaAsset(content_id=c.id, video_file="v.mp4", download_status=status)
    db.add(a); db.commit()
    return c, a

def settings(db, **kw):
    from app.core.process_settings import get_process_settings
    s = get_process_settings(db); s.update(kw); return s

# A. batch=1 逐条（下载路径形态）默认 budget=20，50 条爆款
eng, db = fresh()
n = 0
for i in range(50):
    c, a = mk(db, f"hot{i}", 5000)
    n += enqueue_process_jobs(db, [c], settings=settings(db))
jobs = db.query(JobQueue).filter_by(job_type="understand_video").count()
print(f"A. batch=1 x50 hot, budget=20 -> created={n}, understand_video jobs={jobs}  (expect 20)")

# A'. 对照：旧行为（去掉额度闸）—— 用大 budget 模拟无闸，看是否 50
eng, db = fresh()
n = 0
for i in range(50):
    c, a = mk(db, f"hot{i}", 5000)
    n += enqueue_process_jobs(db, [c], settings=settings(db, budget=9999, top_pct=1.0))
jobs = db.query(JobQueue).filter_by(job_type="understand_video").count()
print(f"A'. batch=1 x50 hot, budget=9999 -> jobs={jobs}  (无闸对照，应≈50)")

# B. budget=3, x50 逐条
eng, db = fresh()
n = 0
for i in range(50):
    c, a = mk(db, f"hot{i}", 5000)
    n += enqueue_process_jobs(db, [c], settings=settings(db, budget=3))
jobs = db.query(JobQueue).filter_by(job_type="understand_video").count()
print(f"B. batch=1 x50 hot, budget=3  -> jobs={jobs}  (expect 3)")

# C. batch=10 一次调用，top_pct=0.2 -> 2
eng, db = fresh()
cs = [mk(db, f"b{i}", 5000)[0] for i in range(10)]
n = enqueue_process_jobs(db, cs, settings=settings(db, budget=20, top_pct=0.2))
jobs = db.query(JobQueue).filter_by(job_type="understand_video").count()
print(f"C. batch=10 hot once, budget=20, top_pct=0.2 -> created={n}, jobs={jobs}  (expect 2)")

# D. budget=0
eng, db = fresh()
c, a = mk(db, "hot", 999999)
n = enqueue_process_jobs(db, [c], settings=settings(db, budget=0))
print(f"D. budget=0 -> created={n}, jobs={db.query(JobQueue).count()}  (expect 0/0)")

# E. 对抗：手动 API 入队是否计入在途额度并挤占自动预算
eng, db = fresh()
from app.core.queue import enqueue
c1, a1 = mk(db, "auto1", 5000)
c2, a2 = mk(db, "auto2", 5000)
# 模拟手动 API：直接 enqueue 一条 understand_video（budget=1）
enqueue(db, "understand_video", {"asset_id": a1.id})
used, pending = _budget_counts(db)
print(f"E. 手动 API enqueue 1 条后 _budget_counts used={used}  (expect 1，证明计入在途)")
n = enqueue_process_jobs(db, [c2], settings=settings(db, budget=1))
print(f"E. budget=1 且已有 1 条在途 -> 自动再入队 created={n}  (expect 0，被挤占)")

# F. 对抗：混合 l2/l3（extract_frames 也占预算？）
eng, db = fresh()
cs = []
cs.append(mk(db, "cold_l2", 800)[0])   # l2 -> extract_frames
cs.append(mk(db, "hot_l3", 5000)[0])   # l3 -> understand_video
n = enqueue_process_jobs(db, cs, settings=settings(db, budget=1, top_pct=1.0))
ef = db.query(JobQueue).filter_by(job_type="extract_frames").count()
uv = db.query(JobQueue).filter_by(job_type="understand_video").count()
print(f"F. batch 1×l2 + 1×l3, budget=1 -> created={n}, extract_frames={ef}, understand_video={uv}  (两者合占额度)")

# G. 对抗：payload 缺 asset_id 的脏 job 不应崩溃/误计
eng, db = fresh()
from app.models import JobQueue as JQ
db.add(JQ(job_type="understand_video", payload={"oops": 1}, priority=120, status="queued"))
db.commit()
try:
    used, pending = _budget_counts(db)
    print(f"G. 脏 payload job -> used={used}, pending={pending}  (expect 0, 无 asset_id 不计)")
except Exception as e:
    print(f"G. 脏 payload job -> EXCEPTION {type(e).__name__}: {e}")
db.close()

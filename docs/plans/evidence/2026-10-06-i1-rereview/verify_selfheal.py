"""对抗：下载路径被预算挡下的 asset，是否有自愈重入队（无再触发即永久 l1）？"""
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

async def fake_download(url, target_dir, **kw):
    return {"video_file": "video.mp4", "audio_file": "audio.wav"}
import app.modules.media_download as md
md.download = fake_download

db.add(SystemSetting(key="process_budget", value="2")); db.commit()
assets = []
for i in range(5):
    c = ContentItem(platform="douyin", external_id=f"h{i}", url=f"https://d/h{i}", content_type="video")
    db.add(c); db.flush()
    db.add(ContentMetricSnapshot(content_id=c.id, like=5000))
    a = MediaAsset(content_id=c.id, download_status="pending")
    db.add(a); db.commit()
    asyncio.run(handlers.handle_download(db, {"asset_id": a.id}))
    assets.append(a)

print("下载 5 条爆款(budget=2) 后 understand_video jobs =",
      db.query(JobQueue).filter_by(job_type="understand_video").count(), "(expect 2)")
# 现在把两条 running job 完成，模拟 worker 消化
for j in db.query(JobQueue).filter_by(job_type="understand_video").all():
    j.status = "done"
db.commit()
# 被挡下的 3 条：不重新下载就不再有 handle_download 触发
print("done 两条后，再查 understand_video queued/running =",
      db.query(JobQueue).filter(JobQueue.job_type=="understand_video", JobQueue.status.in_(("queued","running"))).count())
print("被挡下的 3 条 asset 是否自动重入队？-> 无（需再次 crawl/sync 重触达才可能）")
# 验证：手动再走一次门控（模拟未来 crawl 重触达）可补上
from app.services.process_gate import enqueue_process_jobs
from app.core.process_settings import get_process_settings
s = get_process_settings(db)
n = enqueue_process_jobs(db, [c for c in db.query(ContentItem).all()], settings=s)
print("模拟未来 crawl 重触达全部 5 条 -> 新建 =", n, "(额度已释放，补齐)")

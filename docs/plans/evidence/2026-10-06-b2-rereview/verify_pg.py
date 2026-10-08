"""B2 re-review: 独立复现（真实 PostgreSQL）。

1) 证实 job_queue.payload 在 PG 上是无 `=` 的 json 类型；
2) 用旧实现（ORM `payload == payload`）复现 `operator does not exist: json = json`；
3) 用当前实现（Python 端比较）验证 enqueue / dedup / done 后可再入队 语义；
4) 真实 handle_download（下载完成 → 自动门控）在 PG 上恢复自动分档。

自建/自删 scratch 库 b2rr_smoke，绝不触碰别库。
"""
import os
import sys
import base64

sys.path.insert(0, "/www/wwwroot/xsai-workbench/platform-api")

PG_BASE = os.environ.get(
    "PLATFORM_PG_TEST_URL",
    "postgresql+psycopg2://platform:platform@127.0.0.1:5433/platform",
).rsplit("/", 1)[0] + "/"
SCRATCH = "b2rr_smoke"
os.environ["PLATFORM_DATABASE_URL"] = PG_BASE + SCRATCH
os.environ.setdefault("PLATFORM_CREDENTIAL_ENC_KEY", base64.b64encode(os.urandom(32)).decode())

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

admin = create_engine(PG_BASE + "postgres", isolation_level="AUTOCOMMIT")
with admin.connect() as c:
    c.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH}"))
    c.execute(text(f"CREATE DATABASE {SCRATCH}"))

from app.db import Base  # noqa: E402
import app.models as M  # noqa: E402

engine = create_engine(PG_BASE + SCRATCH)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

fail = 0


def check(label, cond):
    global fail
    print(("PASS" if cond else "FAIL") + f": {label}")
    if not cond:
        fail += 1


def new_session():
    return Session()


# 1) payload 列类型
with engine.connect() as c:
    dtype = c.execute(
        text(
            "select data_type from information_schema.columns "
            "where table_name='job_queue' and column_name='payload'"
        )
    ).scalar()
print(f"[info] job_queue.payload data_type = {dtype!r}")
check("payload 列为 json（无 = 运算符的触发条件）", dtype == "json")

# 2) 旧实现复现
db = new_session()
from app.models import JobQueue  # noqa: E402

db.add(JobQueue(job_type="download", payload={"asset_id": 1}))
db.commit()
old_failed = None
try:
    db.scalar(
        select(JobQueue).where(
            JobQueue.job_type == "download",
            JobQueue.status.in_(("queued", "running")),
            JobQueue.payload == {"asset_id": 1},
        )
    )
except Exception as exc:  # noqa: BLE001
    old_failed = f"{type(exc).__name__}: {exc}"
db.rollback()
print(f"[info] 旧实现 dedup 查询 -> {old_failed}")
check("旧实现（ORM payload ==）在 PG 上抛 json=json", bool(old_failed) and "json = json" in old_failed)

# 清空，跑当前实现
db.query(JobQueue).delete()
db.commit()
db.close()

from app.core.queue import complete, enqueue  # noqa: E402

db = new_session()
j1 = enqueue(db, "download", {"asset_id": 1})
check("当前实现 enqueue 不抛错", j1.id is not None)
j2 = enqueue(db, "download", {"asset_id": 1})
check("相同 payload 命中去重（同一行）", j2.id == j1.id)
check("去重后仅 1 行", db.query(JobQueue).filter_by(job_type="download").count() == 1)
j3 = enqueue(db, "download", {"asset_id": 2})
check("不同 payload 正常新增", j3.id != j1.id)
complete(db, j1)
j4 = enqueue(db, "download", {"asset_id": 1})
check("done 任务不参与去重（可再次入队）", j4.id != j1.id)
enqueue(db, "crawl", {})
enqueue(db, "crawl", {})
check("空 payload 判等在 Python 侧一致", db.query(JobQueue).filter_by(job_type="crawl").count() == 1)
# running 状态也参与去重
from app.core import queue as qmod  # noqa: E402

job = enqueue(db, "transcribe", {"asset_id": 9})
job.status = "running"
db.commit()
jr = enqueue(db, "transcribe", {"asset_id": 9})
check("running 任务参与去重", jr.id == job.id)
db.close()

# 3) 真实 handle_download → 自动分档（PG）
import asyncio  # noqa: E402
import subprocess  # noqa: E402

db = new_session()
store = "/tmp/b2rr_store"
os.makedirs(store, exist_ok=True)
root = M.StorageRoot(name="tmp", path=store, is_default=True)
db.add(root)
db.flush()
c = M.ContentItem(
    platform="douyin",
    external_id="b2rrhot",
    content_type="video",
    title="B2 re-review hot",
    author_name="rev",
    url="https://example.com/v",
    source_kind="crawl",
    duration_sec=6,
)
db.add(c)
db.flush()
db.add(M.ContentMetricSnapshot(content_id=c.id, like=5000, comment=300))
a = M.MediaAsset(
    content_id=c.id,
    storage_root_id=root.id,
    relative_path="",
    video_file="",
    download_status="pending",
    process_tier="",
    frames_status="",
    understand_status="",
)
db.add(a)
db.commit()
asset_id, content_id = a.id, c.id
db.close()

from app.workers import handlers  # noqa: E402

db = new_session()


async def fake_download(url, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    return {"video_file": "video.mp4", "audio_file": ""}


handlers.media_download.download = fake_download
asyncio.run(handlers.handle_download(db, {"asset_id": asset_id}))
db.refresh(db.get(M.MediaAsset, asset_id))
asset_after = db.get(M.MediaAsset, asset_id)
check("handle_download 完成（PG 上）", asset_after.download_status == "done")
jobs = db.query(JobQueue).filter_by(job_type="understand_video").all()
print(f"[info] 下载后 understand_video jobs = {[(j.job_type, j.payload) for j in jobs]}")
check("下载完成 → 自动分档在 PG 上入队 understand_video", len(jobs) == 1)
db.close()

# 清理
engine.dispose()
with admin.connect() as c2:
    c2.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH}"))
admin.dispose()

print(f"\n=== {'ALL PASS' if fail == 0 else str(fail) + ' FAILED'} ===")
sys.exit(1 if fail else 0)

import os, sys, time, asyncio, base64
DB, ROOT, FLAG = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["PLATFORM_DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["PLATFORM_CREDENTIAL_ENC_KEY"] = base64.b64encode(os.urandom(32)).decode()
from app.db import SessionLocal
from app.core import queue
from app.workers.handlers import HANDLERS
async def drain():
    n = 0
    while True:
        db = SessionLocal()
        try:
            job = queue.claim(db, job_types=list(HANDLERS.keys()))
            if job is None: break
            try:
                await HANDLERS[job.job_type](db, job.payload); queue.complete(db, job)
            except Exception as e:
                print("JOB FAIL", job.id, job.job_type, repr(e), flush=True); queue.fail(db, job, str(e))
            n += 1
        finally:
            db.close()
    return n
print("worker helper up", flush=True)
while True:
    if os.path.exists(FLAG):
        os.remove(FLAG); print("DRAINED", asyncio.run(drain()), flush=True)
    time.sleep(0.3)

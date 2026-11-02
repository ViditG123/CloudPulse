"""Redis worker with an in-flight queue and startup recovery.

A claimed job remains in cloudpulse:processing until acknowledged. On restart,
unacknowledged jobs are requeued. PostgreSQL job status prevents re-running
completed jobs. This is at-least-once processing, not exactly-once execution.
"""
import time
import psycopg
import redis
from app.tasks import execute
from app.main import DATABASE_URL, REDIS_URL, initialize

MAX_ATTEMPTS = 3
READY = "cloudpulse:jobs"
PROCESSING = "cloudpulse:processing"

def process_job(job_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute(
            "SELECT task, payload, attempts, status FROM jobs WHERE id=%s FOR UPDATE",
            (job_id,),
        ).fetchone()
        if not row:
            return
        task, payload, attempts, status = row
        if status in ("completed", "failed"):
            return
        if attempts >= MAX_ATTEMPTS:
            conn.execute("UPDATE jobs SET status='failed', error='Retry limit reached', updated_at=now() WHERE id=%s", (job_id,))
            return
        attempts += 1
        conn.execute(
            "UPDATE jobs SET status='running', attempts=%s, updated_at=now() WHERE id=%s",
            (attempts, job_id),
        )
    try:
        result = execute(task, payload)
    except Exception as exc:
        retry = attempts < MAX_ATTEMPTS
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(
                "UPDATE jobs SET status=%s, error=%s, updated_at=now() WHERE id=%s",
                ("retrying" if retry else "failed", str(exc)[:500], job_id),
            )
        if retry:
            redis.from_url(REDIS_URL).lpush(READY, job_id)
    else:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute(
                "UPDATE jobs SET status='completed', result=%s, error=NULL, updated_at=now() WHERE id=%s",
                (result, job_id),
            )

def recover_inflight(queue):
    """Requeue unacknowledged IDs after a worker restart.

    For a multi-worker deployment, use per-worker leases instead: a worker
    must not recover another live worker's in-flight jobs.
    """
    while True:
        job_id = queue.rpoplpush(PROCESSING, READY)
        if job_id is None:
            break

def main():
    initialize()
    queue = redis.from_url(REDIS_URL, decode_responses=True)
    recover_inflight(queue)
    print("CloudPulse worker ready", flush=True)
    while True:
        try:
            job_id = queue.brpoplpush(READY, PROCESSING, timeout=5)
            if job_id:
                process_job(job_id)
                queue.lrem(PROCESSING, 1, job_id)
        except (psycopg.Error, redis.RedisError) as exc:
            print("Worker infrastructure error:", exc, flush=True)
            time.sleep(2)

if __name__ == "__main__":
    main()

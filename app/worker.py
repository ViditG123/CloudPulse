"""Redis-backed worker with bounded retries and database status tracking."""
import time
import psycopg
import redis
from app.tasks import execute
from app.main import DATABASE_URL, REDIS_URL, initialize

MAX_ATTEMPTS = 3

def process_job(job_id):
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute("SELECT task, payload, attempts, status FROM jobs WHERE id=%s FOR UPDATE", (job_id,)).fetchone()
        if not row or row[3] not in ("queued", "retrying"):
            return
        task, payload, attempts, _ = row
        attempts += 1
        conn.execute("UPDATE jobs SET status='running', attempts=%s, updated_at=now() WHERE id=%s", (attempts, job_id))
    try:
        result = execute(task, payload)
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute("UPDATE jobs SET status='completed', result=%s, error=NULL, updated_at=now() WHERE id=%s", (result, job_id))
    except Exception as exc:
        retry = attempts < MAX_ATTEMPTS
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute("UPDATE jobs SET status=%s, error=%s, updated_at=now() WHERE id=%s", ("retrying" if retry else "failed", str(exc), job_id))
        if retry:
            redis.from_url(REDIS_URL).lpush("cloudpulse:jobs", job_id)

def main():
    initialize()
    queue = redis.from_url(REDIS_URL, decode_responses=True)
    print("CloudPulse worker ready", flush=True)
    while True:
        item = queue.brpop("cloudpulse:jobs", timeout=5)
        if item:
            try:
                process_job(item[1])
            except (psycopg.Error, redis.RedisError) as exc:
                print("Worker infrastructure error:", exc, flush=True)
                time.sleep(2)

if __name__ == "__main__":
    main()

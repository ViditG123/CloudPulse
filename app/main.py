"""Job API backed by PostgreSQL and Redis queue."""
import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg
import redis

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cloudpulse")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = FastAPI(title="CloudPulse", version="0.1.0")

class JobRequest(BaseModel):
    task: str = Field(pattern="^(uppercase|reverse|word_count)$")
    payload: str = Field(max_length=10000)

def initialize():
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, task TEXT NOT NULL, payload TEXT NOT NULL,
          status TEXT NOT NULL, result TEXT, attempts INTEGER NOT NULL DEFAULT 0,
          error TEXT, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now())""")

@app.on_event("startup")
def startup():
    initialize()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/jobs", status_code=201)
def submit_job(req: JobRequest):
    job_id = str(uuid.uuid4())
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("INSERT INTO jobs (id, task, payload, status) VALUES (%s,%s,%s,'queued')", (job_id, req.task, req.payload))
    try:
        redis.from_url(REDIS_URL).lpush("cloudpulse:jobs", job_id)
    except redis.RedisError:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute("UPDATE jobs SET status='queue_error', error='Redis unavailable' WHERE id=%s", (job_id,))
        raise HTTPException(status_code=503, detail="Queue unavailable; job recorded as queue_error")
    return {"id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute("SELECT id, task, status, result, attempts, error, created_at, updated_at FROM jobs WHERE id=%s", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(zip(("id", "task", "status", "result", "attempts", "error", "created_at", "updated_at"), row))

@app.get("/jobs")
def list_jobs():
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute("SELECT id, task, status, attempts FROM jobs ORDER BY created_at DESC LIMIT 100").fetchall()
    return [{"id": r[0], "task": r[1], "status": r[2], "attempts": r[3]} for r in rows]

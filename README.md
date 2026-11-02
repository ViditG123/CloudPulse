# CloudPulse — Distributed Job Processing (MVP)

FastAPI API, PostgreSQL job store, Redis queue, and an independent Python worker that executes bounded demonstration tasks.

> **Scope:** Local Docker Compose MVP. Crash-safe delivery, monitoring, AWS deployment and production-grade reliability are not yet implemented.

## Run

Install Docker Desktop, then run:

```bash
docker compose up --build
```

Open http://localhost:8000/docs. Submit a job with POST `/jobs`:

```json
{"task":"uppercase","payload":"hello"}
```

GET `/jobs/{id}` to inspect its status. Supported demo tasks: `uppercase`, `reverse`, `word_count`.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

## Architecture

`Client → FastAPI → PostgreSQL + Redis → Worker → PostgreSQL`

## Roadmap

- [ ] Crash-safe queue recovery and dead-letter queue
- [ ] Exponential backoff, monitoring and integration tests
- [ ] AWS deployment and production secrets

The Docker Compose configuration uses development-only credentials. Never submit secrets as job payloads.

## Worker recovery limitations

The worker now claims Redis jobs into an in-flight list, acknowledges them after processing, and requeues unacknowledged jobs on startup. This supports **single-worker restart recovery** in the local demo. PostgreSQL status checks prevent completed jobs from being re-executed after restart. Processing is at-least-once, not exactly-once.

**Do not scale this worker to multiple instances yet:** startup recovery could reclaim a live worker's job. Production use needs per-worker leases, idempotent tasks, delayed retries, durable queue configuration, monitoring and integration tests. AWS deployment has not been implemented or verified.

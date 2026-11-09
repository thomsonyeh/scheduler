# Workflow Scheduler

Runs workflows defined as DAGs of tasks. Ready tasks go to a batch scheduler (currently an in-memory mock), and a React UI shows each workflow's DAG with live per-task status and progress.

```
React UI ──poll 1.5s──▶ FastAPI (/api) ──▶ SQLite
                              ▲
            Orchestrator loop (asyncio, 1s tick)
                              │ submit / status / cancel
                              ▼
              BatchScheduler protocol ──▶ MockBatchScheduler
```

## Quick start

Requires `uv`, `pnpm`, and Node 20+.

```sh
make install
make dev          # backend on :8100, UI on http://localhost:5173
```

Submit a workflow from the UI ("New workflow", prefilled from `examples/`) or with curl:

```sh
curl -X POST localhost:8100/api/workflows -H 'content-type: application/json' -d @examples/diamond.json
```

The backend port defaults to 8100 because 8000 is often taken by Docker or OrbStack. Override it with `BACKEND_PORT=9000 make dev`.

## Workflow format

```json
{
  "name": "etl-nightly",
  "tasks": [
    {"name": "extract", "command": "python extract.py"},
    {"name": "transform", "command": "python transform.py", "depends_on": ["extract"]}
  ]
}
```

Submission returns 422 for duplicate task names, unknown or duplicate dependencies, self-dependencies, and cycles.

## Lifecycle

- **Task:** `PENDING → SUBMITTED → RUNNING → SUCCEEDED | FAILED`. Tasks downstream of a failure become `SKIPPED`. Unfinished tasks become `CANCELLED` when their workflow is cancelled.
- **Workflow:** `PENDING → RUNNING → SUCCEEDED | FAILED | CANCELLED`. A failed task doesn't stop independent branches; the workflow becomes `FAILED` once everything left has finished or been skipped.

The orchestrator (`backend/app/orchestrator.py`) re-derives all of its work from the database on every tick, so restarting the backend resumes in-progress workflows.

## API

| Method | Path | |
|---|---|---|
| POST | `/api/workflows` | Create a workflow |
| GET | `/api/workflows?status=` | List workflows with task counts and overall progress |
| GET | `/api/workflows/{id}` | Workflow plus all tasks |
| POST | `/api/workflows/{id}/cancel` | Cancel in-flight jobs and pending tasks |
| GET | `/api/healthz` | Health check |

Interactive docs are at http://localhost:8100/docs.

## Mock batch scheduler

`backend/app/batch/mock.py` simulates queue delay, a concurrency limit, progress, and failure. Configure it with environment variables:

| Variable | Default | |
|---|---|---|
| `SCHEDULER_MOCK_MIN_DURATION` / `_MAX_DURATION` | 5 / 20 | Job length in seconds |
| `SCHEDULER_MOCK_MAX_QUEUE_DELAY` | 3 | Seconds before a job can start |
| `SCHEDULER_MOCK_MAX_CONCURRENT` | 4 | Jobs running at once; extras stay queued |
| `SCHEDULER_MOCK_FAILURE_RATE` | 0 | Random failure probability |

A command containing the word `fail` (e.g. `--fail`) always fails halfway through. See `examples/failing.json`.

The mock keeps jobs in memory. After a backend restart, jobs that were in flight are reported as `FAILED: job lost`. A real batch backend would not lose jobs this way.

**Adding a real backend:** implement the `BatchScheduler` protocol in `backend/app/batch/base.py` (`submit`, a batched `status`, `cancel`) and pass it to `create_app(scheduler=...)`.

Other settings: `SCHEDULER_DATABASE_URL` (default `sqlite:///./scheduler.db`), `SCHEDULER_TICK_SECONDS` (1.0), `SCHEDULER_CORS_ORIGINS`.

## Development

```sh
make test        # backend pytest + frontend typecheck
make lint        # ruff + oxlint
make gen-types   # regenerate frontend/src/api/types.ts from the FastAPI schema
```

Run `make gen-types` after changing `backend/app/schemas.py`. The generator runs pinned to TypeScript 5.9 because `openapi-typescript` needs the TS 5 compiler API, while the app itself uses TypeScript 7.

Backend tests use a fake clock shared by the orchestrator and the mock scheduler, so full workflow runs finish in milliseconds.

## Not built yet

- Retrying failed tasks
- Task-level logs and outputs
- A real batch backend (AWS Batch, Slurm, k8s Jobs)
- Schema migrations (tables are created with `create_all`; add Alembic before the schema changes)
- Pagination beyond `limit`

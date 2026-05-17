# Backtest Engine Extension — Week 2 Supervised Sprint Plan

**Branch (skeleton):** `feat/backtest-engine-week2-prep`
**Sibling audit:** `docs/EXISTING_BACKTEST_ENGINE_AUDIT.md`
**Blockers:** `BLOCKERS_BACKTEST_WEEK2.md`

---

## Overview

Week 2 ships an **async, persisted, idempotent extension layer** around the existing `app.strategy_engine.backtest` engine without modifying any line of the engine itself. The deliverable family:

- 3 new tables (`backtest_runs`, `backtest_trades`, `backtest_metrics`)
- Celery task that wraps `run_backtest()` with state-machine semantics
- Idempotency hash over canonical input + engine_version
- 3 new API endpoints: `POST /api/backtest`, `GET /api/backtest/{id}`, `GET /api/backtest/{id}/trades`
- Coverage to the project's 96% standard

Skeleton (this branch) ships everything as `NotImplementedError`-bodied modules so Week 2's daily work is "fill in one module a day" rather than "design + implement under deadline."

---

## Day-by-day

### Day 1 — Persistence + migration apply

Goal: 028 lands in dev + staging, persistence helpers can write a synthetic run.

Work:
- Review `backend/migrations/versions/028_add_backtest_runs.py` (DRAFT on this branch). Fix anything the local Alembic dry-run flags.
- `alembic upgrade head` on dev DB.
- Implement `backtest_extension/persistence.py`:
  - `persist_run(db, *, request, hash_, engine_version, status="PENDING") -> uuid`
  - `update_run_status(db, run_id, status, *, error=None, completed_at=None)`
  - `persist_result(db, run_id, result: BacktestResult)` — INSERTs trade rows + metrics row
  - `fetch_cached_run(db, hash_) -> Optional[BacktestRun]` (SUCCEEDED-only, by hash)
- Smoke test: insert a `PENDING` row, look it up by hash, write a `SUCCEEDED` result, fetch trades.

Acceptance:
- `alembic upgrade head` clean on dev DB
- pytest fixture inserts + reads a run round-trip

### Day 2 — Idempotency

Goal: hash function is deterministic, total over the inputs that affect output.

Work:
- Implement `backtest_extension/idempotency.py`:
  - `compute_request_hash(request: BacktestEnqueueRequest) -> str` — canonical JSON of the request payload + `engine_version` constant, hashed with SHA-256, returned as hex
  - Reject any request whose canonical JSON differs by whitespace/ordering: assert hashes match after `json.loads`-roundtrip
- Tests (Day 2 deliverable, not on this skeleton branch):
  - Same input → same hash
  - Dict-order change → same hash (canonical sort)
  - Whitespace change → same hash
  - Engine version bump → different hash
  - `quantity=1.0` vs `quantity=1` → same hash (float coercion)
  - Cost field default vs explicit zero → same hash (defaults canonicalised)

Acceptance:
- 96%+ coverage on `idempotency.py`
- Property-based test (hypothesis) for "permutation of dict keys yields same hash"

### Day 3 — Celery task

Goal: `enqueue_backtest` dispatches to a worker; the worker drives state transitions correctly.

Work:
- Implement `backtest_extension/celery_tasks.py`:
  - `@shared_task(bind=True, max_retries=2, default_retry_delay=15)`
  - `run_backtest_task(self, run_id, request_payload)`:
    1. Load BacktestRun by id, status must be `PENDING` (else log + return — duplicate dispatch)
    2. `update_run_status(..., status="RUNNING")`
    3. Materialise candles (Dhan or synthetic) per `app.strategy_engine.data_provider`
    4. Call `run_backtest(BacktestInput.model_validate(...))`
    5. `persist_result(db, run_id, result)`
    6. `update_run_status(..., status="SUCCEEDED", completed_at=now)`
    7. On any uncaught exception: status=FAILED, error_json={"type", "message", "traceback"}, do NOT retry (retries are reserved for transient infra — Day 4 work)
- Local Celery worker dev script (`scripts/dev/run_backtest_worker.sh`) — new file
- Smoke test: enqueue → poll until SUCCEEDED → fetch trades

Acceptance:
- Local worker runs through happy path in < 10s for a 60-day 5m candle backtest
- Failure path leaves `error_json` populated and status=FAILED
- A duplicate dispatch (same run_id, already RUNNING) is a no-op

### Day 4 — API endpoints

Goal: three endpoints work end-to-end against the test DB.

Work:
- Implement `backtest_extension/api.py`:
  - `POST /api/backtest`:
    1. Build BacktestEnqueueRequest from body
    2. Hash input
    3. Look up `SUCCEEDED` run by hash for this user — if exists, return its `id` with `cached=True`
    4. Else create new `PENDING` `BacktestRun`, dispatch Celery task, return id with `cached=False`
  - `GET /api/backtest/{id}`:
    1. Owned-by-user check
    2. Return run row + metrics row joined (None metrics until SUCCEEDED)
  - `GET /api/backtest/{id}/trades`:
    1. Owned-by-user check
    2. Paginated trades list (default page_size=200; supports `?cursor=`)
- Register router in `app.main._register_routers` AFTER founder approval (this skeleton branch does NOT register)

Acceptance:
- Each endpoint has at least one happy-path + one auth-rejection + one 404 test
- Cached-hit returns in < 50ms (no Celery dispatch)
- Cache-miss returns 202 with run id + `cached=false`

### Day 5 — Rate limiting + queue isolation

Goal: prevent a single user from saturating the worker pool.

Work:
- Decide: Redis-backed token-bucket (existing pattern in `app.api.webhook`) or per-user concurrent-run-cap-from-DB (count of `RUNNING` rows for this user) — see `BLOCKERS_BACKTEST_WEEK2.md` Q1
- Implement chosen approach as middleware on `POST /api/backtest`
- Celery queue config: dedicated queue `backtest` so a flood doesn't starve the existing `notifications` + `kill_switch` queues — see `BLOCKERS_BACKTEST_WEEK2.md` Q2

Acceptance:
- 11th concurrent request from one user → 429 with `Retry-After`
- Dedicated worker started via `celery -A app.tasks.celery_app worker -Q backtest`
- Existing worker (default queue) is not consuming `backtest` messages

### Day 6 — Anonymous-config preview

Goal: enable "preview backtest before save" for the Phase 5 Strategy Builder and "preview template" for the Strategy Templates gallery.

Work:
- `POST /api/backtest` already accepts a `strategy_config` field (BacktestEnqueueRequest is config-first, strategy_id is optional)
- Wire the historical-data routing — see `BLOCKERS_BACKTEST_WEEK2.md` Q3 — to use a default symbol/timeframe/date_range when the request doesn't carry one
- Persistence: `BacktestRun.strategy_id = None` for anonymous-config runs (already supported by migration 028 — `strategy_id` is nullable)
- Audit log entry distinguishes anonymous-config from owned-strategy runs

Acceptance:
- Anonymous preview works end-to-end against a Phase 1 active template's `config_json` (after the Phase 5 → DSL mapping ships separately)
- Owned-strategy run still works against a populated `strategy_json`

### Day 7 — Engine versioning + observability

Goal: ensure cache invalidates correctly when the underlying engine ships a behavioural change.

Work:
- Add `app/strategy_engine/backtest/_version.py` with `__engine_version__: str` — bumped manually by whoever ships engine changes
- Import into `backtest_extension/idempotency.py`
- Engine version bump policy — see `BLOCKERS_BACKTEST_WEEK2.md` Q4 — captured in `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md` (this doc, in the §Engine-version bump policy section below)
- Observability:
  - structured log `backtest.run.completed` with `run_id`, `user_id`, `cached`, `total_trades`, `engine_version`, `duration_ms`
  - structured log `backtest.run.failed` with `error_type`, `traceback_first_line`, `duration_ms`
  - Prometheus counter `backtest_runs_total{status, cached, engine_version}`
- Coverage sweep — bring `backtest_extension/` to 96%+

Acceptance:
- 96%+ line + branch coverage on `backtest_extension/`
- Logs are queryable from CloudWatch
- Engine-version bump from "1.0" to "1.1" busts the cache (new hash on identical input)

---

## §Engine-version bump policy

`__engine_version__` is a `MAJOR.MINOR` string maintained by hand in `app/strategy_engine/backtest/_version.py`. Bump rules:

- **MAJOR (1.0 → 2.0):** semantic change to any output number — different P&L for the same input. Triggers a full cache wipe (every previously-cached run becomes stale). Coordinated rollout, ANNOUNCE in #engineering.
- **MINOR (1.0 → 1.1):** bug fix that materially changes output. Cache busts automatically (new hash). Backwards-compatible in API shape, not in numerics.
- **No-op for**: docstring edits, type annotations, refactors that pass the determinism suite without flagging.

The determinism suite is a small set of pinned `(input, expected_BacktestResult)` pairs in `backend/tests/strategy_engine/backtest/test_determinism_pins.py` — re-run on every PR; any drift either bumps the version OR reverts the offending change.

---

## What this branch ships (skeleton-only)

```
backend/app/backtest_extension/
    __init__.py              # re-exports run_backtest
    schemas.py               # Pydantic request/response models
    persistence.py           # SQL helpers (NotImplementedError bodies)
    celery_tasks.py          # @shared_task wrapper (NotImplementedError bodies)
    idempotency.py           # hash function (NotImplementedError body)
    api.py                   # FastAPI router, 3 endpoints (NotImplementedError bodies)
backend/migrations/versions/028_add_backtest_runs.py   # DRAFT, not applied
backend/tests/backtest_extension/
    __init__.py
    fixtures/                # sample request payloads + golden outputs
docs/EXISTING_BACKTEST_ENGINE_AUDIT.md
docs/BACKTEST_ENGINE_EXTENSION_PLAN.md  # this file
BLOCKERS_BACKTEST_WEEK2.md
```

NOT touched:
- `backend/app/strategy_engine/backtest/*` — entire engine frozen
- `backend/app/main.py` — router not registered until Day 4 of supervised work
- `backend/migrations/env.py` — no migration apply on any env this branch
- `backend/pyproject.toml` — no new packages (Celery + Redis already vendored)

## Verification gates between days

Each day ends with the same gate:
1. `pytest backend/tests/backtest_extension/` green
2. `mypy backend/app/backtest_extension/` clean (no new ignores)
3. `ruff check backend/app/backtest_extension/` clean
4. Coverage report shows `>= 96%` on the day's module
5. No file in `backend/app/strategy_engine/backtest/` was modified (diff-checked)
6. No new package added to `pyproject.toml`

A day that fails its gate **does not advance**. The Week 2 founder review on Day 4 (mid-sprint) and Day 7 (close) is the formal cut.

## Risks

| Risk | Mitigation |
|---|---|
| `precompute_indicators` dispatch table grows during Week 2 → version-bump churn | Engine-version bump is manual; only behavioural changes bump |
| Celery worker OOM on a 5-year minute-bar backtest | Day 5 caps `candles` length per request to 600k (default page_size for our 5y minute window); larger jobs require admin opt-in |
| `cached=True` race when two requests fire concurrently | Partial-unique index on `idempotency_hash WHERE status='SUCCEEDED'` blocks double-insert at the DB layer; the second request sees the first's row on a retry |
| Migration 028 conflicts with future migrations | Numbered sequentially; depends on 026 only. Re-rebase on whatever is HEAD at apply time |

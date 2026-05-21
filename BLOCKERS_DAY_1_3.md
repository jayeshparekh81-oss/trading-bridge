# BLOCKERS — Backtest Engine Extension Day 1-3

**Branch:** `feat/backtest-engine-day-1-3`
**Date:** 2026-05-17 → 2026-05-18 (autonomous 22-hour window)
**Decisions log:** `DAY_1_3_DECISIONS.md`
**Sprint plan:** `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md`

---

## Open questions for founder review before Day 4 begins

### Q1. Apply migration 028 to dev DB

The migration is **apply-ready, NOT applied** (hard guardrail #3).
Founder runs `alembic upgrade head` on dev when this branch lands.

Verify before applying:
- 3 new tables (`backtest_runs`, `backtest_trades`, `backtest_metrics`)
- 5 indexes (incl. partial unique on `(user_id, request_hash) WHERE status='SUCCEEDED'`)
- 3 CHECK constraints on `backtest_runs` (status set + completed_at + error consistency)
- Reversible via `downgrade()` — drops in FK-safe reverse order

```sh
# On dev:
cd backend
alembic upgrade head
# Verify:
psql -c "\d backtest_runs"
psql -c "\d backtest_trades"
psql -c "\d backtest_metrics"
```

### Q2. Register the FastAPI router (the founder-mount step)

Per hard guardrail #4, the router is NOT registered in `app/main.py`.
To activate the three endpoints:

```py
# In app/main._register_routers, add:
from app.backtest_extension.api import router as backtest_extension_router
app.include_router(backtest_extension_router)
```

Place AFTER `/api/strategies` routers so the catch-all
`/api/backtest/{run_id}` doesn't accidentally shadow anything.

### Q3. One existing-file edit: `app/tasks/celery_app.py`

The Celery `include=[]` list got one new entry:
`"app.backtest_extension.celery_tasks"`. This is required for the
worker to autodiscover the `@shared_task` definition. Without it,
`apply_async()` raises `NotRegistered`.

This is the ONLY existing-file edit on this branch (hard guardrail
#5 said "minimal existing-file edits, surface in BLOCKERS first").

Alternative: change to `@celery_app.task` and import `celery_app`
into the task module — same effective behaviour, different decorator.
Either way, an import path needs to be reachable from the worker boot.

Decision needed: accept the include= edit, or rewrite the task with
`@celery_app.task` to keep `celery_app.py` untouched.

### Q4. Decorate `run_backtest_task` with `queue=BACKTEST_QUEUE`?

Decision D6 + sprint spec say "DEFAULT to shared worker pool" — and
the current `@shared_task` decoration HAS NO queue= argument so it
lands on the default queue. The `BACKTEST_QUEUE = "backtest"` constant
is exported but not bound.

Day-5 work (worker isolation) will:
1. Add `queue=BACKTEST_QUEUE` to the decorator
2. Add a dedicated worker container to `docker-compose.yml`:
   `celery worker -A app.tasks.celery_app -Q backtest`

Founder confirms queue isolation strategy (A: dedicated worker, B:
shared with priority, or C: do not isolate) before Day 5 starts.

### Q5. Historical data routing is STUBBED

`celery_tasks._build_synthetic_candles_payload` returns a deterministic
60-bar candle list. This is **enough for tests + structural correctness**
but is NOT real market data. Day 6 of the original 7-day plan replaces
this with `app.strategy_engine.data_provider.fetch_historical_candles`.

Decision needed before Day 6 starts: confirm Dhan-fetch + synthetic-
fallback model + Redis cache TTL (24h proposed in
`BLOCKERS_BACKTEST_WEEK2.md` Q3).

### Q6. Rate limiting is TODO

Decision D7: no rate-limit middleware on `POST /api/backtest`.
The `responses=` block in the OpenAPI doc documents 429 for future
discoverability but no middleware emits it yet.

Decision needed before Day 5: pick rate-limit strategy from
`BLOCKERS_BACKTEST_WEEK2.md` Q1 (Redis token-bucket vs DB concurrent-
cap vs both).

### Q7. `strategy_config` (anonymous-config preview) is REJECTED

Decision D8: `POST /api/backtest` with `strategy_config` set returns
422 with detail "Anonymous-config preview is not yet supported".

Phase 7 (Strategy Builder visual canvas pre-save preview) will lift
this restriction. Until then, the only way to backtest is via an
owned `strategy_id`.

Decision needed: this is the right phasing, confirm or override.

### Q8. Engine version constant `"v1"` is hardcoded

The `idempotency.ENGINE_VERSION = "v1"` constant is hardcoded in
the module. Day 7 of the original plan ships
`app/strategy_engine/backtest/_version.py` with
`__engine_version__`. Until then, the constant is the source of truth.

Bump policy from `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md` §Engine-
version bump policy applies: behavioural changes bump the constant,
docstring-only changes don't.

Decision needed: confirm "v1" is the right starting version (vs "1.0"
which the original skeleton placeholder used). Decision D2 picked "v1"
per the 22-hour spec.

### Q9. `engine_version` field min_length

Original skeleton had `engine_version: str = Field(..., min_length=3, max_length=16)`.
"v1" is 2 chars so I changed to `min_length=2`. This affects
`BacktestEnqueueResponse.engine_version` validation.

Decision needed: keep min_length=2, or rename engine versions to
3-char prefix ("v01", "v02", …) to retain the original validation?

Recommendation: keep min_length=2 — "v1", "v2", "v3" is the natural
versioning vocabulary.

### Q10. `BacktestMetrics.warnings` JSON type

The migration ships `warnings` as JSONB with `default '[]'::jsonb`
on the PG side. The ORM uses `JSONB` with `default=list`. For sqlite
tests this works because the `@compiles(JSONB, "sqlite")` shim
in conftest routes JSONB → JSON. Production PG uses real JSONB.

Decision needed: none — flagging the dual-dialect support for future
test/prod parity questions.

### Q11. Worker autodiscovery + container restart

After founder approves Q3 (the celery_app.py include= edit) and
applies the change to a running worker, the existing worker container
needs to restart so it imports the new task module:

```sh
docker compose restart celery_worker
docker compose restart celery_beat  # if beat schedule changed (it didn't)
```

Decision needed: confirm restart procedure as part of the deploy
runbook for this branch.

### Q12. Test DB JSONB compiler shim is global

The `@compiles(JSONB, "sqlite")` shim in
`backend/tests/backtest_extension/conftest.py` is module-level and
applies process-wide once imported. Tests in other directories that
ALSO import the shim (e.g. `tests/strategy_engine/api/test_get_strategy_with_template_origin.py`)
register the same shim — re-registration is a no-op but the global
effect is real.

Decision needed: none — flagging the pattern. Future a single
shared conftest at `backend/tests/conftest.py` could host this once.

---

## Day 1-3 deliverable summary

```
backend/app/backtest_extension/
    __init__.py                 (kept from skeleton)
    api.py                      (overwritten — 3 endpoints, 501 → real)
    celery_tasks.py             (overwritten — @shared_task state machine)
    idempotency.py              (overwritten — SHA-256 hash function)
    models.py                   (new — ORM matching migration 028)
    persistence.py              (overwritten — 8 helpers)
    schemas.py                  (kept; min_length tweak only)

backend/migrations/versions/028_add_backtest_runs.py
    (docstring DRAFT → APPLY-READY)

backend/tests/backtest_extension/
    __init__.py                 (kept)
    conftest.py                 (new — fixtures + JSONB shim)
    test_api.py                 (new — 13 tests)
    test_celery_tasks.py        (new — 13 tests)
    test_idempotency.py         (new — 14 tests)
    test_persistence.py         (new — 25 tests)
    fixtures/                   (kept from skeleton)

backend/app/tasks/celery_app.py
    (1-line edit — include= list adds backtest_extension.celery_tasks)

DAY_1_3_DECISIONS.md            (new — 20 autonomous decisions)
BLOCKERS_DAY_1_3.md             (this file)
```

## Hard guardrails — confirmation

- ✅ NO modifications to `backend/app/strategy_engine/backtest/*`
  (`git diff origin/feat/backtest-engine-week2-prep --` returns empty)
- ✅ NO push to main, NO merge, NO PR creation
- ✅ NO SSH to EC2, NO docker on prod, NO alembic upgrade
- ✅ NO router register in `app/main.py` (founder mounts after review)
- ✅ Only 1 existing-file edit (Celery include= list, flagged in Q3)
- ✅ NO new external packages
- ✅ STOP at end of Day 3 — 65 tests across 4 files, all passing in 2.09s
- ✅ Days 4-7 work NOT improvised
- ✅ DAY_1_3_DECISIONS.md documents every autonomous call
- ✅ This file documents every founder-review item

## Test result tally

| Day | Test file | Tests | Pass rate |
|---|---|---:|---|
| 1 | `test_persistence.py` | 25 | 25/25 (100%) |
| 2 | `test_celery_tasks.py` | 13 | 13/13 (100%) |
| 3 | `test_idempotency.py` | 14 | 14/14 (100%) |
| 3 | `test_api.py` | 13 | 13/13 (100%) |
| **Total** | | **65** | **65/65 (100%) in 2.09s** |

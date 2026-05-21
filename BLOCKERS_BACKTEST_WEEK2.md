# BLOCKERS — Backtest Engine Week 2 Prep

**Branch:** `feat/backtest-engine-week2-prep`
**Date:** 2026-05-17
**Audit:** `docs/EXISTING_BACKTEST_ENGINE_AUDIT.md`
**Plan:** `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md`

---

## Open questions for founder review before Week 2 begins

### Q1. Rate-limit strategy — Redis token-bucket vs DB concurrent-cap

`POST /api/backtest` needs a per-user rate limit so one user can't
saturate the worker pool. Two patterns already exist in the codebase:

- **(A) Redis token-bucket** (used by `app.api.webhook` — 60 req/60s
  per `user_id` key). Pros: stateless, no DB round-trip, well-tested
  pattern. Cons: counts requests not concurrent jobs — a user can
  fire 60 long-running backtests in one minute and saturate the queue.

- **(B) DB concurrent-cap** — `SELECT COUNT(*) FROM backtest_runs
  WHERE user_id=? AND status IN ('PENDING','RUNNING')` then reject if
  ≥ N. Pros: directly caps the thing we care about (concurrency).
  Cons: DB round-trip per request, more code.

- **(C) Both** — token-bucket (10/min cheap) + concurrent-cap (3 in-flight).

Recommendation: **(C)**. The token-bucket protects against accidental
loops (browser retry storms, misconfigured automations); the
concurrent-cap protects against bona-fide flooders.

Decision needed: which to ship Day 5, or accept (C).

### Q2. Queue isolation — dedicated `backtest` worker vs shared default

Celery is already running with the default worker consuming
`notifications` + `kill_switch` tasks. Backtest jobs are ~5-15s CPU
each (longer for 5-year windows). Two options:

- **(A) Dedicated worker** — `celery worker -Q backtest` started on a
  separate container/process. Pros: backtest flood can't block
  notifications + kill-switch (which have hard latency SLAs). Cons:
  another process to monitor + scale.

- **(B) Shared worker, lower priority** — Celery supports task
  priority on the same worker. Pros: no new process. Cons: priority
  is a Redis broker-level concept and our docker-compose worker pool
  is small; a long backtest still hogs a worker slot.

Recommendation: **(A)**. The kill-switch tasks page someone if they
queue for > 5 s, and the notification tasks back customer-visible
"Order placed" messages — neither can wait behind a backtest.

Decision needed: add new worker container to `docker-compose.yml`
(separate branch, after Week 2 PR lands) and pass dedicated worker
flag to a Day 5 commit on the Week 2 branch.

### Q3. Historical-data routing for anonymous-config backtests

Day 6 wires the anonymous-config preview. The engine needs candles.
Three sources available:

- **Dhan historical** — what the existing Phase D Strategy Tester
  uses (`app.strategy_engine.data_provider.fetch_historical_candles`).
  Pros: real data. Cons: rate-limited at the upstream API; quota
  shared with live-trading paths.

- **Cached candles** — Day 6 could add a Redis cache layer keyed by
  `(symbol, timeframe, start, end)` so repeated preview backtests on
  the same window don't burn Dhan quota.

- **Synthetic fallback** — `app.strategy_engine.api.backtest:236`
  already has this fallback path when Dhan fetch fails. Acceptable
  for preview UX but not for production "real backtest" claims.

Recommendation: **Dhan + Redis cache (TTL 24h)**. Preview backtests
hit hot cache on second+ run, fall back to Dhan on miss, fall back
to synthetic when Dhan errors. Cache key: `bt:candles:{symbol}:{tf}:{start}:{end}`.

Decision needed: Redis cache TTL value (24h proposed) + cache key
collision strategy with the Phase D Strategy Tester (which currently
does not cache).

### Q4. Engine-version bump policy

The skeleton's `idempotency.engine_version()` returns the placeholder
`"1.0"`. Day 7 wires the real version constant in
`app/strategy_engine/backtest/_version.py`. The bump policy is
documented in the §Engine-version bump policy section of
`docs/BACKTEST_ENGINE_EXTENSION_PLAN.md`.

Decision needed:
- Confirm the MAJOR.MINOR scheme + the bump rules (semantic change → MINOR,
  identical output → no-op).
- Who owns the bump call when multiple engine PRs are in flight? Proposal:
  the merging maintainer bumps in the merge commit; conflicts are merge
  conflicts on `_version.py` that force a single resolution.

### Q5. Where does `backtest_runs.strategy_id` FK action go on Strategy delete?

Migration 028 sets `ON DELETE SET NULL` for the strategy_id FK. That
means deleting a strategy preserves its backtest history (run_id +
metrics survive), the row just loses the strategy pointer.

Alternative: `ON DELETE CASCADE` — delete the strategy, delete every
backtest of it. Cleaner DB but destroys historical evidence the user
might want for the marketplace ledger.

Recommendation: **SET NULL** (current). The marketplace ledger needs
historical proof; even a deleted strategy's backtest history is
evidence the user once owned it. Confirm before applying.

### Q6. Result-size guardrails

A 5-year minute-bar backtest produces ~600k candles in
`equity_curve` and potentially thousands of trades. Storing every
equity-point in the DB is wasteful — the API consumer only needs the
metrics + trades.

Migration 028 deliberately **does NOT persist equity_curve**. The
metrics row carries everything most consumers need; trades give the
detail. Consumers who want the equity curve must re-run the engine
(or, post-Phase-9, fetch from a separate equity-points table that
materialises only on demand).

Decision needed: is the "no equity curve persisted" design accepted
for Week 2? If founder wants equity curve cached, add a fourth table
`backtest_equity_points` or compress into a `numpy`-style blob inside
`backtest_runs`.

### Q7. Are 3 endpoints enough?

Skeleton router exposes:
- `POST /api/backtest` (enqueue)
- `GET /api/backtest/{id}` (run + metrics)
- `GET /api/backtest/{id}/trades` (paginated trades)

NOT exposed:
- `DELETE /api/backtest/{id}` — should users be able to delete a
  cached run? (Cost: lose the cache; gain: privacy/clean-up.)
- `GET /api/backtest` — list backtest history for the calling user
  (paginated, filterable by strategy_id / status / date_range).

Recommendation: defer both to Phase F C5 (a follow-up sprint). Week 2
ships the minimum viable surface.

### Q8. New dependencies?

Audit confirms **no new packages required**: Celery + Redis + asyncpg
+ SQLAlchemy are all already in `pyproject.toml`. The extension uses
only existing infra. If Day 6's Redis-cache decision (Q3) needs a new
library (it doesn't — `redis.asyncio` is already vendored), it will
be flagged in a follow-up commit.

---

## What this branch ships

```
docs/EXISTING_BACKTEST_ENGINE_AUDIT.md        full structural audit
docs/BACKTEST_ENGINE_EXTENSION_PLAN.md        7-day sprint plan + version policy
BLOCKERS_BACKTEST_WEEK2.md                    this file
backend/migrations/versions/028_add_backtest_runs.py   DRAFT migration (NOT applied)
backend/app/backtest_extension/
    __init__.py            re-exports run_backtest from strategy_engine.backtest
    schemas.py             Pydantic request + response models
    persistence.py         SQL helpers — NotImplementedError bodies
    celery_tasks.py        @shared_task wrapper — NotImplementedError bodies
    idempotency.py         hash function — NotImplementedError body
    api.py                 FastAPI router, 3 endpoints — 501 bodies, NOT registered
backend/tests/backtest_extension/
    __init__.py
    fixtures/
        __init__.py
        README.md
        sample_enqueue_request.json     placeholder Day-1 fills
        sample_strategy_config.json     real Phase-1 template config_json
```

NOT touched:
- Any file in `backend/app/strategy_engine/backtest/`
- `backend/app/main.py` — router not registered
- `pyproject.toml` — no new packages
- Any existing migration
- Any existing test

## Pre-Week-2 checklist

Before Day 1 of the supervised sprint can begin:

1. Founder answers Q1-Q7 above
2. PR-style review of `028_add_backtest_runs.py` against the audit + plan
3. Decision on whether to merge this prep branch to main as a single
   "Week 2 skeleton" PR, or keep it open and rebase each Day-N commit
   on top
4. Worker container decision (Q2) — if dedicated worker is approved,
   the docker-compose change needs to ship before Day 5

# Queue CCC Sprint 2 — Report

**Date:** 2026-06-12 (resumed from halt of 2026-06-03)
**Branch:** `feat/queue-ccc-historical-candles-skeleton`
**Commits (Sprint 2):** 7 commits a–g (+ DDD fix merge)
**Status:** ✅ SKELETON COMPLETE — Phase 2b green, Phase 2c PENDING (G4 skipped, see §6)

---

## 1. Scope delivered

Persistent `historical_candles` store: ORM, hand-written Alembic migration, schema bridges, async repository, comprehensive unit tests, and a manual Dhan smoke test. All work is additive — no edits to shared files.

| Layer | File | Lines |
|---|---|---|
| F1 ORM model | `backend/app/db/models/historical_candle.py` | 159 |
| F2 Migration | `backend/migrations/versions/029_historical_candles.py` | 144 |
| F3 Services pkg shell | `backend/app/services/historical_candles/__init__.py` | 21 |
| F4 Repository | `backend/app/services/historical_candles/repository.py` | 257 |
| F5 Schema bridges | `backend/app/services/historical_candles/schema_bridge.py` | 161 |
| F6 Tests | `backend/tests/services/historical_candles/*` | 521 (4 files) |
| F7 Manual Dhan smoke test | `backend/scripts/manual_test_phase2c_dhan_nifty50.py` | 185 |

## 2. Commit trail

```
fb1347e  feat(historical-candles): F7 Phase 2c manual Dhan smoke test
5482f0b  test(historical-candles): F6 skeleton tests — 34 cases, 100% coverage
d503eec  feat(historical-candles): F4 repository — upsert_batch + reads + CoverageReport
997e1f1  feat(historical-candles): F5 schema_bridge — 4 pure Candle↔ORM converters
569f83e  feat(historical-candles): F2 alembic migration — create historical_candles table
3b50e74  merge: incorporate Queue DDD 027 UUID-cast fix into Sprint 2 skeleton branch
ad56d95  docs(queue-ccc): Sprint 2 Phase 2b HALTED — 027 migration UUID cast bug  (pre-resume)
93cf3b6  feat(historical-candles): F1 model + F3 services package shell  (pre-resume)
```

Plus the upcoming `(g)` — this report.

## 3. Founder-gates trail

| Gate | Outcome | Notes |
|---|---|---|
| DDD-G1 | ✅ approved (after G1-bis revision) | Originally `::uuid` suffix collided with SQLAlchemy `text()` bindparam parser. Revised to `CAST(:live_id AS uuid)`. Net diff: 2 lines on `027_strategies_is_paper.py`. |
| DDD-G2 | ✅ approved | alembic head reached 028, seeds re-applied cleanly. |
| Sprint 2 G2 | ✅ approved (after G2-bis revision) | Original revision id `029_create_historical_candles_table` (36 chars) overran `alembic_version.version_num` VARCHAR(32). Renamed to `029_historical_candles` (22). |
| Sprint 2 G3 | ✅ approved | 33 test-case list reviewed before pytest run. |
| Sprint 2 G4 | ⏸ SKIPPED | Founder asleep, Dhan creds unavailable. Phase 2c PENDING for Saturday — script `F7` is on disk and runnable. |

## 4. Queue DDD (027 UUID-cast) — folded in

The halt-doc blocker `027_strategies_is_paper.py` was fixed on branch `fix/queue-ddd-migration-027-uuid-cast` (commit `20a8044`) and merged into this skeleton branch via merge-commit `3b50e74`. Net change: 2 lines, no semantic change to the BSE LTD live carve-out (id `89423ecc-…` preserved verbatim). Production EC2 is already past 028, so the fix only matters for fresh-DB bootstraps — exactly the DR/new-environment hazard founder flagged.

## 5. Test results — F6 green

```
34/34 passed, 0 failed

Name                                              Stmts  Miss  Cover
app/services/historical_candles/__init__.py           3     0   100%
app/services/historical_candles/repository.py        57     0   100%
app/services/historical_candles/schema_bridge.py     17     0   100%
TOTAL                                                77     0   100%
```

Two fix iterations were used:
1. **schema_bridge invariant slip** — `test_orm_to_engine_candle__decimal_to_float_via_str` initialised an ORM with `open=42.05` but kept the default `low=1230, high=1240`, violating `EngineCandle`'s `low ≤ open ≤ high` invariant. Fixed by giving the test row a coherent OHLC range.
2. **"Attached to a different loop"** — pytest-asyncio creates a fresh event loop per test, but `get_sessionmaker()` caches an LRU singleton bound to the FIRST loop. Subsequent tests reusing the cached engine raise `RuntimeError`. Fixed by calling `await dispose_engine()` in the `db_session` fixture teardown.

Both fixes are in F6-test files only — no changes to F4/F5 production code.

## 6. Phase 2c (G4 manual Dhan test) — PENDING for Saturday

The manual smoke test (`F7`) is ready to run. Saturday session (creds available) executes:

```bash
export DHAN_CLIENT_ID=...
export DHAN_ACCESS_TOKEN=...
docker compose exec -e DHAN_CLIENT_ID -e DHAN_ACCESS_TOKEN \
    backend python -m scripts.manual_test_phase2c_dhan_nifty50
```

Expected outcome: ≤7 NIFTY 50 daily bars fetched from Dhan v2, persisted via `chart_candle_to_orm` → `repository.upsert_batch`, then verified through `repository.coverage`. Idempotent — re-running is a `ON CONFLICT DO NOTHING` no-op.

## 7. Schema notes

- **CHECK constraint double-prefix:** `SQLAlchemy MetaData` carries an auto naming-convention that prepends `ck_<tablename>_` to CHECK names. The migration's explicit `ck_hc_*` names end up as `ck_historical_candles_ck_hc_*` in Postgres. Functionally identical, but worth knowing when grepping `pg_constraint`. Phase 3 / autogen reconciliation can rename if/when needed.
- **Composite PK + 2 indexes** match the F1 ORM verbatim. `idx_hc_lookup` serves the dominant Phase 3 backtest query (window read, latest first). `idx_hc_freshness` is a partial index on intraday timeframes only.
- **Numeric(18, 4)** on OHLC is load-bearing for paise-safe round-trip via `schema_bridge` (`Decimal(str(float))`).

## 8. Phase 3 handoff

Phase 3 (orchestrator, Celery backfill task, rate-limit guard, backfill jobs ORM + migration 030, 22-symbol backfill script) is being authored in the overnight continuation session immediately following this report. Phase 3 work is **code-only** — no DB migrations applied, no Dhan calls, no main merge. See `docs/QUEUE_CCC_OVERNIGHT_BRIEF.md` for the morning founder menu (commits list, parked gates, anomalies, push decisions).

Approved Phase 3 decisions from design v2 (Q1–Q8) drive the implementation:
- Q1: chunking >90 days intraday / >5 years daily inside the orchestrator
- Q4A: Celery backfill task ships with feature-flag DEFAULT OFF
- Q6A: quality_score populated per-bar by the orchestrator
- 22-symbol scope: BSE LTD, CDSL, 5 indices, 15 NIFTY-50 (script-only tonight)

## 9. Branch / push state

| Branch | HEAD | Pushed |
|---|---|---|
| `fix/queue-ddd-migration-027-uuid-cast` | `20a8044` | (decision in OVERNIGHT_BRIEF) |
| `feat/queue-ccc-historical-candles-skeleton` | `fb1347e` + this commit | (decision in OVERNIGHT_BRIEF) |
| `main` | `0075d08` (local, 14 commits behind origin) | UNTOUCHED |
| `origin/main` | upstream HEAD | UNTOUCHED |

Drift check (3 critical files) at session start vs origin/main: `backend/app/schemas/candle.py`, `backend/app/strategy_engine/schema/ohlcv.py`, `backend/app/brokers/dhan_historical.py` — all unchanged. Sprint 2 is safe to merge to origin/main with a clean fast-forward whenever founder green-lights.

— end of report —

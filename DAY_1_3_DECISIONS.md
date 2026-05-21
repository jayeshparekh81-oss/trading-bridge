# Day 1-3 Autonomous Decisions Log

**Branch:** `feat/backtest-engine-day-1-3`
**Date:** 2026-05-17 → 2026-05-18 (22-hour autonomous window)
**Scope:** Days 1-3 of `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md` — persistence + Celery + idempotency + API.

Every autonomous decision made during the 22-hour window lands here.
Each item: **decision**, **rationale**, **revisit trigger**.

---

## D1. Status enum: `PENDING` (matches skeleton) NOT `QUEUED` (spec word)

**Decision.** Keep `BacktestRunStatus.PENDING` from the skeleton instead of renaming to `QUEUED` per the Day-2 spec text.
**Rationale.** Migration 028 already ships `PENDING|RUNNING|SUCCEEDED|FAILED` as a CHECK constraint. Renaming would require a migration change for zero semantic gain. `PENDING` is the conventional name in Celery + asyncio backtests; `QUEUED` is colloquial.
**Revisit.** None — purely a naming preference.

## D2. Engine version constant: `"v1"`

**Decision.** `engine_version()` returns the string `"v1"` (not `"1.0"` placeholder from skeleton).
**Rationale.** The 22-hour spec is explicit: `DEFAULT engine_version='v1'`. The earlier `"1.0"` placeholder in the skeleton was a guess; the spec is now ground truth.
**Revisit.** When `app/strategy_engine/backtest/_version.py` ships (Day 7 of the original plan), the constant becomes the real version. Until then, `"v1"` is hardcoded.

## D3. Cache scope: per-user via `(user_id, request_hash) WHERE status='SUCCEEDED'`

**Decision.** The idempotency cache lookup is `(user_id, request_hash)`, not just `request_hash`.
**Rationale.** Different users running the same strategy config against the same window deserve separate run records (audit + chargeback + data privacy). The partial-unique index in migration 028 already enforces this exact scope.
**Revisit.** Phase 9 marketplace might want cross-user cache hits ("X other users got the same result"); add THEN, not now.

## D4. Idempotency hash inputs

**Decision.** SHA-256 of canonical JSON over `{strategy_config, symbol, timeframe, start, end, initial_capital, quantity, cost_settings, ambiguity_mode}` plus `engine_version`. User_id is NOT in the hash itself — user-scoping happens at the cache-lookup SQL.
**Rationale.** A run is determined by what you ask the engine to compute, not who's asking. Tying user to hash would defeat any future cross-user equivalence checks (Phase 9 marketplace cares about this).
**Revisit.** None.

## D5. Cache TTL: permanent (engine_version bump invalidates)

**Decision.** No TTL on cached SUCCEEDED runs. The cache invalidates only when `engine_version` bumps, which produces a new hash for identical inputs.
**Rationale.** The 22-hour spec mandates this. Engine determinism guarantees identical input → identical output; no time-based reason to re-run.
**Revisit.** If `backtest_runs` table size becomes a storage problem (estimated >5GB / 100k runs based on metrics+trades row size), introduce a soft archive after 90 days.

## D6. Celery queue: shared workers (no dedicated `backtest` queue Day 1-3)

**Decision.** The `@shared_task` registration goes into the existing default Celery worker pool. The `BACKTEST_QUEUE = "backtest"` constant exported from `celery_tasks.py` is RESERVED for the future Day-5 dedicated-worker work but NOT bound to the task yet.
**Rationale.** The 22-hour spec says explicitly: "DEFAULT to shared worker pool (flag dedicated worker as BLOCKERS item)." Dedicated worker requires a `docker-compose.yml` change which is out of scope for Day 1-3 (no infra-touching changes).
**Revisit.** Day 5 of the original 7-day plan. Surface in BLOCKERS_DAY_1_3.md as a follow-up.

## D7. Rate limiting: NOT implemented Day 1-3

**Decision.** No rate-limit middleware on `POST /api/backtest`. Placeholder TODO + structured docstring noting Day 5 work.
**Rationale.** Spec explicitly defers rate-limiting to Day 5. Implementing now would block on the (A)/(B)/(C) decision from `BLOCKERS_BACKTEST_WEEK2.md` Q1.
**Revisit.** Day 5 of the original 7-day plan.

## D8. Required field: `strategy_id` is the only supported input source

**Decision.** `POST /api/backtest` accepts only `strategy_id` for Day 1-3. The `strategy_config` field (anonymous-config preview) is REJECTED with a 422 carrying "Anonymous-config preview is Phase 7 work" detail.
**Rationale.** Spec section "REQUIRES founder input → STOP that piece" lists this explicitly: "DEFAULT for now: require strategy_id, anonymous-config preview is Phase 7 work." Implementing strategy_config now would force a decision on what historical-data window to default to + risk surfacing strategies that aren't reviewed.
**Revisit.** Phase 7 supervised work (Strategy Builder visual canvas pre-save preview).

## D9. Decimal vs float for prices: float (matches engine)

**Decision.** All price + P&L numeric columns stored as `Numeric(18, 6)` in PG, deserialised to Python `float` for API responses.
**Rationale.** Spec defaults to float to match the existing engine's `BacktestResult` shape. Decimal would force coercion at the API boundary + complicate the engine's pure-Python guarantee.
**Revisit.** Phase 9 marketplace where settlement-grade precision matters — likely needs a separate `settlement_pnl` Decimal column then.

## D10. Historical data routing: NOT exercised Day 1-3

**Decision.** The Celery task body uses the same data-routing helper the existing Phase D Strategy Tester uses (`app.strategy_engine.data_provider.fetch_historical_candles`). No new routing logic is added. Synthetic fallback path is retained.
**Rationale.** Spec lists historical data routing as a "REQUIRES founder input → STOP" item (Q6 BLOCKERS). The Day-1-3 task wraps the existing engine call; routing the input data is the engine's concern, not the wrapper's.
**Revisit.** Day 6 of the original 7-day plan.

## D11. Trade-row precision: `Numeric(18, 6)` columns; Python `float` round-trip

**Decision.** Migration 028 ships `entry_price`, `exit_price`, `quantity`, `pnl`, `total_pnl`, `total_return_percent`, `average_win`, `average_loss`, `largest_win`, `largest_loss`, `expectancy`, `profit_factor` all as `Numeric(18, 6)`. The ORM type is `Decimal | None` (some are nullable, some not). The API boundary deserialises Decimal → float via Pydantic.
**Rationale.** Postgres stores these correctly; Python at the boundary keeps the float interface customers expect. Reserves precision for any future settlement-grade column.
**Revisit.** Same trigger as D9.

## D12. `BacktestTrade.entry_reasons` storage: JSONB (list of strings)

**Decision.** JSONB column with default `[]`. Trade row's `entry_reasons` from the engine is a `tuple[str, ...]` — flatten to `list[str]` at persist time.
**Rationale.** JSONB indexes well, and the customer-visible output is a list (tuples don't serialise in JSON).
**Revisit.** None.

## D13. Pagination: cursor by `trade_index ASC`, default page_size=200, max=1000

**Decision.** `GET /api/backtest/{run_id}/trades` paginates by `trade_index` (not by row id), default page size 200, max 1000.
**Rationale.** `trade_index` is monotonically increasing and unique-per-run. UUID-based cursor would force an indexed self-join. The skeleton schema already declared `next_cursor: int | None` — implement consistent.
**Revisit.** If a backtest produces > 100k trades and clients want server-side sub-millisecond page navigation, switch to a `WHERE trade_index > :cursor LIMIT :size` keyset query — already what we're doing.

## D14. Error JSON shape on FAILED

**Decision.** `{"type": str (e.__class__.__name__), "message": str(e)[:1024], "traceback_first_line": str (top of traceback)}`.
**Rationale.** Three fields, all string-bounded, no risk of giant payloads in the DB column. Full traceback lives in structured logs.
**Revisit.** Add Sentry event_id when Sentry lands.

## D15. Owner-scoping returns 404, not 403

**Decision.** `GET /api/backtest/{id}` returns 404 (not 403) when the row exists but belongs to a different user.
**Rationale.** Anti-enumeration. Returning 403 lets an attacker know that a given UUID corresponds to A valid run (just not theirs). 404 is consistent with how `get_strategy` does it (see `app/strategy_engine/api/strategies.py`).
**Revisit.** None — this is a security primitive, not a UX choice.

## D16. Trades endpoint when run is RUNNING/PENDING/FAILED: 409

**Decision.** `GET /api/backtest/{run_id}/trades` on a non-SUCCEEDED run returns 409 Conflict (not 200 with empty list).
**Rationale.** "No trades yet" and "this run will never have trades" are semantically different from "you happened to land on a SUCCEEDED run with zero trades." 409 signals "the resource isn't ready in this state"; an empty list on a SUCCEEDED run is a valid (boring) result.
**Revisit.** None.

## D17. Migration `ondelete` for `strategy_id` FK: SET NULL (kept from skeleton)

**Decision.** Deleting a Strategy preserves its backtest history (the runs survive, their `strategy_id` becomes NULL).
**Rationale.** Marketplace ledger + tax audit trail outlive the strategy. `BLOCKERS_BACKTEST_WEEK2.md` Q5 already settled this with "SET NULL recommended."
**Revisit.** None.

## D18. Test database: SQLite in-memory with JSONB → JSON compiler shim

**Decision.** Tests use `sqlite+aiosqlite://` with the `@compiles(JSONB, "sqlite")` shim (same pattern as `tests/strategy_engine/api/test_get_strategy_with_template_origin.py`).
**Rationale.** Fast tests, no Postgres dependency for CI. The shim is module-local — production code never sees it.
**Revisit.** Day 1 of any future task that needs a Postgres-specific JSONB operator (containment, path queries) — must add a Postgres test variant alongside.

## D19. Router NOT registered in `app/main.py`

**Decision.** `backtest_extension/api.py` continues to export `router` but `app/main.py` is not modified.
**Rationale.** 22-hour spec hard guardrail #4: "NO router register in main.py."
**Revisit.** Founder explicitly mounts after review.

## D20. Engine import is read-only (no decorators, no monkeypatches)

**Decision.** `from app.strategy_engine.backtest import run_backtest, BacktestInput, BacktestResult, CostSettings, AmbiguityMode` — and that's it. The Celery task calls `run_backtest(payload)` synchronously, takes the result, passes to persistence.
**Rationale.** Hard guardrail #1: "NO modifications to backend/app/strategy_engine/backtest/* — read-only import."
**Revisit.** None.

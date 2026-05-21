# Milestone 3 — Design Notes (Queue DD)

Decisions made (and decisions deferred) while shipping the backtest
trade-markers backend in Queue DD.

---

## 1. `backtest_run_id` storage: signal_metadata JSON vs new column

**Choice made:** store `backtest_run_id` inside the existing
`trade_markers.signal_metadata` JSON column. No migration.

**Alternatives considered:**

| Option | Pros | Cons |
|--------|------|------|
| **JSON metadata (chosen)** | Zero schema change; ships tonight. | Per-run lookup is Python-side filter — O(n) on per-strategy markers. |
| **New indexed column** (`backtest_run_id UUID FK NULLABLE`) | O(log n) lookup; clean JOIN to `backtest_runs`. | Requires alembic migration; Queue CC+DD explicitly forbid migrations from this session. |
| **Separate `backtest_run_markers` link table** | Strictest referential integrity. | Doubles writes; over-engineered for read-mostly chart data. |

**Trade-off accepted:** the JSON path lookup will be acceptably fast
until per-strategy marker counts pass ~10k rows. At that point, add the
indexed column in a follow-up migration. The persist + fetch functions
in `app/backtest_extension/trade_markers.py` are written so that
swap-in is a localised edit, not a rewrite.

---

## 2. DB-level partial unique index on `(strategy_id, side, price, second(timestamp_utc))`

**Concern:** the existing partial unique index (migration 025) prevents
TWO different backtest runs on the same strategy from writing markers
at the SAME (price, second) — which would happen routinely since
identical strategies re-run on identical data produce identical trades.

**Behaviour today:** `bulk_emit_markers` pre-scans for the dedup window
and returns the existing row instead of inserting. So the second backtest
run silently "borrows" the first run's markers (which carry the FIRST
run's `backtest_run_id` in `signal_metadata`).

**Impact:** if a user re-runs a backtest and then queries
`GET /api/backtest/{run_id}/markers` with the SECOND run's id, the
fetch will return ZERO markers (because the persisted rows carry the
first run's id). The user would see an empty chart even though the
backtest succeeded.

**Mitigation (today's prototype):** the per-run idempotency check
in `persist_backtest_trade_markers` runs BEFORE the bulk insert. If a
prior run's markers already exist (matching by strategy/mode/dedup
window), the function returns 0 and the second run's id never gets
persisted — but the user still sees the SECOND run's markers via the
strategy-mode-scoped `/api/markers` endpoint (which doesn't filter by
run id).

**Permanent fix:** drop the `(strategy_id, side, price, second(ts))`
unique constraint for `mode=BACKTEST` rows specifically — backtest
markers carry their own run-id and don't need wall-clock-second dedup.
That's a follow-up migration; not done tonight.

---

## 3. Exit-reason mapping (engine string → MarkerExitReason enum)

**Choice:** map known engine strings (`stop_loss`, `target`,
`trailing_stop`, `signal`, `backtest_end`) to the closest enum member.
Unknown strings degrade to `SIGNAL`.

**Rationale:** `exit_reason` is used by the chart for the tooltip label
only — never for any logic gate. A wrong tooltip label on an unrecognised
reason is a smaller harm than raising and failing the persist call.

Mapping table is in `_EXIT_REASON_MAP` (lowercase keys; case-insensitive
lookup). Adding new mappings is a one-line edit.

---

## 4. Quantity coercion (float → int)

Engine `Trade.quantity` is `float` (supports fractional lots). The
`trade_markers.quantity` column is `Integer` (per existing schema).
Coercion: `int(round(quantity))` with floor at 1.

**Trade-off:** lose sub-integer precision (1.5 lots → 2). Acceptable
because chart markers don't use quantity for sizing visualisation —
the arrow is fixed-size; quantity drives nothing visible.

If precision matters for a future "size-weighted marker" feature, add
a `quantity_decimal: Numeric(20,8)` column or migrate the existing
column to Numeric. Not blocking.

---

## 5. Symbol + exchange defaults in the celery hook

The hook reads `payload.get("symbol", "NIFTY")` and `payload.get("exchange", "NSE")`.
The request schema has `symbol` (default "NIFTY") but NO `exchange` field.

**Implication:** every backtest currently records markers with
`exchange="NSE"`. If the BSE-Ltd live strategy or other BSE-traded
templates need backtest chart markers, the request schema needs to
gain an `exchange` field (or the symbol → exchange resolution moves
to the celery task itself, similar to the live-trading `futures_resolver.py`).

**Not blocking for ship:** the existing customer-facing path is
NSE-only equity templates. BSE templates aren't in the active seed
set yet (per Queue Z + AA audits). When they ship, this is a known
follow-up.

---

## Summary of follow-ups (in priority order)

1. **Migration: drop the backtest-mode entries from the partial unique
   index** (or scope it to PAPER/LIVE only). Unblocks accurate per-run
   marker queries when users re-run backtests.
2. **Migration: add `trade_markers.backtest_run_id` (indexed FK).**
   Replaces the JSON-path lookup with O(log n) query; simplifies the
   persist + fetch functions.
3. **Request schema: add `exchange` field** to `BacktestEnqueueRequest`.
   Unblocks BSE / multi-exchange templates.
4. **Frontend: wire the chart panel to the new endpoint** (~2 hr; see
   `MILESTONE_3_NEXT_STEPS.md`).

All four are independent and can land in separate small PRs.

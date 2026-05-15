# Phase A — Persistent Trade Markers

> **Status:** backend infrastructure landed on `feat/phase-a-markers`
> as 8 new files. Router + registry wire-ups deferred to manual patch
> (see `backend/PATCH_INSTRUCTIONS_PHASE_A.md`). No existing file
> modified.

---

## TL;DR

Phase A introduces a single new table — **`trade_markers`** — that
persists every strategy entry/exit event across all three execution
modes: BACKTEST, PAPER, and LIVE. Today the chart marker overlay
*derives* paper-mode markers on-read from `paper_trades` rows
(`app.services.chart_marker_service`). Phase A is the future
write-side that will, in Phase B+, replace that derivation path so
backtests and live executions can also surface markers on the chart.

The two systems coexist in parallel until Phase B migrates the read
path. Until then, **no production behaviour changes** — the legacy
`/api/chart/markers` route stays unmodified.

---

## Architecture

```mermaid
flowchart LR
    subgraph WriteSide["Phase A — write side (NEW)"]
        BE[Backtest engine] -->|bulk_emit_markers| EM[marker_emitter]
        PE[Paper engine]     -->|emit_*_marker|     EM
        LE[Live order_router]-->|emit_*_marker|     EM
        EM -->|INSERT| TM[(trade_markers)]
    end

    subgraph ReadSide["Phase A — read side (NEW)"]
        UI1[Chart UI / Strategy Tester] -->|GET /api/markers| API[trade_markers router]
        API --> EM
        EM -->|SELECT| TM
    end

    subgraph Legacy["Existing — paper-only read derivation (UNCHANGED)"]
        UI2[Chart UI Day-3 path] -->|GET /api/chart/markers| LR[chart_markers router]
        LR --> CMS[chart_marker_service]
        CMS -->|SELECT| PT[(paper_trades)]
    end

    style WriteSide fill:#e7f3ff,stroke:#1f77b4
    style ReadSide  fill:#e7f3ff,stroke:#1f77b4
    style Legacy    fill:#fff3e0,stroke:#ff9800
```

The dotted boundary is the Phase B/C migration cut-line: once
`trade_markers` is the source of truth, the Legacy box is retired and
`paper_trade.exit_reason` derivation is removed.

---

## Schema

| Column            | Type             | Notes                                                                |
| ----------------- | ---------------- | -------------------------------------------------------------------- |
| `id`              | UUID PK          | uuid4                                                                |
| `strategy_id`     | UUID FK CASCADE  | → `strategies.id`. Indexed.                                          |
| `user_id`         | UUID FK CASCADE  | → `users.id`. Indexed.                                               |
| `symbol`          | String(64)       | Uppercased on emit. Indexed.                                         |
| `exchange`        | String(16)       | Uppercased on emit (NSE / BSE / NFO / IDX).                          |
| `side`            | String(16)       | CHECK ∈ {LONG_ENTRY, LONG_EXIT, SHORT_ENTRY, SHORT_EXIT}.            |
| `price`           | Numeric(20,8)    | NEVER Float. Wire-emitted as JSON string.                            |
| `quantity`        | Integer > 0      |                                                                      |
| `timestamp_utc`   | DateTime tz-aware| Indexed.                                                             |
| `mode`            | String(16)       | CHECK ∈ {BACKTEST, PAPER, LIVE}.                                     |
| `linked_marker_id`| UUID self-FK     | `ON DELETE SET NULL`. Exit points to its entry; nullable.            |
| `pnl`             | Numeric(20,8)    | NULL on entries. CHECK: only on `*_EXIT` rows.                       |
| `exit_reason`     | String(16)       | NULL on entries. CHECK ∈ {SIGNAL, STOP_LOSS, TAKE_PROFIT, MANUAL, SQUARE_OFF, EXPIRY}. |
| `signal_metadata` | JSONB / JSON     | `{}` default. Pydantic `SignalMetadata` validates known keys, allows extras. |
| `created_at`      | DateTime tz-aware| `func.now()`.                                                        |
| `updated_at`      | DateTime tz-aware| `func.now()` + `onupdate`.                                           |

### Indexes

- `ix_trade_markers_strategy_id` (single column)
- `ix_trade_markers_user_id`
- `ix_trade_markers_symbol`
- `ix_trade_markers_timestamp_utc`
- `ix_trade_markers_strategy_id_timestamp_utc` (composite — primary read path)
- `ix_trade_markers_user_id_symbol_mode` (composite — strategy-list-by-user path)
- `uq_trade_markers_idempotent_second` UNIQUE on
  `(strategy_id, side, price, date_trunc('second', timestamp_utc))` — **Postgres only**, dialect-gated in the migration.

### Idempotency

A retry of the same emit within 1 wall-clock second returns the
already-persisted row instead of inserting a duplicate:

1. **DB-level:** the Postgres partial unique index over
   `date_trunc('second', timestamp_utc)` rejects the duplicate INSERT
   with `IntegrityError`.
2. **Service-level:** `_find_dedup_row()` runs a `[ts_floor, ts_floor +
   1s)` SELECT before insert (so SQLite tests get the same dedup
   semantics) and after any IntegrityError.

The service catches the error, rolls back, and returns the existing
row. Callers never see a duplicate; retries are safe.

---

## API reference

All endpoints require JWT auth (`get_current_active_user` dependency)
and gate by strategy ownership. A request for a non-owned or
non-existent strategy returns **403** (not 404) so existence cannot
be probed.

### `GET /api/markers`

Paginated marker list for one strategy + mode.

| Query param   | Type          | Required | Default | Notes                                |
| ------------- | ------------- | -------- | ------- | ------------------------------------ |
| `strategy_id` | UUID          | ✅       | —       |                                      |
| `mode`        | MarkerMode    | ✅       | —       | `BACKTEST` / `PAPER` / `LIVE`        |
| `from`        | ISO 8601 tz   | optional | —       | tz-aware required                    |
| `to`          | ISO 8601 tz   | optional | —       | tz-aware required                    |
| `symbol`      | string        | optional | —       | Filter (case-insensitive)            |
| `side`        | MarkerSide    | optional | —       | Filter to one of the four sides      |
| `limit`       | int 1..500    | optional | 100     |                                      |
| `offset`      | int ≥ 0       | optional | 0       |                                      |

**Response 200:**

```json
{
  "strategy_id": "uuid",
  "mode": "PAPER",
  "limit": 100,
  "offset": 0,
  "total": 2,
  "markers": [
    {
      "id": "uuid",
      "strategy_id": "uuid",
      "user_id": "uuid",
      "symbol": "NIFTY",
      "exchange": "NSE",
      "side": "LONG_ENTRY",
      "price": "22500.00000000",
      "quantity": 50,
      "timestamp_utc": "2026-05-14T09:15:00+00:00",
      "mode": "PAPER",
      "linked_marker_id": null,
      "pnl": null,
      "exit_reason": null,
      "signal_metadata": {"broker_order_id": "ORD-1"},
      "created_at": "2026-05-14T09:15:00.123456+00:00"
    }
  ]
}
```

### `GET /api/markers/strategy/{strategy_id}/summary`

Aggregate stats over EXIT rows only (entries don't contribute to
realised P&L or win-rate).

| Query param | Required | Notes                          |
| ----------- | -------- | ------------------------------ |
| `mode`      | ✅       | `BACKTEST` / `PAPER` / `LIVE`  |

**Response 200:**

```json
{
  "strategy_id": "uuid",
  "mode": "PAPER",
  "trade_count": 4,
  "total_pnl": "650.00000000",
  "win_rate": 0.5,
  "avg_pnl": "162.50000000"
}
```

`win_rate` is `(EXIT rows where pnl > 0) / trade_count` in
`[0.0, 1.0]`. Returns `0.0` for `win_rate` and `Decimal('0')` for
the P&L fields when `trade_count == 0` — frontend never has to
handle NaN.

---

## Integration guide

### Phase B — Strategy Tester (next)

The Strategy Tester UI consumes `GET /api/markers/strategy/{id}/summary`
for the headline stats panel and `GET /api/markers?mode=BACKTEST` for
the trade-by-trade drill-down. Backtest runs call
`bulk_emit_markers()` at the end of the run with the full marker list.

### Phase C — Backtest/Paper/Live mode toggle

The chart UI's mode toggle selects `mode=<...>` on every
`/api/markers` request. The same strategy can have markers in all
three modes; they coexist in the table and are partitioned by `mode`.

### Phase D — Strategy executor integration (RISKY, supervised)

`app.strategy_engine.live_orders.order_router` and
`app.strategy_engine.paper_trading.engine` call `emit_entry_marker()`
on fills and `emit_exit_marker()` on closes. The
`linked_marker_id` ties the exit back to its entry so the trade-pair
view can group them.

**Constraints for the executor integration:**

- Emit AFTER fill confirmation, not before.
- `signal_metadata.broker_order_id` MUST be the real broker id for
  audit traceability.
- Errors from `emit_*_marker` must NOT fail the order placement —
  log the structured warning and continue. The audit log is the
  source of truth for trades; markers are a visualisation
  convenience.

---

## Risk notes for Jayesh's morning review

1. **Coexistence with legacy path.** The existing
   `chart_marker_service` (paper-trade derivation) is **not modified
   and not migrated**. The chart UI's current marker overlay continues
   to read from `/api/chart/markers`. Phase A adds a parallel
   `/api/markers` route. Two routes serve the same conceptual data
   from two different sources until Phase B+ cuts the migration.

2. **Migration not auto-applied.** Migration 025 is committed in the
   branch but `alembic upgrade head` is NOT in any deploy script
   change. Jayesh runs it manually on staging/prod once the merge
   lands.

3. **Router not registered.** `main.py` is unedited. The
   `/api/markers` endpoint returns 404 until Jayesh adds the
   `include_router` line (see `PATCH_INSTRUCTIONS_PHASE_A.md`).

4. **No frontend integration.** The frontend chart module continues to
   call `/api/chart/markers`. A Phase B frontend ticket switches to
   `/api/markers` with mode filtering.

5. **Dedup is best-effort on SQLite.** The Postgres partial unique
   index on `date_trunc('second', timestamp_utc)` is the canonical
   guard. The Python-side `_find_dedup_row` reproduces it on SQLite
   (tests) but only under serialised access — a true concurrent test
   harness would expose this. Not a production risk because Postgres
   enforces.

6. **`exit_reason` taxonomy.** Six values (SIGNAL, STOP_LOSS,
   TAKE_PROFIT, MANUAL, SQUARE_OFF, EXPIRY) cover the current
   strategy-engine vocabulary. The legacy `paper_trades.exit_reason`
   uses lowercase strings (`target`, `stop_loss`, `trailing_stop`,
   `square_off`, `time`, `backtest_end`, `partial`, `indicator`,
   `reverse_signal`). A Phase B mapping layer translates one to the
   other when the read path cuts over.

7. **No back-relationship on Strategy.** `Strategy.trade_markers`
   relationship is intentionally **not** declared (would require
   editing `strategy.py`). Service queries explicitly join via
   `strategy_id`. See PATCH_INSTRUCTIONS section 4 for the future
   tightening.

---

## Test coverage

| Module                                  | Statements | Coverage |
| --------------------------------------- | ---------- | -------- |
| `app/db/models/trade_marker.py`         | 53         | **100%** |
| `app/api/trade_markers.py`              | 42         | **100%** |
| `app/schemas/trade_marker.py`           | 109        | **92%**  |
| `app/services/marker_emitter.py`        | 108        | **88%**  |
| **TOTAL (4 new files)**                 | **312**    | **93%**  |

70 tests, all passing. Uncovered paths are IntegrityError race
fallbacks (hard to exercise without DB-level contention) and a few
Pydantic early-return validator branches.

---

## File map

| File                                                       | LOC | Purpose                                            |
| ---------------------------------------------------------- | --- | -------------------------------------------------- |
| `backend/migrations/versions/025_add_trade_markers.py`     | 199 | Alembic migration (upgrade + downgrade)            |
| `backend/app/db/models/trade_marker.py`                    | 222 | ORM model + three enums                            |
| `backend/app/schemas/trade_marker.py`                      | 226 | Pydantic schemas (Create/Read/Bulk/Filter/Summary) |
| `backend/app/services/marker_emitter.py`                   | 379 | Write + read service layer                         |
| `backend/app/api/trade_markers.py`                         | 162 | FastAPI routes                                     |
| `backend/tests/test_trade_marker_model.py`                 | 230 | Structural + migration tests                       |
| `backend/tests/test_marker_emitter.py`                     | 519 | Service tests over real aiosqlite                  |
| `backend/tests/test_trade_markers_api.py`                  | 296 | API tests over TestClient + dep overrides          |
| `backend/PATCH_INSTRUCTIONS_PHASE_A.md`                    | —   | Manual wire-up steps for Jayesh                    |
| `docs/PHASE_A_MARKERS.md`                                  | —   | This file                                          |

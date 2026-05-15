# Phase B — Strategy Tester Aggregation API

Branch: `feat/phase-b-strategy-tester`
Author: Claude (parallel-CC session) • 2026-05-15

Phase B builds the chart **Strategy Tester** read API on top of the
Phase A `trade_markers` table. It is the TRADETRI equivalent of the
TradingView Strategy Report panel: total P&L, win rate, profit factor,
equity curve, and a trade list.

This document is the morning-review artifact. The code itself is in
seven new files; nothing existing was modified per the new-files-only
parallel-CC branch rule.

---

## Files added (Phase B)

| Path | Purpose |
|---|---|
| `backend/app/schemas/strategy_tester.py` | Response Pydantic models. |
| `backend/app/services/strategy_tester_service.py` | Async aggregators + pure drawdown helper. |
| `backend/app/api/strategy_tester.py` | Three FastAPI routes — auth + ownership-gated. |
| `backend/tests/test_strategy_tester_service.py` | Service unit tests + drawdown helper tests. |
| `backend/tests/test_strategy_tester_api.py` | HTTP route tests over private FastAPI app. |
| `docs/PHASE_B_STRATEGY_TESTER.md` | This document. |
| `backend/PATCH_INSTRUCTIONS_PHASE_B.md` | One-liner Jayesh applies to register the router. |

Zero edits to existing files. No DB migration (reads only, the `trade_markers`
table itself was created in Phase A migration `025_add_trade_markers`).

---

## API endpoint reference

All three endpoints share the auth + ownership shape:

* JWT via `get_current_active_user` (existing dep).
* "Strategy doesn't exist" + "strategy belongs to another user" both
  collapse into **HTTP 403** so existence cannot be probed.
* Naive (tz-unaware) `from`/`to` query params return **400**.
* Inverted window (`from > to`) returns **400**.

### `GET /api/strategy-tester/{strategy_id}/metrics`

Aggregate report-card numbers over CLOSED trades in the window.

**Query params**

| Name | Type | Default | Notes |
|---|---|---|---|
| `mode` | `BACKTEST \| PAPER \| LIVE` | required | Splits the read; same `mode` enum as Phase A markers. |
| `from` | ISO 8601 with offset | none | Window start (`timestamp_utc >= from`). |
| `to` | ISO 8601 with offset | none | Window end (`timestamp_utc <= to`). |
| `starting_equity` | Decimal > 0 | `100000` | Only used by the drawdown walk; does NOT affect P&L counts. |

**Response — `200 StrategyTesterMetrics`**

```json
{
  "total_pnl": "300",
  "win_rate_pct": 50.0,
  "profit_factor": 2.5,
  "total_trades": 2,
  "profitable_trades": 1,
  "max_drawdown_pct": 0.199,
  "sharpe_ratio_proxy": 0.85,
  "avg_win": "500",
  "avg_loss": "-200",
  "largest_win": "500",
  "largest_loss": "-200",
  "expectancy": "150"
}
```

**Field semantics** (all over CLOSED trades in window):

* `total_pnl` — sum of `pnl` across exit rows.
* `win_rate_pct` — `profitable_trades / total_trades * 100`. Returns `0.0` on empty sets.
* `profit_factor` — `gross_profit / |gross_loss|`. **`null`** when there are wins but no losses (mathematically infinite — surface deliberately rather than cap). **`0.0`** when there are losses but no wins. **`null`** on a fully empty set.
* `total_trades` / `profitable_trades` — counts.
* `max_drawdown_pct` — peak-relative drawdown over the equity walk seeded with `starting_equity` (see drawdown algorithm below).
* `sharpe_ratio_proxy` — `mean(pnl) / stdev(pnl)` (population stdev, NOT annualised). **`null`** for fewer than 2 trades or zero variance. The chart UI labels it explicitly as a proxy.
* `avg_win` / `avg_loss` — means within the win and loss subsets. `Decimal('0')` on empty subsets.
* `largest_win` / `largest_loss` — max/min within their subsets. `Decimal('0')` on empty subsets.
* `expectancy` — `(p × avg_win) + (q × avg_loss)` where `p = win_rate`, `q = 1−p`. (avg_loss is already negative, so the formula is mathematically equivalent to the textbook `(p × W) − (q × |L|)`.)

### `GET /api/strategy-tester/{strategy_id}/equity`

Equity-vs-time curve, anchored on `starting_equity`, stepping by exit P&L.

**Query params**

| Name | Type | Default | Notes |
|---|---|---|---|
| `mode` | `BACKTEST \| PAPER \| LIVE` | required | |
| `starting_equity` | Decimal > 0 | `100000` | Anchor and the peak baseline for drawdown%. |
| `from` / `to` | ISO 8601 with offset | none | Window. |

**Response — `200 EquityCurveResponse`**

```json
{
  "starting_equity": "100000",
  "ending_equity": "100300",
  "max_equity": "100500",
  "min_equity": "100000",
  "points": [
    { "timestamp": "2026-05-14T09:15:00+00:00", "equity": "100000", "drawdown_pct": 0.0,   "trade_id_or_none": null },
    { "timestamp": "2026-05-14T09:16:00+00:00", "equity": "100500", "drawdown_pct": 0.0,   "trade_id_or_none": "8b…" },
    { "timestamp": "2026-05-14T09:18:00+00:00", "equity": "100300", "drawdown_pct": 0.199, "trade_id_or_none": "9c…" }
  ]
}
```

* The first point is the anchor — `equity = starting_equity`, `drawdown_pct = 0`, `trade_id_or_none = null`.
* The anchor's `timestamp` is `from` if supplied; else the first exit's timestamp; else `now()` UTC if there are no exits AND no `from` (degenerate but render-safe).
* Each subsequent point sits at an exit marker's `timestamp_utc` with `equity = previous + pnl`. `trade_id_or_none` is the exit marker's UUID (drill-in handle for the frontend).

### `GET /api/strategy-tester/{strategy_id}/trades`

Paginated trade list anchored on entry markers.

**Query params**

| Name | Type | Default | Notes |
|---|---|---|---|
| `mode` | `BACKTEST \| PAPER \| LIVE` | required | |
| `from` / `to` | ISO 8601 with offset | none | Filters on entry timestamp. |
| `symbol` | `str` (1..64 chars) | none | Case-insensitive (uppercased before query). |
| `limit` | `int` (1..500) | `100` | |
| `offset` | `int` (≥ 0) | `0` | |

**Response — `200 TradeListResponse`**

```json
{
  "mode": "PAPER",
  "pagination": { "limit": 100, "offset": 0, "total": 2 },
  "trades": [
    {
      "entry_marker_id": "…",
      "exit_marker_id":  "…",
      "symbol": "NIFTY",
      "side": "LONG",
      "entry_time": "2026-05-14T09:15:00+00:00",
      "exit_time":  "2026-05-14T09:16:00+00:00",
      "entry_price": "22500",
      "exit_price":  "22510",
      "qty": 50,
      "pnl": "500",
      "pnl_pct": 0.0444,
      "duration_minutes": 1.0,
      "exit_reason": "TAKE_PROFIT"
    },
    {
      "entry_marker_id": "…",
      "exit_marker_id":  null,
      "symbol": "BANKNIFTY",
      "side": "SHORT",
      "entry_time": "2026-05-14T09:19:00+00:00",
      "exit_time":  null,
      "entry_price": "48000",
      "exit_price":  null,
      "qty": 15,
      "pnl": null,
      "pnl_pct": null,
      "duration_minutes": null,
      "exit_reason": null
    }
  ]
}
```

* Trades are anchored on entries. **Open trades** (entries with no linked exit yet) appear with all `exit_*` and `pnl*` fields `null`.
* `side` is the **position** side (`LONG`/`SHORT`), derived from the entry marker's `LONG_ENTRY`/`SHORT_ENTRY`.
* `pnl_pct = pnl / (entry_price × qty) × 100`. Sign is preserved (negative for losses).
* `duration_minutes` = `(exit_time − entry_time).total_seconds() / 60`.
* **Orphan exits** (`linked_marker_id IS NULL` — rare; e.g. manual broker-side close that emitted an exit without a linked entry) do NOT appear in this list. They DO contribute to `/metrics` and `/equity` because they carry realised P&L.

---

## Service method reference

`backend/app/services/strategy_tester_service.py` — four public symbols:

* `aggregate_metrics(*, strategy_id, mode, from_ts, to_ts, db, starting_equity=Decimal("100000")) -> StrategyTesterMetrics`
* `build_equity_curve(*, strategy_id, mode, starting_equity, from_ts, to_ts, db) -> EquityCurveResponse`
* `get_trades(*, strategy_id, mode, from_ts, to_ts, limit, offset, db, symbol_filter=None) -> TradeListResponse`
* `compute_drawdown_series(equity_points: Sequence[float]) -> list[float]` — **pure, sync**.

Service-layer signatures are kw-only on purpose so callers can't accidentally swap `from_ts` and `to_ts`.

---

## Drawdown algorithm

```python
peak = equity[0]
out = []
for v in equity:
    if v > peak: peak = v
    out.append(max(0.0, (peak - v) / peak * 100) if peak > 0 else 0.0)
```

* O(n) single pass.
* Drawdown is **percent**, in `[0, 100]`. Clamped to `0.0` on a non-positive peak (degenerate case — e.g. caller passed all-zeros).
* Pure helper exposed publicly so future client-side recompute paths can reuse the exact same formula.

---

## Frontend integration guide (next phase — not yet implemented)

1. Pull metrics on Strategy Tester panel mount: `GET /metrics?mode=<active>`.
2. Pull equity curve for the chart strip: `GET /equity?mode=<active>&starting_equity=<user setting>`.
3. Lazy-load trades list on tab activation: `GET /trades?mode=<active>&limit=50`. Paginate with `offset += 50` on scroll.
4. Drill-in: each `EquityPoint.trade_id_or_none` is the EXIT marker UUID. The trade-list response carries the same UUID as `exit_marker_id`. Use it for click-through to the trade-detail panel.
5. Decimal fields arrive as **JSON strings** to preserve precision. Parse with `Number(x)` at render time (or `parseFloat(x)` if you want NaN-safety).
6. The new endpoints coexist with the existing Phase A `GET /api/markers/...` routes — Strategy Tester uses the new ones; the on-chart marker overlay continues to use Phase A.

---

## Risk notes for morning review

* **No existing files modified.** The router is **not** registered in `main.py` — Jayesh applies the one-liner from `backend/PATCH_INSTRUCTIONS_PHASE_B.md` during morning review.
* **Read-only paths.** Service writes nothing. No new DB table. No new env var. No new background worker.
* **Reads from the same `trade_markers` table that's actively being written by the Phase A emitters.** Concurrent reads against the index `ix_trade_markers_strategy_id_timestamp_utc` are cheap.
* **Pagination on `/trades`** loads all entries in window first, then slices in Python (and only the slice's exits hit a second query). For typical strategy volumes (sub-1k trades), this is fine. If a single strategy ever exceeds ~10k entries in a window, push the slice to SQL with `OFFSET/LIMIT` on the entry query and add a `COUNT(*)` round-trip — same shape as `marker_emitter.get_markers_by_strategy`.
* **Sharpe-ratio "proxy"** is per-trade (not annualised). Frontend label MUST read "Sharpe (proxy, per-trade)" so users don't compare to industry-standard annualised Sharpe.
* **Profit factor `null` semantics**: the API distinguishes "all wins, no losses" (`null`, undefined) from "no wins, no losses" (`null`, empty) from "no wins, has losses" (`0.0`). Frontend must handle the null case explicitly — render `∞` or `—`, NOT `0`.
* **Open trades in the trade list** intentionally have all exit fields `null`. The frontend should style these visibly differently (e.g. greyed-out P&L cell, "Open" badge) to avoid confusion.
* **Pre-existing test failures** on `main` (Phase A surfaced 11: HMAC ×3, CORS ×1, Celery ×3, users-Depends ×3, Telegram ×1) are unrelated to Phase B and were NOT touched in this branch.

---

## Test summary

* `backend/tests/test_strategy_tester_service.py` — 7 drawdown helper cases + 11 service async cases covering all metric branches (empty, all wins, all losses, mixed, mode isolation, pagination, window filter, short-position pnl%, Sharpe edge cases).
* `backend/tests/test_strategy_tester_api.py` — 14 HTTP cases covering owned/foreign/nonexistent strategies, missing `mode`, naive timestamps, inverted window, pagination, default + custom `starting_equity`, symbol filter, 401 on missing auth.

Targeted ≥ 90% coverage on the two new production files; actual coverage reported in commit message body.

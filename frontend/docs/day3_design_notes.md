# Day 3 — chart-markers design notes

Snapshot of the markers-overlay design as it stands AFTER the
Phase-6 (backend scaffold) + Phase-7 (frontend scaffold) office-day
work. The wire contract + read path are locked; what remains for
Day-3 dispatch is wiring + UI polish (strategy picker, marker
shapes/colours on the canvas, optional toggle).

---

## Wire contract (locked)

### Endpoint

```
GET /api/chart/markers
    ?strategy_id=<uuid>
    &symbol=<str>          (1..64 chars; uppercased server-side)
    &timeframe=<str>       (1..8 chars; passes through)
    &from=<iso8601 with tz>
    &to=<iso8601 with tz>
```

### Response (`ChartMarkersResponse`)

```json
{
  "strategy_id": "11111111-1111-1111-1111-111111111111",
  "symbol": "NIFTY",
  "timeframe": "5m",
  "from_ts": "2026-05-12T03:45:00+00:00",
  "to_ts": "2026-05-12T10:00:00+00:00",
  "cached": false,
  "markers": [
    { "kind": "ENTRY",  "timestamp": "...", "price": "22500.00",
      "quantity": 50, "side": "BUY", "pnl": null,      "exit_reason": null     },
    { "kind": "TP_HIT", "timestamp": "...", "price": "22580.00",
      "quantity": 50, "side": "BUY", "pnl": "4000.00", "exit_reason": "target" }
  ]
}
```

### Error envelope

- `400` — naive datetime, inverted window.
- `403` — strategy missing OR owned by another user (collapsed —
  no existence leak).
- The route wraps everything else through FastAPI's default
  500 path; the service layer is exception-free.

### Cached / not-cached

Same 5-minute Redis TTL as `GET /api/chart/history`. Cache key
uses epoch-second buckets so two callers querying the same window
with different timezone formatting still hit the same entry.

---

## Exit-reason vocabulary discovery

Source-of-truth is `app.strategy_engine.engines.exit.ExitType`
(StrEnum). Backtest also writes the literal `"backtest_end"`. Full
mapping:

| `paper_trades.exit_reason`      | `ChartMarkerKind` | Notes                              |
| ------------------------------- | ----------------- | ---------------------------------- |
| `"target"`                      | `TP_HIT`          | `_TP_REASONS = {"target"}`         |
| `"stop_loss"` / `"trailing_stop"` | `SL_HIT`        | `_SL_REASONS = {…}`                |
| anything else                   | `EXIT`            | catch-all (PARTIAL, INDICATOR,     |
|                                 |                   | REVERSE_SIGNAL, TIME, SQUARE_OFF,  |
|                                 |                   | `"backtest_end"`, future additions)|

The catch-all is deliberate. A future `ExitType` addition (Day-N
new exit kind) shouldn't break the route — it just renders as a
neutral EXIT marker until the operator decides whether it warrants
its own kind.

The mapping lives in `chart_marker_service.classify_exit` so a
future change is a one-line edit.

---

## Read path

```
GET /api/chart/markers
    ↓
1. Validate query (tz-aware, from < to)
    ↓
2. Cache lookup (markers:{strategy}:{symbol}:{tf}:{from_epoch}:{to_epoch})
    ↓ (miss)
3. _resolve_strategy_owned_by_user — Strategy.user_id == user.id (403 otherwise)
    ↓
4. build_markers_for_strategy
   ├── list_sessions(user_id, strategy_id) — store function
   ├── asyncio.gather(list_trades(s.id) for s in sessions)
   ├── per trade: _markers_for_trade
   │   ├── filter: trade.symbol == requested symbol
   │   ├── filter: trade.entry_at within [from, to]
   │   ├── ENTRY marker (always — entry_price, side, quantity)
   │   ├── if open trade (exit_at IS NULL): stop here
   │   ├── if exit_at > to_ts: stop here (entry-only)
   │   └── else: <classify_exit(exit_reason)> marker
   │       (price=exit_price, pnl=pnl, exit_reason=exit_reason)
   └── sort by timestamp ASC
    ↓
5. Wrap in ChartMarkersResponse, cache for 5min, return
```

Memory footprint at the live-orders 7-session minimum: ~70 markers
per strategy (7 × 5 trades × 2 markers). Trivial for a JSON
response — no streaming or cursoring needed.

---

## Frontend hook contract (Phase-7 scaffold)

```ts
const { markers, isLoading, hasLoaded, error, refetch } = useChartMarkers({
  strategyId: "uuid"  | null,   // null → disabled
  symbol: "NIFTY",
  timeframe: "5m",
  fromIso: "2026-05-12T03:45:00.000Z" | null,  // null → disabled
  toIso:   "2026-05-12T10:00:00.000Z" | null,  // null → disabled
  enabled?: boolean,                            // override
  forceMock?: boolean,                          // test seam
});
```

- Fetches on mount + on every dep change (strategyId, symbol,
  timeframe, fromIso, toIso, enabled, forceMock).
- `hasLoaded` distinguishes "loading initial response" from
  "loaded, found zero markers". Set in the `finally` block —
  flips on success AND failure.
- `markers` is in render-ready numeric form: `time` is epoch
  SECONDS (matches `Candle.time`), `price` and `pnl` are
  `number`. Wire shape (`WireChartMarker`) keeps Decimal-as-
  string for precision; `parseChartMarker` does the conversion.
- `refetch()` is exposed for manual retry / strategy-picker
  cancellation flows. Stale-response gate via `versionRef` so
  late-resolving fetches drop silently when the user has
  changed strategies mid-flight.

---

## Day-3 dispatch tasks (NOT in office-day scope)

### Backend

1. Add the include_router line in `backend/app/main.py`:
   ```python
   from app.api.chart_markers import router as chart_markers_router
   app.include_router(chart_markers_router)
   ```
2. Run `pytest tests/api/test_chart_markers.py` — verify the
   suite the office-day push wrote actually passes in the live
   venv (the office-day env had no Python venv, so end-to-end
   wasn't run; AST syntax was verified).

### Frontend

1. Decide where the strategy_id comes from:
   - Option A: URL param (`/chart?strategy_id=<uuid>`) read via
     Next.js 16 async `searchParams`. Most operator-friendly for
     "share this view" links.
   - Option B: dedicated strategy picker in the top bar.
   - Option C: pre-existing strategy detail page (already at
     `/strategies/[id]`) hosts an embedded chart with the
     strategy_id pre-bound.
2. Wire `useChartMarkers` into `ChartContainer`. Pass
   `markers` down to `CandlestickChart` as a NEW prop.
3. Inside CandlestickChart, after the price-series setData,
   call `series.setMarkers(markers.map(toLwcMarker))` where
   `toLwcMarker` translates ChartMarker → Lightweight Charts'
   `SeriesMarker` shape:
   ```ts
   function toLwcMarker(m: ChartMarker): SeriesMarker<UTCTimestamp> {
     return {
       time: m.time as UTCTimestamp,
       position: m.kind === "ENTRY" ? "belowBar" : "aboveBar",
       shape:    m.kind === "ENTRY" ? "arrowUp"
              : m.kind === "TP_HIT" ? "circle"
              : m.kind === "SL_HIT" ? "arrowDown"
              :                       "square",
       color:    m.kind === "ENTRY" ? "#22c55e"
              : m.kind === "TP_HIT" ? "#3b82f6"
              : m.kind === "SL_HIT" ? "#ef4444"
              :                       "#737373",
       text:     m.exit_reason ?? undefined,
     };
   }
   ```
4. Optional: a "Show markers" toggle in the top bar. Local state
   guarded by a Tailwind `hidden` swap (no animation needed).

---

## Hinglish copy palette (operator-facing strings)

For consistency with the rest of the dashboard:

- 403 "you can't see this":
  > Is strategy ke markers dekhne ka access nahi hai. Strategy ID
  > confirm karo aur apni login session check karo.
- 400 timezone:
  > from + to dono ISO 8601 timezone-aware hone chahiye
  > (e.g. 2026-01-01T09:15:00+05:30).
- 400 inverted:
  > from is greater than to — invalid window.

These are already in `app/api/chart_markers.py`; the frontend
should surface them verbatim (no translation layer).

---

## Open questions for Day-3 review

1. Do markers persist across symbol/timeframe changes the same
   way candles do? (Probably no — markers are strategy-scoped, so
   `useChartMarkers` keying on (symbol, timeframe) makes sense.)
2. Should the marker fetch include OPEN trades? Phase-6 service
   does (entry-only marker, no exit). Operator may want to filter
   open trades out for cleaner backtest-style replay.
3. Should there be a position-line overlay (a horizontal line
   from entry timestamp to exit timestamp at the entry price) in
   addition to the markers? Day-3 nice-to-have, not in scope.

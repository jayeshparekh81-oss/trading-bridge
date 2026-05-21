# Milestone 3 — Next Steps After Queue CC+DD Push

**Status after Queue CC+DD:** backend write-path + read-API for backtest
trade markers is shipped. Frontend wiring is the remaining ~1–2 hr of
work to complete Milestone 3 ("chart with trade markers").

---

## What ships in this branch (already done)

### Backend
- `app/backtest_extension/trade_markers.py` — `persist_backtest_trade_markers()` +
  `fetch_markers_for_run()`.
- `app/backtest_extension/celery_tasks.py` — post-SUCCEEDED hook that
  writes markers, wrapped in try/except so marker failure can't fail
  the backtest task.
- `app/backtest_extension/api.py` — new `GET /api/backtest/{run_id}/markers`
  endpoint returning Lightweight Charts `SeriesMarker` shape directly:
  `{time, position, color, shape, text}`.

### Side-mapping (consistent with frontend's existing `adaptMarkerToChartMarker`)

| MarkerSide | position | color | shape | text |
|------------|----------|-------|-------|------|
| LONG_ENTRY | belowBar | `#22c55e` | arrowUp | BUY |
| LONG_EXIT | aboveBar | `#ef4444` | arrowDown | SELL |
| SHORT_ENTRY | aboveBar | `#ef4444` | arrowDown | SHORT |
| SHORT_EXIT | belowBar | `#22c55e` | arrowUp | COVER |

### Tests
- 15 tests in `backend/tests/backtest_extension/test_trade_markers.py`:
  persist behaviour, idempotency, exit-reason mapping, chart projection
  table coverage.

---

## What's left for the frontend (~1–2 hours)

### Recommended approach (lowest delta)

The existing backtest results page at
`frontend/src/app/(dashboard)/strategies/[id]/backtest/page.tsx` already
renders the equity curve + trades table. Add a candlestick chart panel
above the existing `BacktestResultPanel` that consumes the new endpoint.

```tsx
// 1. After the runBacktest setData() call, fire a second fetch:
const markersResp = await api.get<{run_id: string; markers: ChartMarker[]}>(
  `/api/backtest/${data.run_id}/markers`,
);

// 2. Pass markers to an inline CandlestickChart component:
import { CandlestickChart } from "@/components/chart/CandlestickChart";

<CandlestickChart
  candles={candlesFromBacktestWindow}  // derive from data.backtest equity timestamps
  markers={markersResp.markers}
  height={420}
/>
```

The `CandlestickChart` component already accepts a `markers` prop and
calls `series.setMarkers([...])` directly — per Queue AA audit
(`docs/FRONTEND_GAP_AUDIT.md` Section A). The wire shape from
`GET /api/backtest/{run_id}/markers` is already exactly what
Lightweight Charts wants, so NO client-side mapping is needed.

### Candles source for the chart panel

Two options:

1. **Re-fetch via the existing `/api/chart/history` endpoint** using the
   backtest's symbol + window. Adds one HTTP round trip per results-page
   render. Reuses existing rate-limited chart-history backend.
2. **Embed candles in the backtest response** (modify
   `/api/strategies/{id}/backtest` to include `candles` alongside
   `backtest`/`reliability`/etc.). Heavier change; touches the response
   schema. NOT recommended for a 1-day task.

Recommend **option 1** — fits the existing data-fetch pattern and keeps
the backtest response unchanged.

### Existing alternative: the `useTradeMarkers` hook

The frontend already has `useTradeMarkers` hook (Queue AA audit) that
calls `GET /api/markers?strategy_id=X&mode=BACKTEST`. This would ALSO
work — returns the same trade_markers rows, just via the strategy-id
+ mode filter instead of the backtest_run_id filter. The new
`/api/backtest/{run_id}/markers` endpoint is preferred for backtest
results because:

- Cleaner run-scoped semantics (returns only THIS run's markers, not
  prior runs on the same strategy).
- Already projects to Lightweight Charts shape (no client mapping).
- Owner-scoped 404 collapses unknown-id + cross-user to one response.

If the frontend team prefers reusing `useTradeMarkers`, both endpoints
work; the run-scoped endpoint is just a cleaner fit for backtests.

---

## Estimated effort

| Task | Effort |
|------|--------|
| Add `<CandlestickChart>` panel to backtest results page | ~1 hour |
| Hook to fetch candles for the backtest window | ~30 min |
| Hook to fetch markers via new endpoint | ~15 min |
| Visual polish (panel height, loading state) | ~15 min |
| **Total** | **~2 hours** |

---

## Design notes (for follow-up sprints)

See `docs/MILESTONE_3_DESIGN_NOTES.md` for the schema decisions made in
this prototype (cross-run idempotency via `signal_metadata.backtest_run_id`
instead of a dedicated indexed column). A future iteration that adds
`backtest_run_id` as a real column would simplify queries and improve
performance — flagged but out of scope for tonight.

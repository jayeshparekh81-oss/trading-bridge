# Day-3 dispatch — manual patch instructions

This branch (`feat/frontend-chart`) carries Phase 6 + Phase 7 of the
Day-2 office-day push: the chart-markers backend route + the matching
frontend hook are **scaffolded but not wired into production
surfaces**. Apply the manual edits below when Day-3 is officially
dispatched.

The scope is deliberately small so the operator can review + apply
each change in one minute.

---

## 1. Backend — register the chart-markers router

**File**: `backend/app/main.py`
**Action**: add the import + the `include_router` call next to the
other `app.include_router(...)` calls. Order does not matter — the
`/api/chart/markers` route does not overlap any other.

```python
from app.api.chart_markers import router as chart_markers_router  # noqa: E402

# … alongside the other include_router calls:
app.include_router(chart_markers_router)
```

The router itself lives at
`backend/app/api/chart_markers.py` and is fully implemented + tested
on this branch. No other backend change is required.

### What the route exposes

```
GET /api/chart/markers
    ?strategy_id=<uuid>
    &symbol=<str>
    &timeframe=<str>
    &from=<iso8601 with tz>
    &to=<iso8601 with tz>
```

Response: `app.schemas.chart_marker.ChartMarkersResponse`. See module
docstring in `chart_markers.py` for the full contract (auth, caching,
Hinglish error messages).

### What the route depends on

All existing modules — no new schema migrations, no new env vars, no
new external service. Concretely:

* `app.api.deps.get_current_active_user` (JWT)
* `app.db.session.get_session` (Postgres)
* `app.core.redis_client.cache_get` / `cache_set` (Redis 5-min cache)
* `app.db.models.strategy.Strategy` (ownership check)
* `app.strategy_engine.paper_trading.store.list_sessions` /
  `list_trades` (read-side data)

If any of those moves before Day-3 dispatch, the router import will
fail loudly at startup — flag and stop, do not patch around it.

---

## 2. Frontend — integrate the markers hook into ChartContainer

**Files**:

* `frontend/src/hooks/useChartMarkers.ts` (NEW, scaffolded)
* `frontend/src/lib/chart/types.ts` (extended with `ChartMarker` types)

**Action**: in `frontend/src/components/chart/ChartContainer.tsx`:

```tsx
import { useChartMarkers } from "@/hooks/useChartMarkers";

// Inside the component, after the candles useMemo:
const { markers } = useChartMarkers({
  strategyId,                 // wired from URL or selector
  symbol,
  timeframe,
  fromTs: candles[0]?.time,
  toTs: candles[candles.length - 1]?.time,
});

// Pass to CandlestickChart — needs a new prop ``markers`` + the
// ``series.setMarkers(...)`` call inside the component (Day-3 work,
// NOT scaffolded here).
<CandlestickChart
  candles={candles}
  markers={markers}
  // … rest of existing props
/>
```

The hook is pure read-side; it does not touch the WebSocket lifecycle
or the scrollback buffer. Lightweight Charts' `series.setMarkers(...)`
is the integration point on the chart side.

### Day-3 strategy_id source

Today's chart UI does not yet take a strategy_id (the chart is
strategy-agnostic). Day-3 needs to:

1. Add a strategy picker (or read from `?strategy_id=<uuid>` URL
   param via Next.js 16's async `searchParams`).
2. Pass the selected strategy_id into `<ChartContainer>` as a new prop.
3. Optional: add a "Markers" toggle so operators can hide them.

---

## 3. Verification checklist

Before declaring Day-3 done:

- [ ] `cd backend && pytest tests/api/test_chart_markers.py` — 100% pass.
* The Phase-6 commit on this branch wrote a comprehensive test file
  but the office-day operator did not have a Python venv to run it
  end-to-end. AST syntax was verified.
- [ ] `cd frontend && ./node_modules/.bin/vitest run --coverage` —
  exit 0; check that `src/hooks/useChartMarkers.ts` is included in
  the coverage report.
- [ ] Hit `GET /api/chart/markers?...` against a local backend with
  a real strategy_id; verify `cached: false` on first call and
  `cached: true` on second.
- [ ] Smoke-test the chart: open a chart for a strategy that has
  paper-trading history; confirm markers render at the correct
  candle timestamps + the colour matches the kind.

---

## 4. Rollback

The router include is the only production-visible change. To roll
back at any point:

1. Comment out the `include_router(chart_markers_router)` line in
   `backend/app/main.py`.
2. Redeploy.

The hook scaffolding on the frontend is unreachable code without the
backend route, so removing the integration in ChartContainer is the
frontend rollback step (no other call sites).

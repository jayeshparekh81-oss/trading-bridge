# Milestone 3 — Frontend Chart Audit (Queue EE, Phase 1)

**Branch:** `feat/milestone-3-frontend-chart` (base: `feat/milestone-1-ship`)
**Date:** 2026-05-21
**Author:** Queue EE (AI-first)

---

## 1. Lightweight Charts installation

| Field | Value |
|---|---|
| Package | `lightweight-charts` |
| Version | `^4.2.3` (from `frontend/package.json`) |
| Next.js | `16.2.4` (App Router, breaking-changes flagged in `frontend/AGENTS.md`) |
| React | `19.2.4` |

No version mismatch — Queue EE's new component uses the same `lightweight-charts@^4.2.3` already
shipped on the `(dashboard)/chart` route.

## 2. Where the existing chart lives

```
frontend/src/app/(dashboard)/chart/page.tsx        ← route
frontend/src/components/chart/ChartContainer.tsx   ← orchestrator (top-level)
frontend/src/components/chart/CandlestickChart.tsx ← LWC wrapper
frontend/src/lib/chart/types.ts                    ← wire shapes (Candle, ChartMarker, …)
frontend/src/lib/chart/api.ts                      ← fetchChartHistory(), fetchChartMarkers(), …
frontend/src/hooks/useChartHistory.ts              ← initial-window candles fetcher
frontend/src/hooks/useTradeMarkers.ts              ← live paper-trading markers
frontend/src/hooks/useChartWebSocket.ts            ← live tick / candle stream
```

## 3. Existing `<CandlestickChart>` contract — can we reuse?

```ts
interface CandlestickChartProps {
  candles: Candle[];
  markers?: ChartMarker[];           // ← four-way taxonomy (ENTRY | EXIT | SL_HIT | TP_HIT)
  highlightedMarkerId?: string | null;
  onMarkerClick?: (id: string) => void;
  showSMA20 / showEMA50 / showRSI / showMACD / showVolume?: boolean;
  onRequestOlderHistory?: ...;       // scroll-back lazy load
  isLoadingOlder?: boolean;
  createChartFn?: typeof createChart; // test seam
}
```

**Verdict: partially reusable, but NOT a clean fit for backtest results.**

Reasons to not delegate to it:

1. **Marker-shape mismatch.** Backend's `GET /api/backtest/{run_id}/markers`
   (Queue CC+DD) returns the **Lightweight Charts `SeriesMarker` shape directly**:
   `{ time, position, color, shape, text }`. `<CandlestickChart>` accepts the
   legacy four-way `ChartMarker` (`kind: ENTRY | EXIT | SL_HIT | TP_HIT`). An
   adapter would lose information (the backend's per-side colour/text projection
   is richer than the four-way bucket).
2. **WS / scroll-back / indicator baggage.** `<CandlestickChart>` is designed
   for the live chart route — it owns ResizeObserver + touch gestures +
   keyboard shortcuts + lazy indicator series + scroll-back triggers. Backtest
   results are a **static snapshot**; pulling in all that machinery is dead
   code on this surface.
3. **Single-use rendering.** A standalone thin wrapper using `createChart`
   directly (mirroring CandlestickChart's dark theme constants + candle colours)
   keeps the backtest panel ~150 LoC vs. delegating + adapting.

→ Queue EE ships **`BacktestChartPanel`** as a new component using
`createChart` directly, consuming the backend's LWC shape with **zero
adaptation**.

## 4. Backtest-results page structure

**File:** `frontend/src/app/(dashboard)/strategies/[id]/backtest/page.tsx` (562 lines)

**Critical architectural finding:** this page does **NOT** use the async
`/api/backtest` extension (the one Queue CC+DD shipped on this branch). It
uses the **synchronous** flow:

```ts
const result = await api.post<BacktestResponse>(
  `/strategies/${id}/backtest`,    // ← SYNC engine path, returns full payload inline
  { include_deviation_demo: true, candles_request? }
);
```

The `BacktestResponse` carries `backtest.trades: BacktestTrade[]` inline
(via `BacktestResultPanel`). There is **no `run_id`** in the response and **no
call to the async `/api/backtest/{run_id}/markers` endpoint**.

### Panels currently rendered (8 per Queue AA — verified)

```
BacktestResultPanel      (metrics + equity + trades + warnings)
StrategyCoachCard
TrustPanelPreview        (locally defined, reads BacktestResponse.reliability)
StrategyTruthPanel
MarketRegimePanel
TradeQualityCard
AIDoctorCard
DeviationMonitorPanel
```

Plus chrome: header (`PlayCircle` + back link + re-run buttons + candle-source picker)
and `RerunWithDifferentDataDialog`. All wrapped in a `motion.div` stagger sequence.

### How `run_id` would be obtained (for Phase 3 integration)

Two options:

- **(A) Refactor the page to use the async flow.** Replace
  `POST /strategies/${id}/backtest` with `POST /api/backtest` → poll
  `GET /api/backtest/${runId}` until SUCCEEDED → fetch results. This is a
  **page rewrite** and out of scope for Queue EE.
- **(B) Run async-flow IN PARALLEL.** Keep the sync POST for the existing
  8 panels (no regression risk), additionally enqueue an async backtest with
  the same request payload, surface the new chart panel once the async run
  reaches SUCCEEDED. Costs an extra Celery invocation per page load but is
  zero-risk to the existing surface.

Queue EE chooses **option (B)** for the patch — see `PATCH_INSTRUCTIONS_MILESTONE_3.md`.

## 5. Marker data format — backend vs. component

Backend `ChartMarkerOut` (from `backend/app/backtest_extension/api.py`):

```python
class ChartMarkerOut(BaseModel):
    time: int                                  # UNIX epoch seconds (UTC)
    position: Literal["aboveBar", "belowBar"]
    color: str                                 # CSS, e.g. "#22c55e"
    shape: Literal["arrowUp", "arrowDown", "circle"]
    text: str                                  # short tooltip, e.g. "BUY"
```

This **maps 1:1** onto Lightweight Charts' `SeriesMarker<UTCTimestamp>` —
literally `{ ...m, time: m.time as UTCTimestamp }` is enough.

## 6. Data-fetcher pattern

Existing chart uses `fetchChartHistory({ symbol, exchange, timeframe, from, to })`
from `@/lib/chart/api`. Returns `{ candles: WireCandle[] }`; caller parses each
via `parseCandle()` → numeric `Candle`. Auth + 401 refresh + mock toggle are all
encapsulated.

`BacktestChartPanel` will reuse `fetchChartHistory` so the auth/mock/refresh
behaviour stays consistent with the live chart. Window is derived from the
**markers' min/max time ± one bar** (when markers exist) or skipped (empty
backtest).

## 7. Hard-stop checks (Phase 1)

| Condition | Status |
|---|---|
| Lightweight Charts version mismatch | ✅ pass — same `^4.2.3` |
| Existing chart can't be reused | ⚠️ chose NOT to reuse for design reasons (see §3) — no STOP |
| Backtest page incompatible with new panel | ⚠️ surfaced architectural mismatch (sync vs. async backtest flows); patch via option (B) — no STOP |

→ Phase 1 complete. Proceeding to Phase 2.

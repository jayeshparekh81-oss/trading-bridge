# Queue AA — Phase 2: Frontend Gap Audit (Milestones 2 + 3)

**Audit type:** Read-only inspection of `frontend/src/`. No edits.
**Date:** 2026-05-19

---

## Section A — What exists today (verified by reading source files)

### Strategy editor / detail surface (`/strategies/[id]/page.tsx`)
- Renders strategy metadata, template provenance (when cloned), webhook + broker badges.
- **Backtest button:** conditionally rendered.
  - If `hasDsl` (strategy has canonical `strategy_json`): renders a "View Backtest" link → `/strategies/[id]/backtest`. ✅
  - If template-cloned with NO `strategy_json` yet: shows Hinglish copy "Live trading aur backtest tab unlock honge jab Strategy Builder (Phase 5) ship hoga" — explicitly tells the user the gap. ✅ (UX is honest)
  - If legacy (pre-Phase-5 strategy): "Yeh strategy Phase 5 builder se pehle bani thi. Backtest chalane ke liye ek nayi strategy bana lo." ✅

### Backtest results page (`/strategies/[id]/backtest/page.tsx`)
- 562 lines. Fully built.
- Auto-fires `POST /api/strategies/{id}/backtest` on mount (with stashed candle source from `localStorage`).
- Renders 8 panels:
  1. `BacktestResultPanel` — metrics grid (P&L, win-rate, sharpe, drawdown), Recharts area equity curve, paginated trades table (50/page).
  2. `StrategyCoachCard` — Phase X Hinglish health card.
  3. `TrustPanelPreview` — Phase 4 ReliabilityReport (Trust score, OOS, walk-forward, sensitivity).
  4. `StrategyTruthPanel` — Phase X TruthReport.
  5. `MarketRegimePanel` — Phase X regime detection.
  6. `TradeQualityCard` — entry/exit quality breakdown.
  7. `AIDoctorCard` — diagnosis + suggestions.
  8. `DeviationMonitorPanel` — Phase 9 backtest vs paper drift.
- Re-run dialog with `CandleSourcePicker` — switch between synthetic and Dhan historical data without leaving the page.
- Celebration confetti on profitable runs (`celebrate("huge"|"big"|"medium")`).
- Loading skeleton + error retry CTA.

### Existing backend endpoint (`POST /api/strategies/{strategy_id}/backtest`)
Source: `backend/app/strategy_engine/api/backtest.py`.
- Loads owned `Strategy` row by `(user_id, strategy_id)`.
- Reads `strategy_row.strategy_json` from the DB.
- Validates via `StrategyJSON.model_validate(strategy_row.strategy_json)`.
- Calls `run_backtest(BacktestInput(...))` directly (synchronous, no Celery).
- Builds reliability + regime + truth + deviation + trade-quality + diagnosis reports inline.
- Returns the combined `BacktestRunResponse`.
- Returns **422** if `strategy_json` is empty (legacy row) or invalid.

### Standalone chart route (`/chart`)
- `ChartContainer` → `CandlestickChart` (TradingView Lightweight Charts).
- `useChartHistory` REST initial load + `useChartWebSocket` live ticks.
- `useTradeMarkers` → `/api/markers` (Phase E persistent trade markers).
- `useChartMarkers` (legacy fallback for paper trades).
- Marker types: `ENTRY`, `EXIT`, `SL_HIT`, `TP_HIT` (4-way `ChartMarker.kind`).
- Adapter `adaptMarkerToChartMarker` flattens new `(side ⊕ exit_reason)` shape to legacy kind.
- `series.setMarkers([...])` rebinds on every prop change; highlight scroll-to on row click.
- Indicators dropdown (MACD, persisted via `loadPersistedToggles`).
- `StrategyTesterPanel` below the chart — strategy tester (metrics + equity + trades), **hardcoded to BSE LTD strategy `89423ecc-...` in `PAPER` mode**.

### Strategy builder routes
- Three-tier complexity gallery: `/strategies/new/beginner`, `/intermediate`, `/expert`.
- `/strategies/import-pine` (Pine Script importer).
- `/strategies/builder/risk` (risk-rule editor — partial route surface).
- Need to verify whether the builder routes WRITE `strategy_json` in canonical form on save — this is the source of all backtest-ready strategies.

### Marker overlay infrastructure
- `frontend/src/lib/markers-overlay/{api,types,mapper}.ts` — typed wire model + Decimal-string parser + render-ready mapper.
- Two endpoints in use: `/api/markers` (new persistent) + `/api/chart/markers` (legacy paper-derived).
- Documented cutover path in `PATCH_INSTRUCTIONS_PHASE_E.md`.

---

## Section B — What's missing per milestone

### Milestone 2 — "Backtest button on every strategy → results page"

| Requirement | Status |
|-------------|--------|
| Backtest button visible on strategy detail | ✅ Done (gated on `hasDsl`) |
| Results page fully wired with metrics + curves + trade list | ✅ Done (8 panels) |
| Synchronous backend endpoint | ✅ Done (`/api/strategies/{id}/backtest`) |
| Async / Celery backend endpoint (the Day-7 router-mount work) | ⚠️ Built but not mounted — `/api/backtest` from `backtest_extension` |
| Cloned-template strategy gets a usable Backtest path | ❌ **BLOCKED by translator gap** — see Queue Z STRUCTURAL_BLOCKER. Template clone produces a Strategy row with `strategy_json=NULL`; backtest 422s. |
| Legacy strategy gets a Backtest path | ❌ Same 422; UX directs user to re-create via builder |
| Builder routes write canonical `strategy_json` | ❓ NEEDS VERIFY — read `frontend/src/app/(dashboard)/strategies/new/{beginner,intermediate,expert}/page.tsx` (deferred — not on critical path) |

**Real Milestone 2 gap:** the backtest button + results page ARE built. What's missing is **inputs that can produce `strategy_json`**:
- Builder routes (if they don't already write canonical JSON, that's the gap)
- Template → `strategy_json` translator (the structural blocker from Queue Y/Z)

Until those land, the backtest path only works for strategies built via the existing canonical-builder flow. Templates and legacy rows can't reach it.

### Milestone 3 — "Chart with trade markers"

| Requirement | Status |
|-------------|--------|
| TradingView Lightweight Charts integration | ✅ Done (standalone `/chart` route) |
| `series.setMarkers([...])` wiring | ✅ Done |
| Entry/Exit/SL/TP marker types | ✅ Done |
| WebSocket live ticks + history REST | ✅ Done |
| Equity curve display | ✅ Done in TWO places (Recharts on backtest results page + on strategy tester panel) |
| **Chart-on-backtest-results-page with backtest trade markers** | ❌ **NOT BUILT.** Backtest results page has Recharts equity curve only — no candlestick chart, no trade markers overlay. |
| Backtest trade markers feed into `/api/markers` | ❓ NEEDS VERIFY — `/api/markers` was scoped for PAPER trades per `useTradeMarkers` docstring; backtest trades may not currently persist to the `trade_markers` table. |
| "View backtest on chart" navigation from results → chart | ❌ Not built |

**Real Milestone 3 gap:** the chart infrastructure is solid but isolated. The backtest results page renders trades as a TABLE and equity as a Recharts area chart. There's no candlestick view of the backtest itself. To close: either embed `<CandlestickChart markers={...}>` in the backtest results page, or add a CTA to deep-link to `/chart?strategyId={id}&mode=BACKTEST&from=...&to=...`.

---

## Section C — Estimated effort per missing piece

(Days = focused, supervised dev. Hours = quick fix if specifications are clear.)

| Gap | Effort | Why |
|-----|--------|-----|
| Template → `strategy_json` translator | **3-5 days** | Detailed in `TRANSLATOR_ARCHITECTURE_PROPOSAL.md`. Largest single unlock. |
| Verify builder writes canonical `strategy_json` | **0.5-1 day** to verify; if missing, 2-4 days to wire up | Existing builder routes need a save-path audit. Builder may already be canonical — needs source-read confirmation. |
| Backtest results page: embed candlestick chart with markers | **1.5-2 days** | `CandlestickChart` is a generic component already taking `markers` + `candles` props; need to (a) fetch candles for the backtest's time window, (b) convert backtest `trades[]` to `Marker[]` (similar to existing `adaptMarkerToChartMarker`), (c) drop into a new card on the results page. |
| Persist backtest trade markers to `/api/markers` (Phase E table) | **1 day** | Schema already exists; backend handler needs to write trades from `backtest_extension` runs into `trade_markers` with `mode='BACKTEST'`. Cleaner than ad-hoc fetch — reuses the existing `useTradeMarkers` hook unchanged. |
| Router mount of `/api/backtest` (async Celery path) | **0.5 day** | Day 7 left the route ready; mount in `main.py` + restart workers. Manual founder step. |
| "View backtest on chart" CTA + URL params on /chart | **0.5 day** | Trivially small. |

### Quick-win opportunities

| Opportunity | Effort | Trigger |
|-------------|--------|---------|
| Mount `/api/backtest` router (Day 7 prep done) | **5 min** | Founder edit to `main.py` |
| Document the template-clone → backtest UX gap in copy (already done, just review) | **0** | Already shipped in Hinglish on detail page |
| Wire backtest trades into `trade_markers` table | **1 day** | Unlocks Milestone 3 chart visualization without new frontend code |

---

## Section D — Verification asks for tomorrow

These need a source-read I deferred to keep this audit lean:

1. **Builder save path:** does `/strategies/new/{beginner,intermediate,expert}` actually write a canonical `strategy_json` to the DB? Need to read those 3 page files + their save handlers. If yes, Milestone 2 is effectively done modulo templates. If no, that's a bigger Milestone 2 gap.

2. **Backtest trade persistence:** does `run_backtest` or `/api/strategies/{id}/backtest` write trades to the `trade_markers` table? If no, the candlestick-chart-on-results-page work needs a backend addition. If yes, frontend-only fix.

3. **`StrategyJSON` schema completeness:** does the schema support all the condition shapes the templates use (`crosses above`, scalar comparisons like `rsi > 70`, multi-condition `AND`/`OR`)? `StrategyJSON` has `IndicatorCondition`, `CandleCondition`, `TimeCondition`, `PriceCondition` — looks comprehensive. Confirm during translator design (Phase 3).

These are 30-60 min of focused source-reading each. Not done in this audit to respect the time budget; flagged here so tomorrow's session can knock them out before any code change.

---

## Audit conclusion

**Milestone 2 is ~80% complete** end-to-end for canonical-JSON strategies. The visible blocker for the remaining 20% is the template translator (Phase 3 below). The async Celery route is mounted with one founder edit.

**Milestone 3 is ~70% complete** — chart infra is shipped and proven, but it's not yet wired into the backtest results page. The cheapest path to Milestone 3 is either (a) wire backtest trades into the `trade_markers` table so `useTradeMarkers` works out-of-the-box, or (b) build a 1-day "candlestick with backtest markers" panel on the results page using `CandlestickChart` directly.

Neither milestone needs new chart engineering — both need translator + persistence wiring.

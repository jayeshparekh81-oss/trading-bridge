# PATCH_INSTRUCTIONS_PHASE_E

Manual edits to wire the Phase E `useTradeMarkers` hook (Phase A
`/api/markers` backend, persistent `trade_markers` table) into the
existing chart UI. Files in this list ALREADY EXIST on `main` — the
parallel-CC "new-files-only" rule means Phase E code in this branch
cannot edit them. Apply these patches by hand on a follow-up branch
(or directly on `main` if you're ok with that policy locally).

Branch: `feat/phase-e-markers-overlay-cutover`
Snapshot date: 2026-05-16
Author: Phase E parallel-CC session

---

## Summary

Phase E ships these NEW files (already on this branch):

| Path | Purpose |
|---|---|
| `src/lib/markers-overlay/types.ts` | Wire + render-ready TS types + parsers (Phase A schema mirror) |
| `src/lib/markers-overlay/api.ts` | URL builder + thin fetch wrapper over `@/lib/api` |
| `src/lib/markers-overlay/mapper.ts` | `Marker → SeriesMarker` palette/shape mapper |
| `src/hooks/useTradeMarkers.ts` | Fetch + parse + memoised SeriesMarker[] for `series.setMarkers()` |

Plus 4 test files under `tests/markers-overlay/` (66 tests, all passing).

The new hook is **not yet rendered anywhere** on the chart page — Phase E
deliberately ships behind a manual wire-up step so the chart's existing
marker overlay doesn't change without your review. The legacy hook
(`useChartMarkers` → `/api/chart/markers`, paper-trade-derived) remains
untouched.

---

## Field mapping (legacy → new)

The legacy `ChartMarker` (consumed by `CandlestickChart`) has one axis
(`kind: ENTRY | EXIT | SL_HIT | TP_HIT`). The new `Marker` has two
orthogonal axes (`side: LONG_ENTRY | LONG_EXIT | SHORT_ENTRY | SHORT_EXIT`
plus `exit_reason: SIGNAL | STOP_LOSS | TAKE_PROFIT | MANUAL | SQUARE_OFF | EXPIRY`).

The mapper (`src/lib/markers-overlay/mapper.ts`) collapses the two-axis
shape back into `SeriesMarker` directly — the new hook returns
`SeriesMarker[]` ready for `series.setMarkers()`, no intermediate
`ChartMarker[]` step. **This means the chart's internal `toLwcMarker`
function becomes redundant for markers sourced from this hook**, but
since `CandlestickChart` accepts `markers: ChartMarker[]` today, the
recommended wire-up is to keep the chart's prop signature unchanged
and use a thin adapter (Option A below) OR refactor the chart to
accept `SeriesMarker[]` directly (Option B, larger blast radius).

### Side-by-side comparison

| Concept | Legacy (`/api/chart/markers`) | New (`/api/markers`) |
|---|---|---|
| URL | `/chart/markers?strategy_id=…&symbol=…&timeframe=…&from=…&to=…` | `/markers?strategy_id=…&mode=…&from=…&to=…&symbol=…&side=…&limit=…&offset=…` |
| Mode | implicit (paper-trade-only) | **required** query param (`BACKTEST | PAPER | LIVE`) |
| Side | `string` (e.g. "BUY") | enum (`LONG_ENTRY | …`) |
| Kind | `ENTRY | EXIT | SL_HIT | TP_HIT` | derived from `(side, exit_reason)` |
| Stable id | derived `kind:time` fingerprint | UUID row id from DB |
| Pagination | implicit (uses `from/to`) | explicit `limit` + `offset` + `total` echo |

### Highlight handshake

The legacy chart-↔-list highlight uses `chartMarkerId(m)` =
`"${kind}:${time}"`. The new hook uses the backend UUID directly via
`marker.id`. If you keep both lists alive in parallel (Option A), the
two highlight schemes won't collide — each list uses its own id field.
If you cutover the list to consume the new hook too (recommended for
clean delete-later), update `PaperTradeList.markerId(m)` (currently
exported from `src/components/chart/PaperTradeList.tsx`) to read
`m.id` for new-shape rows.

---

## Step 1 — Pick a wire-up strategy

Three reasonable options.

### Option A (recommended for safe cutover) — Adapter inside `ChartContainer.tsx`

`CandlestickChart` keeps its `markers: ChartMarker[]` prop. We feed it
from the new hook by mapping `Marker[]` back into the legacy
`ChartMarker` shape just for the chart canvas. Smallest blast radius;
fastest rollback (revert one import in `ChartContainer.tsx`).

**Edit: `src/components/chart/ChartContainer.tsx`**

1. Add a `mode` prop with default `"PAPER"`:

```tsx
export interface ChartContainerProps {
  initialSymbol?: string;
  initialTimeframe?: Timeframe;
  exchange?: Exchange;
  /** Phase E — execution mode the markers overlay reads from. */
  mode?: MarkerMode;
}

export function ChartContainer({
  initialSymbol = "NIFTY",
  initialTimeframe = "5m",
  exchange = "NSE",
  mode = "PAPER",
}: ChartContainerProps) {
```

2. Swap the import:

```tsx
// remove:
import { useChartMarkers } from "@/hooks/useChartMarkers";

// add:
import { useTradeMarkers } from "@/hooks/useTradeMarkers";
import type { Marker, MarkerMode } from "@/lib/markers-overlay/types";
```

3. Replace the `useChartMarkers` call with the new hook (still passes
   the candle-derived `fromIso`/`toIso` window):

```tsx
const markersState = useTradeMarkers({
  strategyId,
  mode,
  symbol,
  fromIso,
  toIso,
  highlightedId: highlightedMarkerId,
});
```

4. Add an adapter from `Marker[]` to the legacy `ChartMarker[]` shape
   the canvas + `PaperTradeList` still consume:

```tsx
// Local adapter — keeps CandlestickChart + PaperTradeList unchanged.
// Delete once those components consume the new Marker shape directly.
const chartMarkers: ChartMarker[] = useMemo(
  () => markersState.rawMarkers.map(adaptMarkerToChartMarker),
  [markersState.rawMarkers],
);

function adaptMarkerToChartMarker(m: Marker): ChartMarker {
  // side ⊕ exit_reason → legacy 4-way kind
  const kind: ChartMarker["kind"] = (() => {
    if (m.side === "LONG_ENTRY" || m.side === "SHORT_ENTRY") return "ENTRY";
    if (m.exitReason === "STOP_LOSS") return "SL_HIT";
    if (m.exitReason === "TAKE_PROFIT") return "TP_HIT";
    return "EXIT";
  })();
  return {
    kind,
    time: m.time,
    price: m.price,
    quantity: m.quantity,
    side: m.side, // string in legacy shape — enum works fine
    pnl: m.pnl,
    exit_reason: m.exitReason,
  };
}
```

5. Update the `CandlestickChart` + `PaperTradeList` props that previously
   referenced `markersState.markers` (which under the legacy hook was
   `ChartMarker[]`) to instead pass `chartMarkers`:

```tsx
<CandlestickChart
  /* …other props… */
  markers={chartMarkers}
  /* …other props… */
/>
/* …and: */
<PaperTradeList
  markers={chartMarkers}
  isLoading={markersState.isLoading}
  hasLoaded={markersState.hasLoaded}
  error={markersState.error}
  /* …other props unchanged… */
/>
```

6. Strategy_id source: keep the existing `StrategySelector` flow — it
   already drives `strategyId`. **No MVP hardcoded constant needed**
   for Phase E (different from Phase D which had no selector). The
   selector persists per-(symbol, timeframe) to localStorage.

**Rollback**: revert the import (`useTradeMarkers` → `useChartMarkers`),
delete the adapter, revert the `mode` prop. The component shape is
unchanged.

### Option B (bigger refactor, cleaner long-term)

Refactor `CandlestickChart` to accept `markers: SeriesMarker<UTCTimestamp>[]`
directly (it builds them internally today via `toLwcMarker`). The new
hook already returns that shape. Drop the adapter from Option A and
delete `toLwcMarker` from `CandlestickChart.tsx`. Touches more files;
breaks the existing `tests/chart/CandlestickChart.test.tsx` fixtures.
**Not recommended for the cutover branch** — do this as a follow-up
sprint once Option A is stable in prod.

### Option C (coexist behind a feature flag)

Render both hooks in parallel, gate the consumer with a
`NEXT_PUBLIC_USE_PHASE_E_MARKERS` env flag. Useful if you want to A/B
the two sources on the same chart. Adds complexity without buying much
once Option A is proven — recommend skipping unless prod surfaces a
regression you want to roll back without redeploying.

---

## Step 2 — Backend router registration (PREREQUISITE)

The Phase A backend route lives at `backend/app/api/trade_markers.py`
but per its module docstring (lines 33-37) it is **not** registered in
`main.py` yet. Phase E's frontend hook will 404 against any environment
where the include_router line hasn't been applied.

Check `backend/PATCH_INSTRUCTIONS_PHASE_A.md` for the exact line, and
verify with:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$API_URL/api/markers?strategy_id=11111111-1111-1111-1111-111111111111&mode=PAPER"
# expect 200 with { strategy_id, mode, limit, offset, total, markers: [] }
# OR 403 if the strategy isn't owned by $TOKEN's user
```

If you get 404, the router is unmounted — apply the Phase A patch
first.

---

## Step 3 — Smoke test on staging

After applying Option A and the backend router registration:

1. Sign in as a user who owns at least one strategy with paper-trade
   activity in the last 24h.
2. Open the chart page, select that strategy from the selector.
3. Expected: same marker shapes + colors as before the cutover (the
   mapper preserves the legacy palette). The only visible difference
   is that markers now have proper exit-reason text (e.g. "TP 22550"
   instead of just the bar position).
4. Mode-switching smoke (if `mode` is wired to a UI control): toggle
   between PAPER and BACKTEST → markers should swap entirely.
5. Console: no 4xx/5xx in network tab; no React warnings about
   missing keys / invalid props.

---

## Step 4 — Decision log

When you apply these patches, append a one-line note to
`CHANGELOG.md` (or your equivalent) — Phase E is the cutover from the
legacy paper-trade-derived markers endpoint to the persistent
trade_markers table.

Example:

```
- chart: cutover marker overlay from /api/chart/markers to /api/markers
  (Phase E). Source-of-truth is now the trade_markers table; backtest +
  live modes show their own markers. Legacy /api/chart/markers endpoint
  + useChartMarkers hook stay mounted for one release as a rollback path.
```

---

## Files NOT touched in this branch

For audit / parallel-CC compliance:

- `src/components/chart/ChartContainer.tsx` — wire-up documented above
- `src/hooks/useChartMarkers.ts` — legacy hook stays as fallback
- `src/lib/chart/api.ts` — legacy fetcher stays as fallback
- `src/lib/chart/types.ts` — legacy `ChartMarker` type stays
- `src/components/chart/CandlestickChart.tsx` — Option A keeps it as-is
- `src/components/chart/PaperTradeList.tsx` — Option A keeps it as-is
- `backend/**` — Phase A endpoint already exists; no backend changes

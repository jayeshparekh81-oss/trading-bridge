# PATCH_INSTRUCTIONS_PHASE_D

Manual edits to wire the Phase D Strategy Tester panel into the
existing chart UI. Files in this list ALREADY EXIST on `main` — the
parallel-CC "new-files-only" rule means Phase D code in this branch
cannot edit them. Apply these patches by hand on a follow-up branch
(or directly on `main` if you're ok with that policy locally).

Branch: `feat/phase-d-strategy-tester-panel`
Snapshot date: 2026-05-16
Author: Phase D parallel-CC session

---

## Summary

Phase D ships these NEW files (already on this branch):

| Path | Lines | Purpose |
|---|---|---|
| `src/lib/strategy-tester/types.ts` | ~210 | Wire + render-ready TS types + parsers |
| `src/lib/strategy-tester/api.ts` | ~110 | URL builders + thin fetch wrappers over `@/lib/api` |
| `src/hooks/useStrategyTester.ts` | ~150 | Parallel fetch of metrics + equity + trades; refetch; error |
| `src/components/strategy-tester/StrategyTesterPanel.tsx` | ~170 | Top-level composition + loading/error/empty rendering |
| `src/components/strategy-tester/MetricsHeader.tsx` | ~140 | 12-tile report-card stats grid |
| `src/components/strategy-tester/EquityCurveChart.tsx` | ~135 | recharts AreaChart over the equity curve |
| `src/components/strategy-tester/TradeListTable.tsx` | ~250 | Sortable trade-log table |

Plus 6 test files under `tests/strategy-tester/`.

The panel is **not yet rendered anywhere** on the chart page — Phase D
deliberately ships behind a manual wire-up step so the chart route's
existing layout doesn't change without your review.

---

## Step 1 — Pick a target file

Two reasonable integration points on the chart page:

**Option A (simpler) — Render below the chart on the existing route**

Edit: `src/app/(dashboard)/chart/page.tsx`

Current contents (verified on `main` at 44a8bbf):

```tsx
"use client";

import { ChartContainer } from "@/components/chart/ChartContainer";

export default function ChartPage() {
  return <ChartContainer />;
}
```

Patch to:

```tsx
"use client";

import { ChartContainer } from "@/components/chart/ChartContainer";
import { StrategyTesterPanel } from "@/components/strategy-tester/StrategyTesterPanel";

// MVP: hardcoded strategy ID + mode. Replace with URL params or
// context once the strategy selector is wired up.
const MVP_STRATEGY_ID = "11111111-1111-1111-1111-111111111111";

export default function ChartPage() {
  return (
    <div className="flex flex-col gap-6">
      <ChartContainer />
      <StrategyTesterPanel strategyId={MVP_STRATEGY_ID} mode="PAPER" />
    </div>
  );
}
```

**Option B (better long-term) — Embed inside ChartContainer alongside the chart**

Edit: `src/components/chart/ChartContainer.tsx` — add an import + an
extra section after the existing chart canvas. The contract is the
same (`strategyId` + `mode` props); placement depends on the existing
container's layout (sidebar vs full-width).

Recommendation: ship Option A first, iterate on Option B once the
mode-toggle UI lands.

---

## Step 2 — Source the `strategyId`

Three escalation paths, in order of effort:

1. **Hardcoded UUID** (MVP, fastest) — paste a real strategy ID from
   `users.strategies` for the seed user. Good enough for the May 18
   demo.
2. **Query param** — read `searchParams.strategy_id` from the
   `(dashboard)/chart` route. Next.js 16 App Router signature is async
   (`params: Promise<{ ... }>`); see `AGENTS.md` in this folder for
   the breaking-change note. Requires un-marking the page as a Client
   Component or wrapping the strategy id in a server-shell.
3. **Strategy selector** — there's already a chart-module strategies
   fetch wrapper at `src/lib/chart/strategies.ts` powering a future
   selector dropdown; thread its selection into `<StrategyTesterPanel
   strategyId={selected} />` when that selector lands.

For the May 18 launch, **option 1 is fine** — paper-mode customers
will see their first strategy automatically once you swap in the real
seed UUID.

---

## Step 3 — Mode toggle (deferred to next phase)

The panel currently takes `mode` as a static prop. The Phase B
backend exposes `BACKTEST | PAPER | LIVE` so the same panel works
across all three modes — only the data source changes. A future
sub-component (a 3-segment toggle next to the panel header) will let
the user switch modes and trigger a refetch.

For now: hardcode `mode="PAPER"` to match the production paper-only
posture (`STRATEGY_PAPER_MODE=true`).

---

## Step 4 — Coverage include (optional, repo hygiene)

The new paths are NOT in `vitest.config.ts` coverage includes:

```ts
// Current includes — Phase D paths missing
"src/lib/chart/**",
"src/hooks/useChartMarkers.ts",
// ...
```

To measure Phase D coverage as part of the regular `vitest --coverage`
run, add these to `vitest.config.ts` (NEW edit, after the parallel-CC
freeze ends):

```ts
coverage: {
  include: [
    // ... existing entries ...
    "src/lib/strategy-tester/**",
    "src/hooks/useStrategyTester.ts",
    "src/components/strategy-tester/**",
  ],
  thresholds: {
    // ... existing thresholds ...
    "src/lib/strategy-tester/**": {
      lines: 90,
      branches: 80,
      statements: 90,
    },
    "src/hooks/useStrategyTester.ts": {
      lines: 85,
      branches: 70,
      statements: 85,
    },
    "src/components/strategy-tester/**": {
      lines: 75,
      branches: 60,
      statements: 75,
    },
  },
},
```

Until that edit lands, coverage for the new paths can be inspected
ad-hoc via:

```bash
cd frontend
npx vitest run tests/strategy-tester/ \
  --coverage \
  --coverage.include='src/lib/strategy-tester/**' \
  --coverage.include='src/hooks/useStrategyTester.ts' \
  --coverage.include='src/components/strategy-tester/**'
```

---

## Step 5 — Smoke test the integration

After applying step 1 + step 2:

```bash
cd frontend
npm run dev
# Open http://localhost:3000/chart
```

Expected:
- Chart renders as before (no regression).
- New "Strategy Tester" header + mode badge appear below the chart.
- For a strategy with zero closed trades: empty-state messages render
  ("No metrics yet", "No equity data yet", "No trades yet for this
  strategy"). No 4xx in the network panel except 401 if the user
  isn't logged in.
- For a strategy with at least one closed paper trade: metrics tiles
  populate with rupee figures, equity curve renders, trade row(s)
  render.

Failure modes to watch:
- 403 from the backend means the seed `strategyId` doesn't belong to
  the logged-in user. Pick a different UUID.
- 500 from `/metrics` with all other endpoints green almost always
  means the starting-equity walk hit a Decimal arithmetic edge case
  — check backend logs for `strategy_tester_service.aggregate_metrics`.

---

## Notes

- Decimal-as-string convention: backend serialises every P&L / equity
  / price field as a JSON string (cents-level precision preservation).
  All parsing happens in `src/lib/strategy-tester/types.ts` — components
  receive plain `number` types, no surprises at render time.
- ApiError 401 is handled by the shared `@/lib/api` client (auto
  refresh → ApiError on second failure). The panel's error banner
  will surface "Session expired. Please login again." on a hard 401.
- The panel intentionally does NOT subscribe to live ticks — equity
  curves and trade lists update on `refetch()` only. A live-mode
  variant (websocket-fed) is out of scope for Phase D.

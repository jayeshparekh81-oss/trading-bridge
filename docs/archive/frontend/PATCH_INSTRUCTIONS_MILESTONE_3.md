# PATCH_INSTRUCTIONS — Milestone 3 (Queue EE)

**Branch:** `feat/milestone-3-frontend-chart`
**Target file (cross-cutting edit):** `frontend/src/app/(dashboard)/strategies/[id]/backtest/page.tsx`
**Why a PATCH file instead of a direct edit:** parallel-CC branches follow
the **new-files-only rule** — Queue EE adds `BacktestChartPanel.tsx` + tests
+ audit doc, but the shared backtest results page (which is also touched by
adjacent queues) is changed manually by the founder. This file is the
hand-off.

---

## Architectural prerequisite (READ FIRST)

The existing page uses the **synchronous** backtest path:
`POST /strategies/${id}/backtest` → full payload inline (no `run_id`).
`BacktestChartPanel` needs `run_id` from the **async** path
`POST /api/backtest` (Queue CC+DD shipped on `feat/milestone-1-ship`).

Two integration shapes — pick one:

### Option (B) — Run async-flow in parallel (Queue EE recommendation)

Keep the existing sync POST untouched (no regression on the 8 existing
panels). Additionally fire an async enqueue with the same payload, surface
the chart panel once the async run reaches `SUCCEEDED`. The async run is
cache-friendly per Queue CC+DD's `request_hash` design, so the second call
is effectively free on cache hits.

### Option (A) — Page rewrite to use async-only

Replace `POST /strategies/${id}/backtest` with the async dispatch + poll
loop. Larger change, removes the duplicate enqueue, but touches every panel.
**Out of scope for Milestone 3.**

This patch describes Option (B).

---

## Patch — three insertion points

### 1. Add imports (top of file, after the existing `@/components/strategies/*` imports)

```ts
import { BacktestChartPanel } from "@/components/backtest/BacktestChartPanel";
```

### 2. Add async-enqueue state + effect (inside `StrategyBacktestPage`, after the existing `runBacktest` callback)

```ts
// Milestone 3 (Queue EE) — additionally enqueue an async backtest so
// BacktestChartPanel has a run_id to query /api/backtest/{run_id}/markers
// against. Cache-keyed identically to the sync POST so concurrent calls
// dedupe at the backend (Queue CC+DD's request_hash). Runs in parallel
// with the sync POST — does NOT block the existing 8 panels.
const [chartRunId, setChartRunId] = useState<string | null>(null);
const [chartRunSymbol, setChartRunSymbol] = useState<string | null>(null);
const [chartRunTimeframe, setChartRunTimeframe] = useState<Timeframe | null>(
  null,
);

useEffect(() => {
  if (!data) return;
  if (chartRunId) return; // already enqueued — page-load-once
  let cancelled = false;
  (async () => {
    try {
      const symbol = /* derive from strategy config or data — see note */;
      const timeframe = /* derive from strategy config or data — see note */;
      const enqueue = await api.post<{
        run_id: string;
        status: string;
        cached: boolean;
      }>("/backtest", {
        strategy_id: id,
        symbol,
        timeframe,
        start: /* backtest window start ISO */,
        end:   /* backtest window end ISO */,
        initial_capital: 100000,
        quantity: 1,
      });
      if (cancelled) return;
      // Poll until SUCCEEDED — Queue CC+DD's GET /api/backtest/{run_id}
      // returns status. Markers endpoint is safe to call as soon as
      // status === SUCCEEDED. ~1s interval is fine for cached hits.
      let done = false;
      for (let i = 0; i < 60 && !done; i++) {
        const status = await api.get<{ status: string }>(
          `/backtest/${enqueue.run_id}`,
        );
        if (cancelled) return;
        if (status.status === "SUCCEEDED") {
          done = true;
          setChartRunId(enqueue.run_id);
          setChartRunSymbol(symbol);
          setChartRunTimeframe(timeframe);
        } else if (status.status === "FAILED") {
          done = true; // chart panel will show empty state on no markers
        } else {
          await new Promise((r) => setTimeout(r, 1000));
        }
      }
    } catch {
      // Silently swallow — the existing sync panels are unaffected;
      // BacktestChartPanel just won't mount.
    }
  })();
  return () => {
    cancelled = true;
  };
}, [data, id, chartRunId]);
```

> **Symbol/timeframe derivation:** the strategy's `strategy_json` or the
> backtest request payload is the canonical source. If those aren't surfaced
> in `BacktestResponse`, fetch via `GET /api/strategies/${id}` and read
> `strategy_json.symbol` / `strategy_json.timeframe`. Cache the result so
> the enqueue effect doesn't refire on every render.

### 3. Mount the panel (inside the `data ? (<> … </>)` block, immediately after `<BacktestResultPanel>`)

```tsx
<motion.div variants={fadeUp}>
  <BacktestResultPanel result={data.backtest} />
</motion.div>

{/* Milestone 3 (Queue EE) — chart with trade markers from async run */}
{chartRunId && chartRunSymbol && chartRunTimeframe ? (
  <motion.div variants={fadeUp}>
    <BacktestChartPanel
      runId={chartRunId}
      strategyId={id}
      symbol={chartRunSymbol}
      timeframe={chartRunTimeframe}
    />
  </motion.div>
) : null}

<motion.div variants={fadeUp}>
  <StrategyCoachCard card={data.health_card} />
</motion.div>
```

---

## Why not edit the page directly?

`feat/milestone-3-frontend-chart` is one of several parallel-CC branches.
Direct edits to shared files like the backtest page create avoidable merge
conflicts with other queues and violate the user's recorded **new-files-only
rule for parallel-CC branches**. Precedent: this repo already uses
`PATCH_INSTRUCTIONS_FRONTEND_DAY3.md`, `PATCH_INSTRUCTIONS_PHASE_D.md`,
`PATCH_INSTRUCTIONS_PHASE_E.md` for the same reason.

## Deploy gate

- `BacktestChartPanel` will 404 in prod if merged to `main` **before** the
  Queue CC+DD `/api/backtest/*` routes are also live there.
- `feat/milestone-1-ship` (which carries those routes) deploys today
  (2026-05-21, 4 PM IST) — `feat/milestone-3-frontend-chart` must merge
  **into** `feat/milestone-1-ship` before that main merge, OR wait for the
  next deploy.
- Recommended sequence:
  1. Founder reviews this patch + applies the page edits manually.
  2. `feat/milestone-3-frontend-chart` → merge into `feat/milestone-1-ship`.
  3. Combined `feat/milestone-1-ship` → merge into `main` per the 4 PM deploy.

## Test plan after patch is applied

- [ ] Manual smoke: open the backtest page for the live BSE LTD strategy
      `89423ecc-c76e-432c-b107-0791508542f0` (Dhan), wait for async run to
      complete, confirm chart panel appears under `BacktestResultPanel`
      with green up-arrows on entries / red down-arrows on exits.
- [ ] Forced-failure smoke: temporarily stub `/api/backtest/*/markers` to
      500 → confirm error state + retry surface.
- [ ] Empty smoke: backtest a strategy known to generate zero trades →
      confirm "No trades in this backtest run".
- [ ] Pre-existing regression: re-run the full `vitest` suite; the 3
      failures in `tests/templates/TemplateCard.test.tsx` (1) and
      `tests/chart/ChartContainer.test.tsx` (2) are **pre-existing on
      `feat/milestone-1-ship`** and not caused by Milestone 3.

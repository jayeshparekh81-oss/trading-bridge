# Frontend chart patch instructions

Day-5 deliverable on `feat/frontend-chart`. Three tiers below.

---

## 🟥 Required for the chart UI to function

### 1. Install runtime dependency: `lightweight-charts`

```bash
cd frontend
npm install --save lightweight-charts@^4.2.0
```

Pin to v4.x intentionally — Lightweight Charts v5 introduces a
different series API (`addSeries(CandlestickSeries, ...)` vs v4's
`addCandlestickSeries(...)`). The chart component is written
against the v4 surface. A v5 migration is its own scoped change.

### 2. Install dev dependencies: Vitest stack + msw/ws

```bash
cd frontend
npm install --save-dev \
  vitest@^4 \
  @vitejs/plugin-react@^5 \
  @testing-library/react@^16 \
  @testing-library/jest-dom@^6 \
  @testing-library/dom@^10 \
  jsdom@^28 \
  @vitest/coverage-v8@^4 \
  msw@^2 \
  @types/ws@^8
```

`msw` (Mock Service Worker) + `@types/ws` are bundled into this
install instead of waiting for Day 4. Rationale: Day-4 budget should
spend on writing WS lifecycle tests, not on debugging mock-tooling
setup. With msw/ws pre-installed, the Day-4 work (item 7 below) goes
straight to test code.

Also add the test scripts to `package.json` under `"scripts"`:

```json
"test": "vitest run",
"test:watch": "vitest",
"test:coverage": "vitest run --coverage"
```

The Vitest config is committed at `frontend/vitest.config.ts` and
the global setup at `frontend/tests/setup.ts`. No additional config
required — `npm test` will discover the chart tests under
`frontend/tests/chart/`.

### 3. Register the chart route in main navigation

The route file is at `frontend/src/app/(dashboard)/chart/page.tsx`
and inherits auth + Sidebar + TopBar from `(dashboard)/layout.tsx`
— no extra wiring needed at the page level.

**However**, the Sidebar component
(`frontend/src/components/dashboard/sidebar.tsx`) does not yet have
a link to `/chart`. Add a nav entry alongside the existing ones
(strategies, brokers, indicators, etc.). Suggested label: "Chart"
with `lucide-react`'s `LineChart` icon. Manual edit so this PR
does not touch shared chrome.

### 4. Environment variable for mock toggle

The Day-5 branch ships with a static-fixture + in-memory-WS-server
mock that activates when `NEXT_PUBLIC_USE_MOCK=true`. Leave the env
var **unset** in production. For local development before the
backend smoke test is green, add to `frontend/.env.local`:

```
NEXT_PUBLIC_USE_MOCK=true
```

Operator switches it off (or removes it from `.env.local`) once
the chart pipeline backend smoke test is green tomorrow morning.

---

## 🟨 Day 4 mandatory completion list

**Budget commitment:** ~5 hours of Day-4 (May 14) is allocated to
the items below. They are non-negotiable for the May-18 launch, not
"best effort" — Day 5 ships with a known WS-hook coverage gap and
Day 4 closes it.

| # | Item | Budget | Status entering Day 4 |
|---|---|---|---|
| 7 | `useChartWebSocket` → 96%+ via msw/ws | 2 hr | tooling pre-installed (PATCH §2) |
| 8 | `ChartContainer` + `CandlestickChart` tests | 2 hr | components shipped, 0% covered |
| 8.1 | `app/(dashboard)/chart/page.tsx` happy-path integration | 30 min | 0% covered |
| 6 | sonner toast disconnect swap (replaces inline `<Alert>` overlay) | 20 min | inline banner present |
| 4.x | Re-enable vitest thresholds (commit: `chore(chart-fe): enforce coverage thresholds post-Day-4 testing completion`) | 10 min | thresholds disabled in `vitest.config.ts` per §4 below |

Manual smoke-test scenarios (PATCH item 3.x — new file
`frontend/docs/chart_fe_manual_smoke.md`) compensate for the
Day-5 WS coverage gap until Day-4 closes it.

### 5. Coverage gates per R5 tier — current state vs target

The brief's R5 tier system splits 96%+ mandatory (hooks + lib) from
softer expectations (components, page integration). Day 5 ships at:

| Module | Day-5 actual | R5 target | Gap |
|---|---|---|---|
| `src/lib/chart/api.ts` | 100% stmts, 92% branch | 96/90 | ✅ |
| `src/lib/chart/mock_data.ts` | 98% stmts, 88% branch | 96/90 | branch −2pp |
| `src/lib/chart/types.ts` | 100% (via parseCandle + guards) | 96 | ✅ |
| `src/hooks/useWsToken.ts` | 94% stmts | 96 | −2pp |
| `src/hooks/useChartHistory.ts` | 94% stmts | 96 | −2pp |
| `src/hooks/useChartWebSocket.ts` | **9% stmts** | 96 | **−87pp ⚠️** |
| `src/components/chart/*` (5 files) | 62% avg | softer | ⚠️ ChartContainer + CandlestickChart at 0% |
| `src/app/(dashboard)/chart/page.tsx` | 0% | 1 integration test | ⚠️ |

The big gap is `useChartWebSocket` — see item 7 below for the
explanation + Day-4 fix path.

The smaller `useWsToken` / `useChartHistory` 2pp gap is the
``enabled=false`` short-circuit branch on the first render commit
not being reached because the effect body runs synchronously
before the test's ``await act`` resolves. Easy fix in Day 4.

The `vitest.config.ts` does NOT currently enforce thresholds.
**Day-4 re-enable plan** (CONDITION 4 from the senior review):

After Day-4 testing items 6/7/8/8.1 complete, restore thresholds in
`vitest.config.ts`:

```ts
thresholds: {
  "src/lib/chart/**":           { lines: 96, branches: 90, statements: 96 },
  "src/hooks/**":               { lines: 96, branches: 90, statements: 96 },
  // Components: enforce file-level minimum of at least one
  // snapshot or interaction test per file.
  "src/components/chart/**":    { lines: 60, branches: 50, statements: 60 },
  // Page: integration test gate.
  "src/app/(dashboard)/chart/**": { lines: 60, branches: 50, statements: 60 },
},
```

Commit message for this exact change (per the senior-review brief):

```
chore(chart-fe): enforce coverage thresholds post-Day-4 testing completion
```

### 6. Replace inline-banner disconnect overlay with sonner toast

Day-5 disconnect overlay is an inline `<Alert>` positioned over
the chart. The `sonner` toast library is already in the dep tree
and is the project's standard non-blocking notification. Day 4
swap is a 20-line change in `ChartContainer.tsx`.

### 7. WS-hook unit tests — `useChartWebSocket` lifecycle (Day-4 polish)

**Why deferred:** The full lifecycle (`open` / `message` /
`reconnect` / `heartbeat` / `disconnect`) needs a WebSocket
double. Two approaches tried during Day 5, both hit walls:

1. **Hand-rolled fake on `globalThis.WebSocket`**: drove a
   reconnect → close → reconnect → close loop under
   `vitest --pool=forks` because the fake's synchronous
   construction doesn't model the real async handshake. Heap
   exhausted in ~40s.
2. **Removing reconnect from the equation by using `token=null`**:
   does cover the reducer's reset path but leaves the actual
   WS-instance interaction untested.

Day-4 polish should add **MSW-WS** (`msw/ws`) which intercepts
WebSocket constructions at the worker level and gives a clean
async handshake model. ~30 min setup + ~3 hr to write the lifecycle
tests = under half a day budget.

### 8. ChartContainer + CandlestickChart integration tests

The orchestrator and the Lightweight Charts wrapper currently have
0% coverage. Day-4 should add:

- ChartContainer happy-path: mock the 3 hooks (`useWsToken`,
  `useChartHistory`, `useChartWebSocket`) to return canned state,
  render, assert the chart canvas appears + the selectors fire
  onChange.
- CandlestickChart: inject the `createChartFn` test seam (already
  present on the component) to capture the calls to
  `chart.addCandlestickSeries`, `series.setData`, `series.update`,
  `chart.applyOptions` — verifies the R1 ResizeObserver path + the
  tail-update vs full-setData branching.

### 9. Phase 2: extract shared chart-data helper

Both this branch's `useChartHistory` and the backend's chart-history
route call the same logical fetch. After backend Phase 2 ships
`services/chart_data.py`, the frontend's `useChartHistory` can move
to a tanstack-query (or SWR) caching layer that shares state with
the indicator hooks Day 6 will add.

---

## 🟦 Day-5 R5 coverage tier reminder (documented per brief)

For future Day 6+ frontend work, the same tier rules apply:

| Tier | Modules | Coverage gate |
|---|---|---|
| Logic-heavy | `src/hooks/**`, `src/lib/chart/**` | 96%+ lines, 90%+ branches |
| Presentational | `src/components/chart/**` | snapshot + at least one interaction test per critical path |
| Page integration | `src/app/(dashboard)/chart/page.tsx` and future indicator pages | one happy-path render test (mock data loads, renders, no console errors) |

---

## Manual verification before merge

```bash
cd frontend

# 1. Install deps per items 1 + 2 above.
npm install

# 2. Run the chart tests.
npm test -- tests/chart

# Expected: 63 passed (lib + hooks + components).
# Day-4 polish (item 7 + 8) will add ~30 more tests.

# 3. Local dev with mock data — until backend smoke test is green.
echo "NEXT_PUBLIC_USE_MOCK=true" >> .env.local
npm run dev
# → open http://localhost:3000/chart in a logged-in browser
# → confirm chart canvas renders 200 candles
# → confirm new candle appears every ~5 seconds (mock WS tick)
# → confirm symbol/timeframe selectors swap the data

# 4. Backend smoke green tomorrow morning — switch to live:
sed -i.bak 's/NEXT_PUBLIC_USE_MOCK=true//' .env.local
# Or just remove the line. Restart dev server.
# → confirm /api/chart/history fires, candles render
# → confirm /api/chart/ws-token fires, WS connects
# → confirm browser DevTools shows the WS receiving frames
```

## Don't merge until

- [ ] PATCH §1 (`lightweight-charts`) installed in `package.json`.
- [ ] PATCH §2 (Vitest stack + msw + @types/ws) installed in
      `package.json` and test scripts added.
- [ ] PATCH §3 (sidebar nav entry) applied manually.
- [ ] PATCH §3.x — `frontend/docs/chart_fe_manual_smoke.md` exists
      and all 5 scenarios (A–E) executed at least once before launch.
- [ ] Backend chart pipeline smoke test green (separate sprint gate).
- [ ] Dev smoke against live backend passes (steps 3 + 4 above).
- [ ] **Day 4 mandatory completion list (§5 + Day-4 budget block)**:
      items 7, 8, 8.1, 6, and 4.x ALL completed. Non-negotiable.
      Coverage thresholds re-enabled in vitest.config.ts via the
      exact commit message specified above.

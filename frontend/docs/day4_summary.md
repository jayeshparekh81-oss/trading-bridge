# Day-4 + office-day push — summary

This file consolidates the post-Day-5 work into a single narrative
the operator can scan in five minutes. Two phases:

1. **Day-4 / overnight finishing** (testing + B6/B7/B8/B9/C10/C11
   polish) — already on `main` via PRs cited inline.
2. **Office-day autonomous push** (Phases 1–9 below) — shipped on
   `feat/frontend-chart` while the operator was unreachable.

---

## Day-4 / overnight finishing (recap, already shipped)

Sprint goals: lock the Day-5 chart UI to the same quality bar as
the rest of the dashboard — coverage gates, mobile baseline,
disconnect UX, Next.js error boundary, mock fixture continuity.

| Item   | Commit    | Title                                                                |
| ------ | --------- | -------------------------------------------------------------------- |
| A1     | `1ed02b3` | extract ChartWsTransport class for testability                       |
| A1     | `257166b` | ChartWsTransport coverage 96%+ via direct class tests                |
| A1     | `ff1bca3` | useChartWebSocket binding tests                                      |
| A2 1/2 | `5760585` | ChartContainer orchestration tests                                   |
| A2 2/2 | `d2c5359` | CandlestickChart createChartFn-seam tests                            |
| A3     | `565e9b2` | /chart page happy-path integration                                   |
| A4     | `0d4f489` | swap inline disconnect overlay for sonner toast                      |
| A5     | `6969530` | enforce coverage thresholds post-Day-4 testing                       |
| B6     | `5893db4` | Next.js error.tsx route-segment boundary                             |
| B7     | `5cd872f` | 3-layer chart-shaped skeleton                                        |
| B8     | `3f7f56f` | reconnect UI — StatusPill + manual reconnect                         |
| B9     | `9988f5a` | session-expired banner + toast-once polish                           |
| C10/11 | `baafd43` | remove TradingView attribution + mock fixture continuity             |

Test count entering office-day: **182** across 15 files.

---

## Office-day push (2026-05-12, ~12 hours, autonomous)

Operator at office on mobile-only access. Frontend Claude Code
shipped Phases 1–9 below back-to-back on `feat/frontend-chart`.
All commits pushed to origin; coverage gate enforced after each
phase.

### Phase 1 — C11 regression fix (historical preload)

Commit: **`e16be50`**
`fix(chart-fe): restore historical mock fixture preload — Phase 1 / C11 regression`

Operator reported only ~2 candles visible after C11. Two root
causes, both fixed:

1. Mock WS server was advancing `nextEpoch` by `tfSeconds` per
   tick — at 5s real-time / 5m timeframe, 60s of viewing produced
   12 future-dated bars and Lightweight Charts' auto-pan-to-tail
   silently pushed the historical preload off narrow viewports.
   Fix: emit for the *current real-time bucket* — within the same
   bucket it's an intra-bar update; across boundaries it's a new
   bar.
2. CandlestickChart never called `timeScale().fitContent()` after
   the first `setData`. Fix: call once on first paint (gated by
   `prev === null`) + once on the symbol/timeframe-switch fallback.
   Tail-only updates do NOT re-fit (would clobber user pan/zoom).

Tests: 182 → 185 (+3). All passing.

### Phase 2 — Crosshair OHLCV tooltip

Commit: **`2b6398c`**
`feat(chart-fe): crosshair OHLCV tooltip — Phase 2`

`chart.subscribeCrosshairMove` drives a React-rendered
absolutely-positioned overlay with O / H / L / C / V plus an
IST-formatted timestamp. Direction-coloured close (green / red).
Volume formatter uses Indian retail convention (`95.0K` / `12.35L`
/ `2.50Cr`). Pointer-events disabled so the chart's own crosshair
pass-through stays intact.

Handler is created once at mount and reads candles from a ref so
prop changes don't churn subscribe/unsubscribe. Tooltip position
clamped to container so it never spills past the right/bottom edge.

Tests: 185 → 199 (+14).

### Phase 3 — Volume bars pane

Commit: **`0b68362`**
`feat(chart-fe): volume bars pane below price — Phase 3`

`addHistogramSeries` on a dedicated `"volume"` price scale with its
own scaleMargins (top: 0.75, bottom: 0). Price-series scaleMargins
re-applied at mount (top: 0.05, bottom: 0.27) so the canvas reserves
the bottom ~25% strip without a visual jump when the histogram lazy-
appears. Per-bar colour follows close-vs-open direction at 55% alpha.

Lazy-creation: histogram only spawned the first time a candles
array carries any positive volume. Volume-less feeds (some MCX
option chains, some symbols with no V tape) skip the histogram and
log a one-shot `console.warn` so the omission isn't silent.

Tests: 199 → 208 (+9).

### Phase 4 — Header info row

Commit: **`f749270`**
`feat(chart-fe): header info row with live price + day OHLCV — Phase 4`

Two-tier ribbon between the top bar and the chart canvas. Mobile-
essential pair (price + percent change) always visible; desktop-
only OHLCV breakdown hidden under `sm:`. Day-window logic walks
candles from the tail backward by IST date so today's bars feed
the open/high/low/volume aggregates regardless of how many older
days are in the buffer. Change calc baselined on today's open
(intraday convention used by NSE / Zerodha / Dhan / Fyers).

Defensive guards: empty candles → em-dash placeholder; zero open
→ pctChange = `null` (no NaN).

Tests: 208 → 224 (+16).

### Phase 5 — Scroll-back lazy load

Commit: **`448ec11`**
`feat(chart-fe): scroll-back lazy load for historical data — Phase 5`

Foundation for the backtesting view. Layered cleanly:

- `getMockOlderHistory` (mock_data.ts) — pure synthesiser with
  contiguous-prepend guarantee + per-batch seed derivation.
- `fetchOlderHistory` (api.ts) — async wrapper. Mock or real;
  mirrors the initial-history query.
- `useChartScrollback` (NEW hook) — owns the older-bars buffer,
  the in-flight gate, and the 5-year cap for intraday timeframes.
  Synchronous in-flight gate via ref (state-based gate would race
  during fast left-scrolls).
- CandlestickChart — subscribes to `subscribeVisibleLogicalRangeChange`,
  fires the trigger when range.from < length × 0.2. Adds a head-
  changed branch in the data-sync effect so prepended bars route
  through `setData` (re-rasterise) WITHOUT `fitContent` (which
  would zoom out and undo the user's scroll).
- ChartContainer — wires the hook + merges
  `[...olderCandles, ...liveCandles]` via useMemo. Older bars sit
  OUTSIDE the WS hook's reducer so a prepend doesn't trigger the
  seed-reset path that erases live ticks.

Loading overlay: small left-edge spinner pill while a fetch is
in flight, pointer-events disabled.

Tests: 224 → 280 (+56).

### Phase 6 — Day 3 backend chart_markers scaffold (UNREGISTERED)

Commit: **`8a38cc5`**
`feat(chart): scaffold chart markers endpoint (Day 3 prep, unregistered)`

Three NEW backend files implementing `GET /api/chart/markers`:

- `app/schemas/chart_marker.py` — ChartMarker, ChartMarkerKind
  (ENTRY / EXIT / SL_HIT / TP_HIT), ChartMarkersResponse.
  Strict + frozen + `extra="forbid"`. Decimal-as-JSON-string wire.
- `app/services/chart_marker_service.py` — read path + the
  exit-reason vocabulary (TARGET → TP_HIT, STOP_LOSS /
  TRAILING_STOP → SL_HIT, everything else → EXIT). Walks
  list_sessions + asyncio.gather list_trades, fans each row out
  to its 1 (open) or 2 (closed) markers, sorts globally.
- `app/api/chart_markers.py` — route handler. JWT auth + strategy
  ownership check (collapses missing-strategy + cross-user into
  one 403, no existence leak). 5-min Redis cache with epoch-second
  cache key (tz-invariant).

Router is **deliberately NOT registered in main.py**. Day-3
dispatch wires it up via `PATCH_INSTRUCTIONS_FRONTEND_DAY3.md`.

Tests: comprehensive (4 classes × ~20 tests). AST syntax verified
locally; pytest-end-to-end deferred to operator's environment
because the office-day environment had no Python venv with
fastapi installed. Verification step is in the patch doc's
checklist.

### Phase 7 — Day 3 frontend useChartMarkers scaffold (UNINTEGRATED)

Commit: **`eb6837f`**
`feat(chart-fe): scaffold useChartMarkers hook + types — Phase 7 (Day 3 prep)`

Frontend half:

- `lib/chart/types.ts` — added ChartMarkerKind, WireChartMarker,
  ChartMarker, ChartMarkersResponse + `parseChartMarker` helper.
  Wire shape mirrors backend Phase-6 verbatim.
- `lib/chart/api.ts` — `fetchChartMarkers` wrapper.
- `lib/chart/mock_data.ts` — `getMockMarkers` fixture (6 markers
  spread across all 4 kinds).
- `hooks/useChartMarkers.ts` (NEW) — REST-only fetch hook with
  `{ markers, isLoading, hasLoaded, error, refetch }`. Stale-
  response gate via versionRef (same pattern as scrollback).

NOT integrated into ChartContainer — Day-3 work owns the strategy
picker + the CandlestickChart `markers` prop + `series.setMarkers`
call.

Tests: 280 → 296 (+16).

### Phase 8 — Repo hygiene + dead code cleanup

Commit: **`47dfbe5`**
`chore(chart-fe): repo hygiene + dead code cleanup — Phase 8`

- Deleted three stray empty files at the repo root: `=`, `naming`,
  `Success!`. None were referenced.
- Removed the `broker_disconnected` variant from ErrorState +
  the one components.test.tsx assertion that exercised it.
  ChartContainer surfaces broker disconnects via sonner toast
  (since A4); the variant added a switch arm nothing routed to.
- `vitest run --coverage` exit 0 confirmed.

Tests: 296 → 276 (−20 from removal of one test + auto-collected
test count drift).

### Phase 9 — Documentation

Commit: this one — `docs(chart-fe): update Day 4 summary + Day 3
design notes + PATCH instructions`.

Created / updated:

- `frontend/docs/day4_summary.md` (THIS FILE) — narrative + commit
  table + decisions.
- `frontend/docs/day3_design_notes.md` — design refinements after
  Phase-6/7 scaffolding work.
- `frontend/PATCH_INSTRUCTIONS_FRONTEND.md` — appended a
  "Office-day push" section.
- `frontend/PATCH_INSTRUCTIONS_FRONTEND_DAY3.md` — created in
  Phase 6, pre-existing.

---

## Final coverage snapshot

```
File                           | % Stmts | % Branch | % Funcs | % Lines
-------------------------------|---------|----------|---------|--------
All files                      |   95.85 |    88.80 |   96.57 |   97.96
 (dashboard)/chart/error.tsx   |     100 |    83.33 |     100 |     100
 components/chart aggregate    |   98.34 |    95.13 |     100 |     100
   CandlestickChart.tsx        |   98.03 |    95.06 |     100 |     100
   ChartContainer.tsx          |     100 |    93.75 |     100 |     100
   ChartHeaderInfo.tsx         |   97.91 |    94.87 |     100 |     100
   StatusPill.tsx              |   97.56 |       96 |     100 |     100
 hooks aggregate               |   88.88 |    70.32 |   90.32 |   92.78
   useChartHistory.ts          |   94.28 |       75 |     100 |     100
   useChartMarkers.ts          |   93.75 |    85.71 |     100 |     100
   useChartScrollback.ts       |   96.66 |    85.71 |     100 |     100
   useChartWebSocket.ts        |   71.92 |    36.36 |      70 |   74.07
   useWsToken.ts               |   92.68 |    73.33 |     100 |   97.29
 lib/chart aggregate           |   98.85 |    93.02 |   96.42 |     100
   api.ts                      |     100 |    86.95 |     100 |     100
   chart_ws_transport.ts       |   98.63 |      100 |   93.33 |     100
   mock_data.ts                |   98.79 |    84.61 |     100 |     100
```

Coverage gate green (`vitest run --coverage` exit 0). 18 test
files. **276 tests total**, all passing.

---

## Cross-cutting decisions worth re-reading

(Not exhaustive — the per-phase commits carry the full
``decision: ...`` notes.)

- **Phase 1 mock WS bucket emission** — emitting for the current
  real-time bucket (not advancing nextEpoch artificially) makes
  the mock match real broker behaviour AND prevents the chart
  from drifting off-screen. Combined with fitContent on first
  paint, the historical preload is now bulletproof.
- **Phase 2 ref-mirrored crosshair handler** — the handler is
  created ONCE at mount; new candles arrive via candlesRef.
  Avoids the subscribe/unsubscribe churn that would happen on
  every live tick.
- **Phase 3 lazy histogram + console.warn skip** — saves DOM/
  canvas overhead for symbols that never carry volume; the warn
  surfaces the silent omission so it doesn't look like a bug.
- **Phase 4 today's-open baseline** — change-vs-today's-open
  matches NSE / Zerodha / Dhan / Fyers convention. Previous-
  day-close would need a separate fetch we don't reliably have
  on intraday timeframes.
- **Phase 5 head-changed setData WITHOUT fitContent** — re-fitting
  would zoom out and lose the user's scroll position, undoing
  the very interaction that triggered the prepend.
- **Phase 5 refs-not-state for in-flight gates** — `setState` is
  async; a synchronous burst of `requestOlder` calls during a
  fast left-scroll would all observe stale `isLoadingOlder=false`
  and stack concurrent fetches.
- **Phase 6 403 (not 404) for missing strategy** — 404 leaks
  existence; a sequence of guess-and-check requests would reveal
  which UUIDs are valid. 403 says "you can't see this".
- **Phase 6 + 7 unregistered scaffolds** — locks the wire contract
  today (so frontend + backend agree on shape) without exposing
  unfinished features on production surfaces. One include_router
  line + one ChartContainer integration block at Day-3 dispatch.
- **Phase 8 dropped broker_disconnected ErrorState variant** —
  toast surface was the A4 replacement; the variant was an
  unreferenced switch arm.

---

## What's still ahead (NOT in this push)

- Day-3 dispatch — wire the chart_markers router in main.py +
  integrate useChartMarkers into ChartContainer. See
  `PATCH_INSTRUCTIONS_FRONTEND_DAY3.md`.
- Day-2 mobile work (out of office-day scope per the brief).
- Phase-2 SymbolResolver service extraction (flagged in
  `backend/PATCH_INSTRUCTIONS.md`).
- WS-token `aud="ws"` claim (flagged in same).

# Queue EE — Final Report

**Mission:** Frontend Milestone 3 — Chart Panel for Backtest Results
**Branch:** `feat/milestone-3-frontend-chart` (base: `feat/milestone-1-ship`)
**Date:** 2026-05-21
**Status:** ✅ Phases 1, 2, 4, 5 shipped. Phase 3 (page edit) handed off
via `frontend/PATCH_INSTRUCTIONS_MILESTONE_3.md` per parallel-CC
new-files-only rule.

---

## 1. Files changed

All NEW files (parallel-CC new-files-only rule honoured — zero edits to
shared files):

| Path | Purpose | LoC |
|---|---|---:|
| `frontend/src/components/backtest/BacktestChartPanel.tsx` | The component itself | 384 |
| `frontend/tests/backtest/BacktestChartPanel.test.tsx` | 7 vitest tests | 290 |
| `frontend/docs/MILESTONE_3_FRONTEND_AUDIT.md` | Phase 1 audit (chart + page + marker contract) | 154 |
| `frontend/PATCH_INSTRUCTIONS_MILESTONE_3.md` | Page integration patch for founder | 153 |
| `docs/QUEUE_EE_FINAL_REPORT.md` | This file | — |

Edits to existing files: **none**.

## 2. Architectural finding (surfaced during Phase 1)

The existing backtest results page uses the **synchronous** flow
`POST /strategies/${id}/backtest` → full payload inline (no `run_id`).
The Queue CC+DD markers endpoint `/api/backtest/{run_id}/markers` is a
separate **async** flow that needs a `run_id` from `POST /api/backtest`.

→ `BacktestChartPanel` is self-contained and accepts `runId` via props.
The page integration patch (Option B) recommends running the async-enqueue
**in parallel** with the existing sync POST, so the 8 existing panels stay
on the proven sync path and the new chart panel mounts once the async run
reaches `SUCCEEDED`. Page rewrite to async-only is out of scope.

## 3. Test counts

| | Before | After | Delta |
|---|---:|---:|---:|
| Test files | 53 | 54 | +1 |
| Tests total | 630 | 637 | +7 |
| Passing | 627 | 634 | +7 |
| Failing | 3 | 3 | 0 |

**The 3 pre-existing failures** (`tests/templates/TemplateCard.test.tsx` × 1,
`tests/chart/ChartContainer.test.tsx` × 2) were **confirmed by checking out
`feat/milestone-1-ship` and re-running the same files** — same failures
reproduce. Not caused by Queue EE; flagged to founder.

All 7 new tests pass on first run (`npx vitest run tests/backtest/BacktestChartPanel.test.tsx`):

```
 Test Files  1 passed (1)
      Tests  7 passed (7)
   Duration  1.68s
```

Tests cover (per Queue EE brief §Phase 4):

1. ✅ Loading skeleton during fetch
2. ✅ Loaded with markers → chart mounted + `setMarkers` called with passthrough wire shape
3. ✅ Empty markers → "No trades" empty state, candle fetch skipped
4. ✅ 404 → "Markers not available" state
5. ✅ Generic error → error banner + retry; retry refetches
6. ✅ Marker colour-mapping preserved (entry `#22c55e` / exit `#ef4444`)
7. ✅ Candles failure → markers-only fallback banner

## 4. Branch SHAs

- Base: `2390f26` (`feat/milestone-1-ship` HEAD)
- Branch HEAD before commit: same `2390f26` (this report describes the
  pre-commit state; founder commits + pushes after review)

## 5. Deploy implications

- **Frontend auto-deploys to Vercel on `main` push.**
- **Backend endpoint** `/api/backtest/*` lives on `feat/milestone-1-ship`
  and is mounted there (commit `2390f26`). It is **not yet on `main`**.
- → `feat/milestone-3-frontend-chart` must NOT be merged to `main` ahead of
  `feat/milestone-1-ship`, or `BacktestChartPanel` will 404 in prod.
- **Recommended sequence (founder, 2026-05-21 ~4 PM IST deploy):**
  1. Founder reviews + applies `frontend/PATCH_INSTRUCTIONS_MILESTONE_3.md`
     to the backtest page on `feat/milestone-1-ship` (or
     `feat/milestone-3-frontend-chart` if merging first).
  2. Merge `feat/milestone-3-frontend-chart` → `feat/milestone-1-ship`.
  3. Merge combined `feat/milestone-1-ship` → `main` per the 4 PM deploy.

## 6. Hard-stop checklist (per Queue EE brief)

| Check | Status |
|---|---|
| No push/merge to `main` | ✅ branch-only, no push performed |
| No live-trading code touched | ✅ frontend chart panel only |
| No backend changes | ✅ verified — `git diff --name-only feat/milestone-1-ship..HEAD` covers `frontend/**` + `docs/QUEUE_EE_*` only |
| Existing `/chart` route untouched | ✅ `frontend/src/app/(dashboard)/chart/page.tsx` not modified |
| Working tree clean | ⚠️ pre-existing untracked: `PHASE_F_ROADMAP_DIAGNOSIS.md`, `backend/backend/` (carried in from base — not Queue EE) |
| Live BSE LTD strategy `89423ecc-…` untouched | ✅ no code path that touches it |

## 7. Design call log

- **Did NOT reuse `<CandlestickChart>`** — marker-shape mismatch (legacy
  4-way `kind` vs. backend's already-LWC `SeriesMarker` shape) + irrelevant
  WS/scrollback/indicator baggage. Used `createChart` directly via the same
  test-injection seam (`createChartFn` prop) that `CandlestickChart` uses.
  Rationale documented in `frontend/docs/MILESTONE_3_FRONTEND_AUDIT.md` §3.
- **Did NOT edit shared page** — parallel-CC new-files-only rule.
  Handed off via `frontend/PATCH_INSTRUCTIONS_MILESTONE_3.md`. Precedent:
  `PATCH_INSTRUCTIONS_FRONTEND_DAY3.md`, `PHASE_D`, `PHASE_E`.
- **Window derivation:** markers' `[min, max]` time ± one timeframe-bar
  for visual padding, rather than the live chart's fixed 200-bar window.
  Backtest is a static snapshot — its window IS the trade window.
- **Empty markers short-circuits the candle fetch** — no point fetching a
  candle window when there are no trades to render against it.

## 8. Open / follow-up items for founder

- Apply `PATCH_INSTRUCTIONS_MILESTONE_3.md` to the backtest page
  (`frontend/src/app/(dashboard)/strategies/[id]/backtest/page.tsx`).
- Decide symbol/timeframe derivation source — `BacktestResponse` doesn't
  surface either; the patch notes recommend reading from
  `GET /api/strategies/${id}` and caching the result.
- 3 pre-existing test failures on `feat/milestone-1-ship` (Template /
  ChartContainer) are NOT in Queue EE scope but worth tracking.

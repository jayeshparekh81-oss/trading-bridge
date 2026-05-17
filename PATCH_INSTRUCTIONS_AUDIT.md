# PATCH_INSTRUCTIONS_AUDIT

**Date:** 2026-05-17 (T-1 from May-18 launch)
**Scope:** Inventory of every `PATCH_INSTRUCTIONS*.md` file in the
repository, with applied / unapplied status and risk rating.
**Method:** Read each file's stated patches; cross-check against the
current `main` HEAD via grep / git log / route inspection. Read-only —
no patches were executed by this audit.

---

## Summary

| Metric | Count |
|---|---:|
| Total `PATCH_INSTRUCTIONS*.md` files | **9** |
| Fully APPLIED | 7 |
| PARTIALLY applied (some patches done, some pending) | 1 |
| UNAPPLIED | 0 |
| Risk-LOW gaps | 7 (all the fully-applied docs are now historical) |
| Risk-MEDIUM gaps | 1 (the partially-applied INDICATORS doc) |
| Risk-HIGH gaps | 0 |

**Net pre-launch verdict:** zero HIGH-risk pending patches. One MEDIUM-
risk gap (the `/api/chart/indicator` HTTP route mount) is scheduled
for tonight's supervised override session.

---

## Per-file status table

| # | File | Scope | Last commit | Status | Risk if unapplied |
|---:|---|---|---|---|---|
| 1 | `backend/PATCH_INSTRUCTIONS_INDICATORS.md` | Day-6 indicator service: register `/api/chart/indicator` router in `main.py`, ensure TA-Lib system pkg + pyproject pin | `42fad70` 2026-05-11 | **PARTIAL** — service built ✓, ta-lib pin in pyproject.toml ✓, ta-lib installed on EC2 (brew) ✓, **but router NOT mounted in main.py** | **MEDIUM** — limits feature surface (chart UI can't render the 230-indicator catalog via HTTP), but does NOT break existing chart functionality (default 5 indicators are computed client-side). |
| 2 | `backend/PATCH_INSTRUCTIONS_PHASE_A.md` | Phase A markers backend (`/api/markers`, `trade_markers` table, persistence) | `d2ccf8c` 2026-05-15 | APPLIED — `/api/markers` confirmed live in prod via Phase E session memory | LOW |
| 3 | `backend/PATCH_INSTRUCTIONS_PHASE_B.md` | Phase B strategy-tester backend (aggregation API) | `164f40f` 2026-05-15 | APPLIED — Phase D strategy-tester panel went live on customer dashboards, which depends on this | LOW |
| 4 | `backend/PATCH_INSTRUCTIONS.md` | Chart-module cross-cutting (chart api routes: history, ws-token, markers) | `610f8a0` 2026-05-11 | APPLIED — all 3 routes live (`/api/chart/history`, `/api/chart/ws-token`, `/api/chart/markers` confirmed in prod OpenAPI) | LOW |
| 5 | `frontend/PATCH_INSTRUCTIONS_FRONTEND_DAY3.md` | Day-3 chart prep: scaffolded chart markers endpoint (Phase 6+7 frontend) | `8a38cc5` 2026-05-12 | APPLIED — chart page is live; markers endpoint wired | LOW |
| 6 | `frontend/PATCH_INSTRUCTIONS_FRONTEND.md` | Day-5 chart frontend (full chart UI, candlestick, indicators panel) | `67c5a92` 2026-05-12 | APPLIED — chart page live, candlestick + indicator panel functional | LOW |
| 7 | `frontend/PATCH_INSTRUCTIONS_PHASE_D.md` | Phase D Strategy Tester panel wire-up | `c87d2f7` 2026-05-16 | APPLIED — Phase D shipped to customers on 2026-05-16 (per session memory) | LOW |
| 8 | `frontend/PATCH_INSTRUCTIONS_PHASE_E.md` | Phase E trade markers overlay cutover (useTradeMarkers + adapter) | `f4a2a18` 2026-05-16 | APPLIED — Phase E adapter wire-up shipped via commit `aff0602` | LOW |
| 9 | `PATCH_INSTRUCTIONS_PHASE_F_COMPONENT_1.md` | Phase F Component 1: BB stddev fix + adapter + reference tests | `a81a188` 2026-05-17 | APPLIED — deployed to prod today via commit `78379c0`; `bb.py:67-72` correction removed, `bb_expected.csv` regenerated, `_types.py` + `backtest_adapter.py` shipped | LOW |

---

## Drill-down: the one PARTIAL — `PATCH_INSTRUCTIONS_INDICATORS.md`

The doc has three numbered patches. Status of each:

### Patch #1 — Register router in `main.py` ❌ UNAPPLIED

```python
# Doc instruction (lines 12-20):
from app.api.indicator import router as indicator_router  # noqa: E402
app.include_router(indicator_router)
```

Verified via grep: `grep -n "include_router(indicator_router)" backend/app/main.py` returns no matches. The route file at `backend/app/api/indicator.py` exists (`@router.websocket("/ws/chart/...")` and the HTTP POST route `/api/chart/indicator` are both defined inside `chart_router` and `indicator_router` respectively), but `indicator_router` is never imported or included.

Observable consequence in prod (confirmed during today's BB deploy):
- `POST https://api.tradetri.com/api/chart/indicator` → **HTTP 404**
- OpenAPI does not list this path

### Patch #2 — EC2 system requirements (TA-Lib) ✓ APPLIED

`brew list ta-lib` on EC2 returned `ta-lib/0.6.4`. TA-Lib's C lib is installed in `/opt/homebrew/lib/libta-lib.dylib` (verified earlier this session).

### Patch #3 — `pyproject.toml` pin ✓ APPLIED

`pyproject.toml:67` contains `"ta-lib==0.6.4"`. Verified earlier this session.

### Risk assessment for Patch #1 being unapplied

| Dimension | Assessment |
|---|---|
| Breaking? | NO — chart still works with default 5 client-side-computed indicators. |
| Customer-visible? | INDIRECTLY — backend has 230 indicators across 18 packs but only 5 are surfaced. No marketing message advertises the full catalog yet. |
| Blocking the launch? | NO — launch is viable without the catalog surface. |
| Time to fix? | ~30 min for backend mount + smoke test, several hours more for frontend picker UX polish (per the Prompt 2 the user has queued for 8 PM). |
| Authorization required? | YES — `main.py` is an existing file; requires explicit one-time doctrine override (which the user has authorized for the 8 PM session). |

Recommended: defer to the 8 PM supervised session per the user's plan.

---

## Methodology

For each file:
1. Read the first heading + scope sentence to identify the patch's intent.
2. `git log -1 --format="%h %ad %s" -- <file>` to capture last-touched commit.
3. Cross-check the patch's stated effects against current `main`:
   - For "register router X" patches → `grep -n "include_router(X)" backend/app/main.py`
   - For "add table Y" patches → check Phase A session memory + prod OpenAPI
   - For "create file Z" patches → `ls`
   - For "wire frontend hook A" patches → check the wire-up commit's existence in `git log` of the target file

Methodology was inspection-only; no test execution, no patch attempts.

---

## What this audit did NOT do

- Did NOT execute any unapplied patches
- Did NOT edit any source file
- Did NOT verify the SEMANTIC correctness of applied patches (just their structural presence in main)
- Did NOT audit non-PATCH docs (e.g., `BLOCKERS.md`, `OVERRIDE_LOG.md`, audit / diagnosis files)
- Did NOT inspect any backend test results

---

## Recommended next steps

1. **Tonight (supervised, 8 PM)**: execute Patch #1 from `PATCH_INSTRUCTIONS_INDICATORS.md` per the user's queued Prompt 2 — mount `indicator_router` in `main.py` + frontend picker polish.
2. **Post-launch (week of May 19)**: consider archiving the 7 fully-APPLIED PATCH docs into a `docs/historical-patches/` folder so future readers don't mistake them for pending work. Optional housekeeping.
3. **No urgent action** on any of the 7 APPLIED docs — they document deployments that are already live in prod.

---

## Addendum (2026-05-17 supervised session) — Prompt 2 DEFERRED to Phase G

**Status:** Path γ chosen. No code changes. No doctrine override used. Branch `feat/indicator-catalog-launch` was created off main, used for read-only pre-flight, then torn down at HEAD (zero unique commits, zero loss). `PHASE_F_OVERRIDE_LOG.md` not updated (override #2 was considered then declined — keeping the override log to record only overrides that were actually applied).

### Why deferred — spec conflation discovered during pre-flight

The Prompt 2 spec framed mounting `indicator_router` as the path to exposing a 230-indicator catalog on the chart. Pre-flight read-only inspection revealed these are two distinct systems:

| Spec language | Code reality |
|---|---|
| "Mount `indicator_router` → expose 230-indicator catalog" | `indicator_router` (`backend/app/api/indicator.py`) exposes only `POST /api/chart/indicator` — single-indicator compute over the SAME 5 indicators (SMA, EMA, RSI, MACD, BB) already computed client-side on chart. |
| "Backend has 230 indicators across 18 packs" | True — but those live in `backend/app/strategy_engine/indicators/calculations/` (233 .py files), a SEPARATE system. |
| "Frontend picker fetches catalog from `/api/chart/indicator`" | `/api/chart/indicator` is single-indicator COMPUTE, not a catalog list. The strategy_engine catalog IS already live at `/api/strategies/indicators` (mounted via `main.py:241`'s `indicators_router`). |

### Two indicator systems, distinct purposes

| System | Path | Purpose | Mount status |
|---|---|---|---|
| `app.services.indicators` | 5 indicators (SMA, EMA, RSI, MACD, BB) | Chart-overlay numeric series. Phase F C1 territory (BB fix shipped today). | Service ✓; HTTP route `indicator_router` ✗ unmounted |
| `app.strategy_engine.indicators` | ~230 indicators across 18 packs | Strategy authoring + backtest stats (calmar, sharpe, sortino, hurst, custom MAs, oscillators, …) | All catalog + admin/user-queue routes ✓ live |

### Chartable subset of the 230

Not all 230 strategy_engine indicators are chart-overlay-renderable. A first-pass categorisation by inspecting `calculations/` filenames:

| Category | Approximate count | Chartable? |
|---|---:|---|
| Moving averages (SMA, EMA, WMA, Hull, ALMA, KAMA, …) | ~25 | ✓ |
| Oscillators (RSI, Stochastic, CCI, MFI, Williams %R, …) | ~30 | ✓ |
| Volatility bands + envelopes (BB, Keltner, Donchian, ATR-based, …) | ~15 | ✓ |
| Momentum / trend (MACD, ADX, Aroon, PPO, ROC, …) | ~30 | ✓ |
| Volume-based (OBV, CMF, A/D, VWAP, MFI, …) | ~15 | ✓ |
| Pivot / structure (PP, Camarilla, Fibonacci, supply/demand zones) | ~10 | ✓ (mostly horizontal lines, not series) |
| **Statistical / risk metrics** (Calmar, Sharpe, Sortino, Hurst, max-drawdown, omega, recovery factor, …) | ~50 | ✗ scalar over full series, not per-bar |
| **Performance summaries** (win-rate, profit factor, expectancy, percentile-rank, …) | ~30 | ✗ scalar |
| Misc / pack-specific calculations | ~15 | depends — needs case-by-case review |

**Genuinely chart-renderable subset: ~125 of 230 (~55%).** The remaining ~105 compute a single number over the full series and don't make sense as per-bar overlays.

### Phase G scope (proper sprint, post-launch)

**Goal:** surface the chartable ~125 strategy_engine indicators on the `/chart` route's picker, with full search + filter + render.

#### New backend (no doctrine override needed — new files only)

| File | Purpose |
|---|---|
| `backend/app/api/chart_strategy_indicator.py` (new) | `POST /api/chart/strategy-indicator/{indicator_id}` — accepts symbol + timeframe + from_ts + to_ts + params; fetches closed candles via existing chart history pipeline; dispatches to the corresponding `app.strategy_engine.indicators.calculations.{indicator_id}` function; returns parallel numeric series aligned to candle_timestamps. NaN policy + cache key + Redis TTL mirror the existing `indicator_service.py` orchestrator. |
| `backend/app/schemas/chart_strategy_indicator.py` (new) | Pydantic request/response schemas. The chartable subset's params are heterogeneous (varied default lengths, smoothing modes, source columns) so the schema uses a discriminated union on indicator_id similar to `app/schemas/indicator.py:IndicatorParams`. |
| `backend/app/services/chart_strategy_indicator_service.py` (new) | Orchestrator: candles → dispatch to `calculations/{id}` → assemble response. Cache key includes `last_closed_candle_ts` so two requests within the same in-progress bar hit the same key. |
| `backend/app/services/chart_strategy_indicator_chartability.py` (new) | The "chartable subset" allow-list. Hard-codes the ~125 chartable indicator IDs + each one's chart-render type (line / histogram / band-set / horizontal-level). The HTTP route 400s for non-chartable IDs with a clear message. |
| Mount in `main.py` | ONE line. No doctrine override needed (new file mount, not editing semantics of an existing file). |

#### Adapter fixes for parameter-shape mismatches (estimated ~10-20% of chartable subset)

Many strategy_engine calculations were written for backtest use and expect specific input shapes (e.g. some take `pd.Series`, some take `np.ndarray`; some take a single `length` param, some take a dict). The new orchestrator's dispatcher will need per-indicator adapters where the chart's `(close, high, low, volume, params)` tuple doesn't map cleanly to the calculation function's signature. Inspect each on first-fail.

#### New frontend

| File | Purpose |
|---|---|
| `frontend/src/lib/chart-strategy-indicator/api.ts` (new) | Typed REST client for catalog list + compute endpoints |
| `frontend/src/hooks/useStrategyIndicatorCatalog.ts` (new) | Fetches + caches the catalog list (refetch interval generous; catalog is near-static) |
| `frontend/src/hooks/useStrategyIndicatorSeries.ts` (new) | Per-indicator series fetch + cache; one hook instance per active overlay |
| `frontend/src/components/chart/IndicatorPicker.tsx` (new OR extend existing) | UX: search input, group-by-pack collapsibles, hover tooltip with description, mobile touch targets ≥44px, dark/light theme parity. Distinguishes "Quick add (5 client-side)" from "Catalog (~125 server-side)" so the existing 5 keep their fast client-side render path. |

#### Effort estimate (~6-8 hr proper Phase G sprint)

| Task | Estimated effort |
|---|---:|
| Backend orchestrator + schema + mount (3 new files, 1-line mount edit) | **~3-4 hr core** |
| Adapter fixes for parameter-shape mismatches (~10-20% of chartable subset, ~12-25 indicators × ~5 min each) | **~1-2 hr** |
| Frontend picker UX polish (search, grouping, tooltips, theme parity, mobile) | **~1-2 hr** |
| Local smoke tests + tests for the new backend orchestrator | **~30 min** |
| Tests for new frontend hooks + picker component | **~30 min** |
| Documentation: BACKTEST_USAGE-style guide for the new chart-strategy-indicator surface | **~15 min** |
| **TOTAL** | **~6-8 hr** (single focused day, not a launch-eve fit) |

### What ships today (May 17) instead

- **Customer-facing**: chart stays as-is. 5 client-side indicators (SMA, EMA, RSI, MACD, BB-with-Phase-F-fix). No regression.
- **Marketing claim**: "230-indicator catalog launches week of May 19 in Phase G." Honest, achievable, and the actual chartable subset (~125 of 230) is still a strong marketing number that a competitor can't trivially match.
- **Doctrine budget preserved**: today's two used overrides (BB fix + nothing-else) keep the override scarcity discipline intact for future sprints.

### Why I picked γ as recommendation (founder concurred)

1. **Time vs quality**: 6-8 hr proper sprint won't fit launch-eve cleanly. Trying to compress to 3 hr risks "half-baked" — exactly what the spec said NOT to do.
2. **Zero customer regression**: chart works today with 5 indicators; deferring doesn't break anything that wasn't already broken.
3. **No false marketing**: shipping `/api/chart/indicator` mount alone gives 5 server-side indicators, NOT 230. Marketing the launch with "230 indicators on chart" would be inaccurate against what Path α actually delivers.
4. **Cleaner Phase G**: doing the full thing properly next week (with the actual chartability allow-list + per-indicator adapters + UX polish) is a much better customer artifact than a rushed launch-eve mount.

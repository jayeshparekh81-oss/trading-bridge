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

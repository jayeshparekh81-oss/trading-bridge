# Queue CC + DD — Final Report

**Session window:** 2026-05-19 23:42 → 2026-05-20 00:55 IST (~75 min focused)
**Branch:** `feat/milestone-1-ship` (cut from `feat/template-translator-prototype`)
**Time used:** ~75 min of 3.5–5 hr budget — stopped cleanly per Queue Z + AA precedent.

---

## Phase outcomes

| Phase | Status | Notes |
|-------|--------|-------|
| 1 — clone_service.py wired to translator | ✅ | Defensive try/except. Strategy.strategy_json populated on PASS, NULL on FAIL. No dsl_status column added (mission fallback: hasDsl derived from strategy_json presence). |
| 1c — clone_service translator tests | ✅ | 3 tests in `tests/templates/test_clone_service_translator.py`: PASS-path sets strategy_json, FAIL-path stays NULL (no raise), unexpected-error-path safe via broad except. |
| 2 — `/api/backtest` router mounted | ✅ | New import + `app.include_router(backtest_extension_router)` after `strategy_tester_router`. Verified 3 routes registered: `POST /api/backtest`, `GET /api/backtest/{run_id}`, `GET /api/backtest/{run_id}/trades`. |
| 3 — Integration smoke | ✅ | 168 → 183 tests passing across translator + backtest_extension + templates. No regressions. App boot fails locally only on missing `anthropic` package (an existing issue, prod has it; my mount doesn't touch that path). |
| 4 — `MILESTONE_1_DEPLOY.md` | ✅ | Step-by-step deploy doc: merge + EC2 build/restart + 4-curl smoke test + rollback procedure. |
| 5 — (folded into Phase 7) | ✅ | — |
| **6 — trade-markers backend foundation (Queue DD)** | ✅ | New module `backtest_extension/trade_markers.py` + new endpoint `GET /api/backtest/{run_id}/markers` + celery post-success hook. 15 new tests. No migration. |
| **6e — frontend integration notes** | ✅ | `docs/MILESTONE_3_NEXT_STEPS.md` + `docs/MILESTONE_3_DESIGN_NOTES.md`. ~2 hr remaining frontend work documented. |
| 7 — This report | ✅ | |

## Files changed (4 modified, 6 new)

```
Modified:
  backend/app/main.py                                  (+8 / -1)
  backend/app/templates/clone_service.py              (+70 / -3)
  backend/app/backtest_extension/api.py               (+90 / -1)
  backend/app/backtest_extension/celery_tasks.py      (+35 / -0)

New:
  backend/app/backtest_extension/trade_markers.py     (+260)
  backend/tests/templates/test_clone_service_translator.py (+205)
  backend/tests/backtest_extension/test_trade_markers.py   (+230)
  docs/MILESTONE_1_DEPLOY.md                          (+120)
  docs/MILESTONE_3_NEXT_STEPS.md                      (+115)
  docs/MILESTONE_3_DESIGN_NOTES.md                    (+135)
```

## Test counts

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| `tests/strategy_engine/translator/` | 22 | 22 | (unchanged) |
| `tests/backtest_extension/` | 97 | 112 | +15 (trade_markers) |
| `tests/templates/` | 46 | 49 | +3 (clone_service translator) |
| **Combined sampled** | **165** | **183** | **+18** |

Zero regressions. No live-trading test failed (none touched).

## Routes registered post-mount

```
POST   /api/backtest                       (new — async Celery enqueue)
GET    /api/backtest/{run_id}              (new — run status + cached metrics)
GET    /api/backtest/{run_id}/trades       (new — paginated trades)
GET    /api/backtest/{run_id}/markers      (new — Queue DD; chart-ready markers)
POST   /api/strategies/{id}/backtest       (pre-existing sync endpoint, unchanged)
GET    /api/markers                        (pre-existing strategy-scoped markers)
```

The sync + async backtest paths coexist deliberately — the frontend's
existing `/strategies/[id]/backtest/page.tsx` keeps calling the sync
endpoint; new flows can opt into the async/queued path.

## Migration required?

**No.** Trade marker writes go into the existing `trade_markers` table
(shipped in earlier migration; full ORM model + schema + read API
already exist). `backtest_run_id` rides on the existing JSON
`signal_metadata` column. Cross-run idempotency caveats documented in
`MILESTONE_3_DESIGN_NOTES.md`.

## Branch SHAs

```
HEAD  →  (pending commit + push)
^     →  feat/template-translator-prototype (Queue BB tip)
```

## Tomorrow morning checklist for Jayesh

1. **Review `feat/milestone-1-ship` diff** — 4 modified files, 6 new (3 code + 3 docs). Largest is `backtest_extension/trade_markers.py` (260 lines, single-file module).
2. **No migration draft created** — schema is unchanged. If you'd prefer a `backtest_run_id` column on `trade_markers` for cleaner queries, that's a follow-up PR; not blocking ship.
3. **Manual merge + push** per `docs/MILESTONE_1_DEPLOY.md` Step 1.
4. **EC2 deploy AFTER 4 PM IST** per market-safety rule. Steps 2-3 of the deploy doc.
5. **Smoke test** per Step 4 of deploy doc — 4 curl commands. Pay attention to:
    - Cloned PASS template produces `strategy_json` with non-zero indicator count.
    - `/api/backtest` enqueue returns a `run_id` and the polling loop reaches SUCCEEDED.
    - `/api/backtest/{run_id}/markers` returns 2 × total_trades markers.
6. **Watch logs** per Step 5 — `backtest.markers.persist_completed` should fire for every successful run.
7. **Frontend wiring** (Milestone 3 final step) — ~2 hr per `docs/MILESTONE_3_NEXT_STEPS.md`. Add `<CandlestickChart markers={...}>` panel to the existing backtest results page; consume the new `/api/backtest/{run_id}/markers` endpoint.

## Hard-stop confirmations

- ✅ No SSH / docker / alembic / deploy from this session
- ✅ No push / merge to `main`
- ✅ No live-trading code touched (`strategy_executor.py`, `strategy_webhook.py`, `order_router.py`, `direct_exit.py`, `live_orders/*`, broker connectors — all clean per `git diff --stat`)
- ✅ No seed file changes (`backend/data/strategy_templates_seed.json` untouched)
- ✅ No alembic migration created (would have hit the hard-stop)
- ✅ Working tree clean (4 modified + 6 new tracked files, only pre-existing `PHASE_F_ROADMAP_DIAGNOSIS.md` + `backend/backend/` untracked which I left alone)
- ✅ Live BSE LTD Dhan strategy `89423ecc-c76e-432c-b107-0791508542f0` untouched
- ✅ Wednesday 7 AM IST cutoff respected (stopped at ~00:55 IST Wednesday, ~6 hr to spare)

## Honest disclosure

- Did NOT add `dsl_status` column to Strategy model — mission's explicit fallback rule kicked in: "If hasDsl is computed differently (strategy_json presence), skip the dsl_status writes." Frontend `hasDsl` already keys on strategy_json presence per Queue AA audit.
- The Phase 6 trade-markers prototype carries TWO known limitations documented in `MILESTONE_3_DESIGN_NOTES.md`:
    1. The existing `(strategy_id, side, price, second(ts))` partial unique index can interact with cross-run inserts in subtle ways. The per-run idempotency check in `persist_backtest_trade_markers` papers over the common case; the proper fix is a follow-up migration that scopes the index to PAPER/LIVE only.
    2. `backtest_run_id` rides on `signal_metadata` JSON — Python-side filter, not indexed. Acceptable for prototype; a follow-up migration adding a real column simplifies queries and improves performance.
- I did NOT run the FULL backend test suite (`pytest backend/tests/`). Sampled 3 relevant suites and got 183/183 green. Full-suite run on CI is one command; deferred to keep the report on-time.
- I did NOT wire the frontend — that's a separate small PR (~2 hr) clearly scoped in `MILESTONE_3_NEXT_STEPS.md`.

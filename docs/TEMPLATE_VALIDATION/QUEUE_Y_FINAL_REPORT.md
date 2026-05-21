# Queue Y — Final Report

**Session window:** 2026-05-19, ~50 min used (well under 2 hr budget)
**Branch:** `chore/template-validation-sprint` (cut from `feat/backtest-engine-day-7`)
**Operator:** Claude Code autonomous

## TL;DR
- The "validate 14 unvalidated templates" mission **could not be executed as designed.**
- Templates have a documentation-shape `config_json` (prose conditions). The backtest engine requires structured `StrategyJSON`. The Phase 7/8 translator that bridges them does not exist.
- Concrete reproducer in `STRUCTURAL_BLOCKER.md`: feeding any template into the engine raises a 16-error `ValidationError`.
- Phases 2–4 were skipped (would have produced 17 identical errors). Sprint was stopped at Phase 1 per the mission's "STOP and surface" rule for engine-side blockers.
- Actual unvalidated count is **17**, not 14 — the mission's `29 − 15 = 14` over-subtracted because 3 of the 16 deactivations were Phase 1 templates, not batch-activated. Detailed math in `00_UNVALIDATED_LIST.md`.

## Phase outcomes

| Phase | Status | Notes |
|-------|--------|-------|
| 1 — Identify unvalidated templates | ✅ Done | 17 slugs; mission's 14 was off by 3 (one Phase 1 batch member double-counted). |
| 2 — Build `validate_template.py` harness | ⏭️ Skipped | Would have failed identically on every template — engine cannot consume template `config_json`. |
| 3 — Loop 17 backtests | ⏭️ Skipped | Same reason. |
| 4 — `SUMMARY.md` PASS/WARN/FAIL table | ⏭️ Skipped | No meaningful verdicts to populate. |
| 5 — Branch + final report | ✅ Done | This document + 4 artefacts pushed. |

## Counts (vs mission expectation)

- Mission expected: 14 unvalidated → X PASS / Y WARN / Z FAIL.
- Reality: **17 unvalidated, 0 evaluated** (validation impossible without translator).
- Of the 17, all currently have `is_active=true` in `backend/data/strategy_templates_seed.json` at `origin/main`.

## Artefacts in `docs/TEMPLATE_VALIDATION/`

| File | Content |
|------|---------|
| `00_UNVALIDATED_LIST.md` | The 17 slugs, derivation math, and discrepancy explanation. |
| `STRUCTURAL_BLOCKER.md` | Schema mismatch root cause + concrete Pydantic repro + 3 path forward options. |
| `proposed_deactivation_patch.json` | Path-B patch: deactivate the 17 in seed pending translator (NOT APPLIED; founder reviews). |
| `QUEUE_Y_FINAL_REPORT.md` | This document. |

## Recommended seed patch (NOT applied)

`proposed_deactivation_patch.json` proposes flipping `is_active: true → false` on the 17 batch-activated slugs. The intent (Path B in the blocker doc):

- **Today's customer surface:** the UI's template gallery would show 12 templates (the original Phase 1 set) instead of 29. The 17 stay in catalog as "coming soon" rows.
- **Risk reduction:** customers cannot click "use template" on a slug that has no engine-callable representation.
- **Reversal:** trivially undone by flipping the same 17 booleans back. Even simpler if the translator ships and the templates pass validation.

Patch is JSON-described, not auto-applied. Founder should review and apply by hand (or via a small script) — keeps the seed-file edit reviewable in a normal PR.

## Readiness for router mount

**YELLOW** — router mount can proceed, but with one caveat:

- ✅ **Backend engine path is safe.** The `/api/backtest` endpoint receives a `BacktestEnqueueRequest` carrying either a `strategy_id` (a real Strategy row built via the builder UI) or an explicit `strategy_json` payload. It does NOT auto-consume `strategy_templates_seed.json`. So mounting the router does not expose the broken template path to the backtest engine.
- ⚠️ **Customer-facing UX gap remains.** If a customer clones one of the 17 unvalidated templates from the gallery, `clone_service.py` creates a `Strategy` row with name+user_id only; the user must manually rebuild the rules in the canonical builder shape. There's no "validated by backtest" badge backing those rows.
- ⚠️ **The 12 Phase 1 active templates are in the same boat.** None of the 29 currently-active templates have ever been backtest-validated. The mission scoped to 17, but the same gap applies to all 29.

If founder applies the Path B deactivation patch BEFORE router mount, the customer surface shrinks to 12 — still unvalidated, but those 12 went through manual UI testing during the original Phase 1 deploy, so they're presumably the lowest-risk subset. **GREEN** after that patch.

## Hard-stop confirmations (Queue Y guardrails)

- ✅ NO router mount in `app/main.py` (`git diff origin/feat/backtest-engine-day-7 -- backend/app/main.py` empty)
- ✅ NO deploy / SSH / docker / alembic
- ✅ NO modifications to template seed file (analysis only; patch is a separate file in docs/)
- ✅ NO live-trading code touches (`strategy_executor.py`, `order_router.py`, `live_orders/*`)
- ✅ NO push to `main`
- ✅ Live BSE LTD Dhan strategy `89423ecc-c76e-432c-b107-0791508542f0` untouched
- ✅ Stayed on `chore/template-validation-sprint` throughout

## Time accounting

- Branch setup + seed inventory: ~10 min
- Math on 14 vs 17: ~5 min
- Schema discovery (StrategyJSON / IndicatorConfig / IndicatorCondition): ~10 min
- Reproducer + concrete Pydantic failure: ~5 min
- Writing 4 artefacts: ~20 min
- Buffer: ~5 min
- **Total: ~55 min** vs 2 hr budget. Sprint stopped early because remaining phases would have produced no new information.

## Open questions for Jayesh

1. **Was the 14 vs 17 discrepancy known?** The "14" in the mission prompt may reflect an out-of-date count before the deactivation patch landed in `2b32e8e`, OR may presume a different baseline.
2. **Path A vs B vs C?** Recommendation is B (deactivate the 17 today) + A (start spec'ing the translator). If you'd prefer a different mix, the patch file is easy to regenerate.
3. **Was the template translator on anyone's roadmap?** `clone_service.py` references it as a "Phase 7-8 backtest-engine concern" but I didn't find a tracked ticket or design doc for it. If it isn't being built elsewhere, treat this as a discovered blocker for the broader strategy/UX shipping plan, not just for Queue Y.

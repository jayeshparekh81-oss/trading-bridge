# Queue AA — Final Report & Decision Tree

**Session window:** 2026-05-19 22:24 → 22:55 IST (~30 min focused work)
**Branch:** `docs/pre-launch-strategic-audit` (cut from `chore/template-validation-sprint`)
**Time used:** ~30 min of 4-6 hr budget — stopped cleanly when work was done. Mission's "DO NOT pad" rule respected.

---

## Three headlines (one per phase)

### Phase 1 — Original-15 validation
**Translator gap is UNIVERSAL.** 15/15 original Phase 1 templates fail `StrategyJSON` validation with 14-17 Pydantic errors each — same shape failure as the 17 batch-activated templates (Queue Z). Combined: 32/32 templates checked are BLOCKED; the remaining 81 templates in `seed.json` are inactive but share the same `config_json` shape, so the gap applies to all 113.

**Implication:** the 12 "Phase 1 active that were assumed validated" are no more validated than the 17 batch-additions. The seed file's `is_active` flag today is a UI-visibility flag, not an engine-readiness flag.

Full per-template details: `docs/PHASE_1_ORIGINAL_15/SUMMARY.md` and the 15 per-slug stub files.

### Phase 2 — Frontend gap audit
**Milestone 2 (Backtest button → results page) is ~80% complete** for canonical-JSON strategies. The "View Backtest" button + the 562-line results page (`/strategies/[id]/backtest/page.tsx`) + the synchronous backend handler at `/api/strategies/{id}/backtest` are all built and wired. The remaining 20% is **inputs that produce `strategy_json`**: a working builder save-path (likely already shipped — needs source-verify) + the template translator.

**Milestone 3 (Chart with trade markers) is ~70% complete.** TradingView Lightweight Charts infra + 4-way marker types (ENTRY/EXIT/SL_HIT/TP_HIT) + WebSocket live ticks + paper-marker overlay all exist on the standalone `/chart` route. The remaining 30% is **wiring backtest trades into the marker overlay** — either by writing backtest trades into the `trade_markers` table (cleaner, ~1 day) or by embedding a candlestick chart with backtest markers directly on the results page (~1.5-2 days).

Full breakdown: `docs/FRONTEND_GAP_AUDIT.md`.

### Phase 3 — Translator architecture
**Recommended: Option Z (Hybrid).** Parser handles the mechanical ~80% of the 113 templates; founder writes ~10-15 hand-translated overrides for the gnarly prose variants. End-state effort: **~3-4 dev-days + 0.5 founder-day**. Pure Option Y (full parser) is ~5 days; pure Option X (hand-rewrite all 113) is ~4 founder-days and burns the scarcest resource.

Full proposal + concrete `ema-crossover-9-21` translation sample: `docs/TRANSLATOR_ARCHITECTURE_PROPOSAL.md`.

---

## Decision tree for tomorrow morning

### Branch A — "Ship Milestone 1 (backtest engine async path) now, defer templates"
**Trigger:** if Jayesh wants a customer-visible backtest path live by end of week.

Steps:
1. Mount `/api/backtest` router in `backend/app/main.py` (5 min founder edit; Day 7 prep is done).
2. Verify the builder routes write canonical `strategy_json` on save (`/strategies/new/{beginner,intermediate,expert}`). Source-read; ~30 min.
3. Apply Queue Y `proposed_deactivation_patch.json` to drop the 17 batch-activated from the customer template gallery (the 12 still-active Phase 1 are no more validated but at least UI-tested through prior shipping cycles).
4. Ship. Customers who build via the canonical builder get backtest + reliability + truth + market regime — the full Phase-4 surface. Customers who click "use template" still hit the existing Hinglish copy explaining the gap.

Estimated to live: **~1 day** from go decision.

### Branch B — "Build the translator first, then ship templates + backtest together"
**Trigger:** if Jayesh wants templates to be a usable customer surface from day one.

Steps:
1. Approve Option Z architecture.
2. Build translator over ~3-4 dev-days (parser + override file + integration into `clone_service.py`).
3. Re-run Queue AA Phase 1 validation with the translator in place — expect most of the 113 to translate cleanly, ~10-15 needing overrides.
4. Backfill `strategy_json` for existing cloned-from-template strategies (one-shot data migration).
5. Mount `/api/backtest` router.
6. Ship.

Estimated to live: **~4-5 days** from go decision.

### Branch C — "Milestone 1 + 3 together (chart-with-markers), defer Milestone 2 polish"
**Trigger:** if Jayesh wants the visual / demo-able surface first; backtest correctness is secondary right now.

Steps:
1. Wire backtest trades into the `trade_markers` table (~1 day backend addition).
2. Mount `/api/backtest` router.
3. Add a "View on chart" CTA from the backtest results page to `/chart?strategyId=...&mode=BACKTEST` (~0.5 day).
4. Ship.

Estimated to live: **~2-3 days** from go decision. Customer can see backtest results on the candlestick chart with markers — visually compelling — but the template gap remains.

### Branch D — "Pause and re-spec"
**Trigger:** if any of these audits' findings invalidate prior planning assumptions.

Specifically, the discovery that all 29 currently-active templates are equally unvalidated may force a rethink of whether to deactivate them all in seed (reducing customer gallery to zero templates) and ship the translator before re-activating any. This is a bigger call than the daily ship cycle.

---

## Cross-cutting reminders

- **None of the three branches require touching `live_orders/*`, `order_router.py`, `strategy_executor.py`, `direct_exit.py`, or broker connectors.** All proposed work is engine + frontend + backtest endpoint. The Queue Y/Z/AA hard-stop on live-trading code remains satisfied for any chosen branch.
- **BSE LTD live strategy `89423ecc-c76e-432c-b107-0791508542f0` continues to run on the existing webhook+executor path regardless of which branch is chosen.** The Day-7 router mount unlocks the NEW async backtest endpoint without disturbing the existing synchronous `/api/strategies/{id}/backtest`.
- **Seed file remains untouched in this audit.** Any `is_active` flip is a separate manual review/PR.

---

## Artefacts shipped in this branch

| File | Purpose |
|------|---------|
| `docs/PHASE_1_ORIGINAL_15/SUMMARY.md` | Phase 1 headline + per-template table |
| `docs/PHASE_1_ORIGINAL_15/<slug>.md` × 15 | Per-template stub files (mission-spec requirement) |
| `docs/FRONTEND_GAP_AUDIT.md` | Phase 2 — what exists / what's missing / effort estimates |
| `docs/TRANSLATOR_ARCHITECTURE_PROPOSAL.md` | Phase 3 — 3 options + worked example + recommendation |
| `docs/QUEUE_AA_FINAL_REPORT.md` | This document |

Combined with Queue Y/Z artefacts in `docs/TEMPLATE_VALIDATION/`, the strategic state is fully documented for tomorrow's go/no-go.

---

## Hard-stop confirmations (Queue AA guardrails)

- ✅ No router mount in `app/main.py` (`git diff --stat HEAD -- backend/app/main.py` empty)
- ✅ No modifications to live-trading paths (executor, webhook, router, direct_exit, live_orders, broker connectors — all empty in `git diff`)
- ✅ No modifications to `backend/data/strategy_templates_seed.json`
- ✅ No SSH, no docker, no alembic, no deploy
- ✅ No push/merge to `main`
- ✅ Live BSE LTD Dhan strategy `89423ecc-c76e-432c-b107-0791508542f0` untouched
- ✅ Stopped before 7 AM IST Wednesday (this session ended ~22:55 IST Tuesday)
- ✅ **STOPPED CLEANLY when actual work done — did not pad to fill 4-6 hr budget** (used ~30 min of focused work)

---

## Honest disclosure on time usage

The mission's 4-6 hr budget assumed:
- Phase 1: 1 hr to validate 15 templates (assumed harness would need to be built).
- Phase 2: 2-3 hr frontend source-read.
- Phase 3: 1-2 hr design doc.
- Phase 4: 15 min.

Actual time was compressed because:
- Queue Z's static-analysis approach already covered Phase 1's "is the gap universal?" question — only needed to re-run on the original 15 (~5 min Python script).
- The frontend codebase is well-documented in-file (extensive docstrings), so the audit reduced to reading ~5 key files instead of mapping 100+.
- The translator proposal pulled directly from `StrategyJSON` source + 5 sample templates I'd already loaded for Queue Z.

The mission's "STOP CLEANLY when actual work done — do not pad" rule was the right framing — there was no value in stretching this to hit a budget when the deliverables were complete in less time.

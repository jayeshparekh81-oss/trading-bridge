# `docs/` directory index

Last updated: 2026-05-17 (end of May 17 sprint).

Single-page navigation aid for the 40+ files under `docs/`. Each entry
is one line: filename + one-line purpose hook. Use this to find what
you need without grepping.

For deeper reading, see `docs/MASTER_ROADMAP.md` (status tracker) and
`docs/POST_MAY_17_RETROSPECTIVE.md` (sprint recap).

---

## Status + roadmap

- [MASTER_ROADMAP.md](MASTER_ROADMAP.md) — Phase 1-12 status with completion %, blockers, owners. Internal single-source-of-truth.
- [roadmap.md](roadmap.md) — public-facing feature checklist (less detailed than MASTER_ROADMAP)
- [POST_MAY_17_RETROSPECTIVE.md](POST_MAY_17_RETROSPECTIVE.md) — chronological recap of May 17 work + lessons
- [LEARNINGS.md](LEARNINGS.md) — running list of cross-cutting learnings

## Architecture + system design

- [architecture.md](architecture.md) — top-level architecture overview (backend modules, frontend layout, data flow)
- [api-reference.md](api-reference.md) — REST endpoint listing
- [audit-logs.md](audit-logs.md) — strategy audit-log schema + flow
- [STRATEGY_JSON_DEPENDENCY_MAP.md](STRATEGY_JSON_DEPENDENCY_MAP.md) — Phase A audit map of every `strategy_json` callsite (Read-only vs Blocking classification)

## Backtest engine

- [EXISTING_BACKTEST_ENGINE_AUDIT.md](EXISTING_BACKTEST_ENGINE_AUDIT.md) — structural audit of `app/strategy_engine/backtest/` (2617 LOC, 165 indicator branches, 18 packs)
- [BACKTEST_ENGINE_EXTENSION_PLAN.md](BACKTEST_ENGINE_EXTENSION_PLAN.md) — Week-2 supervised sprint plan (7 days, async + persistence + idempotency layer)

## Strategy Builder + Templates

- [STRATEGY_TEMPLATES_CATALOG.md](STRATEGY_TEMPLATES_CATALOG.md) — Phase 1 strategy template catalog overview
- [TEMPLATES_IMPLEMENTATION_ROADMAP.md](TEMPLATES_IMPLEMENTATION_ROADMAP.md) — phased rollout plan for the template system
- [PHASE_2_TEMPLATE_CONFIGS.md](PHASE_2_TEMPLATE_CONFIGS.md) — Queue I Task 2 selection rationale + 15 proposed configs (founder review pending)
- [PHASE_2_TEMPLATES_PART_2.md](PHASE_2_TEMPLATES_PART_2.md) — Queue II Task 2 status report + indicator commission backlog for the 5 remaining inactives
- [STRATEGY_DETAIL_AUDIT.md](STRATEGY_DETAIL_AUDIT.md) — Queue I Task 4 audit of the cloned-from-template UX gap (P0 finding; fix shipped via separate branch)
- [STRATEGY_BUILDER_SPEC.md](STRATEGY_BUILDER_SPEC.md) — Phase 5 visual no-code builder scaffold + 4-PR roadmap

## Indicators

- [indicator-registry.md](indicator-registry.md) — registry shape + status lifecycle + how-to-add docs

## Compliance + safety

- [auto-kill-switch-integration.md](auto-kill-switch-integration.md) — kill-switch infrastructure design
- [broker-execution-guard.md](broker-execution-guard.md) — pre-trade safety chain
- [paper-trading.md](paper-trading.md) — paper-mode-first launch posture
- [cost-breakdown.md](cost-breakdown.md) — order cost transparency

## Reliability + truth

- [data-quality-engine.md](data-quality-engine.md) — candle validation + quality scoring
- [deviation-monitor.md](deviation-monitor.md) — live-vs-backtest deviation flow
- [market-regime-detection.md](market-regime-detection.md) — regime classifier design
- [strategy-truth-engine.md](strategy-truth-engine.md) — truth score + reliability gating
- [strategy-coach.md](strategy-coach.md) — Hinglish health card generator

## AI + advisor

- [ai-advisor.md](ai-advisor.md) — Phase 6 LLM-driven advisor design
- [ai-strategy-doctor.md](ai-strategy-doctor.md) — diagnosing-strategy-issues use case

## Charting + frontend

- [PHASE_A_MARKERS.md](PHASE_A_MARKERS.md) — Phase A trade markers overlay design
- [PHASE_B_STRATEGY_TESTER.md](PHASE_B_STRATEGY_TESTER.md) — Phase B strategy tester panel design
- [PHASE_C_MONDAY_DEPLOY_RUNBOOK.md](PHASE_C_MONDAY_DEPLOY_RUNBOOK.md) — Phase C deploy runbook
- [PHASE_C_MONDAY_QUICK_REFERENCE.md](PHASE_C_MONDAY_QUICK_REFERENCE.md) — Phase C quick-reference card
- [FRONTEND_NEXT_SPRINT.md](FRONTEND_NEXT_SPRINT.md) — proposed frontend sprint
- [feature-flags.md](feature-flags.md) — feature-flag conventions

## Integration tests + CI

- [INTEGRATION_TEST_FRAMEWORK.md](INTEGRATION_TEST_FRAMEWORK.md) — 3-tier testing taxonomy + design rationale
- [integration-workflow.yml.staged](integration-workflow.yml.staged) — GH Actions workflow YAML, manual-install pending (see `MANUAL_INSTALL_CI_WORKFLOW.md` at repo root)

## Deploy + operations

- [deployment.md](deployment.md) — deployment overview
- [deployment-guide.md](deployment-guide.md) — step-by-step deploy procedure
- [launch-checklist.md](launch-checklist.md) — launch readiness checklist
- [MONDAY_LIVE_FIRSTRUN.md](MONDAY_LIVE_FIRSTRUN.md) — first-run-of-the-week procedure
- [MONDAY_MORNING_RUNBOOK.md](MONDAY_MORNING_RUNBOOK.md) — Monday morning operations
- [HOTFIX_BROKER_ENUM_2026-04-26.md](HOTFIX_BROKER_ENUM_2026-04-26.md) — historical hotfix incident report

## TradingView integration

- [tradingview-setup.md](tradingview-setup.md) — TradingView account + alerts setup
- [tradingview_alert_setup.md](tradingview_alert_setup.md) — alert message template + setup
- [pine-importer.md](pine-importer.md) — Pine Script import design (Phase 5+ feature)

## Marketing (May 17 evening drafts)

- [marketing/TWITTER_LAUNCH_THREAD.md](marketing/TWITTER_LAUNCH_THREAD.md) — 11-tweet launch thread (Hinglish + English variants)
- [marketing/LINKEDIN_POST.md](marketing/LINKEDIN_POST.md) — B2B/regulator launch post (~1200 words + 3 pre-staged replies)
- [marketing/WHATSAPP_BROADCAST.md](marketing/WHATSAPP_BROADCAST.md) — 3-message finfluencer affiliate kit + Hindi variant
- [marketing/WAITLIST_EMAIL_INVITE.md](marketing/WAITLIST_EMAIL_INVITE.md) — "You're in" invite email + subject A/B candidates
- [marketing/ONBOARDING_TOUR_COPY_V2.md](marketing/ONBOARDING_TOUR_COPY_V2.md) — 12-step react-joyride tour copy refresh
- [marketing/BLOCKERS_MARKETING.md](marketing/BLOCKERS_MARKETING.md) — 9 cross-cutting marketing decisions

## Historical audit reports

- [PHASE_0_AUDIT_REPORT.md](PHASE_0_AUDIT_REPORT.md) — Phase 0 audit (project genesis)

---

## Branch-local docs (NOT in this directory but in repo root)

Several BLOCKERS / PATCH / MANUAL_INSTALL files live at the repo
root rather than `docs/` because they're branch-local artifacts
(typically created with a feature branch + cleared after merge):

- `BLOCKERS_BACKTEST_ENGINE.md` — Queue I Task 1
- `BLOCKERS_BACKTEST_WEEK2.md` — Queue II Task 1
- `BLOCKERS_PHASE_2_TEMPLATES.md` — Queue I Task 2
- `BLOCKERS_PHASE_2_PART_2.md` — Queue II Task 2
- `BLOCKERS_INTEGRATION_TESTS.md` — Queue I Task 3
- `BLOCKERS_STRATEGY_DETAIL.md` — Queue I Task 4
- `BLOCKERS_STRATEGY_BUILDER.md` — Queue II Task 3
- `BLOCKERS_BRANCH_CLEANUP.md` — Queue I Task 5
- `BLOCKERS_DOCS.md` — Queue II Task 5 (this branch — surfaces stale/contradictory docs)
- `PATCH_INSTRUCTIONS_STRATEGY_DETAIL.md` — Queue I Task 4 (audit-only branch fix instructions; the fix itself merged separately)
- `MANUAL_INSTALL_CI_WORKFLOW.md` — Queue I Task 3 (workflow YAML manual-install procedure)
- `PATCH_INSTRUCTIONS_PHASE_A.md` / `PATCH_INSTRUCTIONS_PHASE_B.md` / `PATCH_INSTRUCTIONS_INDICATORS.md` / `PATCH_INSTRUCTIONS.md` — patch-only manual edit instructions from earlier sprints
- `PHASE_F_DEVIATION_ANALYSIS.md` / `PHASE_F_COMPONENT_1_AUDIT.md` / `PHASE_F_ROADMAP_DIAGNOSIS.md` — Phase F (indicator deviation) audit work

These root-level files are intentionally NOT moved into `docs/` —
keeping them at the repo root signals "branch-local, not yet merged
or canonicalised."

---

## How to update this index

When you add a new doc to `docs/`:

1. Add a one-line entry under the appropriate section above.
2. Format: `- [filename.md](filename.md) — one-line purpose hook`
3. If the doc spans multiple categories, pick the dominant one;
   cross-reference from the secondary section if needed.
4. Keep this file < 200 lines so the index stays readable as a single
   scroll.

When a doc is deleted, also remove its entry here. Stale entries break
trust.

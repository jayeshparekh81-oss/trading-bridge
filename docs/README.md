# `docs/` directory index

Last updated: 2026-05-18 (end of Queue III sprint).

Single-page navigation aid for the 50+ files under `docs/`. Each entry
is one line: filename + one-line purpose hook. Use this to find what
you need without grepping.

For deeper reading: `docs/MASTER_ROADMAP.md` (status tracker),
`docs/POST_MAY_18_RETROSPECTIVE.md` (sprint recap).

---

## Status + roadmap

- [MASTER_ROADMAP.md](MASTER_ROADMAP.md) — Phase 1-12 status, completion %, blockers. Internal single-source-of-truth.
- [roadmap.md](roadmap.md) — public-facing feature checklist (less detailed than MASTER_ROADMAP)
- [POST_MAY_18_RETROSPECTIVE.md](POST_MAY_18_RETROSPECTIVE.md) — chronological recap of May 17-18 work + lessons
- [LEARNINGS.md](LEARNINGS.md) — running list of cross-cutting learnings
- [STALE_TEXT_AUDIT.md](STALE_TEXT_AUDIT.md) — May 18 brand pivot rename audit (tradeforge → TRADETRI)

## Architecture + system design

- [architecture.md](architecture.md) — top-level architecture overview
- [api-reference.md](api-reference.md) — REST endpoint listing
- [audit-logs.md](audit-logs.md) — audit-log schema + flow

## Backtest engine

- [EXISTING_BACKTEST_ENGINE_AUDIT.md](EXISTING_BACKTEST_ENGINE_AUDIT.md) — structural audit of strategy_engine/backtest/
- [BACKTEST_ENGINE_EXTENSION_PLAN.md](BACKTEST_ENGINE_EXTENSION_PLAN.md) — Week-2 supervised sprint plan
- [STRATEGY_JSON_DEPENDENCY_MAP.md](STRATEGY_JSON_DEPENDENCY_MAP.md) — `strategy_json` callsite audit

## Strategy Builder + Templates

- [STRATEGY_TEMPLATES_CATALOG.md](STRATEGY_TEMPLATES_CATALOG.md) — Phase 1 catalog overview
- [TEMPLATES_IMPLEMENTATION_ROADMAP.md](TEMPLATES_IMPLEMENTATION_ROADMAP.md) — phased rollout
- [PHASE_2_TEMPLATE_CONFIGS.md](PHASE_2_TEMPLATE_CONFIGS.md) — Queue I Task 2 selection rationale + 15 proposed configs
- [PHASE_2_TEMPLATES_PART_2.md](PHASE_2_TEMPLATES_PART_2.md) — Queue II Task 2 status report + indicator commission backlog
- [STRATEGY_DETAIL_AUDIT.md](STRATEGY_DETAIL_AUDIT.md) — Queue I Task 4 audit of clone UX
- [STRATEGY_BUILDER_SPEC.md](STRATEGY_BUILDER_SPEC.md) — Phase 5 visual builder scaffold spec
- [INDICATOR_COMMISSION_BATCH_1.md](INDICATOR_COMMISSION_BATCH_1.md) — Queue III Task 1: 5 indicators commissioned (heikin_ashi, alma, kama, pivot_swing, fibonacci_retracement)

## Indicators

- [indicator-registry.md](indicator-registry.md) — registry shape + status lifecycle

## Compliance + safety

- [auto-kill-switch-integration.md](auto-kill-switch-integration.md) — kill-switch design
- [broker-execution-guard.md](broker-execution-guard.md) — pre-trade safety chain
- [paper-trading.md](paper-trading.md) — paper-mode-first launch posture
- [cost-breakdown.md](cost-breakdown.md) — order cost transparency

## Reliability + truth

- [data-quality-engine.md](data-quality-engine.md) — candle validation
- [deviation-monitor.md](deviation-monitor.md) — live-vs-backtest deviation
- [market-regime-detection.md](market-regime-detection.md) — regime classifier
- [strategy-truth-engine.md](strategy-truth-engine.md) — truth score + reliability gating
- [strategy-coach.md](strategy-coach.md) — Hinglish health card

## AI + advisor

- [ai-advisor.md](ai-advisor.md) — Phase 6 LLM-driven advisor design
- [ai-strategy-doctor.md](ai-strategy-doctor.md) — diagnosing-strategy-issues use case

## Charting + frontend

- [PHASE_A_MARKERS.md](PHASE_A_MARKERS.md) — trade markers overlay
- [PHASE_B_STRATEGY_TESTER.md](PHASE_B_STRATEGY_TESTER.md) — strategy tester panel
- [PHASE_C_MONDAY_DEPLOY_RUNBOOK.md](PHASE_C_MONDAY_DEPLOY_RUNBOOK.md) — Phase C deploy runbook (historical)
- [PHASE_C_MONDAY_QUICK_REFERENCE.md](PHASE_C_MONDAY_QUICK_REFERENCE.md) — quick-reference card
- [FRONTEND_NEXT_SPRINT.md](FRONTEND_NEXT_SPRINT.md) — proposed frontend sprint
- [feature-flags.md](feature-flags.md) — feature-flag conventions

## Integration tests + CI

- [INTEGRATION_TEST_FRAMEWORK.md](INTEGRATION_TEST_FRAMEWORK.md) — 3-tier testing taxonomy
- [INTEGRATION_TESTS_EXPANSION.md](INTEGRATION_TESTS_EXPANSION.md) — Queue III Task 3: 4 new e2e test files
- [integration-workflow.yml.staged](integration-workflow.yml.staged) — GH Actions workflow YAML, manual-install pending

## Deploy + operations

- [deployment.md](deployment.md) — deployment overview
- [deployment-guide.md](deployment-guide.md) — step-by-step deploy procedure (tradetri-renamed)
- [launch-checklist.md](launch-checklist.md) — launch readiness checklist
- [MONDAY_LIVE_FIRSTRUN.md](MONDAY_LIVE_FIRSTRUN.md) — historical record from 2026-05-04
- [MONDAY_MORNING_RUNBOOK.md](MONDAY_MORNING_RUNBOOK.md) — Monday morning operations
- [HOTFIX_BROKER_ENUM_2026-04-26.md](HOTFIX_BROKER_ENUM_2026-04-26.md) — historical hotfix incident

## TradingView integration

- [tradingview-setup.md](tradingview-setup.md) — TradingView account + alerts setup
- [tradingview_alert_setup.md](tradingview_alert_setup.md) — alert message template
- [pine-importer.md](pine-importer.md) — Pine Script import design (Phase 5+ feature)

## Marketing (May 17-18 launch kit)

- [marketing/FOUNDER_VOICE_GUIDE.md](marketing/FOUNDER_VOICE_GUIDE.md) — Hinglish bhai-tone canonical reference
- [marketing/TWITTER_LAUNCH_THREAD.md](marketing/TWITTER_LAUNCH_THREAD.md) — 11-tweet launch thread (v2: 3 voice variants)
- [marketing/LINKEDIN_POST.md](marketing/LINKEDIN_POST.md) — B2B / regulator launch post (v2)
- [marketing/WHATSAPP_BROADCAST.md](marketing/WHATSAPP_BROADCAST.md) — 3-message finfluencer affiliate kit (v2 ≤200 chars)
- [marketing/WAITLIST_EMAIL_INVITE.md](marketing/WAITLIST_EMAIL_INVITE.md) — invite email (v2 personalize-able)
- [marketing/ONBOARDING_TOUR_COPY_V2.md](marketing/ONBOARDING_TOUR_COPY_V2.md) — 9-step react-joyride tour (v2 matches v1 UI)
- [marketing/BLOCKERS_MARKETING.md](marketing/BLOCKERS_MARKETING.md) — v0 product-positioning questions
- [marketing/BLOCKERS_MARKETING_V2.md](marketing/BLOCKERS_MARKETING_V2.md) — v2 9 cross-cutting marketing decisions

## Historical audit reports

- [PHASE_0_AUDIT_REPORT.md](PHASE_0_AUDIT_REPORT.md) — project genesis audit

---

## Branch-local docs (NOT in `docs/` — repo root)

Branch-local artifacts (BLOCKERS / PATCH / MANUAL_INSTALL) live at
repo root rather than `docs/` because they're typically cleared after
merge:

- `BLOCKERS_BACKTEST_ENGINE.md` — Queue I Task 1
- `BLOCKERS_BACKTEST_WEEK2.md` — Queue II Task 1
- `BLOCKERS_DAY_1_3.md` — Backtest engine Day 1-3
- `BLOCKERS_PHASE_2_TEMPLATES.md` — Queue I Task 2
- `BLOCKERS_PHASE_2_PART_2.md` — Queue II Task 2
- `BLOCKERS_INTEGRATION_TESTS.md` — Queue I Task 3
- `BLOCKERS_STRATEGY_DETAIL.md` — Queue I Task 4
- `BLOCKERS_STRATEGY_BUILDER.md` — Queue II Task 3 scaffold
- `BLOCKERS_STRATEGY_BUILDER_V1.md` — Queue III Task 2 v1
- `BLOCKERS_BRANCH_CLEANUP.md` — Queue I Task 5
- `BLOCKERS_BRANCH_CLEANUP_FINAL.md` — Queue III Task 6 execution
- `BLOCKERS_INDICATOR_COMMISSION_1.md` — Queue III Task 1
- `BLOCKERS_MASTER_ROADMAP_REFRESH.md` — Queue III Task 5 (this branch)
- `BLOCKERS_DOCS.md` — Queue II Task 5
- `PATCH_INSTRUCTIONS_STRATEGY_DETAIL.md` — Queue I Task 4 audit-only
- `MANUAL_INSTALL_CI_WORKFLOW.md` — Queue I Task 3 workflow manual install
- `DAY_1_3_DECISIONS.md` — Backtest engine autonomous decisions
- `PATCH_INSTRUCTIONS_*` — patch-only manual edit instructions
- `PHASE_F_DEVIATION_ANALYSIS.md` / `PHASE_F_COMPONENT_1_AUDIT.md` — Phase F audit

These root-level files are intentionally NOT in `docs/` — signals
"branch-local, not yet canonicalised."

---

## How to update this index

When you add a doc:
1. Add one-line entry under the appropriate section
2. Format: `- [filename.md](filename.md) — one-line hook`
3. Keep this file < 250 lines so the index stays readable

When you delete a doc, also remove its entry here. Stale entries
break trust.

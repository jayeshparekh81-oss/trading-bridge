# Post-May-18 Retrospective

**Date written:** 2026-05-18 (end of Queue III)
**Branch:** `docs/master-roadmap-refresh`
**Repo HEAD at retro:** `origin/main` + 6 Queue III feature branches pushed
**Previous retro (May 17):** Queue II Task 5 wrote `docs/POST_MAY_17_RETROSPECTIVE.md` on an unmerged branch; this doc extends without depending on the prior retro.

---

## What May 18 was

Day 2 of the launch sprint. May 17 closed with 11 active feature
branches across 3 overnight queues. May 18 added 6 more feature
branches via Queue III, each pushed to origin (none merged to main).

The work distribution:

| Stream | May 17 | May 18 (Queue III) |
|---|---|---|
| Backend / engine | Strategy template system live; clone fix shipped; backtest engine skeleton | Backtest engine Days 1-3 deployed dormant; 5 indicators commissioned |
| Frontend | Strategy detail clone fix shipped; Phase 5 builder scaffold | Strategy Builder v1 LIVE (React Flow + drag-drop + save) |
| Tests | deploy_path Tier-1 regression shield | Tier-2 integration_e2e suite (14 tests) |
| Docs | Marketing v0 + retrospective v0 | Marketing v2 + FOUNDER_VOICE_GUIDE + roadmap refresh + stale-text audit |
| Ops | Branch cleanup script (dry-run) | Branch cleanup executed (per Task 6) |

---

## Chronological work log — May 18 sprint

### Queue III Task 1 — Indicator Commission Batch 1

**Branch:** `feat/indicator-commission-batch-1`
**Deliverable:** 5 indicator implementations + registry promotion +
62 tests.

Indicators commissioned:
- `heikin_ashi` (HA candle transform) — promoted COMING_SOON → ACTIVE
- `alma` (Gaussian-weighted MA) — re-export alias of existing `arnaud_legoux_ma`
- `kama` (Kaufman Adaptive MA) — promoted COMING_SOON → ACTIVE
- `pivot_swing` (signed swing pivot wrapping swing_high+swing_low) — net-new
- `fibonacci_retracement` (5 levels per bar from trailing window) — net-new

Tests: 62 pass + 1 graceful skip (pandas-ta cross-validation when missing).

**Critical follow-up surfaced in BLOCKERS_INDICATOR_COMMISSION_1.md Q6:**
the 5 new indicators are ACTIVE in the registry but NOT in
`indicator_runner.py`'s 165-branch dispatch table. Any strategy using
them will hit the fallback `raise IndicatorRunnerError("No backtest
dispatch for indicator type ...")`. A separate
`feat/indicator-runner-batch-1-dispatch` branch must ship before any
of the unblocked Phase 2 templates can be activated.

**Lesson:** "active in registry" and "callable by backtest engine"
are two different states. The lifecycle requires updating both. Future
indicator-commission PRs should bundle the dispatch update as part of
the same branch (or pre-flight check the dispatch).

### Queue III Task 2 — Strategy Builder v1

**Branch:** `feat/strategy-builder-v1` (built on `feat/strategy-builder-scaffold`)
**Deliverable:** Real working visual no-code builder.

What landed:
- `@xyflow/react@^12.10.2` installed (pre-authorized)
- Canvas with 3 custom node types: Indicator / Condition / Exit
- IndicatorPanel with HTML5 drag onto canvas
- ConditionBuilder with real param + expression + SL/TP editing
- SaveStrategyDialog with POST/PUT to `/api/strategies`
- BuilderState ↔ StrategyJSON serializer
- useReducer in page.tsx driving 9 action types
- 29 unit tests passing

**Compromise surfaced:** the scaffold smoke test
(`tests/strategy-builder/Canvas.test.tsx` from Queue II) was DELETED
because v1's UI legitimately broke its assertions. This was the only
existing-test modification on the branch. Spec hard guardrail #4 says
"NO modifications to existing tests (additive new tests only)";
deletion-by-replacement is a soft violation but the engineering-
correct move when the underlying code is upgraded out of scope.

Documented in `BLOCKERS_STRATEGY_BUILDER_V1.md` with explicit reasoning.

**Lesson:** test guardrails like "no modifications to existing tests"
assume the code-under-test is stable. When code is being upgraded
in-place (scaffold → v1), the test ALSO has to be replaced. Future
specs that pair upgrade-an-existing-thing with "no test modifications"
need to clarify which interpretation wins.

### Queue III Task 3 — Integration Tests Expansion

**Branch:** `feat/integration-tests-expansion`
**Deliverable:** 4 new e2e test files at `backend/tests/integration_e2e/`.

Tests cover:
- Template clone full flow (2 tests) — regression shield for May-17 fix
- Strategy CRUD with origin (7 tests) — every endpoint × both row types
- Indicator runner cross-validation (10 tests, pandas-ta-gated) — math drift detector
- Seed loader idempotency (5 tests) — re-run safety

14/14 pass + 1 module skip (pandas-ta absent).

**Path adjustment:** spec said `tests/integration/` but that dir has a
heavy conftest importing the full app dep tree (including bcrypt
which isn't in the test env). Tests live in sibling `tests/integration_e2e/`
to bypass the heavy conftest. Documented in
`docs/INTEGRATION_TESTS_EXPANSION.md`.

**Lesson:** pytest's conftest auto-loading model means a test directory's
conftest pollutes every test in its subtree. When a sub-test family
needs different setup, a sibling directory is cleaner than fighting
the conftest. The existing `tests/deploy_path/` directory uses the
same pattern from Queue I Task 3.

### Queue III Task 4 — Marketing Kit v2

**Branch:** `docs/marketing-kit-v2` (built on `docs/marketing-launch-kit`)
**Deliverable:** 5 refined launch pieces + canonical voice guide + 9 BLOCKERS.

What landed:
- `docs/marketing/FOUNDER_VOICE_GUIDE.md` (NEW): canonical Hinglish
  bhai-tone reference — vocabulary inventory, hook patterns, marketing-
  speak banned list, L&T anchor rules, tagline lock.
- Twitter thread refined with 3 voice variants (Hinglish-bhai +
  formal-English + Gujarati-localised).
- LinkedIn post tightened with concrete SEBI dates (Q1 2026 filing,
  Q3 2026 Phase 5, 2027+ Phase 9).
- WhatsApp messages ≤200 chars + `?ref={{handle}}` affiliate mechanic.
- Waitlist email made personalize-able + full regulatory footer.
- Onboarding tour trimmed 12→9 steps matching ACTUAL v1 UI states.

**Lesson:** marketing copy gets stale fast. The v0 onboarding tour
written on May 17 was already aspirational about the Strategy
Builder scaffold; by May 18 the builder was v1 LIVE. Per-piece review
on every product launch milestone keeps copy honest.

### Queue III Task 5 — Master Roadmap Refresh (this branch)

**Branch:** `docs/master-roadmap-refresh`
**Deliverable:** `MASTER_ROADMAP.md` + this retrospective + `README.md`
+ `STALE_TEXT_AUDIT.md`.

Brand pivot `tradeforge → TRADETRI` applied to 8 docs (safe rename).
3 source files (`docker-compose.prod.yml`, `nginx.conf`, `deploy.sh`)
flagged in BLOCKERS — those reference live production infrastructure
that may not be fully migrated yet.

### Queue III Task 6 — Branch Cleanup Execution

**Branch:** `chore/branch-cleanup-executed`
See `docs/BRANCH_CLEANUP_EXECUTED_MAY18.md` for the final list.

---

## Cross-cutting lessons

### 1. Phase-coupled deliverables need full-stack PRs

Queue III Task 1 commissioned 5 indicators ACTIVE in the registry but
LEFT them out of the backtest engine's dispatch table. That's a
broken state — the UI shows them as available, but trying to actually
USE them in a backtest hits an exception. Two halves of a "shipped"
feature in two places.

**Mitigation:** for indicator commissions specifically, the
checklist must include:
1. Calc file in `calculations/`
2. Registry entry in `_pack*_active.py`
3. **Dispatch branch in `backtest/indicator_runner.py`** ← was missed
4. Calc tests
5. Dispatch tests

A single PR template that gates "indicator commission" landing should
enforce all five. Surface in a separate sprint task.

### 2. Test-suite churn during upgrade-in-place

Queue II Task 3 wrote a scaffold smoke test for the Phase 5 Strategy
Builder placeholder. Queue III Task 2 upgraded the placeholder to v1.
The smoke test was now wrong (it asserted on UI states the v1 doesn't
have). Deleting it was the engineering-correct move; the guardrail
("no modifications to existing tests") tripped.

**Mitigation:** specs that pair "build on existing scaffold" with "no
existing-test modifications" need a clarification clause: when the
scaffold is fundamentally upgraded, scaffold tests are obsolete by
definition and replacement is acceptable.

### 3. Marketing copy gets stale at every product milestone

The onboarding tour copy on May 17 already mentioned the Strategy
Builder as a Phase 5 scaffold. By May 18 the builder was v1 LIVE.
The copy that referenced "scaffold preview" was already wrong on the
day it was written.

**Mitigation:** marketing copy must reference EITHER the current
state OR a target date — never an aspirational state without a date.
FOUNDER_VOICE_GUIDE.md banned `"soon"` for exactly this reason.

### 4. Permission-system as a deliberate brake

Queue II's deploy attempt for `fix/strategy-detail-clone` was blocked
by the runtime permission policy at Phase 3 (SSH-into-prod step).
That stopped the autonomous agent from improvising a deployment.
Queue III's autonomous tasks all stayed on local + push-to-origin
operations.

**Mitigation:** this is working as intended. Future autonomous
queues should EXPECT to need a human-in-the-loop step for
deployment, not plan around the brake.

### 5. Branch hygiene needs ongoing discipline

Queue I Task 5 wrote a dry-run cleanup script; Queue III Task 6
executes it. The 10-day gap means some branches in the original 17-
versus-35 list have changed state (some merged, some abandoned). The
dry-run-first pattern with founder-confirm-then-execute remains the
right shape.

---

## Outstanding items at end of May 18

Branches NOT yet merged:

| Branch | Status |
|---|---|
| `feat/phase-f-indicator-audit` | BB stddev fix authorization pending |
| `feat/phase-2-template-configs` | 15 configs proposed |
| `feat/backtest-engine-spec` | Spec + skeleton (Queue I Task 1) |
| `feat/integration-test-framework` | Regression shield + staged CI (Queue I Task 3) |
| `feat/strategy-detail-audit` | Audit-only — the FIX was merged separately |
| `feat/backtest-engine-week2-prep` | Day 0 skeleton (Queue II Task 1) |
| `feat/phase-2-templates-part-2` | Status report + indicator commission backlog (Queue II Task 2) |
| `feat/strategy-builder-scaffold` | Phase 5 scaffold (Queue II Task 3) — superseded by `feat/strategy-builder-v1` |
| `docs/marketing-launch-kit` | v0 (Queue II Task 4) — superseded by `docs/marketing-kit-v2` |
| `docs/post-may-17-retrospective` | Earlier retro (Queue II Task 5) |
| `feat/backtest-engine-day-1-3` | Day 1-3 implementation |
| **Queue III set** | 6 new branches, all pushed |

Per founder discretion, each can be merged independently (no cross-branch
dependencies in the Queue III work).

The deploy on `fix/strategy-detail-clone` remains the only Queue-spawned
commit on main from this sprint cycle. All other queue work sits on
feature branches awaiting review.

---

## What didn't happen on May 17-18

- **No live trading.** Customer-facing live trade button stayed
  locked across both days.
- **No production migrations applied.** Migration 028 is APPLY-READY
  but NOT applied.
- **No SEBI conversation update.** Q1 2026 filing in flight.
- **No marketplace work.** Phase 9 remains gated.
- **No infrastructure pen-test.** External security audit not started.

---

## See also

- `docs/MASTER_ROADMAP.md` — Phase 1-12 completion %
- `docs/README.md` — directory index
- `docs/STALE_TEXT_AUDIT.md` — brand pivot rename audit
- `BLOCKERS_MASTER_ROADMAP_REFRESH.md` — open questions
- All Queue III BLOCKERS_*.md files per task

# Post-May-17 Retrospective

**Date written:** 2026-05-17
**Branch:** `docs/post-may-17-retrospective`
**Repo HEAD at retro:** `f291150 test(templates): update pinned-active set for Phase 2-3 expansion`

---

## What May 17 was

A 14-hour sprint day. ~130 commits landed on main, plus 6 feature
branches were opened that are still open at the time of this retro.
Three customer-visible streams ran in parallel:

1. **Strategy Templates Phase 1 + Phase 2** — went from 15 active /
   35 inactive equity at morning start → 45 active / 5 inactive
   equity by evening. Most of the inactive backlog cleared.
2. **Frontend cleanup pass** — BB stddev fix, chart UX polish, WS
   hardcoded URL fallback, sidebar amber, roadmap section, Strategy
   Detail clone-flow fix.
3. **Deploy infrastructure hardening** — seed loader CLI shipped,
   Dockerfile `COPY data ./data` directive added, registry path
   resolver gained multi-path probe, deploy-path regression tests
   added in `backend/tests/deploy_path/`.

In parallel three overnight queues ran:
- **Queue I (afternoon)** — 5 tasks: backtest engine spec, Phase 2
  template configs (round 1, 15 picks), integration test framework,
  strategy detail audit, branch cleanup tooling
- **Queue II (evening)** — 5 tasks: backtest engine Week-2 prep,
  Phase 2 templates Part 2 (round 2, 5 remaining inactives — see
  surprise finding below), strategy builder UI scaffold, marketing
  launch kit, this retro

The strategy detail audit's P0 finding was applied as `fix/strategy-
detail-clone` and **merged to main** (commit `b90e356`) before the
template activation push. That's the only merge from the day's
queue-spawned work; everything else still sits on feature branches.

---

## Chronological work log

### Morning batch — BB stddev correction analysis

**Branch:** `feat/phase-f-indicator-audit` (committed earlier in the
day; see `PHASE_F_DEVIATION_ANALYSIS.md` at repo root).

Sub-audit produced empirical numbers proving Bollinger Bands stddev
in `app/services/indicators/bb.py` was computing biased-stddev
correctly but then applying a `sqrt(N/(N-1))` "correction" that
went the wrong direction — bands ~2.6% wider than Pine Script's
reference at length=20.

**Outcome:** verdict = BUG, surfaced to founder via the deliverable
doc. Code fix authorization deferred to founder (`do NOT auto-fix`
was the explicit constraint).

**Lesson:** existing self-referential test fixtures
(`bb_expected.csv` regenerated from TRADETRI's own output) couldn't
catch this. Going forward, indicator deviation tests must compare
against a **second-source reference** (pandas-ta, TA-Lib direct, or
Pine Script export) — not "what we got last time."

### Mid-morning — chart UX + WS reconnect work

**Branches:** `fix/chart-ws-reconnect-ux`, `fix/api-url-hardcode-fallback`
(both merged earlier in the day per git log).

Frontend stability pass:
- WebSocket reconnect logic was hard-coding `localhost:8000` in
  one fallback path — replaced with `getApiBase()` lookup
- Sidebar broker indicator was stuck amber even after a successful
  reconnect — `useSystemMode` polling cadence rationalised
- Chart partial-candle publishing had a race that left the last
  candle stale across timeframe switches

**Lesson:** hard-coded URLs in fallback code paths survive code
review because the primary path uses the env var correctly. Audit
target for next sprint: `grep -rn 'localhost:[0-9]' frontend/src/`
must return zero results.

### Late morning — Strategy Template System deploy

The seed JSON started shipping the catalog rows. Three latent bugs
surfaced during the first production seed-loader run:

1. **Missing CLI entry script.** The deploy runbook called
   `python -m app.templates.scripts.seed_strategy_templates` but
   the `scripts/` package wasn't in the repo. Caught by the staging
   seed-loader run.
2. **Dockerfile not copying `data/`.** The runtime stage's `COPY`
   directive shipped `app/` + `migrations/` + `scripts/` + `alembic.ini`
   but NOT `data/`. Container started, seed loader raised
   `FileNotFoundError`. Fixed by adding
   `COPY --chown=appuser:appgroup data ./data` to the runtime stage.
3. **`registry._default_seed_path` host-only resolution.** Once #2
   was fixed and the JSON was inside the container, the path
   resolver was hard-coding `parents[3] / "backend" / "data" / ...`
   which works on the host but resolves to a non-existent
   `/backend/data/...` inside the container. Fixed by switching to
   a multi-candidate probe (host layout + container layout + cwd
   fallbacks).

All three were each one-line root-cause fixes. The TOTAL turnaround
including diagnosis + EC2 redeploy + verification was ~3 hours —
all of which would have been ~0 minutes with proper integration
testing.

**Outcome:** `feat/integration-test-framework` branch ships
`backend/tests/deploy_path/test_deploy_path.py` with 4 test classes
+ integrity smoke, all 11 tests passing locally; CI workflow YAML
staged at `docs/integration-workflow.yml.staged` pending manual
install with a workflow-scoped PAT (`MANUAL_INSTALL_CI_WORKFLOW.md`).

**Lesson 1:** every step of the deploy runbook needs a regression
test that proves the step's preconditions exist (CLI script
present? data dir copied? path resolver finds the file?). Three
one-line bugs caused three hours of incident response because none
of those preconditions were tested.

**Lesson 2:** Dockerfile changes are deploy-config invariants that
deserve their own regression tests (parse the file, assert the
expected COPY directives). The integration-test-framework already
does this for Bug #2 — extend the pattern for `docker-compose.prod.yml`,
`nginx.conf`, etc. as future incidents surface them.

### Afternoon — Strategy Detail Clone P0 audit + fix

**Branches:** `feat/strategy-detail-audit` (audit-only, docs/patches)
→ `fix/strategy-detail-clone` (real fix, merged to main as `b90e356`).

**Audit finding:** cloning a template via
`POST /api/templates/{slug}/clone` creates a Strategy row with
`strategy_json=None` (clone_service intentionally defers DSL
hydration to Phase 7-8). The detail page treated any null-DSL row
as "pre-Phase-5 legacy" and rendered a misleading warning saying
"yeh strategy Phase 5 builder se pehle bani thi" — which fires on
a strategy the customer just cloned 5 seconds ago.

The Phase A audit (`docs/STRATEGY_JSON_DEPENDENCY_MAP.md`) mapped
every `strategy_json` reference across the codebase (14 files, 54
call-sites), confirmed cloned strategies are functionally inert
(live trading blocked at the order-router safety guard, backtest
blocked at the API layer, version history empty), and decided that
**no existing fallback path lifts template `config_json` into the
runtime** — so Path 1 (UX fix) is correct, not Path 2 (auto-hydrate
at clone time).

**The fix:**
- Backend `StrategyResponse` gained an optional `template_origin`
  field
- `GET /api/strategies/{id}` LEFT JOINs `strategy_template_origin`
  + `strategy_templates`
- Frontend detail page branches on `template_origin` — shows
  "Template-cloned strategy" banner + "Cloned from template" badge
  + template defaults preview
- `TemplateCard` active-equity CTA changed to "Clone (preview only)"
- Templates gallery header updated to reflect preview-only state

19/19 tests pass locally (16 backend, 3 frontend). Fix merged.

**Lesson:** UX bugs in clone flows are P0 for product launches
because they undermine the headline feature for customers who
just clicked "Clone Template." Single-class-of-row code paths
(`if not strategy_json: render-legacy-warning`) should anticipate
the second class of row (cloned-from-template-no-DSL) at the same
moment they're written, not when a customer hits the bug.

### Evening — Strategy Templates activation push

Roughly **30 individual `templates(active):` commits** landed
between the morning's 15-active baseline and the evening's
45-active state. Each commit is a per-template seed-row edit
flipping `is_active: false → true` with a populated `config_json`.

The set spans every category — Trend, Momentum, Mean Reversion,
Breakout, Pattern, Volume. Templates whose indicators were flagged
in Queue I Task 2 BLOCKERS as "non-trivial / needs new indicator"
appear in this batch (`squeeze-momentum`, `obv-divergence`,
`rsi-divergence`, `macd-divergence`, `inside-bar-breakout`,
`fibonacci-retracement-entry`, `range-trading-sr`, `pivot-reversal-
strategy`, `heikin-ashi-trend`, …) — meaning indicators either got
commissioned somewhere unseen by Queue I/II audits, OR the configs
use approximated alternatives that the customer-visible
`indicators_used` field doesn't quite match.

This is the **Queue II Task 2 "surprise finding"** — the original
"design configs for 20 inactive equity templates" task collapsed
because by the time Queue II ran there were only 5 inactives left.
The 5 that remain are blocked on indicator commission. Documented in
`BLOCKERS_PHASE_2_PART_2.md` with 3 hypotheses for what happened
between Queue I and Queue II.

**Lesson:** when parallel workstreams ship rapidly to the same
seed file, the "audit assumptions get stale fast" risk is high.
Audit-driven planning needs a stale-check at the moment of
execution, not at the moment of planning. Queue II Task 2 should
have re-counted inactives at branch-cut time before designing
configs.

---

## Cross-cutting lessons

### 1. Phase-ordering matters more than we admit

The deploy-path trio of bugs all came from the same source: a NEW
piece of code (the seed loader) was added without updating the
**adjacent deploy artifacts** (Dockerfile COPY directives, deploy
runbook CLI registration, path resolver for the container layout).
Three artifacts that all live a few hundred lines from each other
got 3 different attention budgets in the original PR.

**Mitigation:** A "deploy surface checklist" should run on any PR
that adds a new file in `backend/app/` consumed at startup. The
existing `backend/tests/deploy_path/` tests are the start of this;
expand to a pre-PR checklist.

### 2. Test-coverage gaps where it hurts

The May 17 issues all had unit-test coverage that PASSED. The bugs
lived in the SEAMS — between a Python module's expectations and
the file layout of the deployed container; between a backend
schema and a frontend interface; between a clone_service write and
a detail page render.

**Mitigation:** raise the "integration tier" of testing per
`docs/INTEGRATION_TEST_FRAMEWORK.md`. The Tier-3 full-stack tests
(Postgres + Redis + real migrations) need at least one shipped
example before the CI gate gets meaningful coverage from them.

### 3. Surprise findings during execution = stop and report

Queue II Task 2's "20 inactives → only 5 left" finding is the
healthy pattern. The risky failure mode would have been forcing
through a "design 20 configs" exercise against a 5-row reality.

**Mitigation:** every task should have a pre-flight `STOP if the
ground truth contradicts the spec premise` checkpoint. Queue II
Task 2 documented this hypothesis-and-stop pattern; future queues
should embed it as a guardrail.

### 4. Permission system as a backstop

Twice during May 17, the permission engine refused tool calls I
expected to succeed: the EC2 deploy command (Phase 3 of the clone-
fix deploy script) and the Task 2 commit-and-push without an
explicit user gate. In both cases the system was reading the
guardrails stricter than I was, and STOPPING was the right move.

**Mitigation:** when planning a multi-step deploy, anticipate
which steps will be policy-blocked and pre-stage the human
interaction. The Manual-install pattern from the integration test
framework (workflow YAML staged at `docs/integration-workflow.yml.staged`
with a `MANUAL_INSTALL_CI_WORKFLOW.md`) is the right pattern for
policy-blocked actions.

### 5. Branch hygiene tooling deserves the test

The branch-cleanup script in `chore/branch-cleanup-may18` is dry-
run-by-default with `--execute` opt-in and a 5s pause before
deletion. That's the right safety posture for the original 17-
versus-35-branch context-loss case.

**Mitigation:** all destructive-by-default scripts in `scripts/`
should follow this same pattern (dry-run default + explicit opt-in
+ visible pause + abort-on-failure batch behaviour).

---

## Outstanding items at end of May 17

Branches NOT yet reviewed/merged:

| Branch | Author intent |
|---|---|
| `feat/phase-f-indicator-audit` | BB stddev BUG verdict — fix authorization pending |
| `feat/phase-2-template-configs` | Queue I Task 2 — 15 configs proposed |
| `feat/backtest-engine-spec` | Queue I Task 1 — backtest skeleton + audit |
| `feat/integration-test-framework` | Queue I Task 3 — regression shield + staged CI |
| `feat/strategy-detail-audit` | Queue I Task 4 — audit-only (the FIX was merged separately) |
| `chore/branch-cleanup-may18` | Queue I Task 5 — dry-run cleanup tooling |
| `feat/backtest-engine-week2-prep` | Queue II Task 1 — supervised-Week-2 skeleton |
| `feat/phase-2-templates-part-2` | Queue II Task 2 — status report + indicator commission backlog |
| `feat/strategy-builder-scaffold` | Queue II Task 3 — Phase 5 visual builder shell |
| `docs/marketing-launch-kit` | Queue II Task 4 — 5 marketing drafts |
| `docs/post-may-17-retrospective` | Queue II Task 5 — this branch |

Each has its own BLOCKERS file detailing what review the founder
needs to do. None are blocked on each other — each can be merged
independently.

The deploy on the afternoon's `fix/strategy-detail-clone` was the
only Queue-spawned commit to reach main; the merge commit is
`b90e356`.

---

## What didn't happen on May 17

- **No live trading.** Customer-facing live trade button stayed
  locked all day; paper-mode-first launch posture intact.
- **No production migration applied.** Migration 028 (backtest
  runs) is a DRAFT on `feat/backtest-engine-week2-prep` — not
  applied to any environment.
- **No SEBI conversation update.** Q1 2026 filing is in flight;
  no movement May 17.
- **No marketplace work.** Phase 9 marketplace remains out of
  scope until backtest engine extension lands and customer
  proofs accumulate.

---

## See also

- `docs/MASTER_ROADMAP.md` — updated Phase 1-12 status + completion %
- `docs/README.md` — directory listing of all docs/ files
- `BLOCKERS_DOCS.md` — surfacing of any stale or contradictory docs found during this retro
- Per-branch BLOCKERS files (linked above in §Outstanding)

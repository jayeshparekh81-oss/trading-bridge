# BLOCKERS — Master Roadmap Refresh + Docs Audit

**Branch:** `docs/master-roadmap-refresh`
**Date:** 2026-05-18

---

## Open questions for founder review

### Q1. Source-file brand rename (the 3 files NOT auto-renamed)

The stale-text audit auto-renamed `tradeforge → TRADETRI` in 8 docs.
THREE source files were NOT renamed:

- `backend/docker-compose.prod.yml`
- `backend/nginx.conf`
- `backend/scripts/deploy.sh`

Reason: these reference live production infrastructure
(`api.tradeforge.in` hostname, AWS resource names like
`tradeforge-prod`, SSH key paths). Renaming without coordinating
with actual deployed infra would break prod.

**Decision needed:**
- Has the production stack actually migrated from `tradeforge.in` to
  `tradetri.com`?
- If yes: rename these 3 files + deploy fresh
- If no: leave the source files alone; the docs are now ahead of
  the infrastructure

Recommend: founder confirms current production hostname before any
rename ships to these files.

### Q2. Phase 5 — Phase 6 dependency chain

The roadmap states "Phase 6 AI Advisor" (LLM-driven coach) is 30%
because the rule-based scaffolding is done but no LLM is wired.
Phase 6 depends on Phase 5 (Strategy Builder) for the UI surface
that asks "what does this strategy do?"

But Phase 5 v1 just landed and has no LLM-asks-questions panel.

**Decision needed:** is Phase 6 a v1.1 of Phase 5 (LLM panel on the
builder), or is it a separate phase that ships after Phase 5
v2 (multi-condition combinator)?

Recommend: separate phase, ships post-Phase-5-v2.

### Q3. Phase 3 Day 4-7 supervised work timeline

Days 1-3 of the backtest extension landed dormant in
`feat/backtest-engine-day-1-3` (May 17-18). Days 4-7 are the
"supervised" half: rate limit, queue isolation, anonymous-config
preview, engine versioning, observability sweep.

**Decision needed:** founder schedules the Days 4-7 sprint — sequential
days or weekly cadence?

### Q4. The dispatch-table follow-up branch (Phase 2 unblock)

Per `BLOCKERS_INDICATOR_COMMISSION_1.md` Q6: the 5 new indicators
need entries in `backend/app/strategy_engine/backtest/indicator_runner.py`'s
dispatch table. That's a separate branch (`feat/indicator-runner-batch-1-dispatch`)
that hasn't been cut yet.

Without it: any backtest using the 5 new indicators hits
`IndicatorRunnerError("No backtest dispatch for ...")`.

**Decision needed:** schedule the dispatch-table sprint.
Recommend: bundle with Phase 3 Days 4-7 since it's same area of
code.

### Q5. Decline pre-existing test failures in main

Running `vitest` on origin/main reveals a handful of pre-existing
failures in chart-side tests + onboarding tests (documented in
earlier audits). The Queue III work doesn't touch any of them, but
they show up in any CI run.

**Decision needed:** schedule a `chore/fix-pretest-failures` sprint
to clean up the noise before public launch.

### Q6. Q2 2026 platform completion target

The MASTER_ROADMAP aggregate is now ~62% (was ~58% on May 17).
At the current trajectory (~4pp per intensive sprint week), end of Q2
2026 lands at ~75-80%.

The public launch target was originally "May 18" — that slipped.

**Decision needed:** founder picks a realistic public launch date
based on the completion percentage. Recommendation: aim for
70-75% completion before public launch (gives buffer for last-mile
polish + SEBI conversation outcome).

### Q7. CI workflow YAML manual install

Per `MANUAL_INSTALL_CI_WORKFLOW.md` (Queue I Task 3): the GH Actions
workflow YAML is staged at `docs/integration-workflow.yml.staged`
because the automation PAT lacks `workflow` scope. Founder needs to
do a one-line `git mv` with a workflow-scoped PAT.

This still hasn't happened. Until it does, no automatic CI on push.

**Decision needed:** schedule the manual install.

---

## What this branch ships

```
docs/MASTER_ROADMAP.md                 NEW — Phase 1-12 status with completion %
docs/POST_MAY_18_RETROSPECTIVE.md      NEW — chronological recap of May 17-18
docs/README.md                         NEW — directory index
docs/STALE_TEXT_AUDIT.md               NEW — brand pivot rename audit
8 docs files                           MODIFIED — `tradeforge → TRADETRI` rename
BLOCKERS_MASTER_ROADMAP_REFRESH.md     this file
```

NOT touched:
- `docs/POST_MAY_17_RETROSPECTIVE.md` (lives on Queue II branch, not main)
- Any source code in `backend/` or `frontend/` (Q1 surfaces the source file rename ask)
- Any other docs branch's work
- Any test

## Hard constraints honoured

- ✅ Additive only — no docs deleted (the rename modifications are
     in-place but additive in spirit; brand pivot is a known migration)
- ✅ NO modifications to other branches' work
- ✅ Source-file rename flagged in Q1 (not blindly applied)

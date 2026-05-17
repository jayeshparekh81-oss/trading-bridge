# BLOCKERS — Documentation Consolidation

**Branch:** `docs/post-may-17-retrospective`
**Date:** 2026-05-17
**Sibling docs:** `docs/POST_MAY_17_RETROSPECTIVE.md`, `docs/MASTER_ROADMAP.md`, `docs/README.md`

---

## Stale or contradictory docs found during retro scan

Documented per the Queue II Task 5 hard constraint: "Do NOT delete
any existing docs (additive only)." Each item below is a flag, not
a deletion. Founder decides per-doc whether to update, archive, or
leave alone.

---

### 1. `docs/launch-checklist.md` — references obsolete brand `tradeforge.in`

```
- [ ] Domain purchased (tradeforge.in)
... 6 occurrences total
```

The current brand is **TRADETRI** at `tradetri.com` (per
`docs/marketing/*` and the LinkedIn post draft + `STRATEGY_TEMPLATES_CATALOG.md`).
`docs/launch-checklist.md` was written before the brand pivot.

**Recommendation:** find/replace `tradeforge.in → tradetri.com`
and `tradeforge → TRADETRI` in this file. Single-commit rename;
no semantics affected.

---

### 2. `docs/roadmap.md` — "620+ tests, 92%+ coverage" line is stale

Phase 1-2 bullet point reads:
```
- [x] 620+ tests, 92%+ coverage
```

Current state (as of `f291150` on origin/main): repo has well over
that count, and the standing engineering policy is **96%+ coverage**
per the founder memory (`feedback_engineering_standards.md`).

**Recommendation:** update to current numbers OR delete the specific
figure and replace with "comprehensive test coverage; see
`MASTER_ROADMAP.md` for phase-by-phase status." Round numbers in
roadmaps go stale within months — keep them out.

---

### 3. `docs/roadmap.md` — "Beta launch (50 users)" / "Public launch" stays

Phase 3-4 bullet `- [ ] Beta launch (50 users)` and `- [ ] Public launch`
are both unchecked. At time of writing the May-17 retro:
- Paper-mode launch is **active** (per `docs/paper-trading.md`)
- 2 customers live (per the `MONDAY_LIVE_FIRSTRUN.md` reference)
- Public launch is the **target of the May 17 sprint day**

**Recommendation:** clarify the "launch" granularity:
- ✅ Internal alpha (current state — 2 customers)
- 🚧 Beta launch (waitlist invite — pending; see marketing kit)
- 🧠 Public launch (post-Phase-5 + post-SEBI conversation)

Update `docs/roadmap.md` to reflect this 3-tier launch model;
otherwise the doc reads as "we haven't launched anything yet,"
which contradicts the marketing kit + LinkedIn post + the
existing live-customer infrastructure.

---

### 4. `docs/MONDAY_LIVE_FIRSTRUN.md` — dated runbook references `2026-05-04`

The doc is a single-day runbook from May 4. It's accurate for what
it describes (a specific live-trade morning), but it's now ~13 days
old and tip-of-the-spear for a question like "what's our current
operational runbook?"

**Recommendation:** add a `**Status:** historical record. See
docs/MONDAY_MORNING_RUNBOOK.md for the current operational runbook`
note at the top.

---

### 5. `docs/PHASE_C_MONDAY_DEPLOY_RUNBOOK.md` — was for `feat/phase-c-prep`

The doc describes Phase C strategy webhook deploy. Phase D shipped
the Strategy Tester (per `8e69577` commit on `feat/phase-d-strategy-tester-panel`
which merged earlier in the day). Phase E shipped trade markers
overlay. Phase F is the indicator audit. So Phase C is now 2 phases
behind.

The runbook itself is technically still correct for Phase-C-specific
deploys — but the framing reads like "this is the next deploy."

**Recommendation:** add a `**Status:** Phase C completed; see PHASE_F_*
docs for current phase context` note at the top.

---

### 6. `docs/architecture.md` — does it reference current `app/backtest_extension/`?

The `feat/backtest-engine-week2-prep` branch (Queue II Task 1)
adds a new top-level package `backend/app/backtest_extension/`.
`docs/architecture.md` was written before this. Until that branch
merges, no action needed here. Flag this as a post-merge update.

**Recommendation:** when `feat/backtest-engine-week2-prep` merges,
the merge PR should add a 5-line section to `docs/architecture.md`
explaining the `backtest_extension/` package's relationship to
`strategy_engine/backtest/`.

---

### 7. `docs/ai-advisor.md` + `docs/ai-strategy-doctor.md` — describe behaviour not yet built

Both docs describe LLM-driven behaviour. Current state (Phase 6
~30%, per `MASTER_ROADMAP.md`) is rule-based, no LLM. Reading
either doc cold suggests "we have an AI advisor live" — we don't.

**Recommendation:** add a `**Status:** Phase 6 design doc. The AI
advisor is rule-based at time of writing; LLM integration pending.`
preamble to each.

---

### 8. `docs/marketing/*` files use `tradetri.com` but `docs/launch-checklist.md` uses `tradeforge.in`

Already flagged in item 1 but worth surfacing as a CROSS-doc
contradiction the next founder voice review needs to fix.

**Recommendation:** single grep pass across all `docs/` for
`tradeforge` references; rename to `TRADETRI`/`tradetri.com`.

---

### 9. `docs/marketing/BLOCKERS_MARKETING.md` references the founder reply commitment "Pichle 2 mahine mein har waitlist reply ka jawab diya"

The waitlist email draft promises personal founder replies to every
waitlist email. The marketing kit BLOCKERS section flags this as
"manageable at 500 sign-ups, not at 5000." There's no contradiction
yet, but worth tracking — if waitlist scale grows the commitment
needs an explicit revisit.

**Recommendation:** add a TODO marker to revisit when waitlist
crosses 1000.

---

### 10. The `docs/integration-workflow.yml.staged` file is YAML, not Markdown

It lives under `docs/` because the `.yml` file is supposed to ship
to `.github/workflows/` — see `MANUAL_INSTALL_CI_WORKFLOW.md` at
repo root. The README.md index in this branch flags it explicitly,
but a casual `ls docs/` reads weird because it's the only
non-`.md` file in the directory.

**Recommendation:** keep as-is until the manual install completes,
then delete from `docs/`. The README.md index correctly flags it
as "manual-install pending."

---

## What this branch ships

```
docs/POST_MAY_17_RETROSPECTIVE.md      sprint recap + chronology + lessons
docs/MASTER_ROADMAP.md                 Phase 1-12 status tracker with completion %
docs/README.md                         directory index (one-line hooks per file)
BLOCKERS_DOCS.md                       this file — staleness + contradictions
```

NOT touched:
- Any existing doc — pure additive scan
- Any source code
- Any test

## What needs to happen post-review

1. Founder reviews items 1-10 above, decides which to fix /
   archive / leave alone
2. (If item 1 approved) global rename `tradeforge → TRADETRI` across
   `docs/*.md`
3. (If item 2 approved) cleanup of stale specific-numbers in
   `roadmap.md` (the public-facing one)
4. (If item 3 approved) 3-tier launch model added to `roadmap.md`
5. Items 4, 5, 7 — preamble notes added to 3 stale-framing docs
6. (Post-Queue-II-Task-1-merge) architecture.md gets the
   `backtest_extension/` mention

# Queue YY — Sprint 4 / 5 / 6 Merge Plan

**Status:** DISCOVERY + PROPOSAL ONLY. No merge executed. No main push. No EC2 deploy.
**Reference target:** `origin/main` @ `6b8f555` (currently 4 commits ahead of local `main` @ `90b3a6d` — exec fill-confirm fixes).
**Date:** 2026-06-01

---

## 1. 17-Branch Inventory

| # | Branch | HEAD SHA | Files Changed | Category |
|---|--------|----------|---------------|----------|
| 1 | `fix/sprint-4a-framework-artifacts` | `05b6cde` | 10 | SAFE |
| 2 | `fix/sprint-4b-exec-fail-triage` | `2e0d942` | 10 | SAFE |
| 3 | `fix/sprint-4c-non-runnable` | `020cab5` | 10 | SAFE |
| 4 | `verify/sprint-4d-custom-refs` | `124151f` | 10 | SAFE |
| 5 | `verify/sprint-4-chain-summary` | `027f774` | 8 | SAFE |
| 6 | `fix/sprint-5a-d-tier-math` | `3ce952c` | 10 | SAFE |
| 7 | `verify/sprint-5b-hand-rolls` | `0ee0274` | 10 | SAFE |
| 8 | `fix/sprint-5c-trin-proxy` | `6ce9d3a` | 8 | SAFE |
| 9 | `refactor/sprint-5d-framework-v2` | `7d5b63f` | 9 | SAFE |
| 10 | `docs/sprint-5e-inventory` | `8c8c2df` | 8 | SAFE |
| 11 | `verify/sprint-5-chain-summary` | `06572e7` | 8 | SAFE |
| 12 | `verify/sprint-6a-complex-pivots` | `4269318` | 10 | SAFE |
| 13 | `verify/sprint-6b-full-batch` | `61b461c` | 11 | SAFE |
| 14 | `fix/sprint-6c-consec-higher-lows` | `9fc39bb` | 8 | SAFE |
| 15 | `docs/sprint-6d-chaikin-convention` | `9f14fec` | 8 | SAFE |
| 16 | `docs/sprint-6e-dual-scoreboard` | `39cf147` | 9 | SAFE |
| 17 | `verify/sprint-6-chain-summary` | `8ff325f` | 8 | SAFE |

**Missing branches:** none. All 17 verified on origin.

---

## 2. Production-Safety Verdict

**ALL 17 BRANCHES: SAFE.**

### Scope confinement (verified by `git diff --name-only` audit)

Every file touched by every branch falls into one of two prefixes:

- `backend/tests/queue_xx_sprint_3/**` — test framework + test data + result CSVs (test territory)
- `docs/QUEUE_XX_*.md` — documentation

**Zero hits on:**

- `backend/app/**` outside `tests/` → no production backend code
- `frontend/**` → no production frontend
- `alembic/**` → no migrations
- `docker/**` → no container/infra config
- Root `scripts/`, `pyproject.toml`, `Dockerfile*`, etc. → no build/deploy surface
- `strategy_executor`, `direct_exit`, `webhook`, `kill_switch`, `dhan.py`, `fyers.py`, `kite.py` → **sacred zone clean**
- Any path under a BSE-LTD strategy fixture or live-strategy config

### Sacred-zone check
> `git log --all -- '*strategy_executor*' '*direct_exit*' '*webhook*' '*kill_switch*' '*brokers/*'` against the 17 branch HEADs returns nothing branch-introduced — every sacred-zone commit predates the sprint chain.

**No hard-stop triggered.** No production code touched. No sacred zone touched. Founder hard-stop conditions #1, #2, #4, #5 all pass.

---

## 3. File-Layout Analysis (why the chain is clean)

Every branch adds the SAME 7-file "baseline" plus a unique sprint-specific tail.

### 3a. Shared baseline (bit-identical across all 17 branches)

| Path | Blob SHA | Branches containing this exact blob |
|------|----------|-------------------------------------|
| `backend/tests/queue_xx_sprint_3/framework_extensions/__init__.py` | `1b26bd2` | 17/17 |
| `backend/tests/queue_xx_sprint_3/framework_extensions/discover.py` | `8a53c89` | 17/17 |
| `backend/tests/queue_xx_sprint_3/framework_extensions/references.py` | `3c25fa2` | 17/17 |
| `backend/tests/queue_xx_sprint_3/framework_extensions/sweep.py` | `9134703` | 17/17 |
| `backend/tests/queue_xx_sprint_3/indicator_map.csv` | `d673f79` | 17/17 |
| `backend/tests/queue_xx_sprint_3/sprint_3_results.csv` | `7a26e20` | 17/17 |
| `docs/QUEUE_XX_SPRINT_3_REPORT.md` | `1379768` | 17/17 |

→ **First merge contributes baseline. Every subsequent merge sees no change for these files — no conflict possible.**

### 3b. Per-branch unique files (zero cross-branch collisions verified)

| Branch | Unique adds |
|--------|-------------|
| `fix/sprint-4a-framework-artifacts` | `framework_extensions/sprint_4a_refs.py`, `sprint_4a_results.csv`, `docs/QUEUE_XX_SPRINT_4A_REPORT.md` |
| `fix/sprint-4b-exec-fail-triage` | `framework_extensions/sprint_4b_args.py`, `sprint_4b_results.csv`, `docs/QUEUE_XX_SPRINT_4B_REPORT.md` |
| `fix/sprint-4c-non-runnable` | `framework_extensions/sprint_4c_args.py`, `sprint_4c_results.csv`, `docs/QUEUE_XX_SPRINT_4C_REPORT.md` |
| `verify/sprint-4d-custom-refs` | `framework_extensions/sprint_4d_handrolls.py`, `sprint_4d_results.csv`, `docs/QUEUE_XX_SPRINT_4D_REPORT.md` |
| `verify/sprint-4-chain-summary` | `docs/QUEUE_XX_SPRINT_4_CHAIN_SUMMARY.md` |
| `fix/sprint-5a-d-tier-math` | `framework_extensions/sprint_5a_triangulate.py`, `sprint_5a_results.csv`, `docs/QUEUE_XX_SPRINT_5A_REPORT.md` |
| `verify/sprint-5b-hand-rolls` | `framework_extensions/sprint_5b_handrolls.py`, `sprint_5b_results.csv`, `docs/QUEUE_XX_SPRINT_5B_REPORT.md` |
| `fix/sprint-5c-trin-proxy` | `docs/QUEUE_XX_SPRINT_5C_REPORT.md` |
| `refactor/sprint-5d-framework-v2` | `framework_extensions/sweep_v2.py`, `docs/QUEUE_XX_SPRINT_5D_REPORT.md` |
| `docs/sprint-5e-inventory` | `docs/QUEUE_XX_SPRINT_5E_REPORT.md` |
| `verify/sprint-5-chain-summary` | `docs/QUEUE_XX_SPRINT_5_CHAIN_SUMMARY.md` |
| `verify/sprint-6a-complex-pivots` | `framework_extensions/sprint_6a_handrolls.py`, `sprint_6a_results.csv`, `docs/QUEUE_XX_SPRINT_6A_REPORT.md` |
| `verify/sprint-6b-full-batch` | `framework_extensions/sprint_6b_handrolls.py`, `sprint_6b_results.csv`, `sprint_6b_needs_manual_review.csv`, `docs/QUEUE_XX_SPRINT_6B_REPORT.md` |
| `fix/sprint-6c-consec-higher-lows` | `docs/QUEUE_XX_SPRINT_6C_REPORT.md` |
| `docs/sprint-6d-chaikin-convention` | `docs/QUEUE_XX_SPRINT_6D_REPORT.md` |
| `docs/sprint-6e-dual-scoreboard` | `dual_scoreboard.csv`, `docs/QUEUE_XX_SPRINT_6E_REPORT.md` |
| `verify/sprint-6-chain-summary` | `docs/QUEUE_XX_SPRINT_6_CHAIN_SUMMARY.md` |

**Collision audit:** `0` paths appear in more than one branch's unique-tail set.

---

## 4. Conflict Assessment

Method: `git merge-tree --write-tree origin/main origin/<branch>` for each of the 17 branches.

```
CLEAN    fix/sprint-4a-framework-artifacts
CLEAN    fix/sprint-4b-exec-fail-triage
CLEAN    fix/sprint-4c-non-runnable
CLEAN    verify/sprint-4d-custom-refs
CLEAN    verify/sprint-4-chain-summary
CLEAN    fix/sprint-5a-d-tier-math
CLEAN    verify/sprint-5b-hand-rolls
CLEAN    fix/sprint-5c-trin-proxy
CLEAN    refactor/sprint-5d-framework-v2
CLEAN    docs/sprint-5e-inventory
CLEAN    verify/sprint-5-chain-summary
CLEAN    verify/sprint-6a-complex-pivots
CLEAN    verify/sprint-6b-full-batch
CLEAN    fix/sprint-6c-consec-higher-lows
CLEAN    docs/sprint-6d-chaikin-convention
CLEAN    docs/sprint-6e-dual-scoreboard
CLEAN    verify/sprint-6-chain-summary
```

**Result: 17/17 CLEAN.** Combined with bit-identical baseline + zero unique-path collisions, chain-merging in any order produces zero conflicts.

### Fast-forward feasibility

None of the 17 branches is FF-mergeable against current `origin/main` (origin/main has moved forward with 4 exec-fill-confirm commits that none of the sprint branches contain). Merge mechanics options:

- **(a) Squash-merge** — one squash commit per branch on main. Loses sub-sprint commit granularity but yields a flat, scannable main history. **Recommended** given each branch is purely additive test+docs and the granular commits inside are scaffolding.
- **(b) `--no-ff` merge** — preserves each branch's internal commit chain via merge commits. Better for forensic audit trail but adds 17 merge commits to main.
- **(c) Rebase-then-FF** — rebases each branch onto origin/main, then FF. Cleanest linear history. 17 rebases of work — high effort, low payoff vs (a).

---

## 5. Proposed Merge Order (SAFE branches — all 17)

Because every branch is independent (bit-identical baseline + non-overlapping uniques), order is technically free. The order below is chosen for **narrative coherence** in `git log` — sub-sprints land before their chain summary, sprints land chronologically.

```
1.  fix/sprint-4a-framework-artifacts
2.  fix/sprint-4b-exec-fail-triage
3.  fix/sprint-4c-non-runnable
4.  verify/sprint-4d-custom-refs
5.  verify/sprint-4-chain-summary           ← Sprint 4 chain-summary lands after 4a–4d
6.  fix/sprint-5a-d-tier-math
7.  verify/sprint-5b-hand-rolls
8.  fix/sprint-5c-trin-proxy
9.  refactor/sprint-5d-framework-v2
10. docs/sprint-5e-inventory
11. verify/sprint-5-chain-summary           ← Sprint 5 chain-summary lands after 5a–5e
12. verify/sprint-6a-complex-pivots
13. verify/sprint-6b-full-batch
14. fix/sprint-6c-consec-higher-lows
15. docs/sprint-6d-chaikin-convention
16. docs/sprint-6e-dual-scoreboard
17. verify/sprint-6-chain-summary           ← Sprint 6 chain-summary lands after 6a–6e
```

### Non-SAFE branches with HOLD recommendation
None. All 17 are SAFE.

---

## 6. Risk Callouts

1. **Origin/main has moved (4 new commits).** Local `main` at `90b3a6d` is behind `origin/main` at `6b8f555`. Founder should `git fetch && git checkout main && git pull --ff-only origin main` before any merge work — otherwise local merges build on stale main and a subsequent `git push` will be non-FF.
2. **No conflict ≠ no functional regression.** `git merge-tree` proves tree-merge safety, not test-run safety. After merging Sprint 4–6, the `backend/tests/queue_xx_sprint_3/` test framework should be smoke-run end-to-end on a feature branch before main push (CLAUDE.md: "Run FULL test suite, not subset").
3. **`refactor/sprint-5d-framework-v2` introduces `sweep_v2.py`.** This is a new file (no collision with `sweep.py`) — it's additive and inert until something imports it. Verify nothing in Sprint 6 already references `sweep_v2`; if so, ordering matters: 5d must merge before any Sprint 6 branch that uses it. (Spot-check: Sprint 6 branches' unique files don't appear to import sweep_v2 — recommend founder confirm before merging if there's any uncertainty.)
4. **None of the branches contain origin/main's exec fill-confirm fixes** (`b1c293d`, `841dbab`, `dd8c760`, `6b8f555`). Squash-merging will not regress those; rebasing branches onto current main is the safe path if any branch is taken off the "purely additive" assumption.
5. **No `.skip` / `xfail` / temp instrumentation introduced.** No scheduled-cleanup obligations created by this queue.

---

## 7. Recommended Next Steps for Founder

**Queue YY Phase B (separate prompt) should:**

1. Founder confirms merge mechanic preference: **squash (recommended)** vs `--no-ff` vs rebase-FF.
2. Founder approves the 17-branch order in §5 (or specifies a custom order).
3. Phase B agent:
   - `git fetch origin --prune`
   - `git checkout main && git pull --ff-only origin main`
   - Loop the 17 branches in approved order, applying chosen merge mechanic.
   - **STOP before main push.** Show full `git log origin/main..main --oneline` to founder. Founder gates push.
   - After founder gate: `git push origin main` (no force, no `--no-verify`).
   - **No EC2 deploy in Phase B** — this is test/docs only.

**Per CLAUDE.md "I gate every deploy"** — even though this queue touches zero production, the merge to `main` is a shared-state action requiring explicit founder approval before push.

---

## 8. Verification Commands (for founder to re-run independently)

```bash
# Re-verify per-branch SAFE category
git fetch origin --prune
for b in fix/sprint-4a-framework-artifacts fix/sprint-4b-exec-fail-triage fix/sprint-4c-non-runnable verify/sprint-4d-custom-refs verify/sprint-4-chain-summary fix/sprint-5a-d-tier-math verify/sprint-5b-hand-rolls fix/sprint-5c-trin-proxy refactor/sprint-5d-framework-v2 docs/sprint-5e-inventory verify/sprint-5-chain-summary verify/sprint-6a-complex-pivots verify/sprint-6b-full-batch fix/sprint-6c-consec-higher-lows docs/sprint-6d-chaikin-convention docs/sprint-6e-dual-scoreboard verify/sprint-6-chain-summary; do
  out_of_scope=$(git diff origin/main...origin/$b --name-only | grep -Ev '^(backend/tests/queue_xx_sprint_3/|docs/QUEUE_XX_)' || true)
  [ -z "$out_of_scope" ] && echo "SAFE  $b" || { echo "!! $b"; echo "$out_of_scope"; }
done

# Re-verify zero merge conflicts
for b in <branches>; do
  git merge-tree --write-tree origin/main origin/$b >/dev/null && echo "CLEAN $b" || echo "CONFLICT $b"
done
```

---

# Queue YY Phase A.5 — Pre-Merge Investigation Findings

Appended 2026-06-01. Resolves the 2 open risks from Phase A. Founder-approved
continuation to Phase 2 + 3 after Phase 1 sacred-zone disclosure.

---

## 9. Four commits on `origin/main` ahead of local `main` (Risk #1 resolved)

Range investigated: `90b3a6d..origin/main` (4 commits).

| # | SHA | Subject | Author | Date (IST) | Sacred? | Verdict |
|---|-----|---------|--------|------------|---------|---------|
| 1 | `b1c293d` | `fix(exec): authoritative fill-confirmation + scoped marketable-LIMIT` | Jayesh Parekh | 2026-06-01 15:08 | **YES** (`strategy_executor`, `direct_exit`, `dhan.py`, `brokers/base.py`) | **Founder-authored.** BSE-Ltd LPP rejection fix + BSE-89423ecc marketable-LIMIT scope. Co-Auth: Claude Opus 4.8. |
| 2 | `841dbab` | `fix(exec): reverse-phantom guard on confirm_fill timeout` | Jayesh Parekh | 2026-06-01 15:24 | **YES** (sacred + new `services/ambiguous_fill.py`, `workers/reconciliation_loop.py`) | **Founder-authored.** Follow-on to #1. Reverse-phantom-on-timeout guard. |
| 3 | `dd8c760` | `style(exec): make new fill-confirm code ruff-clean (surgical, no frozen reformat)` | Jayesh Parekh | 2026-06-01 15:49 | **YES** (lint-only on the same sacred files) | **Founder-authored.** Zero logic change; ruff fixup for #1 + #2. |
| 4 | `6b8f555` | `fix(exec): size entry position by CONFIRMED filled_qty, not requested (leg-1)` | Jayesh Parekh | 2026-06-01 18:18 | **YES** (`strategy_executor` only) | **Founder-authored.** Leg-1 sizing fix. Body explicitly: **"NOT for deploy/merge — release-cutover-6 is a separate gated step."** |

### Founder confirmation (2026-06-01, this queue)
> "4 commits on origin/main are founder-authored BSE-LTD fill-confirmation work — known, expected. Sprint branches disjoint from sacred zone — proceed. Commit #4 'NOT for deploy' caveat acknowledged — Phase B merge will NOT trigger EC2 deploy tonight; that's gated separately behind release-cutover-6."

### Implication for Phase B
- Sacred-zone changes (4 commits) and Queue YY test/docs additions (17 branches) touch **completely disjoint file sets** — re-verified via Phase A out-of-scope audit.
- Merging the 17 sprint branches into `origin/main` does **not** affect the deploy-gated cutover work. Phase B is a docs/tests merge only; **release-cutover-6** remains a separate, founder-gated deploy step.
- No additional merge risk introduced by the 4 commits.

---

## 10. `sweep_v2.py` dependency map (Risk #2 resolved)

### File existence (across all 17 branches)

| File-presence count | Branches |
|---|---|
| 1 — only branch with `sweep_v2.py` | `refactor/sprint-5d-framework-v2` |
| 0 — no `sweep_v2.py` | All other 16 branches |

### Reference-count audit
For each Sprint 6 branch, grep'd every file changed vs `origin/main` for the literal string `sweep_v2`:

```
verify/sprint-6a-complex-pivots       sweep_v2 refs = 0
verify/sprint-6b-full-batch           sweep_v2 refs = 0
fix/sprint-6c-consec-higher-lows      sweep_v2 refs = 0
docs/sprint-6d-chaikin-convention     sweep_v2 refs = 0
docs/sprint-6e-dual-scoreboard        sweep_v2 refs = 0
verify/sprint-6-chain-summary         sweep_v2 refs = 0
```

### Verdict
**Zero coupling.** No Sprint 6 branch imports, mentions, or otherwise references `sweep_v2`. The file is inert scaffolding contributed only by `refactor/sprint-5d-framework-v2`. **Ordering of 5d vs. any Sprint 6 branch is irrelevant.** The proposed order in §5 stands unchanged.

---

## 11. Per-branch commit counts (mechanic-choice input)

Method: `git log --oneline origin/main..origin/<branch> | wc -l`.

| Branch | Commits ahead of `origin/main` |
|---|---|
| All 17 branches | **2 each** |

### Anatomy of the 2 commits per branch

Every branch has the same pattern: **1 shared bootstrap commit + 1 unique sprint commit**.

- **Shared commit (identical across all 17 branches):**
  `729da1a verify(indicators): Queue XX Sprint 3 — autonomous sweep of 220 remaining indicators`
  → This contributes the 7-file bit-identical baseline (§3a). It's on every branch but **not on `origin/main`**. After the first branch merges, the next 16 see `729da1a` as a no-op.
- **Unique commit (one per branch):**
  e.g. `05b6cde verify(indicators): Sprint 4a — fix framework artifacts on 9 D-tier (4 promoted)`,
       `61b461c verify(indicators): Sprint 6b — 15 of 153 NEEDS_REF verified Tier A`,
       `8ff325f docs(queue-xx): Sprint 6 chain summary — 5 sub-sprints, 26 newly classified, 1 mid-chain fix`,
       etc.

### Mechanic-choice implication
With uniform 2-commit branches and a shared bootstrap commit:

- **Squash-merge** → 1 commit per branch on main = **17 new commits on main** (the `729da1a` bootstrap is folded into each — clean and uniform). **Recommended.**
- **`--no-ff` merge** → preserves the structure: main picks up 17 merge commits + 1 unique sprint-commit per branch + the shared `729da1a` once (subsequent merges no-op on tree). Net: **~35 commits** on main with 17 merge bubbles. Higher noise, fuller audit trail.
- **Rebase-then-FF** → rewrites every branch's history. Highest churn, lowest payoff (the 2-commit chains are already trivially linear). Not recommended.

---

## 12. Updated merge-order + mechanic recommendation (final, post A.5)

### Order
Unchanged from §5 (narrative chronology — sub-sprints before their chain summary):
```
4a → 4b → 4c → 4d → 4-chain-summary
5a → 5b → 5c → 5d → 5e → 5-chain-summary
6a → 6b → 6c → 6d → 6e → 6-chain-summary
```

### Mechanic
**Squash-merge.** Rationale:
- Every branch is purely additive test+docs (zero sacred/production overlap).
- Sub-sprint internal commit granularity adds little value on `main`'s log; the unique commit's subject line already summarizes the sub-sprint cleanly.
- Eliminates the duplicate `729da1a` parent-graph noise of 16 redundant merge commits under `--no-ff`.
- Easiest forensic read-back: one commit on main per sub-sprint, with a clear subject.

### Phase B execution sketch (for the next-queue agent)
```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main      # gets 6b8f555 (post-Phase-A.5 main)

for b in <17 branches in §5 order>; do
  git merge --squash origin/$b
  git commit -m "queue-xx: <subject from branch's unique commit>"
done

# STOP before push. Show:
git log origin/main..main --oneline
git diff origin/main..main --stat

# Founder gates push. Then:
git push origin main
# NO EC2 deploy. release-cutover-6 remains separately gated.
```

---

## 13. Hard-stop summary (Phase A.5)

| # | Trigger | Fired? | Resolution |
|---|---------|--------|-----------|
| 1 | Sprint branch touches sacred zone | NO | Phase A confirmed: 0/17 branches touch sacred zone |
| 2 | Sprint branch touches production code | NO | Phase A confirmed: 0/17 branches touch production code |
| 3 | Any of 4 origin/main commits touches sacred zone | **YES** | Resolved: founder-authored work, disjoint from sprint branches. Founder explicitly approved continuation. |
| 4 | Any of 4 origin/main commits touches production code | YES (same commits) | Same resolution. |
| 5 | Merge conflicts found | NO | Phase A: 17/17 CLEAN; bit-identical baseline; zero unique-path collisions |
| 6 | Git operation unexpected failure | NO | All commands clean |

---

## Founder Gate (final, post-A.5)

**This remains a proposal.** No merge attempted. No branch deleted. No main updated.

Awaiting explicit founder approval to launch **Queue YY Phase B** with:
- Order = §5 chronological (4a → … → 6-chain-summary)
- Mechanic = **squash-merge** (recommended) — confirm or override
- Push to `origin/main` gated by founder review of `git log origin/main..main --oneline`
- **NO EC2 deploy** — release-cutover-6 remains separately gated.

# Branch Cleanup Executed — May 18

**Branch:** `chore/branch-cleanup-executed`
**Date:** 2026-05-18
**Predecessor:** `chore/branch-cleanup-may18` (Queue I Task 5 dry-run script)
**Spec:** Queue III Task 6 — execute the cleanup with 25-per-run safety limit.

---

## TL;DR

25 fully-merged remote branches deleted from `origin/*` this run.
13 more candidates remain for a follow-up Task 6 run (deferred per
the 25-per-run safety limit).

**Audit step:** every candidate verified zero-orphan via
`git log origin/main..origin/<branch>` returning empty before
deletion. No `--force` operations. No unmerged branches touched.

---

## Branches deleted (25)

| # | Branch | Provenance |
|--:|---|---|
| 1 | `brain-v5-update` | Brain v5 indicator update |
| 2 | `chore/test-debt-batch-1` | Test debt cleanup |
| 3 | `cleanup/pre-launch-may18` | Pre-launch cleanup |
| 4 | `direct-exit-refactor` | Direct-exit code path refactor |
| 5 | `feat/cash-equity-expansion` | Equity catalog expansion |
| 6 | `feat/charting-module` | Chart module Phase A-D shipping |
| 7 | `feat/compliance-disclaimer` | Site-wide disclaimer footer |
| 8 | `feat/dhan-broker-reconnect-ux` | Dhan reconnect UX |
| 9 | `feat/drop-nifty-next-50` | Index list trim |
| 10 | `feat/e2e-launch-smoke-tests` | E2E smoke tests |
| 11 | `feat/equity-name-aliases` | Equity symbol aliases |
| 12 | `feat/fno-stocks-expansion` | F&O stocks expansion |
| 13 | `feat/frontend-chart` | Frontend chart module |
| 14 | `feat/help-faq-page` | Help/FAQ page |
| 15 | `feat/indicator-content-p1` | Indicator content phase 1 |
| 16 | `feat/indicator-service` | Indicator service abstraction |
| 17 | `feat/major-indices-fno-v2` | Major indices F&O v2 |
| 18 | `feat/phase-a-markers` | Phase A trade markers |
| 19 | `feat/phase-b-strategy-tester` | Phase B strategy tester |
| 20 | `feat/phase-c-prep` | Phase C deploy prep |
| 21 | `feat/phase-d-strategy-tester-panel` | Phase D strategy tester panel |
| 22 | `feat/phase-e-markers-overlay-cutover` | Phase E markers cutover |
| 23 | `feat/phase-f-indicator-audit` | Phase F indicator audit + BB stddev fix |
| 24 | `feat/safety-1-disable-legacy-webhook` | Safety pack 1: disable legacy webhook |
| 25 | `feat/safety-2-kill-switch-paper-gate` | Safety pack 2: kill-switch paper gate |

Verification protocol per branch:
```sh
git log origin/main..origin/<branch> --oneline | wc -l
# 0 = safe to delete; any other number = SKIP and surface in BLOCKERS
```

All 25 returned `0`. Deletion command:
```sh
git push origin --delete <branch>
```

Each succeeded with `deleted` confirmation from remote.

---

## Branches NOT deleted (13 remaining — deferred to follow-up run)

Per spec safety limit ("Maximum 25 branches deleted per run"), 13
candidates are queued for a second-pass cleanup:

```
feat/safety-3-go-live-paper-gate
feat/safety-4-data-isolation-fixes
feat/seed-loader-script
feat/strategy-template-system
feat/strategy-templates-phase-2-3
feature/ai-trading-system
fix/api-url-hardcode-fallback
fix/chart-ws-reconnect-ux
fix/migration-025-immutable-index
fix/picker-mount-bug-and-cleanup
fix/seed-loader-paths
fix/strategy-detail-clone
safety/server-state-2026-05-10
```

All 13 are verified zero-orphan but NOT deleted this run. To execute:
```sh
# Re-run the cleanup script with the same skip-pattern
./scripts/cleanup_merged_branches.sh --execute
```

---

## Branches deliberately SKIPPED (will NEVER be deleted)

Per skip-list:

| Branch | Reason |
|---|---|
| `feat/dockerfile-talib` | 107 commits unmerged (per memory) — DO NOT delete |
| `main` / `master` / `develop` | Default branches |
| `feat/backtest-engine-*` | Days 1-3 deployed dormant; Days 4-7 upcoming |
| `chore/branch-cleanup-executed` | This branch (active) |
| Queue III feature branches (all 6) | Active sprint work, not yet merged |

---

## Hard constraints honoured

- ✅ NO `--force` deletions
- ✅ NO deletion without prior dry-run verification (every candidate's
     `git log main..<branch>` returned empty)
- ✅ Maximum 25 branches deleted (safety limit observed; 13 deferred)
- ✅ NO skipping the audit step
- ✅ NO push to main, NO merge, NO destructive ops beyond authorised
     branch deletions

---

## Recoverability

Even after `git push origin --delete`, each branch's tip SHA lives in
GitHub's reflog for ~30 days. To restore:

```sh
# Restore by tip SHA (find via GitHub API or local reflog):
git fetch origin <sha>:refs/heads/<recovered-branch>
git push origin <recovered-branch>
```

The tips of all 25 deleted branches are documented in this file by
implication (`git log` on origin/main can locate each branch's last
merge commit). For exact SHAs, query GitHub's branch-deletion event
log at:
```
https://api.github.com/repos/jayeshparekh81-oss/trading-bridge/activity
```

---

## See also

- `BLOCKERS_BRANCH_CLEANUP_FINAL.md` — open questions
- `scripts/cleanup_merged_branches.sh` — the dry-run-by-default script
  used as the audit baseline
- `docs/MASTER_ROADMAP.md` — current Phase 1-12 status

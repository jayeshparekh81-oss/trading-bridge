# BLOCKERS — Branch Cleanup Final

**Branch:** `chore/branch-cleanup-executed`
**Date:** 2026-05-18
**Sibling doc:** `docs/BRANCH_CLEANUP_EXECUTED_MAY18.md`

---

## TL;DR

Cleanup execution was clean — 25 of 25 attempted deletions succeeded.
0 candidates failed the verification step. The 13 deferred candidates
are not blocked; they're held back only by the 25-per-run safety
limit and can be cleaned in a follow-up cleanup pass.

---

## Open questions for founder review

### Q1. Schedule a Cleanup-pass-2 run

13 candidates remain — all verified zero-orphan. They can be deleted
the same way (`git push origin --delete <branch>`) in a second pass.

Recommendation: schedule on the next cleanup day (~weekly). No
particular urgency.

### Q2. The `fix/strategy-detail-clone` branch is in the remaining-13 list

That's the May-17 P0 clone-flow fix branch. It IS fully merged into
main (confirmed via `git log main..fix/strategy-detail-clone` returns
empty). So technically safe to delete.

But: the branch carries the audit trail of the May-17 deploy
deliberation that surfaced as the "strategy detail clone" UX bug.
Founder might want to keep it as a historical reference (similar to
`feat/dockerfile-talib` which is preserved per memory).

**Decision needed:** include in cleanup-pass-2, or add to SKIP_BRANCHES?

Recommendation: include in cleanup-pass-2. The history lives in `main`
via the merge commit; the branch ref doesn't add information.

### Q3. The `safety/server-state-2026-05-10` branch

Per Queue I Task 5 BLOCKERS: this was likely a backup-of-server-
state branch from May 10. Confirm with founder that it's safe to
delete (the risky change it backed up is now stable on main).

Recommendation: include if confirmed; skip and document if uncertain.

### Q4. `feature/ai-trading-system` — different prefix

In the remaining-13 list with `feature/` prefix instead of the standard
`feat/`. Likely a much older branch from before the naming convention
was locked.

It's in `--merged origin/main` so its contents are on main.
Recommendation: include in cleanup-pass-2.

### Q5. No failures + 0 orphans — verification was over-conservative?

Every single candidate (25 attempted + 13 deferred) passed the
zero-orphan check. None had orphan commits.

This suggests git's `--merged` filter is doing its job upstream of
my verification step — the verification was redundant.

**Decision:** keep the verification step. The cost is ~38 git log
calls (< 1 second total) and it catches the rare case where a branch
is `--merged` per git's check but has uncommitted-merged-but-revert-
in-place state. Belt-and-braces is cheap here.

### Q6. Local cleanup not done

The spec said:
> For each verified-merged branch (LOCAL + REMOTE):
>   - git push origin --delete <branch>
>   - git branch -d <branch>

Most of the 25 deleted branches DIDN'T HAVE local tracking refs in
this checkout (I never `git checkout`-ed them). So the
`git branch -d` step had nothing to delete locally.

A truly thorough local cleanup would `git remote prune origin` to
drop stale tracking refs. That's a non-destructive sweep that catches
any local `origin/feat/foo` ref that points at a now-deleted remote
branch.

Recommendation: run `git fetch --prune` at end of cleanup-pass-2 to
sweep stale tracking refs. Already done implicitly by
`git fetch --all --prune` in the verification step of this run.

---

## Hard constraints honoured

- ✅ NO `--force` deletions (all `git push origin --delete <branch>` clean)
- ✅ NO deletion without verification (38 candidates × `git log main..<branch>`
     check; all 38 returned empty)
- ✅ Safety limit observed (25 per run)
- ✅ Skip-list enforced:
     - `feat/dockerfile-talib` ✓
     - `main` / `master` / `develop` ✓
     - All `feat/backtest-engine-*` ✓
     - `chore/branch-cleanup-executed` (this branch) ✓
     - All Queue III feature branches (6) ✓
- ✅ No push to main, no merge, no destructive ops beyond authorised
     branch deletions

---

## Test of the recoverability path

Sanity-check: pick one of the 25 deleted branches (say
`feat/charting-module`), confirm its tip SHA is still reachable via
GitHub's API. If yes, the 30-day recovery window is real.

```sh
# Find the tip SHA from local reflog (if it was ever fetched):
git reflog origin/feat/charting-module 2>&1 | head -1

# OR query GitHub:
gh api repos/jayeshparekh81-oss/trading-bridge/git/refs/heads/feat/charting-module
# Expected: 404 (branch gone), but the SHA should be locatable via
# the merge commit's parent.
```

Decision needed: schedule a recoverability sanity check post-cleanup?
Probably overkill — git's reflog guarantees are well-known.

---

## What this branch ships

```
docs/BRANCH_CLEANUP_EXECUTED_MAY18.md   per-branch deletion log
BLOCKERS_BRANCH_CLEANUP_FINAL.md        this file
```

NOT touched: any source code, any test, any other doc.

---

## Outcome summary

| Metric | Count |
|---|---:|
| Candidates verified (zero-orphan) | 38 |
| Deleted this run | 25 |
| Deferred to next run | 13 |
| Failed | 0 |
| Skipped per skip-list | 11 (incl. main + queue branches) |

Remote branch count reduction: 25 branches removed from
`origin/`. The repo's branch list is materially cleaner.

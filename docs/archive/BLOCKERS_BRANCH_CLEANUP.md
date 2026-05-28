# BLOCKERS — Branch Cleanup (May 18)

**Date:** 2026-05-17 (overnight queue Task 5 of 5)
**Branch:** `chore/branch-cleanup-may18`

---

## Open questions for founder review

### 1. The 17-vs-35 discrepancy (BLOCKS `--execute`)

The Task 5 spec stated **"delete 17 specific merged branches"** but that
explicit list was not preserved across context compaction. The script's
dry-run identified **35 candidates** that are fully merged into
`origin/main` and not in the safety allowlist.

**Action required before `--execute`:**

- Founder provides the original 17-branch list, OR
- Founder confirms the 35-branch superset is fine to delete, OR
- Founder edits `SKIP_BRANCHES` in `scripts/cleanup_merged_branches.sh`
  to add back any of the 18 extras that should be preserved.

Without this confirmation, the script stays in dry-run and **no
branches are deleted on this branch.** This is the right blast-radius
posture for an irreversible destructive operation under uncertainty.

### 2. `feat/chart-partial-candle-publish` was pruned during fetch

During Task 5's `git fetch --all --prune`, output included:

```
- [deleted]         (none)             -> origin/feat/chart-partial-candle-publish
```

Meaning that branch was deleted on the remote between the queue spec
being written and Task 5 running. It's in `SKIP_BRANCHES` defensively
but is now a no-op for the script. Action: remove from `SKIP_BRANCHES`
during the next allowlist edit, since the protection serves no purpose
once the remote branch is already gone.

### 3. `hotfix/enum-values-callable` status

Listed in remote branches but not in the `--merged` set — meaning it
has commits not on main. Either (a) it's still in active development,
or (b) it shipped via a squash-merge so git's merge-base detection
doesn't recognise it as merged. Founder confirms which.

If (b), it can be safely deleted via direct `git push origin --delete
hotfix/enum-values-callable` — the script's `--merged` filter is
conservative and won't sweep it.

### 4. Should the script delete local tracking branches too?

The script only deletes remote branches via `git push origin --delete`.
The user's local `git branch` will still show the old branch names
until `git fetch --prune` runs. This is the safer choice (operator
controls local cleanup) but the script could be extended with a
`--prune-local` flag if useful.

Recommendation: leave as-is. Founder's local checkout state is no
business of an automation script.

### 5. The `safety/server-state-2026-05-10` branch

In the candidate list. Naming suggests it was a "save the server state
before this risky change" backup branch. Confirm with founder that
it's safe to delete (e.g. the risky change is now stable on main, no
need to revert).

If unsure, add to `SKIP_BRANCHES` and leave for a later cleanup.

### 6. Long-running `feature/ai-trading-system` (vs `feat/*`)

In the candidate list with a different prefix (`feature/` instead of
`feat/`). Likely a much older branch. Confirm with founder that its
contents fully landed on main — git says yes (it's `--merged`) but a
sanity check is cheap.

---

## What this branch ships

```
scripts/cleanup_merged_branches.sh           safe dry-run-by-default deletion script
docs/BRANCH_CLEANUP_MAY18.md                 procedure + candidate list
BLOCKERS_BRANCH_CLEANUP.md                   this file
```

NOT executed: any branch deletion. The script is committed in dry-run
default mode; founder runs `--execute` after confirming the list.

## What needs to happen post-review

1. Founder provides the original 17-branch list (or confirms the
   35-branch superset is fine).
2. Founder edits `SKIP_BRANCHES` in the script if any of the 35 should
   be preserved.
3. Founder runs `./scripts/cleanup_merged_branches.sh` (dry-run) to
   visually confirm the final candidate list.
4. Founder runs `./scripts/cleanup_merged_branches.sh --execute` to
   actually delete.
5. Optional: founder runs `git fetch --prune` locally to drop stale
   tracking refs.

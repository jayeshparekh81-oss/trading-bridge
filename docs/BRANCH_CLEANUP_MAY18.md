# Branch cleanup — May 18 pre-launch hygiene

**Branch:** `chore/branch-cleanup-may18`
**Date:** 2026-05-17 (overnight queue Task 5 of 5)
**Tool:** `scripts/cleanup_merged_branches.sh`

## Why

The repo accumulated 35+ remote branches that are fully merged into
`origin/main` — Phase 1 through Phase D sprint branches, safety-pack
sub-branches, equity/F&O expansion branches, hotfix branches. They
clutter the GitHub branch picker, slow down `git fetch --all`, and
make it harder to spot in-flight feature branches in the web UI.

Pre-launch hygiene: tidy them so the May-18 launch state is legible.

## What the script does

`scripts/cleanup_merged_branches.sh`:

- Dry-run by default. `--execute` flips to actual deletion.
- Operates only on branches fully `--merged` into `origin/main` — any
  branch with commits not on main is automatically excluded by git.
- Honours a `SKIP_BRANCHES` allowlist baked into the script. Edit it
  before running `--execute` if you want to add/remove protected branches.
- Iterates deletions one at a time and aborts the batch on any failure
  (so a partial cleanup doesn't strand the repo in an unknown state).
- Sleeps 5s before the first deletion so a misfire can be Ctrl-C'd.

## Who gets preserved

The `SKIP_BRANCHES` allowlist in the script:

| Branch | Reason |
|---|---|
| `main`, `master`, `develop` | Default-protected, always |
| `feat/dockerfile-talib` | Explicit founder ask — preserve as historical reference |
| `feat/backtest-engine-spec` | Active queue-night Task 1 deliverable |
| `feat/phase-2-template-configs` | Active queue-night Task 2 deliverable |
| `feat/integration-test-framework` | Active queue-night Task 3 deliverable |
| `feat/strategy-detail-audit` | Active queue-night Task 4 deliverable |
| `chore/branch-cleanup-may18` | This branch itself |
| `feat/chart-partial-candle-publish` | Possibly active (pre-empted from origin during fetch — needs confirmation) |
| `hotfix/enum-values-callable` | Likely active hotfix — needs confirmation before sweep |

## Candidates for deletion (dry-run output)

The script's dry-run on `origin/*` merged candidates against
`SKIP_BRANCHES` returned 35 branches that are safe to delete:

```
brain-v5-update
chore/test-debt-batch-1
cleanup/pre-launch-may18
direct-exit-refactor
feat/cash-equity-expansion
feat/charting-module
feat/compliance-disclaimer
feat/dhan-broker-reconnect-ux
feat/drop-nifty-next-50
feat/e2e-launch-smoke-tests
feat/equity-name-aliases
feat/fno-stocks-expansion
feat/frontend-chart
feat/help-faq-page
feat/indicator-service
feat/major-indices-fno-v2
feat/phase-a-markers
feat/phase-b-strategy-tester
feat/phase-c-prep
feat/phase-d-strategy-tester-panel
feat/phase-e-markers-overlay-cutover
feat/phase-f-indicator-audit
feat/safety-1-disable-legacy-webhook
feat/safety-2-kill-switch-paper-gate
feat/safety-3-go-live-paper-gate
feat/safety-4-data-isolation-fixes
feat/seed-loader-script
feat/strategy-template-system
feature/ai-trading-system
fix/api-url-hardcode-fallback
fix/chart-ws-reconnect-ux
fix/migration-025-immutable-index
fix/picker-mount-bug-and-cleanup
fix/seed-loader-paths
safety/server-state-2026-05-10
```

35 candidates total — the original Task 5 spec mentioned **17 specific
merged branches**. That list was not preserved across context
compaction this session. The 35-branch dry-run is broader than the
original ask and **MUST be reconciled with founder's original list
before `--execute` runs.** See BLOCKERS.

## Procedure (when ready to execute)

1. **Confirm the candidate list** against the founder's intended 17.
   Edit `SKIP_BRANCHES` to add back any branch that should be preserved.

2. Re-run dry-run:

   ```sh
   ./scripts/cleanup_merged_branches.sh
   ```

   Verify the printed `git push origin --delete <branch>` commands are
   exactly what's expected.

3. Execute:

   ```sh
   ./scripts/cleanup_merged_branches.sh --execute
   ```

4. The script will pause 5s, then delete one at a time. Any non-zero
   exit aborts the batch — investigate before retrying.

5. After deletion, run `git fetch --prune` locally to drop the stale
   tracking refs.

## Recoverability

Even after `git push origin --delete`, each branch's tip commit lives
in GitHub's reflog for ~30 days and can be restored via:

```sh
# Find the deleted ref via GitHub API or local reflog
git fetch origin <sha>:refs/heads/<recovered-branch>
git push origin <recovered-branch>
```

So deletion is reversible within the 30-day window — provided you know
the SHA of the deleted branch tip. The dry-run output above includes
branch names but not SHAs; run

```sh
git ls-remote origin
```

before deletion if SHA recovery insurance is needed.

## What this branch ships

```
scripts/cleanup_merged_branches.sh   safe dry-run-by-default deletion script
docs/BRANCH_CLEANUP_MAY18.md         this doc
BLOCKERS_BRANCH_CLEANUP.md           open questions
```

NO branches actually deleted on this branch — Task 5 stops at the
"founder confirms list, then runs `--execute`" boundary.

## See also

- `BLOCKERS_BRANCH_CLEANUP.md` — outstanding questions
- `scripts/cleanup_merged_branches.sh --list-skip` — current SKIP_BRANCHES contents

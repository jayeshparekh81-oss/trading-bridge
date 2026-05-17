#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# cleanup_merged_branches.sh
#
# Delete remote feature branches that have been merged into origin/main.
# Safety posture: DRY-RUN by default. Pass --execute to actually delete.
#
# Why this script exists:
#   The 35+ merged branches at origin/* are mostly Phase 1-D sprint
#   branches that are now redundant — main has all their commits. Keeping
#   them around clutters branch UIs in the GitHub web view and tab-
#   completes locally. After merge they only matter if you need to look
#   at the original PR thread (which GitHub preserves whether the branch
#   exists or not).
#
# What it does:
#   1. Fetches all remotes (--prune) so the local view of remote branches
#      is current.
#   2. Lists every branch in origin/** that is fully merged into
#      origin/main (= every commit on the branch is also on main).
#   3. Filters out the SKIP_BRANCHES list (e.g. main, feat/dockerfile-talib,
#      and any currently-active feature branches the founder wants
#      preserved as historical reference).
#   4. In dry-run mode (default), prints the list of `git push origin
#      --delete <branch>` commands that WOULD run.
#   5. In --execute mode, runs those commands one at a time, pausing on
#      any non-zero exit code.
#
# Usage:
#     ./scripts/cleanup_merged_branches.sh             # dry-run, prints commands
#     ./scripts/cleanup_merged_branches.sh --execute   # actually deletes
#     ./scripts/cleanup_merged_branches.sh --list-skip # show SKIP_BRANCHES list
#
# Hard guardrails baked in:
#   - main, master, develop are ALWAYS in SKIP_BRANCHES (even if --merged).
#   - The user's explicit ask is to preserve feat/dockerfile-talib.
#   - Active in-flight branches (the queue-night branches) are in SKIP_BRANCHES
#     so they aren't accidentally swept by a clean run from a future
#     teammate who didn't know they're still under review.
#   - --execute prompts for confirmation with a 5-second pause before
#     destroying anything.
#
# What this script will NOT do:
#   - Delete local branches (use git branch -D manually).
#   - Force-delete unmerged branches (only --merged origin/main candidates).
#   - Touch any branch matching the SKIP_BRANCHES allowlist.
# ─────────────────────────────────────────────────────────────────────────

set -euo pipefail

REMOTE="${REMOTE:-origin}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"

# Branches to NEVER delete. Edit this list before running --execute.
SKIP_BRANCHES=(
  # Default-protected
  "main"
  "master"
  "develop"

  # User-specified preservation (Task 5 queue spec)
  "feat/dockerfile-talib"

  # Active queue-night branches (Task 1-4) — preserve until merged
  "feat/backtest-engine-spec"
  "feat/phase-2-template-configs"
  "feat/integration-test-framework"
  "feat/strategy-detail-audit"
  "chore/branch-cleanup-may18"

  # Other potentially-live branches as of 2026-05-17 — confirm before
  # removing from this list:
  "feat/chart-partial-candle-publish"
  "hotfix/enum-values-callable"
)

DRY_RUN=1
LIST_SKIP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --list-skip) LIST_SKIP=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ "$LIST_SKIP" -eq 1 ]]; then
  echo "SKIP_BRANCHES (always preserved):"
  printf '  %s\n' "${SKIP_BRANCHES[@]}"
  exit 0
fi

echo "==> Fetching ${REMOTE} (with prune)..."
git fetch "$REMOTE" --prune

echo "==> Identifying remote branches merged into ${REMOTE}/${MAIN_BRANCH}..."
merged=()
while IFS= read -r line; do
  br=$(echo "$line" | sed 's/^[* ]*//' | sed "s|^${REMOTE}/||")
  [[ -z "$br" ]] && continue
  [[ "$br" == "$MAIN_BRANCH" ]] && continue
  [[ "$br" == "HEAD -> "* ]] && continue
  merged+=("$br")
done < <(git branch -r --merged "${REMOTE}/${MAIN_BRANCH}" | grep -v 'HEAD ->')

candidates=()
skipped=()
for br in "${merged[@]}"; do
  skip=0
  for skip_br in "${SKIP_BRANCHES[@]}"; do
    if [[ "$br" == "$skip_br" ]]; then
      skip=1
      break
    fi
  done
  if [[ "$skip" -eq 1 ]]; then
    skipped+=("$br")
  else
    candidates+=("$br")
  fi
done

echo
echo "Merged into ${REMOTE}/${MAIN_BRANCH}: ${#merged[@]}"
echo "Skipped (preserved):              ${#skipped[@]}"
echo "Will delete:                      ${#candidates[@]}"
echo

if [[ ${#skipped[@]} -gt 0 ]]; then
  echo "── PRESERVED (in SKIP_BRANCHES) ──"
  printf '  %s\n' "${skipped[@]}"
  echo
fi

if [[ ${#candidates[@]} -eq 0 ]]; then
  echo "Nothing to delete. Exit."
  exit 0
fi

echo "── CANDIDATES FOR DELETION ──"
printf '  %s\n' "${candidates[@]}"
echo

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "── DRY-RUN — commands that would execute ──"
  for br in "${candidates[@]}"; do
    echo "  git push ${REMOTE} --delete ${br}"
  done
  echo
  echo "Re-run with --execute to actually delete. (Or run the listed"
  echo "commands manually one at a time if you want finer control.)"
  exit 0
fi

# --execute path — confirm + delete one at a time.
echo "── EXECUTING DELETIONS ──"
echo "Sleeping 5s — Ctrl-C now to abort."
sleep 5
for br in "${candidates[@]}"; do
  echo
  echo "Deleting ${REMOTE}/${br}..."
  if git push "$REMOTE" --delete "$br"; then
    echo "  ok"
  else
    echo "  FAILED — aborting batch to be safe. Inspect manually."
    exit 1
  fi
done
echo
echo "All ${#candidates[@]} branches deleted."

#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Diff-scoped lint/format gate (BLOCKING on PRs)
# ---------------------------------------------------------------------------
# Runs ruff (backend *.py) and eslint + prettier (frontend) ONLY on files
# changed vs a base ref — so new/changed code must be clean, while the legacy
# backlog in untouched files is ignored.
#
#   * backend changed *.py        -> ruff check + ruff format --check (block)
#   * frontend changed JS/TS      -> eslint (block)
#   * frontend changed files      -> prettier --check (block, --ignore-unknown)
#   * no changed files in a group -> that check is skipped (green)
#
# mypy / tsc are intentionally NOT here — they are whole-program and not
# reliable under diff scope; they stay report-only in the workflow.
#
# Usage:  ci/lint_changed.sh [BASE_REF]      (default: origin/main, env BASE_REF)
#         BASE_REF=main ci/lint_changed.sh
# Diff is computed as BASE_REF...HEAD (changes introduced on this branch).
# ---------------------------------------------------------------------------
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE_REF="${1:-${BASE_REF:-origin/main}}"

if ! git rev-parse --verify --quiet "${BASE_REF}^{commit}" >/dev/null; then
  echo "::error:: base ref '${BASE_REF}' not found — fetch it first (e.g. git fetch origin main)."
  exit 2
fi

echo "== diff-scoped lint/format gate =="
echo "base ref: ${BASE_REF}"
echo "diff    : ${BASE_REF}...HEAD (changes introduced on this branch)"
echo

# Collect changed (Added/Copied/Modified/Renamed) files, repo-relative.
BACKEND_PY=()
FRONTEND_LINT=()   # eslint targets (JS/TS only)
FRONTEND_FMT=()    # prettier targets (any frontend file; --ignore-unknown filters)

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  [[ -f "$f" ]] || continue   # skip files that no longer exist on disk
  case "$f" in
    backend/*.py)
      BACKEND_PY+=("${f#backend/}")
      ;;
    frontend/*)
      FRONTEND_FMT+=("${f#frontend/}")
      case "$f" in
        *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) FRONTEND_LINT+=("${f#frontend/}") ;;
      esac
      ;;
  esac
done < <(git diff --name-only --diff-filter=ACMR "${BASE_REF}...HEAD")

rc=0

# ----- backend: ruff check + ruff format --check (BLOCKING) -----
if (( ${#BACKEND_PY[@]} )); then
  echo "--- backend ruff check (${#BACKEND_PY[@]} changed *.py) ---"
  ( cd backend && ruff check "${BACKEND_PY[@]}" ) || rc=1
  echo "--- backend ruff format --check ---"
  ( cd backend && ruff format --check "${BACKEND_PY[@]}" ) || rc=1
else
  echo "backend: no changed *.py — skipped (green)"
fi
echo

# ----- frontend: eslint (BLOCKING) -----
if (( ${#FRONTEND_LINT[@]} )); then
  echo "--- frontend eslint (${#FRONTEND_LINT[@]} changed JS/TS) ---"
  ( cd frontend && npx eslint "${FRONTEND_LINT[@]}" ) || rc=1
else
  echo "frontend eslint: no changed JS/TS — skipped (green)"
fi
echo

# ----- frontend: prettier --check (BLOCKING) -----
if (( ${#FRONTEND_FMT[@]} )); then
  echo "--- frontend prettier --check (${#FRONTEND_FMT[@]} changed file(s)) ---"
  ( cd frontend && npx --yes prettier@3 --check --ignore-unknown "${FRONTEND_FMT[@]}" ) || rc=1
else
  echo "frontend prettier: no changed files — skipped (green)"
fi

echo
if (( rc )); then
  echo "::error:: diff-scoped lint/format gate FAILED on changed files."
  echo "Run ci/fix_changed.sh ${BASE_REF} to auto-fix your own changes, then re-commit."
else
  echo "OK: changed files pass lint/format (or nothing to check)."
fi
exit "$rc"

#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Auto-fix lint/format on YOUR changed files (mirror of ci/lint_changed.sh)
# ---------------------------------------------------------------------------
# Cleans only files changed vs a base ref so you can satisfy the diff-scoped
# gate before pushing — legacy/untouched files are left alone (no repo-wide
# reformat).
#
#   * backend changed *.py   -> ruff check --fix + ruff format
#   * frontend changed JS/TS  -> eslint --fix
#   * frontend changed files  -> prettier --write (--ignore-unknown)
#
# Usage:  ci/fix_changed.sh [BASE_REF]      (default: origin/main, env BASE_REF)
# After running, review `git diff` and re-commit the cleaned changes.
# ---------------------------------------------------------------------------
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE_REF="${1:-${BASE_REF:-origin/main}}"

if ! git rev-parse --verify --quiet "${BASE_REF}^{commit}" >/dev/null; then
  echo "error: base ref '${BASE_REF}' not found — fetch it first." >&2
  exit 2
fi

echo "== auto-fix changed files =="
echo "base ref: ${BASE_REF} (diff ${BASE_REF}...HEAD, plus uncommitted)"
echo

BACKEND_PY=()
FRONTEND_LINT=()
FRONTEND_FMT=()

# Include both committed branch changes AND uncommitted working-tree changes so
# the fixer is useful before the commit too.
{ git diff --name-only --diff-filter=ACMR "${BASE_REF}...HEAD"
  git diff --name-only --diff-filter=ACMR HEAD
  git diff --name-only --diff-filter=ACMR --cached
} | sort -u | while IFS= read -r f; do printf '%s\n' "$f"; done > /tmp/_fix_changed_list.txt || true

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  [[ -f "$f" ]] || continue
  case "$f" in
    backend/*.py) BACKEND_PY+=("${f#backend/}") ;;
    frontend/*)
      FRONTEND_FMT+=("${f#frontend/}")
      case "$f" in
        *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) FRONTEND_LINT+=("${f#frontend/}") ;;
      esac
      ;;
  esac
done < /tmp/_fix_changed_list.txt
rm -f /tmp/_fix_changed_list.txt

if (( ${#BACKEND_PY[@]} )); then
  echo "--- backend ruff check --fix (${#BACKEND_PY[@]} file(s)) ---"
  ( cd backend && ruff check --fix "${BACKEND_PY[@]}" ) || true
  echo "--- backend ruff format ---"
  ( cd backend && ruff format "${BACKEND_PY[@]}" ) || true
else
  echo "backend: no changed *.py"
fi
echo

if (( ${#FRONTEND_LINT[@]} )); then
  echo "--- frontend eslint --fix (${#FRONTEND_LINT[@]} file(s)) ---"
  ( cd frontend && npx eslint --fix "${FRONTEND_LINT[@]}" ) || true
else
  echo "frontend eslint: no changed JS/TS"
fi
echo

if (( ${#FRONTEND_FMT[@]} )); then
  echo "--- frontend prettier --write (${#FRONTEND_FMT[@]} file(s)) ---"
  ( cd frontend && npx --yes prettier@3 --write --ignore-unknown "${FRONTEND_FMT[@]}" ) || true
else
  echo "frontend prettier: no changed files"
fi

echo
echo "Done. Review 'git diff' and re-commit the cleaned changes."

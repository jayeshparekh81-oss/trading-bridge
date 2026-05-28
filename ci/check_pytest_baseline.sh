#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Backend pytest baseline gate
# ---------------------------------------------------------------------------
# Runs the full backend suite and compares the set of failing/erroring test
# nodeids against the documented allow-list in ci/known_failures.txt.
#
#   * NEW failures (present now, absent from the allow-list)  -> exit 1 (block)
#   * Known failures (present now AND in the allow-list)      -> tolerated
#   * Fixed failures (in the allow-list but now passing)      -> notice only
#
# This lets the workflow be GREEN on the current code while still blocking any
# genuinely new regression. The legacy 44-failure debt is paid down by deleting
# lines from ci/known_failures.txt as each is fixed (it then becomes a floor).
#
# Usage (CI):    PYTEST_BIN=python      ci/check_pytest_baseline.sh
# Usage (local): PYTEST_BIN=backend/.venv/bin/python ci/check_pytest_baseline.sh
#                (run from the repo root)
# ---------------------------------------------------------------------------
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KNOWN_FILE="${REPO_ROOT}/ci/known_failures.txt"
BACKEND_DIR="${REPO_ROOT}/backend"
PYTEST_BIN="${PYTEST_BIN:-python}"

# The suite runs with cwd=backend, so a *relative* PYTEST_BIN that contains a
# slash (e.g. backend/.venv/bin/python) would break. Resolve it against the
# repo root up-front. A bare command on PATH (e.g. "python") is left as-is.
if [[ "$PYTEST_BIN" == */* && "$PYTEST_BIN" != /* ]]; then
  PYTEST_BIN="${REPO_ROOT}/${PYTEST_BIN}"
fi

CURRENT_RAW="$(mktemp)"
CURRENT_FAILS="$(mktemp)"
KNOWN_FAILS="$(mktemp)"
trap 'rm -f "$CURRENT_RAW" "$CURRENT_FAILS" "$KNOWN_FAILS"' EXIT

echo "== backend pytest baseline gate =="
echo "repo root : ${REPO_ROOT}"
echo "pytest    : ${PYTEST_BIN} -m pytest (cwd=${BACKEND_DIR})"
echo "allow-list: ${KNOWN_FILE}"
echo

if [[ ! -f "$KNOWN_FILE" ]]; then
  echo "::error:: known-failures allow-list not found: ${KNOWN_FILE}"
  exit 2
fi

# Run the suite. -o addopts="" drops the coverage addopts from pyproject so the
# gate doesn't depend on coverage tooling/thresholds. We never trust pytest's
# own exit code here (failures are expected); we diff nodeids instead.
(
  cd "$BACKEND_DIR" &&
  "$PYTEST_BIN" -m pytest -q -ra --tb=no -o addopts="" -p no:cacheprovider
) > "$CURRENT_RAW" 2>&1 || true

# Surface the suite tail so the run is debuggable from the Actions log.
tail -n 5 "$CURRENT_RAW"
echo

# Did pytest actually run? Guard against a collection/import crash that would
# otherwise yield "0 failures" and silently pass the gate.
if ! grep -qE "(passed|failed|error|no tests ran)" "$CURRENT_RAW"; then
  echo "::error:: pytest did not produce a recognizable summary line — treating as a hard failure."
  echo "----- full output -----"
  cat "$CURRENT_RAW"
  exit 2
fi

# Extract failing/erroring nodeids: "FAILED tests/x.py::test - reason" -> "tests/x.py::test"
grep -E "^(FAILED|ERROR)" "$CURRENT_RAW" \
  | sed -E 's/^(FAILED|ERROR) //; s/ - .*$//' \
  | sort -u > "$CURRENT_FAILS"

# Normalize the allow-list (strip comments + blank lines).
grep -vE '^[[:space:]]*(#|$)' "$KNOWN_FILE" | sort -u > "$KNOWN_FAILS"

current_count="$(wc -l < "$CURRENT_FAILS" | tr -d ' ')"
known_count="$(wc -l < "$KNOWN_FAILS" | tr -d ' ')"
echo "current failures: ${current_count}"
echo "known failures  : ${known_count}"

# FIXED = known - current (informational, never blocks).
fixed="$(comm -13 "$CURRENT_FAILS" "$KNOWN_FAILS")"
if [[ -n "$fixed" ]]; then
  echo
  echo "::notice:: These known-failing tests now PASS — remove them from ci/known_failures.txt to lock the win:"
  echo "$fixed" | sed 's/^/  /'
fi

# NEW = current - known (blocks the build).
new="$(comm -23 "$CURRENT_FAILS" "$KNOWN_FAILS")"
if [[ -n "$new" ]]; then
  echo
  echo "::error:: NEW test failures introduced (not in ci/known_failures.txt):"
  echo "$new" | sed 's/^/  /'
  echo
  echo "If a new failure is genuinely pre-existing/unrelated, add its nodeid to"
  echo "ci/known_failures.txt with justification. Otherwise, fix the regression."
  exit 1
fi

echo
echo "OK: no new failures beyond the documented baseline."
exit 0

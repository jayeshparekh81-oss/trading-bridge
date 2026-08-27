#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Frontend vitest baseline gate
# ---------------------------------------------------------------------------
# Runs the full frontend suite and compares the set of failing test ids against
# the documented allow-list in ci/known_failures_vitest.txt.
#
#   * NEW failures (present now, absent from the allow-list)  -> exit 1 (block)
#   * Known failures (present now AND in the allow-list)      -> tolerated
#   * Fixed failures (in the allow-list but now passing)      -> notice only
#
# This is the frontend twin of ci/check_pytest_baseline.sh and follows the same
# calibrated-green contract: GREEN on the current code, while still blocking any
# genuinely new regression. The legacy 4-failure debt is paid down by deleting
# lines from ci/known_failures_vitest.txt as each is fixed (it then becomes a
# floor).
#
# Test id format: <path-relative-to-frontend>::<full test name>
#   e.g. tests/templates/TemplateCard.test.tsx::TemplateCard — active-equity state Clone & Use button is enabled and fires onClone
#
# Usage (CI):    ci/check_vitest_baseline.sh
# Usage (local): ci/check_vitest_baseline.sh      (run from anywhere; deps must
#                                                  be installed in frontend/)
# ---------------------------------------------------------------------------
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KNOWN_FILE="${REPO_ROOT}/ci/known_failures_vitest.txt"
FRONTEND_DIR="${REPO_ROOT}/frontend"

REPORT="$(mktemp)"   # plain mktemp: `-t` differs between BSD/GNU
CURRENT_FAILS="$(mktemp)"
KNOWN_FAILS="$(mktemp)"
trap 'rm -f "$REPORT" "$CURRENT_FAILS" "$KNOWN_FAILS"' EXIT

echo "== frontend vitest baseline gate =="
echo "repo root : ${REPO_ROOT}"
echo "vitest    : npx vitest run (cwd=${FRONTEND_DIR})"
echo "allow-list: ${KNOWN_FILE}"
echo

if [[ ! -f "$KNOWN_FILE" ]]; then
  echo "::error:: known-failures allow-list not found: ${KNOWN_FILE}"
  exit 2
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  echo "::error:: ${FRONTEND_DIR}/node_modules missing — run 'npm ci' in frontend/ first."
  exit 2
fi

# Run the suite. The default reporter keeps the Actions log human-readable; the
# json reporter is what we diff against. We never trust vitest's own exit code
# here (failures are expected) — we diff test ids instead.
(
  cd "$FRONTEND_DIR" &&
  npx vitest run --reporter=default --reporter=json --outputFile.json="$REPORT"
) || true

echo

# Did vitest actually produce a usable report? Guards against an early crash
# (config error, OOM, import blow-up) that would otherwise yield "0 failures"
# and silently pass the gate.
if [[ ! -s "$REPORT" ]]; then
  echo "::error:: vitest produced no JSON report — treating as a hard failure."
  exit 2
fi

# Extract failing test ids. Two kinds of failure are collected:
#   1. assertion-level  -> "<file>::<fullName>"
#   2. suite-level      -> "<file>::<SUITE-LEVEL FAILURE>"
#      A file that fails to import/collect reports status=failed with an EMPTY
#      assertionResults array. Without case 2 such a file would contribute zero
#      ids and the gate would wave a broken suite straight through.
if ! node -e '
  const fs = require("fs");
  const reportPath = process.argv[1];
  const frontendDir = process.argv[2];

  let r;
  try {
    r = JSON.parse(fs.readFileSync(reportPath, "utf8"));
  } catch (e) {
    console.error("::error:: could not parse vitest JSON report: " + e.message);
    process.exit(2);
  }

  const suites = Array.isArray(r.testResults) ? r.testResults : [];
  if (typeof r.numTotalTests !== "number" || (r.numTotalTests === 0 && suites.length === 0)) {
    console.error("::error:: vitest report contains no tests — treating as a hard failure.");
    process.exit(2);
  }

  const prefix = frontendDir.endsWith("/") ? frontendDir : frontendDir + "/";
  const rel = (p) => (p && p.startsWith(prefix) ? p.slice(prefix.length) : p);

  const ids = [];
  for (const suite of suites) {
    const file = rel(suite.name);
    const assertions = Array.isArray(suite.assertionResults) ? suite.assertionResults : [];
    const failed = assertions.filter((a) => a && a.status === "failed");
    for (const a of failed) {
      const full = (a.fullName && a.fullName.trim()) || a.title || "<unnamed test>";
      ids.push(file + "::" + full);
    }
    if (suite.status === "failed" && failed.length === 0) {
      ids.push(file + "::<SUITE-LEVEL FAILURE>");
    }
  }

  process.stderr.write(
    "total tests: " + r.numTotalTests +
    " | passed: " + (r.numPassedTests ?? "?") +
    " | failed: " + (r.numFailedTests ?? "?") + "\n"
  );
  console.log(ids.join("\n"));
' "$REPORT" "$FRONTEND_DIR" | grep -v '^$' | sort -u > "$CURRENT_FAILS"; then
  echo "::error:: failed to extract results from the vitest report."
  exit 2
fi

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
  echo "::notice:: These known-failing tests now PASS — remove them from ci/known_failures_vitest.txt to lock the win:"
  echo "$fixed" | sed 's/^/  /'
fi

# NEW = current - known (blocks the build).
new="$(comm -23 "$CURRENT_FAILS" "$KNOWN_FAILS")"
if [[ -n "$new" ]]; then
  echo
  echo "::error:: NEW frontend test failures introduced (not in ci/known_failures_vitest.txt):"
  echo "$new" | sed 's/^/  /'
  echo
  echo "If a new failure is genuinely pre-existing/unrelated, add its id to"
  echo "ci/known_failures_vitest.txt with justification. Otherwise, fix the regression."
  exit 1
fi

echo
echo "OK: no new frontend test failures beyond the documented baseline."
exit 0

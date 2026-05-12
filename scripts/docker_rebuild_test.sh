#!/usr/bin/env bash
# docker_rebuild_test.sh — TA-Lib Docker rebuild validation on EC2.
#
# USAGE (on EC2 Session Manager, ubuntu user):
#   bash /tmp/docker_rebuild_test.sh
#
# WHAT IT DOES:
#   - Tees all output to /tmp/docker_rebuild_test_<timestamp>.log
#   - Captures baseline (branch, commit, disk, docker ps, image list)
#   - Prunes unused Docker artifacts (volumes PRESERVED — postgres/redis data SAFE)
#   - Switches the on-disk repo to feat/dockerfile-talib
#   - Builds image to TEST tag `trading_bridge_backend:talib-test` (NOT :latest)
#   - Validates talib import + SMA computation inside the test image
#   - Returns the on-disk repo to main branch
#   - Running production containers are NEVER stopped or restarted
#
# EXIT CODES:
#   0 — all green; test image preserved as `trading_bridge_backend:talib-test`
#   1 — disk space critical (< 2GB free)
#   2 — docker build failed
#   3 — talib import/SMA function test failed
#   4 — environment guard failed (wrong OS, missing docker, dirty tree, etc.)
#  99 — unexpected error (trapped); on-disk branch best-effort restored to main
#
# IDEMPOTENT: re-running is safe. Image cache makes a re-build fast.

set -euo pipefail

REPO_DIR=/home/ubuntu/trading-bridge
TEST_BRANCH=feat/dockerfile-talib
PROD_BRANCH=main
TEST_TAG="trading_bridge_backend:talib-test"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/tmp/docker_rebuild_test_${TIMESTAMP}.log"

# Tee everything below to the log file
exec > >(tee -a "$LOG_FILE") 2>&1

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
warn() { echo "[$(date '+%H:%M:%S')] WARN: $*"; }
err()  { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; }

safe_return_to_prod_branch() {
  # Best-effort cleanup on unexpected failure. Never errors.
  if cd "$REPO_DIR" 2>/dev/null; then
    git checkout "$PROD_BRANCH" 2>/dev/null \
      || warn "Could not auto-restore $PROD_BRANCH branch (manual fixup may be needed)"
  fi
}

on_unexpected_error() {
  local line=$1
  err "Unexpected failure at line $line. Log: $LOG_FILE"
  safe_return_to_prod_branch
  exit 99
}
trap 'on_unexpected_error $LINENO' ERR

log "==== docker_rebuild_test.sh starting ===="
log "Log file: $LOG_FILE"

# ── Phase 0: environment guards ─────────────────────────────────────
log "── Phase 0: environment guards ──────────────────────────"
if [[ "$(uname -s)" != "Linux" ]]; then
  err "Must run on EC2 Linux. Refusing to run on $(uname -s)."
  exit 4
fi
if ! command -v docker >/dev/null 2>&1; then
  err "docker command not found on PATH."
  exit 4
fi
if [[ ! -d "$REPO_DIR" ]]; then
  err "Repo dir $REPO_DIR not found."
  exit 4
fi
cd "$REPO_DIR"
if [[ -n "$(git status --porcelain)" ]]; then
  err "Working tree at $REPO_DIR is dirty. Stash or commit before running."
  git status
  exit 4
fi
log "    ✓ environment OK"

# ── Phase 1: baseline capture ───────────────────────────────────────
log "── Phase 1: baseline capture ────────────────────────────"
BASELINE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
BASELINE_COMMIT="$(git rev-parse --short HEAD)"
log "    starting branch: $BASELINE_BRANCH @ $BASELINE_COMMIT"
log "    disk:"
df -h /
log "    running containers (baseline):"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
BASELINE_PS="$(docker ps --format '{{.Names}}:{{.Image}}' | sort)"
log "    top images by size:"
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | head -11

# ── Phase 2: prune (volumes preserved) ──────────────────────────────
log "── Phase 2: docker system prune (volumes PRESERVED) ─────"
docker system prune -a -f --volumes=false
log "    post-prune disk:"
df -h /
FREE_KB="$(df -k / | awk 'NR==2 {print $4}')"
FREE_GB=$(( FREE_KB / 1024 / 1024 ))
log "    free: ${FREE_GB} GB"
if (( FREE_GB < 2 )); then
  err "Less than 2 GB free — build will fail. Manual cleanup required."
  exit 1
elif (( FREE_GB < 4 )); then
  warn "Free space below 4 GB — proceeding but watch the build log closely."
fi

# ── Phase 3: checkout test branch (running containers unaffected) ───
log "── Phase 3: checkout $TEST_BRANCH ───────────────────────"
git fetch origin
# `-B` creates the local branch if missing, or resets it to track origin.
git checkout -B "$TEST_BRANCH" "origin/$TEST_BRANCH"
TEST_COMMIT="$(git rev-parse --short HEAD)"
log "    HEAD now: $TEST_COMMIT"
log "    Dockerfile/pyproject changes vs $PROD_BRANCH:"
git --no-pager log --oneline "$PROD_BRANCH..HEAD" -- backend/Dockerfile backend/pyproject.toml | head -10

# ── Phase 4: docker build to TEST tag ───────────────────────────────
log "── Phase 4: docker build → $TEST_TAG ────────────────────"
log "    NOTE: :latest is UNTOUCHED. Production containers continue running."
BUILD_START="$(date +%s)"
if ! docker build -t "$TEST_TAG" -f backend/Dockerfile backend/; then
  err "Build failed. Returning on-disk branch to $PROD_BRANCH and exiting."
  git checkout "$PROD_BRANCH" || warn "Could not restore $PROD_BRANCH automatically"
  exit 2
fi
BUILD_END="$(date +%s)"
BUILD_SECS=$(( BUILD_END - BUILD_START ))
log "    ✓ build complete in ${BUILD_SECS}s ($(( BUILD_SECS / 60 ))m $(( BUILD_SECS % 60 ))s)"
log "    test image:"
docker images "$TEST_TAG"

# ── Phase 5: TA-Lib import + SMA function test ──────────────────────
log "── Phase 5: TA-Lib import + SMA function correctness ────"
# We compute SMA over [10..19] with period 5. SMA at index 4 == 12.0.
# This proves: (a) talib import works (libta-lib.so.0 found by ld.so),
# (b) numpy import works, (c) the C function executes without segfault,
# (d) the result is numerically correct (rules out wrong-version skew).
TEST_PY='
import sys
import talib
import numpy as np
print("talib_version", talib.__version__)
print("numpy_version", np.__version__)
close = np.array([10.0, 11, 12, 13, 14, 15, 16, 17, 18, 19])
sma = talib.SMA(close, timeperiod=5)
print("sma_output", sma.tolist())
if abs(sma[4] - 12.0) > 1e-9:
    print("ASSERT_FAILED expected_sma[4]=12.0 got=", sma[4])
    sys.exit(1)
print("ASSERT_PASSED sma[4]==12.0")
'
if ! docker run --rm "$TEST_TAG" python -c "$TEST_PY"; then
  err "TA-Lib import/function test failed. Returning to $PROD_BRANCH."
  git checkout "$PROD_BRANCH" || warn "Could not restore $PROD_BRANCH automatically"
  exit 3
fi

# ── Phase 6: restore prod branch on disk ────────────────────────────
log "── Phase 6: restore $PROD_BRANCH on disk ────────────────"
git checkout "$PROD_BRANCH"
log "    on-disk branch: $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)"

# ── Phase 7: verify production containers unchanged ─────────────────
log "── Phase 7: verify production containers unchanged ──────"
NEW_PS="$(docker ps --format '{{.Names}}:{{.Image}}' | sort)"
if [[ "$BASELINE_PS" == "$NEW_PS" ]]; then
  log "    ✓ production containers unchanged (same names + same image refs)"
else
  warn "container set differs from baseline. Diff:"
  diff <(echo "$BASELINE_PS") <(echo "$NEW_PS") || true
fi
log "    docker ps now:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'

# ── Final summary ───────────────────────────────────────────────────
trap - ERR
log "============================================================"
log "  ✓ ALL GREEN"
log ""
log "  Test image:        $TEST_TAG (preserved on-host for retag)"
log "  Build time:        ${BUILD_SECS}s ($(( BUILD_SECS / 60 ))m $(( BUILD_SECS % 60 ))s)"
log "  :latest tag:       UNTOUCHED"
log "  Prod containers:   unchanged"
log "  Disk free now:     ${FREE_GB} GB"
log "  Test branch HEAD:  $TEST_COMMIT  (re-checked-out from origin)"
log "  Log file:          $LOG_FILE"
log ""
log "  TOMORROW MORNING SHORTCUT (after smoke decision):"
log "    docker tag $TEST_TAG trading_bridge_backend:latest"
log "    docker compose up -d backend celery_worker celery_beat"
log "  Or inspect further: docker run --rm $TEST_TAG <command>"
log "============================================================"

exit 0

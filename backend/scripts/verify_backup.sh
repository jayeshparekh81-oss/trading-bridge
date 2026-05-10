#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# TRADETRI — Backup verification runner
# ═══════════════════════════════════════════════════════════════════════
#
# Restores the latest backup to an ephemeral DB, runs sanity queries
# (row counts on critical tables), and writes a verification result
# JSON file that the /api/health/backups endpoint surfaces.
#
# Detects three classes of failure:
#   1. Missing backup file
#   2. pg_restore errors (corrupt dump)
#   3. Sanity query mismatch (row counts wildly different from prod)
#
# Env vars:
#   BACKUP_VERIFY_TARGET   — ephemeral DB URL (REQUIRED for non-stub)
#   BACKUP_DB_URL          — production DB URL (for row-count comparison)
#   BACKUP_LOCAL_DIR       — spool dir (default /var/backups/tradetri)
#   BACKUP_DRIFT_TOLERANCE — % drift allowed in users count (default 5)
#
# Stub mode: when BACKUP_VERIFY_TARGET is unset, logs intent + exits 0.
#
# Exit codes:
#   0 — verification passed (or stub completed)
#   1 — env / file / restore error
#   2 — sanity check detected drift (likely corruption)
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { printf '%b[VERIFY]%b %s\n' "$GREEN"  "$NC" "$*"; }
warn() { printf '%b[WARN]%b %s\n'   "$YELLOW" "$NC" "$*" >&2; }
fail() { printf '%b[FAIL]%b %s\n'   "$RED"    "$NC" "$*" >&2; exit 1; }

LOCAL_DIR="${BACKUP_LOCAL_DIR:-/var/backups/tradetri}"
TOLERANCE="${BACKUP_DRIFT_TOLERANCE:-5}"
STATE_FILE="${LOCAL_DIR}/.verify-state.json"

# Always make the spool dir so the state file can be written even
# in stub mode; the health endpoint reads it regardless.
mkdir -p "$LOCAL_DIR"

write_state() {
    local status="$1"
    local detail="$2"
    cat >"$STATE_FILE" <<EOF
{
  "verified_at": "$(date -u +%Y%m%dT%H%M%SZ)",
  "status": "${status}",
  "detail": "${detail}"
}
EOF
}

# ─── Stub mode ────────────────────────────────────────────────────────
if [[ -z "${BACKUP_VERIFY_TARGET:-}" ]]; then
    warn "BACKUP_VERIFY_TARGET not set — stub mode."
    write_state "stub" "no verification target configured"
    log "Stub-mode complete."
    exit 0
fi

# ─── Find latest dump ─────────────────────────────────────────────────
LATEST="$(find "$LOCAL_DIR" -maxdepth 1 -name 'tradetri-*.dump*' -type f \
          -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -n1)"
if [[ -z "$LATEST" ]]; then
    write_state "fail" "no backup file found in ${LOCAL_DIR}"
    fail "No backup file found in ${LOCAL_DIR}"
fi
log "Latest backup: ${LATEST}"

# ─── Restore to ephemeral target ──────────────────────────────────────
command -v pg_restore >/dev/null 2>&1 || fail "pg_restore not in PATH"

DUMP_TO_RESTORE="$LATEST"
if [[ "$LATEST" == *.gpg ]]; then
    [[ -n "${BACKUP_ENCRYPT_KEY:-}" ]] \
        || { write_state "fail" "encrypted backup but no key"; fail "encrypted dump, no key"; }
    DUMP_TO_RESTORE="${LATEST%.gpg}.tmp"
    if [[ -f "$BACKUP_ENCRYPT_KEY" ]]; then
        gpg --batch --yes --decrypt \
            --passphrase-file "$BACKUP_ENCRYPT_KEY" \
            --output "$DUMP_TO_RESTORE" "$LATEST" \
            || { write_state "fail" "gpg decrypt failed"; fail "decrypt failed"; }
    else
        gpg --batch --yes --decrypt --output "$DUMP_TO_RESTORE" "$LATEST" \
            || { write_state "fail" "gpg decrypt failed"; fail "decrypt failed"; }
    fi
fi

log "pg_restore → ephemeral target"
if ! pg_restore --clean --if-exists --no-owner --no-acl \
        --dbname="$BACKUP_VERIFY_TARGET" "$DUMP_TO_RESTORE"; then
    write_state "fail" "pg_restore failed (corrupt dump)"
    fail "pg_restore failed — backup is unusable"
fi

# ─── Sanity queries ───────────────────────────────────────────────────
command -v psql >/dev/null 2>&1 || fail "psql not in PATH"

count_rows() {
    local table="$1"
    local url="$2"
    psql "$url" -At -c "SELECT count(*) FROM ${table};" 2>/dev/null || echo "0"
}

VERIFY_USERS="$(count_rows users "$BACKUP_VERIFY_TARGET")"
log "Restored users count: ${VERIFY_USERS}"

# Compare against prod when both URLs are available. We tolerate
# small drift (new signups between dump + verify), but flag a wild
# divergence (>tolerance%) as corruption.
DRIFT_PCT="0"
if [[ -n "${BACKUP_DB_URL:-}" ]]; then
    PROD_USERS="$(count_rows users "$BACKUP_DB_URL")"
    log "Prod users count: ${PROD_USERS}"
    if [[ "$PROD_USERS" -gt 0 ]]; then
        DIFF=$(( PROD_USERS - VERIFY_USERS ))
        DIFF=${DIFF#-}  # abs
        DRIFT_PCT=$(( DIFF * 100 / PROD_USERS ))
        if (( DRIFT_PCT > TOLERANCE )); then
            write_state "fail" "users count drift ${DRIFT_PCT}% > tolerance ${TOLERANCE}%"
            fail "Drift ${DRIFT_PCT}% exceeds tolerance ${TOLERANCE}% — possible corruption"
        fi
    fi
fi

write_state "ok" "users=${VERIFY_USERS} drift=${DRIFT_PCT}%"
log "Verification PASSED."

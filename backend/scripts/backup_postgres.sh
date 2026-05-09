#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# TRADETRI — Postgres backup runner
# ═══════════════════════════════════════════════════════════════════════
#
# Daily 3:00 AM IST cron entry. Streams pg_dump (custom format,
# compressed) optionally through gpg encryption, writes to a local
# spool directory, then mirrors to S3 if a bucket is configured.
#
# Env vars (all optional unless noted):
#   BACKUP_DB_URL          — postgres URL (REQUIRED for non-stub mode)
#   BACKUP_S3_BUCKET       — destination bucket; unset = local-only
#   BACKUP_S3_PREFIX       — key prefix (default "tradetri/")
#   BACKUP_ENCRYPT_KEY     — gpg recipient OR path to passphrase file;
#                            unset = no encryption (local lab only)
#   BACKUP_LOCAL_DIR       — spool dir (default /var/backups/tradetri)
#   BACKUP_RETENTION_DAYS  — local prune horizon (default 30)
#
# Exit codes:
#   0 — backup written (or stub-mode no-op completed cleanly)
#   1 — environment misconfigured / pg_dump failed / upload failed
#
# Stub mode: when BACKUP_DB_URL is unset, the script logs intent +
# exits 0. This lets unit tests + dev-laptop cron entries run
# without touching real infrastructure.
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { printf '%b[BACKUP]%b %s\n'  "$GREEN"  "$NC" "$*"; }
warn() { printf '%b[WARN]%b %s\n'    "$YELLOW" "$NC" "$*" >&2; }
fail() { printf '%b[FAIL]%b %s\n'    "$RED"    "$NC" "$*" >&2; exit 1; }

# ─── Defaults ─────────────────────────────────────────────────────────
LOCAL_DIR="${BACKUP_LOCAL_DIR:-/var/backups/tradetri}"
S3_PREFIX="${BACKUP_S3_PREFIX:-tradetri/}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

mkdir -p "$LOCAL_DIR"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
BASENAME="tradetri-${TS}.dump"
ENCRYPTED_BASENAME="${BASENAME}.gpg"
LOCAL_PATH="${LOCAL_DIR}/${BASENAME}"

# ─── Stub mode (no DB URL → log + exit cleanly) ───────────────────────
if [[ -z "${BACKUP_DB_URL:-}" ]]; then
    warn "BACKUP_DB_URL not set — stub mode."
    log "Intent: would pg_dump → ${LOCAL_PATH}"
    if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
        log "Intent: would upload → s3://${BACKUP_S3_BUCKET}/${S3_PREFIX}${BASENAME}"
    fi
    log "Stub-mode complete (no actual work performed)."
    exit 0
fi

# ─── Real backup ──────────────────────────────────────────────────────
command -v pg_dump >/dev/null 2>&1 || fail "pg_dump not found in PATH"

log "Dumping database → ${LOCAL_PATH}"
# -Fc = custom format, internally compressed, parallel-restorable.
if ! pg_dump -Fc --no-owner --no-acl "$BACKUP_DB_URL" -f "$LOCAL_PATH"; then
    fail "pg_dump failed — backup NOT written."
fi

UPLOAD_PATH="$LOCAL_PATH"
UPLOAD_BASENAME="$BASENAME"

# Optional symmetric encryption with gpg. We accept either a
# passphrase-file path OR a recipient name (asymmetric); the script
# auto-detects by checking whether the value is a readable file.
if [[ -n "${BACKUP_ENCRYPT_KEY:-}" ]]; then
    command -v gpg >/dev/null 2>&1 || fail "gpg not found but BACKUP_ENCRYPT_KEY set"
    log "Encrypting backup with gpg…"
    if [[ -f "$BACKUP_ENCRYPT_KEY" ]]; then
        gpg --batch --yes --symmetric --cipher-algo AES256 \
            --passphrase-file "$BACKUP_ENCRYPT_KEY" \
            --output "${LOCAL_PATH}.gpg" \
            "$LOCAL_PATH" || fail "gpg symmetric encryption failed"
    else
        gpg --batch --yes --encrypt --recipient "$BACKUP_ENCRYPT_KEY" \
            --output "${LOCAL_PATH}.gpg" \
            "$LOCAL_PATH" || fail "gpg recipient encryption failed"
    fi
    rm -f "$LOCAL_PATH"
    UPLOAD_PATH="${LOCAL_PATH}.gpg"
    UPLOAD_BASENAME="$ENCRYPTED_BASENAME"
else
    warn "BACKUP_ENCRYPT_KEY unset — backup is unencrypted (lab only)"
fi

# ─── Optional S3 upload ───────────────────────────────────────────────
if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
    command -v aws >/dev/null 2>&1 || fail "aws CLI not found but BACKUP_S3_BUCKET set"
    S3_KEY="${S3_PREFIX}${UPLOAD_BASENAME}"
    log "Uploading → s3://${BACKUP_S3_BUCKET}/${S3_KEY}"
    if ! aws s3 cp "$UPLOAD_PATH" "s3://${BACKUP_S3_BUCKET}/${S3_KEY}" \
            --only-show-errors --no-progress; then
        fail "S3 upload failed — backup retained locally at ${UPLOAD_PATH}"
    fi
    log "Upload complete."
else
    warn "BACKUP_S3_BUCKET unset — backup retained locally only"
fi

# ─── Local retention prune ────────────────────────────────────────────
log "Pruning local backups older than ${RETENTION_DAYS} days…"
find "$LOCAL_DIR" -maxdepth 1 -name 'tradetri-*.dump*' \
     -type f -mtime +"$RETENTION_DAYS" -delete

# ─── State file (read by /api/health/backups) ─────────────────────────
STATE_FILE="${LOCAL_DIR}/.backup-state.json"
SIZE_BYTES="$(stat -f%z "$UPLOAD_PATH" 2>/dev/null || stat -c%s "$UPLOAD_PATH")"
cat >"$STATE_FILE" <<EOF
{
  "last_backup_at": "${TS}",
  "last_backup_basename": "${UPLOAD_BASENAME}",
  "last_backup_size_bytes": ${SIZE_BYTES},
  "encrypted": $( [[ -n "${BACKUP_ENCRYPT_KEY:-}" ]] && echo true || echo false ),
  "uploaded_to_s3": $( [[ -n "${BACKUP_S3_BUCKET:-}" ]] && echo true || echo false )
}
EOF

log "Backup complete: ${UPLOAD_PATH}"

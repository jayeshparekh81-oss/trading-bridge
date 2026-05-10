#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# TRADETRI — Postgres restore runner
# ═══════════════════════════════════════════════════════════════════════
#
# Reverse of backup_postgres.sh. Downloads a named backup from S3
# (or reads from local spool), optionally decrypts with gpg, then
# pg_restore into the target DB.
#
# Usage:
#   ./restore_postgres.sh <timestamp> --confirm <db_name>
#     timestamp — basename without extension (e.g. "tradetri-20260510T030000Z")
#     --confirm <db_name> — must match the database in BACKUP_RESTORE_TARGET
#                           — guards against accidental production restore.
#
# Env vars:
#   BACKUP_RESTORE_TARGET  — target postgres URL (REQUIRED)
#   BACKUP_S3_BUCKET       — source bucket (optional; falls back to local)
#   BACKUP_S3_PREFIX       — key prefix (default "tradetri/")
#   BACKUP_ENCRYPT_KEY     — gpg passphrase-file or recipient (if encrypted)
#   BACKUP_LOCAL_DIR       — spool dir (default /var/backups/tradetri)
#   BACKUP_PRODUCTION_HOST — refuse to restore against this host (safety)
#
# Exit codes:
#   0 — restore complete
#   1 — environment / arg / safety-check / pg_restore failed
#   2 — confirmation token did not match target DB
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { printf '%b[RESTORE]%b %s\n' "$GREEN"  "$NC" "$*"; }
warn() { printf '%b[WARN]%b %s\n'    "$YELLOW" "$NC" "$*" >&2; }
fail() { printf '%b[FAIL]%b %s\n'    "$RED"    "$NC" "$*" >&2; exit 1; }

# ─── Args ─────────────────────────────────────────────────────────────
if [[ $# -lt 3 ]]; then
    fail "Usage: $0 <timestamp> --confirm <db_name>"
fi

TIMESTAMP="$1"
shift
if [[ "${1:-}" != "--confirm" ]]; then
    fail "Missing --confirm <db_name> (safety check)"
fi
shift
CONFIRM_DB="${1:-}"
[[ -n "$CONFIRM_DB" ]] || fail "--confirm requires a db name"

# ─── Env ──────────────────────────────────────────────────────────────
[[ -n "${BACKUP_RESTORE_TARGET:-}" ]] \
    || fail "BACKUP_RESTORE_TARGET unset — refusing to guess target DB."

LOCAL_DIR="${BACKUP_LOCAL_DIR:-/var/backups/tradetri}"
S3_PREFIX="${BACKUP_S3_PREFIX:-tradetri/}"

# ─── Safety: forbid restore against the prod host pattern ─────────────
if [[ -n "${BACKUP_PRODUCTION_HOST:-}" ]] \
   && [[ "$BACKUP_RESTORE_TARGET" == *"$BACKUP_PRODUCTION_HOST"* ]]; then
    fail "Refusing to restore against production host '${BACKUP_PRODUCTION_HOST}'.
          To override, perform PITR via RDS console or use the
          documented production-failover runbook (DISASTER_RECOVERY.md)."
fi

# ─── Safety: confirm token must match the DB name in the URL ──────────
# Extract path component after the last '/' — that's the DB name.
URL_DB="${BACKUP_RESTORE_TARGET##*/}"
URL_DB="${URL_DB%%\?*}"  # strip ?query
if [[ "$CONFIRM_DB" != "$URL_DB" ]]; then
    printf '%b[ABORT]%b confirm token "%s" != target DB "%s"\n' \
        "$RED" "$NC" "$CONFIRM_DB" "$URL_DB" >&2
    exit 2
fi

# ─── Resolve dump file (S3 or local) ──────────────────────────────────
mkdir -p "$LOCAL_DIR"
DUMP_FILE="${LOCAL_DIR}/${TIMESTAMP}.dump"
ENCRYPTED_FILE="${DUMP_FILE}.gpg"
NEEDS_DECRYPT=0

if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
    command -v aws >/dev/null 2>&1 || fail "aws CLI not found"
    # Try encrypted first, fall back to plain.
    if aws s3 cp "s3://${BACKUP_S3_BUCKET}/${S3_PREFIX}${TIMESTAMP}.dump.gpg" \
                 "$ENCRYPTED_FILE" --only-show-errors 2>/dev/null; then
        log "Downloaded encrypted dump from S3"
        NEEDS_DECRYPT=1
    elif aws s3 cp "s3://${BACKUP_S3_BUCKET}/${S3_PREFIX}${TIMESTAMP}.dump" \
                   "$DUMP_FILE" --only-show-errors; then
        log "Downloaded plaintext dump from S3"
    else
        fail "Neither encrypted nor plaintext dump found at s3://${BACKUP_S3_BUCKET}/${S3_PREFIX}${TIMESTAMP}.dump[.gpg]"
    fi
else
    # Local-only path
    if [[ -f "$ENCRYPTED_FILE" ]]; then
        NEEDS_DECRYPT=1
    elif [[ ! -f "$DUMP_FILE" ]]; then
        fail "No local dump found at ${DUMP_FILE} (or .gpg variant)"
    fi
fi

# ─── Decrypt if needed ────────────────────────────────────────────────
if [[ "$NEEDS_DECRYPT" -eq 1 ]]; then
    [[ -n "${BACKUP_ENCRYPT_KEY:-}" ]] \
        || fail "Encrypted dump but BACKUP_ENCRYPT_KEY unset."
    command -v gpg >/dev/null 2>&1 || fail "gpg required to decrypt"
    log "Decrypting…"
    if [[ -f "$BACKUP_ENCRYPT_KEY" ]]; then
        gpg --batch --yes --decrypt \
            --passphrase-file "$BACKUP_ENCRYPT_KEY" \
            --output "$DUMP_FILE" \
            "$ENCRYPTED_FILE" || fail "gpg decryption failed"
    else
        gpg --batch --yes --decrypt \
            --output "$DUMP_FILE" \
            "$ENCRYPTED_FILE" || fail "gpg decryption failed"
    fi
fi

[[ -f "$DUMP_FILE" ]] || fail "Dump file unexpectedly missing: ${DUMP_FILE}"

# ─── Restore ──────────────────────────────────────────────────────────
command -v pg_restore >/dev/null 2>&1 || fail "pg_restore not in PATH"

log "Restoring ${DUMP_FILE} → ${URL_DB}"
log "(this drops + recreates schema; 30-second grace period before start)"
sleep 30

if ! pg_restore --clean --if-exists --no-owner --no-acl \
        --dbname="$BACKUP_RESTORE_TARGET" "$DUMP_FILE"; then
    fail "pg_restore failed — DB may be in inconsistent state."
fi

log "Restore complete. Run ./verify_backup.sh to validate."

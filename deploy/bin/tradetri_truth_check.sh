#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════
# TRADETRI — the daily 15:50 IST truth check.
#
# ONE Dhan GET. The book is pulled once into a file, then BOTH the ingester
# and the check read that file. No step here calls the broker twice.
#
# READ-ONLY TOWARD pine_replica. It copies the tape OUT of the log directory
# and never writes, moves or rotates anything there.
#
# NO COMPOSE CHANGE, NO RESTART. The backend container has no mounts
# (measured), so the tape is handed to it with `docker cp` rather than by
# adding a bind-mount and restarting the LIVE web container. The copies are
# ephemeral and that is fine: the verdict lives in the database.
# ══════════════════════════════════════════════════════════════════════════
set -uo pipefail

C=trading_bridge_backend
STRATEGY=89423ecc-c76e-432c-b107-0791508542f0
SECURITY_IDS=68456
TAPE_DIR=/home/ubuntu/pine_replica/executor/logs
DAY="${1:-$(TZ=Asia/Kolkata date +%F)}"
BOOK=/tmp/truth_book_${DAY}.jsonl
TAPE=/tmp/truth_tape_${DAY}.jsonl

log() { echo "[$(TZ=Asia/Kolkata date +'%F %T %Z')] $*"; }

log "truth check for ${DAY}"

# ── 1. hand the container today's tape (read-only toward pine_replica) ──
SRC="${TAPE_DIR}/order_updates_${DAY}.jsonl"
if [ -f "$SRC" ]; then
  docker cp "$SRC" "${C}:${TAPE}" || { log "FATAL: could not copy the tape"; exit 2; }
  log "tape copied: $(wc -l < "$SRC") frame(s)"
else
  # A day with no order updates is normal — 05-Sep and 12-Sep had zero fills
  # and no file. An EMPTY tape beside actual fills is the red, and the
  # ingester refuses that case itself rather than mislabelling every fill.
  log "no tape file for ${DAY} (normal on a day with no order updates)"
  docker exec "$C" sh -lc ": > ${TAPE}"
fi

# ── 2. THE ONE DHAN GET of the day ─────────────────────────────────────
docker exec "$C" python -m app.domains.pnl_reconciler.truth_check_runner \
  --day "$DAY" --security-ids $SECURITY_IDS --pull-only --book "$BOOK" \
  || { log "FATAL: the trade-book GET failed"; exit 2; }

# ── 3. record each fill's provenance (idempotent: PK + ON CONFLICT) ────
docker exec "$C" python -m app.domains.pnl_reconciler \
  --strategy "$STRATEGY" --tradebook "$BOOK" --order-tape "$TAPE" --ingest \
  || log "WARNING: ingest did not complete cleanly — the check below will say so"

# ── 4. the verdict, from the SAME file. No second GET. ─────────────────
docker exec "$C" python -m app.domains.pnl_reconciler.truth_check_runner \
  --day "$DAY" --security-ids $SECURITY_IDS --book "$BOOK" --send
RC=$?

# ── 5. tidy up the ephemeral copies ────────────────────────────────────
docker exec "$C" sh -lc "rm -f ${BOOK} ${TAPE}" || true

log "done (verdict exit ${RC}: 0=green 1=red)"
exit $RC

#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════
# MORNING truth check — 08:30 IST, for YESTERDAY's session.
#
# ONE Dhan trade-book GET. By now the book has settled, so this run can see
# the money: settled fills and their BILLED charges against what the site
# stored. It is the only run that may license a "Dhan se verified" badge.
#
# The book is pulled once to a file; the ingester and the check both read it,
# so one session costs exactly one GET.
# ══════════════════════════════════════════════════════════════════════════
set -uo pipefail
C=trading_bridge_backend
STRATEGY=89423ecc-c76e-432c-b107-0791508542f0
SECURITY_IDS=68456
TAPE_DIR=/home/ubuntu/pine_replica/executor/logs
# Default target is YESTERDAY in IST — the session that has now settled.
DAY="${1:-$(TZ=Asia/Kolkata date -d 'yesterday' +%F)}"
BOOK=/tmp/truth_book_${DAY}.jsonl
TAPE=/tmp/truth_tape_${DAY}.jsonl
log() { echo "[$(TZ=Asia/Kolkata date +'%F %T %Z')] $*"; }

log "morning check for ${DAY} (yesterday's session)"
SRC="${TAPE_DIR}/order_updates_${DAY}.jsonl"
if [ -f "$SRC" ]; then
  docker cp "$SRC" "${C}:${TAPE}" || { log "FATAL: could not copy the tape"; exit 2; }
else
  log "no tape file for ${DAY}"
  docker exec "$C" sh -lc ": > ${TAPE}"
fi

# THE ONE DHAN TRADE-BOOK GET of the day.
docker exec "$C" python -m app.domains.pnl_reconciler.truth_check_runner \
  --day "$DAY" --security-ids $SECURITY_IDS --pull-only --book "$BOOK" \
  || { log "FATAL: the trade-book GET failed"; exit 2; }

# Record each fill's provenance (idempotent: PK + ON CONFLICT DO NOTHING).
docker exec "$C" python -m app.domains.pnl_reconciler \
  --strategy "$STRATEGY" --tradebook "$BOOK" --order-tape "$TAPE" --ingest \
  || log "WARNING: ingest did not complete cleanly — the check below will say so"

# The verdict, from the SAME file. No second GET.
docker exec "$C" python -m app.domains.pnl_reconciler.truth_check_runner \
  --kind morning --day "$DAY" --security-ids $SECURITY_IDS --book "$BOOK" --tape "$TAPE" --send
RC=$?
docker exec "$C" sh -lc "rm -f ${BOOK} ${TAPE}" || true
log "done (exit ${RC}: 0=green, 1=red/no-data)"
exit $RC

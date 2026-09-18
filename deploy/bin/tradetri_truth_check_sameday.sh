#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════
# SAME-DAY truth check — 15:50 IST. NO TRADE BOOK, NO DHAN TRADE-BOOK GET.
#
# Sources: the WS order-update tape (a file), our own strategy_executions, and
# ONE Dhan /positions GET for the day quantities. The book is deliberately not
# read: it does not settle for ~40 hours, so at 15:50 it is silent about the
# session that just ended.
#
# READ-ONLY toward pine_replica. Copies the tape out; writes nothing there.
# NO COMPOSE CHANGE: the backend container has no mounts (measured), so the
# tape is handed over with docker cp rather than a bind-mount + restart.
# ══════════════════════════════════════════════════════════════════════════
set -uo pipefail
C=trading_bridge_backend
SECURITY_IDS=68456
TAPE_DIR=/home/ubuntu/pine_replica/executor/logs
DAY="${1:-$(TZ=Asia/Kolkata date +%F)}"
TAPE=/tmp/truth_tape_${DAY}.jsonl
log() { echo "[$(TZ=Asia/Kolkata date +'%F %T %Z')] $*"; }

log "same-day check for ${DAY}"
SRC="${TAPE_DIR}/order_updates_${DAY}.jsonl"
if [ -f "$SRC" ]; then
  docker cp "$SRC" "${C}:${TAPE}" || { log "FATAL: could not copy the tape"; exit 2; }
  log "tape copied: $(wc -l < "$SRC") frame(s)"
else
  log "no tape file for ${DAY} (normal when no order updates arrived)"
  docker exec "$C" sh -lc ": > ${TAPE}"
fi

docker exec "$C" python -m app.domains.pnl_reconciler.truth_check_runner \
  --kind same_day --day "$DAY" --security-ids $SECURITY_IDS --tape "$TAPE" --send
RC=$?
docker exec "$C" sh -lc "rm -f ${TAPE}" || true
log "done (exit ${RC}: 0=green, 1=red/no-data)"
exit $RC

#!/usr/bin/env bash
# levels_daily_host.sh — run levels.daily on the HOST (outside docker).
#
# Why this exists (Monday-0 batch, vetted 2026-07-11/12):
#   * levels.daily -> recorder.creds reads DATABASE_URL etc. from os.environ
#     directly (recorder/creds.py:25) — it never calls load_env_files, so a bare
#     host shell has no DB creds. We source the shared .env files here.
#   * Those files carry the CONTAINER host (@postgres) in DATABASE_URL; on the
#     host we rewrite it to @localhost (postgres publishes 5432:5432).
#   * backend/.env also carries the LIVE bot's TELEGRAM_* names — we unset them
#     immediately (levels.daily doesn't need them; R7 reads only ORDERFLOW_*
#     anyway, but keep the shell clean as defense-in-depth).
#   * The recorder-owned cache/ dir is root-owned (container writes it) — we
#     redirect the historical parquet cache to a host-writable dir. Prefer
#     --security-id over --symbol to also skip the scrip-master CSV write.
#
# Usage (from orderflow_engine/):
#   scripts/levels_daily_host.sh --security-id 61093 --segment NSE_FNO \
#       --instrument FUTIDX --from 2026-05-01 --to 2026-07-13
#   OE_HIST_CACHE=/some/dir scripts/levels_daily_host.sh ...   # cache override
set -euo pipefail
cd "$(dirname "$0")/.."                       # orderflow_engine/

set -a
source ../.env                                 # DEFAULT_USER_ID
source ../backend/.env                         # DATABASE_URL, ENCRYPTION_KEY (+ live TELEGRAM_*)
set +a
unset TELEGRAM_BOT_TOKEN TELEGRAM_ALERT_CHAT_ID 2>/dev/null || true

# container hostname -> host published port (docker-compose.yml: "5432:5432")
export DATABASE_URL="${DATABASE_URL/@postgres:/@localhost:}"
export DATABASE_URL="${DATABASE_URL/@postgres\//@localhost\/}"

CACHE_DIR="${OE_HIST_CACHE:-$HOME/oe_hist}"
mkdir -p "$CACHE_DIR"

exec .venv/bin/python -m levels.daily "$@" --cache "$CACHE_DIR"

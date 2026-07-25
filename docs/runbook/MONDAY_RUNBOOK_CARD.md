# MONDAY MORNING RUNBOOK CARD v1 — 2026-07-27 (docs/runbook/ candidate)
Audience: founder, 09:00 IST, phone + this card. All diagnostics READ-ONLY copy-paste.
Standing facts: recorders on image 589c85a (rebuilt Sat); rollback tags intact:
pre-bse=fd5935, bse-good=40584 (both verified Sat). Watchdog v2 cron fires 09:20 IST
(weekdays); recorders connect 09:05; market opens 09:15. OOS window day 3/15.
GLOBAL NEVER: no code edits, no config changes, no branch switches on the host,
no docker image prune, and NEVER a recreate without the STEP-0 log dump first
(OPS_NOTES 2-MINUTE ROLLBACK block).

## S1 — 09:20 watchdog Telegram ABSENT or RED
DIAG (read-only, prints verdict without sending):
  cd /home/ubuntu/trading-bridge/orderflow_engine && python3 scripts/morning_watchdog_v2.py --dry-run
  tail -5 /home/ubuntu/oe_morning_watchdog_v2.log
DECIDE: dry-run prints GREEN => the send path died, not the market stack -> go S6.
  Prints YELLOW => chain-side only: NOT an emergency, no rollback (watchdog v2 text).
  Prints RED (core not flowing / crash loop) => OPS_NOTES 2-MINUTE ROLLBACK, STEP-0
  log dump FIRST; done by ~09:25 per the standing trigger discipline.
  No message AND no SSH => S5.
  (OPS_NOTES fail-safe: no watchdog output by 09:25 == watchdog itself failed —
  run the manual disk-truth checklist by hand.)
Monday rollback cost = shadow-store day lost, RECORDING preserved — acceptable;
  recording is the machine's oxygen.
NEVER: rollback on a YELLOW; edit the watchdog script live.

## S2 — one recorder container RESTART-LOOPING
DIAG:
  docker inspect orderflow_recorder orderflow_depth_recorder --format '{{.Name}} {{.State.Status}} restarts={{.RestartCount}} OOM={{.State.OOMKilled}}'
  docker logs orderflow_recorder --since 30m 2>&1 | tail -20   # note the 2>&1 (stderr!)
DECIDE: restarts>0 / flapping = RED-class trigger (Wednesday-checklist rule) =>
  STEP-0 dump BOTH containers' logs, then OPS_NOTES 2-MINUTE ROLLBACK
  (docker tag <known-good> orderflow-recorder:latest && docker compose up -d
  --no-deps recorder depth_recorder). Tag choice (pre-bse vs bse-good) = founder
  call in the moment; both verified intact Saturday. If only DEPTH loops and the
  tick recorder is healthy: depth is record-only — acceptable to leave it and
  diagnose post-close (founder call), core stays untouched.
Monday rollback cost = shadow-store day lost, RECORDING preserved — acceptable;
  recording is the machine's oxygen.
NEVER: recreate without STEP-0 (recreate DESTROYS the old container's logs —
  the 07-22 lesson, now codified in OPS_NOTES).

## S3 — both recorders Up but data dir EMPTY/STALE at 09:35
DIAG (two samples ~30s apart; growth = healthy):
  ls -la /home/ubuntu/trading-bridge/orderflow_engine/data/$(date +%F)/NIFTY_FUT_*.tmp \
        /home/ubuntu/trading-bridge/orderflow_engine/data/$(date +%F)/BANKNIFTY_FUT_*.tmp
  (or simply re-run S1's --dry-run: in market hours it does the 45s growth check itself)
DECIDE: .tmp files growing => wait, it's fine (parquet rotates; .tmp is the live
  file — the 07-22 false-stall lesson). NOT growing while containers claim Up =
  core-not-flowing = RED-class => STEP-0 + 2-MINUTE ROLLBACK. Still dead after
  rollback => call it a lost day, leave containers up, diagnose post-close;
  the OOS window tolerates a lost day (report it, never backfill silently).
NEVER: judge staleness from the rotated .parquet size (batching artifact).

## S4 — depth-verify PARTIAL alarm
DECIDE: KNOWN COSMETIC — de-escalated. B2-VERIFY (Machine Health Card, ed96e0f):
  depth PARTIAL at ~99% coverage comes from recovered disconnects/soft tags;
  file-order quirk is TAIL-CONFINED and ReplaySource heals it (zero out-of-order
  emissions); replayed book provably clean. Fix scheduled: OPS_NOTES
  "NEXT MARKET-CLOSED WEEKEND MAINTENANCE BATCH" item (b) (Aug 1-2 window).
  ACTION: none. Log it, move on. Core verdict comes from S1/S3 checks only.
NEVER: roll back or restart anything because of a depth PARTIAL alone.

## S5 — EC2 UNREACHABLE / SSH fails
DIAG (from phone/laptop):
  ssh -o ConnectTimeout=10 <host>   # and/or AWS console instance status checks
DECIDE: NO PROCEDURE — founder decision (AWS console reboot is outside every
  committed runbook). Two standing facts to decide with: (1) containers are
  restart: unless-stopped — if the instance comes back, recorders auto-start
  and resume writing; (2) a missed session = lost day for the window (report,
  don't backfill). If the instance returns mid-session, run S1's --dry-run to
  assess what was captured.
NEVER: panic-terminate/resize the instance; no infra changes mid-session.

## S6 — Telegram itself SILENT (bot vs machine)
DIAG (which died?):
  ssh works? -> machine alive, it's the send path. Then:
  cd /home/ubuntu/trading-bridge/orderflow_engine && python3 scripts/morning_watchdog_v2.py --dry-run   # verdict WITHOUT sending
  python3 scripts/morning_watchdog_v2.py; tail -2 /home/ubuntu/oe_morning_watchdog_v2.log   # real send; look for "telegram sent=True/False"
DECIDE: ssh dead => S5 (machine). sent=False with GREEN verdict => bot/env issue
  (ORDERFLOW_TELEGRAM_BOT_TOKEN/CHAT_ID in orderflow_engine/.env — the namespaced
  pair, never the live bot's bare TELEGRAM_*): NO PROCEDURE beyond checking the
  env pair exists — founder decision (token rotation is a live-credentials act).
  Market stack verdict comes from --dry-run regardless; Telegram being down does
  NOT block the day.
NEVER: touch the live trading bot's TELEGRAM_* credentials.

## GREEN-DAY CHECKLIST (what "all healthy" looks like by ~09:25)
1. Telegram GREEN from watchdog v2 at 09:20 (universe ~477-505, BSE_FUT=Y, core=Y).
2. Both containers running, restarts=0 (S2 one-liner).
3. NIFTY_FUT + BANKNIFTY_FUT .tmp files growing (S3 check).
4. depth/parts/ file count climbing (18-19 instrument dirs).
5. No action taken; phone down; next look = 15:50 evening pipeline.

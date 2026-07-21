# orderflow_engine — Ops Notes

Operational doctrine and incident log for the R0 tick recorder. Read this
before touching the write path or the container's resource limits.

---

## 1. Design doctrine (kdb+tick)

The recorder deliberately follows the **kdb+tick** split that has run
production exchanges for two decades. The capture process does one thing and
does it without ever blocking:

1. **Capture is sacred and dumb.** The hot path (websocket → parse → buffer →
   append) does the minimum work required to get a tick durably onto disk.
   No analytics, no aggregation, no cross-instrument joins, no network calls
   on the write path. Anything clever happens **downstream**, off the capture
   process, reading the files after the fact (the replayer, notebooks, R1+).

2. **Append-only, one logical log per instrument.** Each instrument streams to
   its own file. Flushes are followed by `fsync`; the final file is promoted
   with an atomic `os.replace`. A mid-flush kill can only ever leave a `.tmp`,
   never a corrupt *final* file. This is the tickerplant guarantee: the log on
   disk is always replayable up to the last completed flush.

3. **Bounded, predictable memory.** A tickerplant must run for the whole
   session at flat memory. Anything that grows monotonically with session
   length (open writers, in-RAM day tables, unbounded buffers) is a latent
   host-killer — see incident 2026-07-10 below. Memory must be a **sawtooth**,
   not a ramp.

4. **Recovery is a first-class path, not an afterthought.** Fallback part-files,
   salvage of a half-written primary, and EOD consolidation are all tested
   paths. The system is designed to be killed at any instant and still yield a
   consolidated daily file from whatever reached disk.

5. **Record-only isolation.** The recorder shares the live system's *read-only*
   credential inputs and nothing else. It never places orders, never writes to
   the trading DB, and has no path back into the live-money system. See
   PRODUCTION SAFETY in the repo CLAUDE.md.

**Corollary for future work:** keep the hot path boring. If a feature wants to
compute something, it belongs in a consumer that reads the parquet, not in the
recorder.

---

## 2. Deployed safety layers (current)

| Layer | Trigger | Behaviour |
|-------|---------|-----------|
| **Disk guard** (2026-07-09) | Pre-session gate + in-session poll (60s) | Arm FULL ≥8GB free; CORE-ONLY ≥4GB; pause <2GB; resume ≥3GB. Retention sweep keeps 10d. |
| **Writer rotation** (2026-07-10) | Every `rotate_interval_s` (1200s ≈ 40 row-groups) | Closes + seals the open ParquetWriter into a part, releasing its metadata. Memory = bounded sawtooth. |
| **Flush cadence** (2026-07-10) | `flush_interval_s` 5 → 30 | 6× fewer row-groups. Worst-case loss on a hard kill: ≤30s of ticks (was ≤5s). |
| **Streaming consolidation** (2026-07-10) | EOD `close()` | Merges parts one 64K-row batch at a time (`_stream_consolidate`) instead of materializing the whole day (`concat_tables`). Peak = one batch. |
| **RSS watermark** (2026-07-10) | `mem_log_interval_s` (300s) in-session | Logs `rss / peak / writers / rotated` so a leak is visible live, not only in a post-mortem. |
| **cgroup cap** (2026-07-10) | `mem_limit`/`memswap_limit` = 1500m | Converts any future leak into a recorder-only OOM kill + auto-restart, never a host hang. No spill into host swap. |

---

## 3. Incident log

### 2026-07-09 — disk-full
Recorder filled the root volume. Fix: pre-session disk gate (8/4GB) + in-session
pause/resume (<2GB / ≥3GB) + 10-day retention sweep + salvage of partial files.
Shipped in commit `10ff11d`.

### 2026-07-10 — host hang (OOM with no OOM-kill)
**Symptom:** the host thrashed to a standstill; SSH barely responsive; no
process was killed.

**Root cause (two compounding leaks):**
1. An open `pyarrow.ParquetWriter` retains ~33KB of row-group metadata per
   `write_table()` and frees it only at `close()`. Held open for a ~6h session
   across ~435 instruments at a 5s flush cadence, committed memory climbed past
   **4GB in the first hour** — a monotonic ramp, exactly what doctrine §3
   forbids.
2. EOD consolidation used `pa.concat_tables(read all parts)`, materializing an
   entire instrument-day in RAM at once — a second OOM path stacked on the first.

**Why nothing was killed:** the recorder container had **no cgroup memory
limit**, so the kernel had no per-container ceiling to enforce. RAM + the
(then 2GB) swap were exhausted host-wide; the OOM killer had no bounded cgroup
to target, so it thrashed instead of killing.

**Fix (all deployed, image rebuilt, verified post-reboot):**
- **B1 — writer rotation:** `_rotate_primary()` closes/seals the writer every
  `rotate_interval_s`, releasing metadata → sawtooth memory.
- **B2 — flush 5s→30s:** 6× fewer row-groups, ≤30s worst-case data loss.
- **Streaming consolidation:** `_stream_consolidate()` merges parts one 64K-row
  batch at a time. Applied to both `InstrumentWriter` and `EventWriter`.
- **RSS watermark loop:** in-session memory now logged every 5 min.
- **cgroup cap:** `mem_limit`/`memswap_limit` = 1500m (≈6× steady-state RSS of
  ~250MB in-session). Any future leak → recorder-only OOM kill + auto-restart
  via `restart: unless-stopped`, never a host hang.

**Host hardening done the same night (outside this module's code):**
swap 2GB→4GB; `vm.swappiness=10` + `vm.overcommit_memory=1` (persisted in
`/etc/sysctl.d/99-tradetri-mem.conf`); docker `daemon.json` log rotation
(10m × 3); Redis AOF repaired + proven restart-safe; 21 apt packages upgraded
(incl. docker-ce); kernel → 6.17.0-1019-aws. Verified live after reboot.

**Parity:** rotation/streaming paths produce the same consolidated daily file
as the old single-writer path (row counts + schema equal). Covered by the
+89 lines added to `tests/test_writer.py`; full suite 93 passed.

---

## 4. Runbook quick-refs

- **Next live session:** Monday 2026-07-13 09:05 IST (recorder auto-connects;
  idle-sleeps until then).
- **Token refresh cron:** `0 3 * * 1-5` → `scripts/auto_login.py` (host crontab).
- **Watch during first live session:** `docker logs -f orderflow_recorder`
  → confirm the `memory watermark:` line stays flat (sawtooth), `rotated`
  count climbs, and RSS holds well under the 1500m cap.
- **Config knobs:** `orderflow_engine/config.yaml` → `storage.rotate_interval_s`
  (0 disables rotation), `flush_interval_s`, `mem_log_interval_s`.

---

## 5. Module R1 — 20-level market depth recorder

Separate daemon (`recorder.depth_main`) in its OWN container
(`orderflow_depth_recorder`), sharing R0's image + read-only token but a different
entrypoint. Built 2026-07-11 on `feat/orderflow-r1-depth`.

- **Feed:** Dhan's 20-depth feed is a *separate endpoint*
  (`wss://depth-api-feed.dhan.co/twentydepth`, RequestCode 23, 50 instruments/
  connection), so it never touches R0's `api-feed.dhan.co` sockets. Bid (feed code
  41) and ask (51) arrive as separate 332-byte packets; each is stored as one
  side-tagged row (kdb+tick-clean — no cross-packet state; the book is
  reconstructed downstream for OFI).
- **Universe (18):** the 4 NSE index futures (NIFTY, BANKNIFTY, FINNIFTY,
  MIDCPNIFTY) + 14 NSE cash equities. **SENSEX is excluded** — the depth feed is
  NSE-only and SENSEX is BSE. All 18 fit in one connection.
- **Connection budget:** R0 uses 3 sockets, R1 uses 1. If Dhan's 5-connection cap
  is shared per client_id, that's 4/5 — safe. **Do NOT raise R0 to 5 connections
  while R1 runs** (would risk an `805` first-socket disconnect).
- **Writing:** journal-only from day one (open→write→close→fsync→rename per
  buffer; nothing retained). `mem_limit`/`memswap_limit` = 1000m. The R0 OOM class
  of bug is structurally impossible here.
- **EOD wiring:** data lands in `data/{date}/depth/`. R0's recursive S3 backup
  (`rglob`) uploads it automatically; R0's whole-day retention removes it
  automatically. R1 writes ONLY under `depth/` (its own `depth/manifest.json`,
  `depth/report.json`, `depth/events.parquet`) and runs NO S3 backup and NO
  whole-day retention — R0 owns the day-folder lifecycle. R0's `verify_session`
  uses a non-recursive glob, so it ignores `depth/` (no interference either way).
- **Depth-only retention = 5 days** (`depth.retention.days`), shorter than R0's 10.
  Rationale: S3 is the durable copy (558/558 verified 2026-07-10), so the local
  `depth/` subtree is only a replay-convenience buffer. `depth_retention.py` prunes
  the `depth/` subtree of days older than 5 (guarded by `depth/report.json` +
  the day's `backup.json` success), leaving R0's ticks/day-folder intact.
- **Kill switch:** `config.yaml` → `depth.enabled: false` (one line) idles the
  whole depth recorder.
- **Watch on first depth session:** `docker logs -f orderflow_depth_recorder`
  → `depth memory watermark:` flat, per-instrument rows climbing, RSS << 1000m.

### Open / scheduled items
- **Separate data volume — SCHEDULED next weekend (gated).** Depth adds an
  estimated ~0.5–1.5 GB/day (18 instruments; update-rate is the big unknown,
  refine after day 1). With ~14 GB free, R0 (10d) + depth (5d ≈ 2.5–7.5 GB) +
  disk-guard backstop fits for now, but a dedicated volume is the proper fix. Do
  the data-path migration only AFTER Mon–Fri proves the stack — never this close
  to Monday's first clean day.
- **BSE 20-depth entitlement — curiosity, do NOT investigate now.** The docs say
  the depth feed is "NSE Equity and Derivatives" only, so SENSEX (BSE_FNO) has no
  depth. SENSEX execution uses R0's option-chain + tick data instead. Worth a
  later check whether Dhan ever exposes BSE depth; not a priority.
- **Persist R5 `iv_history` durably — POST-MONDAY follow-up.** R5's IV-percentile
  scaffolding accumulates one ATM-IV per index per session into
  `analysis/iv_history/{index}.parquet`. That is the ONE cross-day-accumulating
  derived artifact — it is gitignored + S3-excluded like all of `analysis/`, and
  cheap to rebuild *only while the raw days still exist* (10d tick / 5d depth
  retention). Once raw days age out, the IV history can't be rebuilt. After Monday
  proves the stack, move `iv_history` to a durable store (a dedicated S3 prefix,
  or a small committed-side parquet) so the IV-percentile series survives raw
  retention. Not urgent (percentile is UNCALIBRATED until 20 sessions anyway).


### 2026-07-21 — BSE stock-F&O deploy + ROLLBACK (pre-bse)
Deployed BSE Ltd FUTSTK + OPTSTK ATM±10 (commit 8d4eb6b, merge 5f396a3). NOTE: the
previously-running image's layers had been PRUNED from the store (13-Jul cleanup), so no
tag/commit of the running image was possible — `orderflow-recorder:pre-bse`
(fd5935c024f0) was built from git ffcc464 (the last pre-BSE commit; recorder-baked files
verified identical to the running era — the BSE commit is the only recorder/config change
since). LESSON: never `docker image prune` without first tagging the running image.

**2-MINUTE ROLLBACK (existing universe not ticking by 09:20 / crash loop / resolve errors):**
```
cd /home/ubuntu/trading-bridge/orderflow_engine
docker tag orderflow-recorder:pre-bse orderflow-recorder:latest
docker compose up -d --no-deps recorder depth_recorder
docker ps --filter name=orderflow --format '{{.Names}} {{.Status}}'   # both Up
docker logs orderflow_recorder --since 2m | tail -20                  # clean start
```
(Recreates both recorders on the pre-BSE image; data/ is a bind mount — untouched.)


### 2026-07-22 — WEDNESDAY 09:15 IST FIRST-SESSION CHECKLIST (BSE deploy)
Run in order; PRIORITY #1 is (b) — the existing universe.
```
cd /home/ubuntu/trading-bridge/orderflow_engine
# (a) BSE armed — expect "resolved BSE stock future", "resolved BSE stock option
#     chain", then "armed BSE options: ... -> N strikes" (expect N=21, ATM±10):
docker logs orderflow_recorder --since 30m | grep -iE "BSE (stock|options)|armed BSE"
# (b) PRIORITY #1 — existing universe ticking (files growing):
watch -n5 'ls -la data/2026-07-22/NIFTY_FUT_*.tmp data/2026-07-22/BANKNIFTY_FUT_*.tmp 2>/dev/null'
ls -la data/2026-07-22/depth/ | head -5          # depth journal growing
# (c) BSE fut ticks + depth:
ls -la data/2026-07-22/BSE_FUT_*.tmp 2>/dev/null && echo BSE_FUT_TICKING
# (d) BSE option ticks + manifest entries:
ls data/2026-07-22/ | grep -c "^BSE_[CP]E_"       # >0 once armed
python3 -c "import json;m=json.load(open('data/2026-07-22/manifest.json'));print(sum(1 for e in m['instruments'] if e['symbol'].startswith('BSE_')),'BSE manifest entries')"
# (e) disk-guard normal:
docker logs orderflow_recorder --since 30m | grep -iE "disk|guard|pause" | tail -3
```
ROLLBACK TRIGGERS (any one -> run the 2-MINUTE ROLLBACK block above IMMEDIATELY,
verify the old recorder healthy, done by 09:25):
  * existing universe (NIFTY/BANKNIFTY ticks or depth) not flowing by 09:20
  * crash loop (restarts > 0 / container flapping)
  * resolve errors in (a)


### 2026-07-22 — ONE-TIME MORNING WATCHDOG (alert-only, 09:20 IST)
scripts/morning_watchdog.py runs ONCE via a DATE-GUARDED cron line (host clock UTC;
09:20 IST = 03:50 UTC — same TZ convention as the 15:50-IST evening-pipeline line;
`at` rejected: atd not installed). The inline `date +%F` guard makes it one-shot:
  50 3 22 7 * [ "$(date +\%F)" = "2026-07-22" ] && cd /home/ubuntu/trading-bridge/orderflow_engine && python3 scripts/morning_watchdog.py >> /home/ubuntu/oe_morning_watchdog.log 2>&1
It checks containers/resolve-log/tick-files/BSE_FUT/log-errors and sends ONE Telegram
(reuses the Pulse transport, ORDERFLOW_TELEGRAM_*). It NEVER acts — rollback stays a
human decision (pre-bse block above).
FAIL-SAFE: NO message by 09:25 == the watchdog itself failed — treat as UNKNOWN state
and run the Wednesday checklist by hand.
REMOVAL: delete this cron line Saturday 2026-07-26 (it is date-guarded and inert after
07-22, but do not let dead lines accumulate).

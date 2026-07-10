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

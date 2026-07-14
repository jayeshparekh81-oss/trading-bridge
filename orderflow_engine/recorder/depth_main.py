#!/usr/bin/env python3
"""Depth recorder daemon entrypoint (Module R1).

A SEPARATE daemon from R0 (its own container/service), capturing Dhan's 20-level
market-depth feed for a small liquid core: NSE index futures + NSE cash equities.
BSE (SENSEX) is excluded — the depth feed is NSE-only.

Same session discipline as R0 (connect 09:05, record 09:07–15:35, verify 15:40,
weekends/holidays skipped) and the same read-only daily-minted token. Writing is
journal-only (open→write→close, retain nothing) from day one. Data lands under
``data/{date}/depth/`` so R0's existing recursive S3 backup + day-folder retention
cover it automatically; a separate SHORTER depth retention prunes the local
``depth/`` subtree. Pure recorder — no order placement anywhere.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from recorder import scrip_master as SM
from recorder.creds import get_dhan_credentials, load_env_files
from recorder.depth_feed import DepthConnectionManager
from recorder.depth_retention import depth_retention_sweep
from recorder.depth_verify import verify_depth, write_report
from recorder.depth_writer import DepthWriter, set_error_log_interval
from recorder.diskguard import DiskGuard
from recorder.scheduler import IST, Phase, Scheduler, load_holidays
from recorder.watchdog import Watchdog
from recorder.writer import EventWriter

log = logging.getLogger("recorder.depth_main")

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/


def _rss_mb() -> float | None:
    try:
        with open("/proc/self/statm") as fh:
            pages = int(fh.read().split()[1])
    except (OSError, IndexError, ValueError):
        return None
    return pages * os.sysconf("SC_PAGESIZE") / (1024 ** 2)


def _now() -> datetime:
    return datetime.now(IST)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")


@dataclass
class DepthRec:
    symbol: str
    exchange_segment: str
    security_id: int
    kind: str            # future | equity


class DepthRecorder:
    def __init__(self, config: dict, root: Path = HERE):
        self.cfg = config
        self.root = root
        d = config.get("depth", {}) or {}
        self.depth_cfg = d
        self.enabled = bool(d.get("enabled", False))
        self.data_dir = root / config["storage"]["data_dir"]
        self.subdir = str(d.get("data_subdir", "depth"))
        self.n_conn = max(1, min(int(d.get("connections", 1)), 5))
        self.flush_interval = float(d.get("flush_interval_s", 2))
        self.max_buffer = int(d.get("max_buffer_rows", 5000))
        self.mem_log_interval = float(d.get("mem_log_interval_s", 300))
        self.gap_threshold = float(config["watchdog"]["gap_threshold_s"])
        self.poll_interval = float(config["watchdog"]["poll_interval_s"])

        st = config["storage"]
        self.disk_start_gb = float(st.get("min_free_gb_start", 8))
        self.disk_runtime_gb = float(st.get("min_free_gb_runtime", 2))
        self.disk_resume_gb = float(st.get("disk_resume_gb", 3))
        self.disk_check_interval = float(st.get("disk_check_interval_s", 60))
        set_error_log_interval(float(st.get("error_log_interval_s", 300)))

        self.ping_interval = float(config["feed"]["ping_interval_s"])
        self.ping_timeout = float(config["feed"]["ping_timeout_s"])
        self.s3_enabled = bool(config.get("s3_backup", {}).get("enabled", False))
        self.ret_cfg = (d.get("retention", {}) or {})

        sch = config["schedule"]
        self.scheduler = Scheduler(
            connect_time=_parse_hhmm(sch["connect"]),
            record_start=_parse_hhmm(sch["record_start"]),
            record_end=_parse_hhmm(sch["record_end"]),
            verify_time=_parse_hhmm(sch["verify"]),
            holidays=load_holidays(root / "holidays.yaml"),
        )
        self.creds = None
        self.instruments: list[DepthRec] = []
        # per-session mutable state
        self._writers: dict[int, DepthWriter] = {}
        self._events: EventWriter | None = None
        self._seq: dict[int, int] = {}
        self._sym_by_id: dict[int, str] = {}
        self._watchdog: Watchdog | None = None
        self._day_dir: Path | None = None
        self._depth_dir: Path | None = None
        self._paused = False
        self._dropped: dict[int, int] = {}
        self._diskguard: DiskGuard | None = None
        self._last_retention: str | None = None

    # -- startup -------------------------------------------------------------
    def load_credentials(self) -> None:
        env_files = [self.root / p for p in self.cfg["credentials"]["env_files"]]
        load_env_files(env_files)
        self.creds = get_dhan_credentials(
            broker_name=self.cfg["credentials"].get("broker_name", "dhan"))

    def resolve_instruments(self) -> None:
        sm_cfg = self.cfg["scrip_master"]
        csv_path = SM.fetch_scrip_master(
            self.root / sm_cfg["cache_dir"], url=sm_cfg["url"],
            today=_now().date(), stale_hours=int(sm_cfg["stale_hours"]))
        rows = SM.load_rows(csv_path)
        ref = _now().date()

        idx_by_name = {i["name"]: i for i in self.cfg.get("indices", [])}
        recs: list[DepthRec] = []
        for name in self.depth_cfg.get("index_futures", []):
            idx = idx_by_name.get(name)
            if idx is None:
                log.warning("depth: index %s not in config indices; skipping", name)
                continue
            ft = idx["future"]
            fut = SM.resolve_future(rows, ref_date=ref, underlying=ft["underlying"],
                                    exch=ft.get("exch", "NSE"),
                                    segment=ft["exchange_segment"], symbol=f"{name}_FUT")
            if fut.exchange_segment not in ("NSE_FNO", "NSE_EQ"):
                log.warning("depth: %s future is %s — depth feed is NSE-only; SKIPPING",
                            name, fut.exchange_segment)
                continue
            recs.append(DepthRec(f"{name}_FUT", fut.exchange_segment, fut.security_id, "future"))
            log.info("depth resolved %s future -> %s (%s, expiry %s)",
                     name, fut.security_id, fut.trading_symbol, fut.expiry)

        for sym in self.depth_cfg.get("equities", []):
            try:
                inst = SM.resolve_equity(rows, sym, exch="NSE", segment="NSE_EQ")
                recs.append(DepthRec(inst.symbol, inst.exchange_segment,
                                     inst.security_id, "equity"))
                log.info("depth resolved equity %s -> id=%s", inst.symbol, inst.security_id)
            except LookupError as exc:
                log.warning("depth: skipping equity %s: %s", sym, exc)

        # dedupe by security_id
        seen: set[int] = set()
        deduped: list[DepthRec] = []
        for r in recs:
            if r.security_id in seen:
                continue
            seen.add(r.security_id)
            deduped.append(r)
        self.instruments = deduped

        cap = self.n_conn * 50
        if len(self.instruments) > cap:
            raise RuntimeError(
                f"depth instrument count {len(self.instruments)} exceeds capacity "
                f"{cap} ({self.n_conn} conns x 50); raise depth.connections")
        log.info("depth universe: %d instruments across %d connection(s) (cap %d)",
                 len(self.instruments), self.n_conn, cap)

    # -- packet handling -----------------------------------------------------
    def _on_packet(self, parsed: dict, ts_recv_ns: int) -> None:
        if not parsed.get("is_depth"):
            self._record_event_packet(parsed, ts_recv_ns)
            return
        sid = parsed["security_id"]
        writer = self._writers.get(sid)
        if writer is None:
            return
        if self._paused:
            self._dropped[sid] = self._dropped.get(sid, 0) + 1
            if self._watchdog is not None and sid in self._watchdog.last_ts:
                self._watchdog.on_packet(sid, ts_recv_ns)
            return
        seq = self._seq.get(sid, 0)
        self._seq[sid] = seq + 1
        parsed["ts_recv_ns"] = ts_recv_ns
        parsed["seq_local"] = seq
        writer.add(parsed)
        if self._watchdog is not None and sid in self._watchdog.last_ts:
            gap = self._watchdog.on_packet(sid, ts_recv_ns)
            if gap is not None and self._events is not None:
                self._events.add(ts_recv_ns, "GAP",
                                 f"{self._sym_by_id.get(sid, sid)} gap",
                                 security_id=sid, value_num=gap.duration_s)

    def _record_event_packet(self, parsed: dict, ts_recv_ns: int) -> None:
        if self._events is None:
            return
        if parsed.get("event") == "disconnect":
            self._events.add(ts_recv_ns, "DISCONNECT",
                             f"code={parsed.get('reason_code')} {parsed.get('reason')}",
                             security_id=parsed.get("security_id"),
                             value_num=float(parsed.get("reason_code") or 0))

    def _on_feed_event(self, kind: str, detail: str, value_num) -> None:
        if self._events is not None:
            self._events.add(time.time_ns(), kind, detail, value_num=value_num)
        log.info("depth feed event %s: %s", kind, detail)

    # -- session -------------------------------------------------------------
    def _make_writer(self, rec: DepthRec) -> None:
        self._writers[rec.security_id] = DepthWriter(
            self._depth_dir, rec.symbol, rec.security_id, max_buffer=self.max_buffer)
        self._sym_by_id[rec.security_id] = rec.symbol

    def _write_manifest(self) -> None:
        if self._depth_dir is None:
            return
        out = self._depth_dir / "manifest.json"
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({
            "date": self._day_dir.name, "kind": "depth",
            "instruments": [{"symbol": r.symbol, "security_id": r.security_id,
                             "exchange_segment": r.exchange_segment, "kind": r.kind}
                            for r in self.instruments],
        }, indent=2, default=str))
        tmp.replace(out)

    def _open_session(self, day_dir: Path) -> None:
        self._day_dir = day_dir
        self._depth_dir = day_dir / self.subdir
        self._depth_dir.mkdir(parents=True, exist_ok=True)
        self._events = EventWriter(self._depth_dir)   # -> depth/events.parquet
        self._writers, self._seq, self._sym_by_id = {}, {}, {}
        self._watchdog = Watchdog(threshold_s=self.gap_threshold)
        self._paused = False
        self._dropped = {}
        self._diskguard = self._make_diskguard()
        for rec in self.instruments:
            self._make_writer(rec)
        self._write_manifest()
        self._events.add(time.time_ns(), "SESSION", f"start {day_dir.name} (depth)")

    def _seed_watchdog(self) -> None:
        seed = time.time_ns()
        for rec in self.instruments:      # all depth instruments are gap-checked
            self._watchdog.register(rec.security_id, seed_ns=seed)

    def _close_session(self, reason: str) -> None:
        for w in self._writers.values():
            try:
                w.close()
            except Exception:  # noqa: BLE001
                log.exception("error closing depth writer %s", w.symbol)
        if self._watchdog is not None and self._events is not None:
            for gap in self._watchdog.close_all(time.time_ns()):
                self._events.add(gap.end_ns, "GAP",
                                 f"{self._sym_by_id.get(gap.security_id, gap.security_id)} open-ended",
                                 security_id=gap.security_id, value_num=gap.duration_s)
        if self._events is not None:
            self._events.add(time.time_ns(), "SESSION", f"end ({reason})")
            self._events.close()
        total_rows = sum(w.rows_written for w in self._writers.values())
        dropped = sum(w.dropped for w in self._writers.values())
        log.info("depth session closed (%s); %d instruments, %d rows, %d dropped",
                 reason, len(self._writers), total_rows, dropped)
        self._writers, self._events, self._watchdog = {}, None, None

    def _free_gb(self) -> float:
        target = self.data_dir if self.data_dir.exists() else self.data_dir.parent
        return shutil.disk_usage(target).free / (1024 ** 3)

    def _make_diskguard(self) -> DiskGuard:
        return DiskGuard(
            min_free_gb_start=self.disk_start_gb,
            min_free_gb_core_only=self.disk_start_gb,   # depth is all-or-nothing
            min_free_gb_runtime=self.disk_runtime_gb,
            disk_resume_gb=self.disk_resume_gb,
            free_gb_fn=self._free_gb)

    async def _flush_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await _sleep_or_stop(stop, self.flush_interval)
            for w in list(self._writers.values()):
                try:
                    w.flush()
                except Exception:  # noqa: BLE001
                    log.exception("depth flush error for %s", w.symbol)

    async def _mem_loop(self, stop: asyncio.Event) -> None:
        peak = 0.0
        while not stop.is_set():
            await _sleep_or_stop(stop, self.mem_log_interval)
            rss = _rss_mb()
            if rss is None:
                continue
            peak = max(peak, rss)
            rows = sum(w.rows_written for w in self._writers.values())
            log.info("depth memory watermark: rss=%.1fMB peak=%.1fMB writers=%d rows=%d",
                     rss, peak, len(self._writers), rows)

    async def _disk_loop(self, stop: asyncio.Event) -> None:
        if self._diskguard is None:
            await stop.wait()   # no guard configured, but must NOT complete early
            return              # (else FIRST_COMPLETED would tear the session down)
        while not stop.is_set():
            await _sleep_or_stop(stop, self.disk_check_interval)
            try:
                transition = self._diskguard.runtime_check()
            except OSError:
                continue
            if transition == "pause":
                self._paused = True
                for w in list(self._writers.values()):
                    try:
                        w.flush()
                    except Exception:  # noqa: BLE001
                        pass
                if self._events is not None:
                    self._events.add(time.time_ns(), "DISK_FULL",
                                     f"depth writes paused, {self._diskguard.free_gb():.2f}GB free",
                                     value_num=self._diskguard.free_gb())
            elif transition == "resume":
                self._paused = False
                dropped_total = sum(self._dropped.values())
                if self._events is not None:
                    self._events.add(time.time_ns(), "DISK_RESUME",
                                     f"depth writes resumed; {dropped_total} rows dropped",
                                     value_num=float(dropped_total))
                self._dropped.clear()

    async def _watchdog_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await _sleep_or_stop(stop, self.poll_interval)
            if self._watchdog is None or self.scheduler.phase(_now()) is not Phase.RECORD:
                continue
            for sid in self._watchdog.poll(time.time_ns()):
                if self._events is not None:
                    self._events.add(time.time_ns(), "GAP_OPEN",
                                     f"{self._sym_by_id.get(sid, sid)} silent > {self.gap_threshold}s",
                                     security_id=sid)

    async def run_session(self, global_stop: asyncio.Event) -> None:
        today = _now().date()
        day_dir = self.data_dir / today.isoformat()
        self._open_session(day_dir)
        session_stop = asyncio.Event()

        mgr = DepthConnectionManager(
            self.n_conn, self.creds.client_id, self.creds.access_token,
            on_packet=self._on_packet, on_event=self._on_feed_event,
            ping_interval=self.ping_interval, ping_timeout=self.ping_timeout)
        # spread instruments across the (few) connections, round-robin
        for i, rec in enumerate(self.instruments):
            mgr.assign(i % self.n_conn, [(rec.exchange_segment, rec.security_id)])
        self._seed_watchdog()

        tasks = [
            asyncio.create_task(mgr.run(session_stop), name="depth_feeds"),
            asyncio.create_task(self._flush_loop(session_stop), name="depth_flush"),
            asyncio.create_task(self._watchdog_loop(session_stop), name="depth_watchdog"),
            asyncio.create_task(self._disk_loop(session_stop), name="depth_disk"),
            asyncio.create_task(self._mem_loop(session_stop), name="depth_mem"),
            asyncio.create_task(self._session_clock(session_stop, global_stop, today),
                                name="depth_clock"),
        ]
        try:
            # Same teardown rule as recorder.main (2026-07-13 hang): never await
            # the feed tasks — the feed's websocket async-for blocks forever on
            # an idle-but-open connection. Wait for the FIRST completed task (the
            # clock, at record_end; or any crashed task) and let the finally
            # cancel the rest.
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if not t.cancelled() and t.exception() is not None:
                    log.error("depth session task %r crashed: %r",
                              t.get_name(), t.exception())
        finally:
            session_stop.set()
            await mgr.close()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            reason = "shutdown" if global_stop.is_set() else "record_end"
            self._close_session(reason)
            if not global_stop.is_set():
                self._run_verify(day_dir)

    async def _session_clock(self, session_stop: asyncio.Event,
                             global_stop: asyncio.Event, today) -> None:
        while not session_stop.is_set():
            if global_stop.is_set():
                session_stop.set()
                return
            if _now() >= self.scheduler.record_end_at(today):
                log.info("depth record_end reached; ending session")
                session_stop.set()
                return
            await _sleep_or_stop(global_stop, 5)

    def _run_verify(self, day_dir: Path) -> None:
        try:
            report = verify_depth(day_dir)
            write_report(day_dir, report)
            log.info("depth verify %s: status=%s, %d instruments, coverage=%.1f%%",
                     day_dir.name, report.get("status"),
                     report.get("counts", {}).get("instrument_files", 0),
                     report.get("coverage", {}).get("coverage_pct", 0.0))
        except Exception:  # noqa: BLE001
            log.exception("depth verification failed for %s", day_dir)

    def _maybe_retention(self, today) -> None:
        if not self.ret_cfg.get("enabled", False):
            return
        if self._last_retention == today.isoformat():
            return
        run_time = _parse_hhmm(self.ret_cfg.get("run_time", "16:10"))
        if _now().timetz().replace(tzinfo=None) < run_time:
            return
        try:
            res = depth_retention_sweep(
                self.data_dir, today=today,
                keep_days=int(self.ret_cfg.get("days", 5)),
                s3_enabled=self.s3_enabled)
            log.info("depth retention: kept %d, deleted %s, skipped %d",
                     len(res.get("kept", [])), res.get("deleted", []),
                     len(res.get("skipped", [])))
        except Exception:  # noqa: BLE001
            log.exception("depth retention sweep failed")
        self._last_retention = today.isoformat()

    async def run(self, global_stop: asyncio.Event) -> None:
        if not self.enabled:
            log.warning("depth recorder DISABLED (depth.enabled=false); idling")
            while not global_stop.is_set():
                await _sleep_or_stop(global_stop, 300)
            return
        ret = (f"{self.ret_cfg.get('days')}d" if self.ret_cfg.get("enabled") else "off")
        log.info("depth recorder config: journal-mode | 20-depth | disk-guard "
                 "start>=%.0fGB runtime<%.0fGB resume>=%.0fGB | flush=%.0fs | "
                 "retention=%s | %d connection(s)",
                 self.disk_start_gb, self.disk_runtime_gb, self.disk_resume_gb,
                 self.flush_interval, ret, self.n_conn)
        log.info("depth recorder starting; %d instruments", len(self.instruments))
        while not global_stop.is_set():
            phase = self.scheduler.phase(_now())
            today = _now().date()
            if phase in (Phase.CONNECT, Phase.RECORD, Phase.WIND_DOWN):
                free = self._free_gb()
                if free < self.disk_start_gb:
                    log.warning("depth: only %.1fGB free (< %.0fGB); SKIPPING depth "
                                "session to protect primary capture", free, self.disk_start_gb)
                    await _sleep_or_stop(global_stop, 300)
                    continue
                try:
                    self.load_credentials()
                    self.resolve_instruments()
                except Exception:  # noqa: BLE001
                    log.exception("depth startup resolution failed; retry in 30s")
                    await _sleep_or_stop(global_stop, 30)
                    continue
                await self.run_session(global_stop)
            else:
                self._maybe_retention(today)
                secs = max(min(self.scheduler.seconds_until_connect(_now()), 300), 5)
                nxt = self.scheduler.next_connect(_now())
                log.info("depth idle (%s); sleeping %.0fs (next connect %s)",
                         phase.value, secs, nxt.strftime("%Y-%m-%d %H:%M IST"))
                await _sleep_or_stop(global_stop, secs)
        log.info("depth recorder stopped")


def _parse_hhmm(s: str):
    from datetime import time as _t
    hh, mm = str(s).split(":")
    return _t(int(hh), int(mm))


async def _sleep_or_stop(stop: asyncio.Event, secs: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=secs)
    except asyncio.TimeoutError:
        pass


def load_config(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


async def _amain() -> int:
    _configure_logging()
    try:
        import uvloop  # type: ignore
        uvloop.install()
        log.info("uvloop enabled")
    except Exception:  # noqa: BLE001
        pass

    config = load_config(HERE / "config.yaml")
    rec = DepthRecorder(config)
    # Eager resolve at startup (parity with R0) so the universe is visible in the
    # boot log immediately. Best-effort: resolution uses the public scrip-master
    # CSV (no live token needed), but a transient failure must not stop the
    # daemon — run() re-resolves per session anyway.
    if rec.enabled:
        try:
            rec.load_credentials()
            rec.resolve_instruments()
        except Exception:  # noqa: BLE001
            log.exception("startup resolve failed (will retry per-session)")
    global_stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: (log.info("signal %s -> shutdown", s),
                                                    global_stop.set()))
    await rec.run(global_stop)
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    sys.exit(main())

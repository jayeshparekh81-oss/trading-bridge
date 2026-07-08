#!/usr/bin/env python3
"""Recorder daemon entrypoint (Module R0).

Runs 24/7. Each trading day: connect at 09:05 IST, record 09:07–15:35, then at
15:40 disconnect + consolidate + verify, and sleep until the next session.

Records, for every configured index: spot + near-month future + ATM±N weekly/
monthly CE/PE option strikes, plus INDIA VIX. Core instruments (spots+futures)
stream from connect; option strikes are ATM-anchored to the LIVE spot at open
and subscribed dynamically ("feed-first"). Instruments are spread across up to 5
websocket connections. Pure recorder — no order placement anywhere.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from recorder import scrip_master as SM
from recorder.creds import get_dhan_credentials, load_env_files
from recorder.feed import ConnectionManager
from recorder.parser import PKT_DISCONNECT, PKT_PREV_CLOSE, PKT_STATUS
from recorder.scheduler import IST, Phase, Scheduler, load_holidays
from recorder.s3_backup import S3Backup
from recorder.schema import normalize_tick_row
from recorder.watchdog import Watchdog
from recorder.writer import EventWriter, InstrumentWriter

log = logging.getLogger("recorder.main")

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/
OPTION_ARM_TIMEOUT_S = 120  # after open, give up waiting for a spot to anchor ATM


def _now() -> datetime:
    return datetime.now(IST)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")


@dataclass
class Rec:
    """A resolved instrument to record."""
    symbol: str
    exchange_segment: str
    security_id: int
    kind: str            # spot | future | option | standalone
    gap_check: bool = False
    expiry: str = ""


@dataclass
class OptionSpec:
    """An index's option config, resolved to a chain at startup; strikes chosen
    at open from the live spot."""
    index: str
    chain: SM.OptionChain
    spot_security_id: int
    future_security_id: int | None
    window: int
    conn_idx: int = 0
    armed: bool = False


class Recorder:
    def __init__(self, config: dict, root: Path = HERE):
        self.cfg = config
        self.root = root
        self.data_dir = root / config["storage"]["data_dir"]
        self.flush_interval = float(config["storage"]["flush_interval_s"])
        self.max_buffer = int(config["storage"]["max_buffer_rows"])
        self.min_free_gb = float(config["storage"]["min_free_gb_warn"])
        self.gap_threshold = float(config["watchdog"]["gap_threshold_s"])
        self.poll_interval = float(config["watchdog"]["poll_interval_s"])
        self.n_conn = max(1, min(int(config.get("connections", {}).get("max", 3)), 5))
        self.opt_window = int(config.get("options", {}).get("atm_window", 5))

        sch = config["schedule"]
        self.scheduler = Scheduler(
            connect_time=_parse_hhmm(sch["connect"]),
            record_start=_parse_hhmm(sch["record_start"]),
            record_end=_parse_hhmm(sch["record_end"]),
            verify_time=_parse_hhmm(sch["verify"]),
            holidays=load_holidays(root / "holidays.yaml"),
        )
        self.s3 = S3Backup(config.get("s3_backup", {}))
        self.creds = None
        self.core: list[Rec] = []
        self.option_specs: list[OptionSpec] = []
        # per-session mutable state
        self._writers: dict[int, InstrumentWriter] = {}
        self._events: EventWriter | None = None
        self._seq: dict[int, int] = {}
        self._watchdog: Watchdog | None = None
        self._sym_by_id: dict[int, str] = {}
        self._latest_price: dict[int, float] = {}
        self._manifest: list[dict] = []
        self._day_dir: Path | None = None

    # -- startup resolution --------------------------------------------------
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

        core: list[Rec] = []
        specs: list[OptionSpec] = []
        for idx in self.cfg.get("indices", []):
            name = idx["name"]
            # spot
            sp = idx["spot"]
            SM.verify_index(rows, int(sp["security_id"]), f"{name}_SPOT",
                            exch=sp.get("exch", "NSE"))
            core.append(Rec(f"{name}_SPOT", sp["exchange_segment"], int(sp["security_id"]),
                            "spot", bool(sp.get("gap_check", True))))
            # future
            ft = idx["future"]
            fut = SM.resolve_future(rows, ref_date=ref, underlying=ft["underlying"],
                                    exch=ft.get("exch", "NSE"),
                                    segment=ft["exchange_segment"], symbol=f"{name}_FUT")
            log.info("resolved %s future -> %s (%s, expiry %s)", name,
                     fut.security_id, fut.trading_symbol, fut.expiry)
            core.append(Rec(f"{name}_FUT", fut.exchange_segment, fut.security_id,
                            "future", bool(ft.get("gap_check", True)), str(fut.expiry)))
            # options (resolve chain now; strikes chosen at open)
            op = idx.get("options", {})
            if op.get("enabled"):
                try:
                    chain = SM.resolve_option_chain(
                        rows, ref_date=ref, underlying=op["underlying"],
                        exch=op.get("exch", "NSE"), segment=op["exchange_segment"])
                    specs.append(OptionSpec(
                        index=name, chain=chain, spot_security_id=int(sp["security_id"]),
                        future_security_id=fut.security_id,
                        window=int(op.get("atm_window", self.opt_window))))
                    log.info("resolved %s option chain -> expiry %s, %d strikes",
                             name, chain.expiry, len(chain.strikes))
                except LookupError as exc:
                    log.warning("no options for %s: %s", name, exc)

        for st in self.cfg.get("standalone", []):
            core.append(Rec(st["symbol"], st["exchange_segment"], int(st["security_id"]),
                            "standalone", bool(st.get("gap_check", False))))

        # assign option groups to connections (core all on conn 0; options across
        # the remaining connections, or conn 0 if only one).
        opt_conns = list(range(1, self.n_conn)) or [0]
        for i, spec in enumerate(specs):
            spec.conn_idx = opt_conns[i % len(opt_conns)]

        self.core = core
        self.option_specs = specs
        log.info("universe: %d core instruments, %d option chains, %d connections",
                 len(core), len(specs), self.n_conn)

    # -- packet handling -----------------------------------------------------
    def _on_packet(self, parsed: dict, ts_recv_ns: int) -> None:
        if parsed.get("is_tick"):
            sid = parsed["security_id"]
            writer = self._writers.get(sid)
            if writer is None:
                return  # not (yet) a subscribed instrument
            seq = self._seq.get(sid, 0)
            self._seq[sid] = seq + 1
            parsed["ts_recv_ns"] = ts_recv_ns
            parsed["seq_local"] = seq
            writer.add(normalize_tick_row(parsed))
            if parsed.get("ltp") is not None:
                self._latest_price[sid] = parsed["ltp"]
            if self._watchdog is not None and sid in self._watchdog.last_ts:
                gap = self._watchdog.on_packet(sid, ts_recv_ns)
                if gap is not None and self._events is not None:
                    self._events.add(ts_recv_ns, "GAP",
                                     f"{self._sym_by_id.get(sid, sid)} gap",
                                     security_id=sid, value_num=gap.duration_s)
        else:
            self._record_event_packet(parsed, ts_recv_ns)

    def _record_event_packet(self, parsed: dict, ts_recv_ns: int) -> None:
        if self._events is None:
            return
        pt = parsed.get("packet_type")
        sid = parsed.get("security_id")
        if pt == PKT_DISCONNECT:
            self._events.add(ts_recv_ns, "DISCONNECT",
                             f"code={parsed.get('reason_code')} {parsed.get('reason')}",
                             security_id=sid, value_num=float(parsed.get("reason_code") or 0))
        elif pt == PKT_STATUS:
            self._events.add(ts_recv_ns, "STATUS", "market status", security_id=sid)
        elif pt == PKT_PREV_CLOSE:
            self._events.add(ts_recv_ns, "PREV_CLOSE",
                             f"prev_close={parsed.get('prev_close')}", security_id=sid,
                             value_num=parsed.get("prev_close"))

    def _on_feed_event(self, kind: str, detail: str, value_num) -> None:
        if self._events is not None:
            self._events.add(time.time_ns(), kind, detail, value_num=value_num)
        log.info("feed event %s: %s", kind, detail)

    # -- session -------------------------------------------------------------
    def _make_writer(self, rec: Rec) -> None:
        self._writers[rec.security_id] = InstrumentWriter(
            self._day_dir, rec.symbol, rec.security_id, max_buffer=self.max_buffer)
        self._sym_by_id[rec.security_id] = rec.symbol
        self._manifest.append({
            "symbol": rec.symbol, "security_id": rec.security_id,
            "exchange_segment": rec.exchange_segment, "kind": rec.kind,
            "gap_check": rec.gap_check, "expiry": rec.expiry,
        })

    def _write_manifest(self) -> None:
        if self._day_dir is None:
            return
        out = self._day_dir / "manifest.json"
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"date": self._day_dir.name,
                                   "instruments": self._manifest}, indent=2, default=str))
        tmp.replace(out)

    def _open_session(self, day_dir: Path) -> None:
        day_dir.mkdir(parents=True, exist_ok=True)
        self._day_dir = day_dir
        self._events = EventWriter(day_dir)
        self._writers, self._seq, self._sym_by_id = {}, {}, {}
        self._latest_price, self._manifest = {}, []
        self._watchdog = Watchdog(threshold_s=self.gap_threshold)
        for rec in self.core:
            self._make_writer(rec)
        self._write_manifest()
        self._events.add(time.time_ns(), "SESSION", f"start {day_dir.name}")
        self._check_disk()

    def _seed_watchdog(self) -> None:
        seed = time.time_ns()
        for rec in self.core:
            if rec.gap_check:
                self._watchdog.register(rec.security_id, seed_ns=seed)

    async def _arm_options(self, stop: asyncio.Event, mgr: ConnectionManager) -> None:
        """Once recording opens, anchor ATM to the live spot and subscribe strikes."""
        if not self.option_specs:
            return
        deadline = None
        pending = list(self.option_specs)
        while not stop.is_set() and pending:
            if self.scheduler.phase(_now()) is not Phase.RECORD:
                await _sleep_or_stop(stop, 1)
                continue
            if deadline is None:
                deadline = time.monotonic() + OPTION_ARM_TIMEOUT_S
            still: list[OptionSpec] = []
            for spec in pending:
                spot = self._latest_price.get(spec.spot_security_id)
                if spot is None and time.monotonic() < deadline:
                    still.append(spec)
                    continue
                if spot is None and spec.future_security_id is not None:
                    spot = self._latest_price.get(spec.future_security_id)  # fallback
                if spot is None:
                    log.warning("no spot for %s after %ss; SKIPPING its options",
                                spec.index, OPTION_ARM_TIMEOUT_S)
                    self._on_feed_event("OPTIONS_SKIP", f"{spec.index} no spot", None)
                    continue
                await self._arm_one(spec, spot, mgr)
            pending = still
            await _sleep_or_stop(stop, 1)

    async def _arm_one(self, spec: OptionSpec, spot: float, mgr: ConnectionManager) -> None:
        insts = SM.select_atm_window(spec.chain, spot, spec.window)
        if not insts:
            log.warning("no ATM strikes selected for %s (spot %s)", spec.index, spot)
            return
        for inst in insts:
            rec = Rec(inst.symbol, inst.exchange_segment, inst.security_id,
                      "option", gap_check=False, expiry=str(inst.expiry))
            self._make_writer(rec)
        self._write_manifest()
        await mgr.add(spec.conn_idx, [(i.exchange_segment, i.security_id) for i in insts])
        spec.armed = True
        strikes = sorted({int(i.symbol.split("_")[-1]) for i in insts})
        log.info("armed %s options: expiry %s spot %.2f -> %d strikes %s (conn%d)",
                 spec.index, spec.chain.expiry, spot, len(strikes), strikes, spec.conn_idx)
        self._on_feed_event("OPTIONS_ARMED",
                            f"{spec.index} exp={spec.chain.expiry} spot={spot:.2f} "
                            f"strikes={strikes}", float(len(insts)))

    def _close_session(self, reason: str) -> None:
        for w in self._writers.values():
            try:
                w.close()
            except Exception:  # noqa: BLE001
                log.exception("error closing writer %s", w.symbol)
        if self._watchdog is not None and self._events is not None:
            for gap in self._watchdog.close_all(time.time_ns()):
                self._events.add(gap.end_ns, "GAP",
                                 f"{self._sym_by_id.get(gap.security_id, gap.security_id)} open-ended",
                                 security_id=gap.security_id, value_num=gap.duration_s)
        if self._events is not None:
            self._events.add(time.time_ns(), "SESSION", f"end ({reason})")
            self._events.close()
        total_rows = sum(w.rows_written for w in self._writers.values())
        log.info("session closed (%s); %d instruments, %d rows total",
                 reason, len(self._writers), total_rows)
        self._writers, self._events, self._watchdog = {}, None, None

    def _check_disk(self) -> None:
        try:
            free_gb = shutil.disk_usage(self.data_dir).free / (1024 ** 3)
            if free_gb < self.min_free_gb:
                log.warning("LOW DISK: %.1f GB free (< %.1f GB threshold)",
                            free_gb, self.min_free_gb)
                if self._events is not None:
                    self._events.add(time.time_ns(), "DISK",
                                     f"low disk {free_gb:.1f}GB", value_num=free_gb)
            else:
                log.info("disk free: %.1f GB", free_gb)
        except OSError:
            log.warning("could not check disk usage for %s", self.data_dir)

    async def _flush_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await _sleep_or_stop(stop, self.flush_interval)
            for w in list(self._writers.values()):
                try:
                    w.flush()
                except Exception:  # noqa: BLE001
                    log.exception("flush error for %s", w.symbol)

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

        mgr = ConnectionManager(
            self.n_conn, self.creds.client_id, self.creds.access_token,
            on_packet=self._on_packet, on_event=self._on_feed_event,
            ping_interval=float(self.cfg["feed"]["ping_interval_s"]),
            ping_timeout=float(self.cfg["feed"]["ping_timeout_s"]))
        # core instruments all stream on connection 0 from connect
        mgr.assign(0, [(rec.exchange_segment, rec.security_id) for rec in self.core])
        self._seed_watchdog()

        tasks = [
            asyncio.create_task(mgr.run(session_stop), name="feeds"),
            asyncio.create_task(self._flush_loop(session_stop), name="flush"),
            asyncio.create_task(self._watchdog_loop(session_stop), name="watchdog"),
            asyncio.create_task(self._arm_options(session_stop, mgr), name="arm_options"),
            asyncio.create_task(self._session_clock(session_stop, global_stop, today),
                                name="clock"),
        ]
        try:
            await asyncio.gather(*tasks)
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
                await self._backup(day_dir)   # durable, server-independent copy

    async def _session_clock(self, session_stop: asyncio.Event,
                             global_stop: asyncio.Event, today) -> None:
        while not session_stop.is_set():
            if global_stop.is_set():
                session_stop.set()
                return
            if _now() >= self.scheduler.record_end_at(today):
                log.info("record_end reached; ending session")
                session_stop.set()
                return
            await _sleep_or_stop(global_stop, 5)

    async def _backup(self, day_dir: Path) -> None:
        """Upload the consolidated+verified day to S3 (local copy always kept).

        Runs in a thread so retry/backoff never blocks the event loop, and never
        raises — a backup failure must not stop the recorder. report.json and
        events.parquet already exist here, so the S3 copy is complete; backup.json
        is written + uploaded last as the audit marker.
        """
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self.s3.backup_day, day_dir)
            self.s3.write_audit(day_dir, result)
            await loop.run_in_executor(None, self.s3.upload_marker, day_dir,
                                       day_dir / "backup.json")
            if not result.skipped and not result.success:
                log.error("S3 BACKUP INCOMPLETE for %s — %d/%d files failed; see backup.json",
                          day_dir.name, result.fail_count, len(result.files))
        except Exception:  # noqa: BLE001 - local data is safe regardless
            log.exception("backup step errored for %s (local copy intact)", day_dir.name)

    def _run_verify(self, day_dir: Path) -> None:
        try:
            import verify_session
            report = verify_session.verify_session(day_dir)
            verify_session._print_report(report)
            out = day_dir / "report.json"
            tmp = out.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(report, indent=2, default=str))
            tmp.replace(out)
        except Exception:  # noqa: BLE001
            log.exception("verification failed for %s", day_dir)

    async def run(self, global_stop: asyncio.Event) -> None:
        log.info("recorder starting; %d core instruments, %d option chains",
                 len(self.core), len(self.option_specs))
        while not global_stop.is_set():
            phase = self.scheduler.phase(_now())
            if phase in (Phase.CONNECT, Phase.RECORD, Phase.WIND_DOWN):
                try:
                    self.load_credentials()      # refresh daily-minted token
                    self.resolve_instruments()   # refresh expiries/strikes for the day
                except Exception:  # noqa: BLE001
                    log.exception("startup resolution failed; retry in 30s")
                    await _sleep_or_stop(global_stop, 30)
                    continue
                await self.run_session(global_stop)
            else:
                secs = max(min(self.scheduler.seconds_until_connect(_now()), 300), 5)
                log.info("idle (%s); sleeping %.0fs until next check", phase.value, secs)
                await _sleep_or_stop(global_stop, secs)
        log.info("recorder stopped")


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
    rec = Recorder(config)
    rec.load_credentials()
    rec.resolve_instruments()

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

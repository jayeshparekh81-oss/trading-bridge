#!/usr/bin/env python3
"""Session verification — run automatically at 15:40 IST and on demand.

Usage:
    python verify_session.py [data/YYYY-MM-DD]   (defaults to today's IST dir)

Reports (stdout + data/{date}/report.json):
  * packets per instrument per type; first/last ltt; wall-clock coverage %
  * gap events: count + total gap seconds (PASS if 0 gaps > threshold)
  * volume monotonic non-decreasing check on the future
  * parquet schema validation + row counts + file sizes
  * overall PASS/FAIL banner
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from recorder.parser import PACKET_TYPE_NAMES
from recorder.schema import TICK_COLUMNS

IST = ZoneInfo("Asia/Kolkata")
# Expected recording window 09:07–15:35 = 23280s (used for coverage %).
EXPECTED_SESSION_S = (15 * 3600 + 35 * 60) - (9 * 3600 + 7 * 60)
GAP_THRESHOLD_S = 10.0                        # 2026-07-15 recalibration: watched index
                                              # instruments legitimately go quiet 3-10s
                                              # (cadence, 96% of raw gaps) — sub-10s is not
                                              # a fault. Only gaps over this reach the log.
# Day-verdict is SCOPED to the liquid tradeable instruments (gaps AND volume): an
# anomaly there implies real signal risk. Thin futures (FINNIFTY/MIDCPNIFTY/SENSEX) +
# all index spots keep logging metrics but do NOT drive PASS/PARTIAL. (Thin futures'
# tiny daily volume inflates any jitter % — e.g. FINNIFTY 60 contracts = 0.667% —
# which is exactly why the volume verdict must be liquid-scoped.)
LIQUID_INSTRUMENTS = frozenset({"NIFTY_FUT", "BANKNIFTY_FUT"})
LIQUID_GAP_OUTAGE_S = 60.0                     # a single liquid gap over this = real feed hole
MIN_COVERAGE_PCT = 95.0                        # below this, the session was genuinely short
# Futures cumulative volume isn't strictly monotonic in RECEIPT order — out-of-order /
# stale feed packets (ltt steps backward) + pre-open corrections cause ~0.005% tiny
# decreases, harmless downstream (tape/trades.py dvol<=0 guard skips them). Only a REAL
# reset drives the verdict: a single decrease > VOLUME_RESET_PCT of max cumulative
# volume (a hard reset -> ~100%), OR summed decreases > VOLUME_BUDGET_PCT (a degraded
# feed). 2026-07-15 liquid jitter was single ≤0.018% / summed ≤0.022% -> ~55x / ~23x
# headroom below these bars.
VOLUME_RESET_PCT = 1.0
VOLUME_BUDGET_PCT = 0.5


def _today_dir() -> Path:
    return Path("data") / datetime.now(IST).date().isoformat()


def _fmt_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:.1f}{unit}"
        nbytes /= 1024
    return f"{nbytes:.1f}GB"


def _load_manifest(day_dir: Path) -> dict | None:
    p = day_dir / "manifest.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None
    return {int(e["security_id"]): e for e in data.get("instruments", [])}


def _is_lenient(path: Path, manifest: dict | None) -> bool:
    """Options and gap-exempt instruments may legitimately record 0 rows."""
    try:
        sid = int(path.stem.split("_")[-1])
    except ValueError:
        sid = None
    if manifest is not None and sid in manifest:
        e = manifest[sid]
        return not (e.get("gap_check") or e.get("kind") in ("spot", "future"))
    return "_CE_" in path.name or "_PE_" in path.name


def _verify_instrument(path: Path, lenient: bool = False) -> dict:
    res: dict = {"file": path.name, "size_bytes": path.stat().st_size,
                 "problems": [], "lenient": lenient}
    table = pq.read_table(str(path))
    res["rows"] = table.num_rows

    # schema validation
    missing = [c for c in TICK_COLUMNS if c not in table.column_names]
    if missing:
        res["problems"].append(f"missing columns: {missing}")

    if table.num_rows == 0:
        if not lenient:
            res["problems"].append("no rows recorded")
        else:
            res["note"] = "no rows (gap-exempt instrument; ok)"
        return res

    # per packet-type counts
    ptypes = table.column("packet_type").to_pylist()
    counts: dict = {}
    for pt in ptypes:
        name = PACKET_TYPE_NAMES.get(pt, str(pt))
        counts[name] = counts.get(name, 0) + 1
    res["packets_by_type"] = counts

    # first/last exchange last-trade-time (ignoring nulls)
    ltt = [v for v in table.column("ltt").to_pylist() if v is not None]
    if ltt:
        res["first_ltt"] = min(ltt)
        res["last_ltt"] = max(ltt)

    # wall-clock coverage from receipt timestamps
    ts = [v for v in table.column("ts_recv_ns").to_pylist() if v is not None]
    if ts:
        span_s = (max(ts) - min(ts)) / 1e9
        res["span_s"] = round(span_s, 1)
        res["coverage_pct"] = round(100.0 * span_s / EXPECTED_SESSION_S, 1)

    # Volume decrease metrics (meaningful for the future; index/VIX volume=0/null).
    # 2026-07-15 recalibration: cumulative volume can dip transiently from out-of-order
    # feed packets (ltt-backward) or pre-open corrections — these are logged for
    # observability but the day-verdict (in verify_session) only fires on a real reset
    # by MAGNITUDE, and only for liquid instruments. No "problem" is appended here.
    vol_col = table.column("volume").to_pylist()
    ltt_col = table.column("ltt").to_pylist()
    va = [int(v) for v in vol_col if v is not None]
    if va:
        decs = [a - b for a, b in zip(va, va[1:]) if b < a]     # decrease magnitudes (receipt order)
        vmax = max(va) or 1
        res["volume_monotonic"] = not decs
        res["volume_decrease_count"] = len(decs)
        res["volume_decrease_total"] = sum(decs)
        res["volume_max_single_decrease"] = max(decs) if decs else 0
        res["volume_max"] = vmax
        res["volume_decrease_pct_single"] = round(100.0 * (max(decs) if decs else 0) / vmax, 3)
        res["volume_decrease_pct_total"] = round(100.0 * sum(decs) / vmax, 3)
        # secondary observability: monotonicity after sorting by ltt isolates pure
        # out-of-order packets (they vanish) from a real reset (persists in both).
        pairs = sorted((int(l), int(v)) for l, v in zip(ltt_col, vol_col)
                       if l is not None and v is not None)
        res["volume_decreases_ltt_sorted"] = sum(1 for a, b in zip(pairs, pairs[1:])
                                                  if b[1] < a[1])
    return res


def _verify_events(day_dir: Path) -> dict:
    ev_path = day_dir / "events.parquet"
    out = {"gap_count": 0, "gap_seconds_total": 0.0, "gap_count_raw": 0,
           "liquid_max_gap_s": 0.0, "liquid_gap_instrument": None,
           "reconnects": 0, "disconnects": 0, "disk_events": 0,
           "session_start": False, "session_end": False}
    if not ev_path.exists():
        out["note"] = "no events.parquet"
        return out
    t = pq.read_table(str(ev_path))
    kinds = t.column("kind").to_pylist()
    vals = t.column("value_num").to_pylist()
    details = t.column("detail").to_pylist()
    for kind, val, detail in zip(kinds, vals, details):
        if kind == "GAP":
            d = str(detail or "")
            out["gap_count_raw"] += 1                 # every watchdog gap (raw, for reference)
            if "open-ended" in d:
                continue                              # session-end artifact: never counts
            dur = float(val or 0.0)
            sym = d.replace(" gap", "").strip()
            if dur > GAP_THRESHOLD_S:                 # non-cadence gaps (logged, not verdict)
                out["gap_count"] += 1
                out["gap_seconds_total"] += dur
            if sym in LIQUID_INSTRUMENTS and dur > out["liquid_max_gap_s"]:
                out["liquid_max_gap_s"] = dur         # drives the verdict
                out["liquid_gap_instrument"] = sym
        elif kind == "RECONNECT":
            out["reconnects"] += 1
        elif kind == "DISCONNECT":
            out["disconnects"] += 1
        elif kind in ("DISK", "DISK_FULL"):
            out["disk_events"] += 1
        elif kind == "SESSION":
            d = str(detail or "")
            if d.startswith("start"):
                out["session_start"] = True
            elif d.startswith("end"):
                out["session_end"] = True
    out["gap_seconds_total"] = round(out["gap_seconds_total"], 1)
    out["liquid_max_gap_s"] = round(out["liquid_max_gap_s"], 1)
    return out


def _coverage(instruments: list[dict]) -> dict:
    """Aggregate wall-clock coverage across CORE (non-lenient) instruments.

    Returns the observed union window + coverage % of the expected session so a
    crashed/paused day still reports exactly how much it captured.
    """
    core = [i for i in instruments if not i.get("lenient")]
    starts = [i["first_ltt"] for i in core if i.get("first_ltt") is not None]
    ends = [i["last_ltt"] for i in core if i.get("last_ltt") is not None]
    spans = [i["span_s"] for i in core if i.get("span_s") is not None]
    cov = {"expected_session_s": EXPECTED_SESSION_S}
    if starts and ends:
        cov["observed_first_ltt"] = min(starts)
        cov["observed_last_ltt"] = max(ends)
    if spans:
        best = max(spans)
        cov["observed_span_s"] = round(best, 1)
        cov["coverage_pct"] = round(100.0 * best / EXPECTED_SESSION_S, 1)
    else:
        cov["observed_span_s"] = 0.0
        cov["coverage_pct"] = 0.0
    return cov


def verify_session(day_dir: Path, partial: bool = False) -> dict:
    """Verify a recorded day and classify it PASS / PARTIAL / FAIL.

    Never raises and never returns "no report": a crashed or disk-paused day
    still produces a structured report with coverage windows.

    * FAIL     — structural corruption: no files, unreadable parquet, or a
                 missing schema column (the data cannot be trusted).
    * PARTIAL  — data is structurally sound but the session was incomplete:
                 ``partial`` was requested (salvage/crash consolidation), OR a
                 disk-full / pause event fired, OR the clean SESSION-end marker
                 is missing, OR core gaps / non-monotonic volume were seen.
    * PASS     — full, clean session with none of the above.
    """
    day_dir = Path(day_dir)
    report: dict = {"date_dir": str(day_dir), "instruments": [], "checks": {}}
    if not day_dir.exists():
        report["overall"] = report["status"] = "FAIL"
        report["error"] = f"directory {day_dir} does not exist"
        report["problems"] = [f"directory {day_dir} does not exist"]
        return report

    manifest = _load_manifest(day_dir)
    files = sorted(p for p in day_dir.glob("*.parquet") if p.name != "events.parquet")
    hard: list[str] = []   # structural corruption -> FAIL
    soft: list[str] = []   # incompleteness / quality -> PARTIAL
    n_core = n_option = 0
    for f in files:
        lenient = _is_lenient(f, manifest)
        n_option += lenient
        n_core += not lenient
        try:
            r = _verify_instrument(f, lenient=lenient)
        except Exception as exc:  # noqa: BLE001
            r = {"file": f.name, "problems": [f"unreadable parquet: {exc}"],
                 "_hard": True}
        report["instruments"].append(r)
        for p in r.get("problems", []):
            tag = f"{f.name}: {p}"
            # Corruption is hard; "no rows"/volume quality flags are soft.
            if r.get("_hard") or "unreadable" in p or "missing columns" in p:
                hard.append(tag)
            else:
                soft.append(tag)
    report["counts"] = {"instrument_files": len(files), "core": n_core,
                        "options_lenient": n_option}

    if not files:
        hard.append("no instrument parquet files found")

    events = _verify_events(day_dir)
    report["checks"]["events"] = events
    # 2026-07-15 gap recalibration: watched index instruments legitimately go quiet
    # 3-10s (96% of raw gaps) — cadence, not faults, so they NO LONGER flip the
    # verdict. PARTIAL only on a real outage signal: (a) a single LIQUID
    # (NIFTY_FUT/BANKNIFTY_FUT) gap over LIQUID_GAP_OUTAGE_S, (b) any reconnect/
    # disconnect, or (c) coverage < MIN_COVERAGE_PCT (checked below). Session-end
    # open-ended gaps are excluded entirely. The non-verdict gap counts stay in the
    # report for observability.
    if events["liquid_max_gap_s"] > LIQUID_GAP_OUTAGE_S:
        soft.append(f"liquid feed gap {events['liquid_max_gap_s']}s on "
                    f"{events['liquid_gap_instrument']} > {LIQUID_GAP_OUTAGE_S}s (real data hole)")
    if events["reconnects"] or events["disconnects"]:
        soft.append(f"{events['reconnects']} reconnect(s) / "
                    f"{events['disconnects']} disconnect(s)")

    coverage = _coverage(report["instruments"])
    report["coverage"] = coverage
    cov_pct = coverage.get("coverage_pct")
    if cov_pct is not None and cov_pct < MIN_COVERAGE_PCT:
        soft.append(f"coverage {cov_pct}% < {MIN_COVERAGE_PCT}%")

    # Volume-reset verdict (2026-07-15): only a REAL reset on a LIQUID future flips
    # the day. Tiny out-of-order/pre-open decreases (logged per-instrument above) do
    # not. A single decrease > VOLUME_RESET_PCT of max cumulative volume = a hard reset
    # (a genuine reset collapses to ~0 -> ~100%); summed > VOLUME_BUDGET_PCT = a
    # degraded feed. Thin futures are excluded (their tiny volume inflates the %).
    for r in report["instruments"]:
        sym = "_".join(r.get("file", "").replace(".parquet", "").split("_")[:-1])
        if sym not in LIQUID_INSTRUMENTS:
            continue
        if r.get("volume_decrease_pct_single", 0.0) > VOLUME_RESET_PCT:
            soft.append(f"{sym} volume RESET: single decrease "
                        f"{r['volume_max_single_decrease']} = {r['volume_decrease_pct_single']}% "
                        f"of max vol > {VOLUME_RESET_PCT}% (real feed reset)")
        elif r.get("volume_decrease_pct_total", 0.0) > VOLUME_BUDGET_PCT:
            soft.append(f"{sym} volume feed degraded: summed decreases "
                        f"{r['volume_decrease_pct_total']}% of max vol > {VOLUME_BUDGET_PCT}%")

    # Incompleteness markers (session crashed / was paused / never closed cleanly).
    incomplete: list[str] = []
    if partial:
        incomplete.append("salvage/partial consolidation")
    if events.get("disk_events"):
        incomplete.append(f"{events['disk_events']} disk event(s)")
    if events.get("session_start") and not events.get("session_end"):
        incomplete.append("no clean session-end marker (crash/kill)")

    report["problems"] = hard + soft + incomplete
    if hard:
        status = "FAIL"
    elif soft or incomplete:
        status = "PARTIAL"
    else:
        status = "PASS"
    report["status"] = report["overall"] = status
    return report


def _print_report(report: dict) -> None:
    print("=" * 64)
    print(f"SESSION VERIFICATION — {report['date_dir']}")
    print("=" * 64)
    if report.get("error"):
        print(f"ERROR: {report['error']}")
    counts = report.get("counts", {})
    if counts:
        print(f"instruments: {counts.get('instrument_files')} files "
              f"({counts.get('core')} core, {counts.get('options_lenient')} options/exempt)")

    core = [i for i in report.get("instruments", []) if not i.get("lenient")]
    options = [i for i in report.get("instruments", []) if i.get("lenient")]

    for inst in core:  # core printed in detail
        print(f"\n• {inst['file']}  rows={inst.get('rows', 0)} "
              f"size={_fmt_size(inst.get('size_bytes', 0))}")
        if "packets_by_type" in inst:
            print(f"    packets: {inst['packets_by_type']}")
        if "coverage_pct" in inst:
            print(f"    coverage: {inst['coverage_pct']}%  span={inst.get('span_s')}s")
        if "first_ltt" in inst:
            print(f"    ltt: {inst['first_ltt']} .. {inst['last_ltt']}")
        if "volume_monotonic" in inst:
            print(f"    volume monotonic: {inst['volume_monotonic']} "
                  f"(decreases={inst.get('volume_decrease_count', 0)})")
        for p in inst.get("problems", []):
            print(f"    ⚠ {p}")

    if options:  # options summarized in aggregate
        total_rows = sum(i.get("rows", 0) for i in options)
        empty = sum(1 for i in options if i.get("rows", 0) == 0)
        print(f"\n• options/exempt ({len(options)}): total_rows={total_rows}, "
              f"empty={empty}")
        for i in options:  # still surface any hard problems (schema/unreadable)
            for p in i.get("problems", []):
                print(f"    ⚠ {i['file']}: {p}")
    ev = report["checks"].get("events", {})
    print(f"\nEvents: gaps={ev.get('gap_count')} "
          f"gap_seconds={ev.get('gap_seconds_total')} "
          f"reconnects={ev.get('reconnects')} disconnects={ev.get('disconnects')} "
          f"disk={ev.get('disk_events', 0)}")
    cov = report.get("coverage", {})
    if cov:
        print(f"Coverage: {cov.get('coverage_pct', 0)}% "
              f"(observed span {cov.get('observed_span_s', 0)}s of "
              f"{cov.get('expected_session_s')}s expected)")
    banner = report.get("status", report.get("overall"))
    icon = {"PASS": "✅ PASS", "PARTIAL": "🟡 PARTIAL"}.get(banner, "❌ FAIL")
    print("\n" + icon)
    if report.get("problems"):
        for p in report["problems"]:
            print(f"   - {p}")
    print("=" * 64)


def main(argv: list[str]) -> int:
    day_dir = Path(argv[1]) if len(argv) > 1 else _today_dir()
    report = verify_session(day_dir)
    _print_report(report)
    if day_dir.exists():
        out = day_dir / "report.json"
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report, indent=2, default=str))
        tmp.replace(out)
        print(f"report written -> {out}")
    # PASS + PARTIAL both captured usable data (exit 0); only FAIL is nonzero.
    return 1 if report.get("status") == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

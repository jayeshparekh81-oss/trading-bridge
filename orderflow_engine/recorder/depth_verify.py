"""Depth session verification (Module R1).

Runs at 15:40 IST after consolidation and writes ``data/{date}/depth/report.json``.

2026-07-16 GAP-VERDICT RECALIBRATION (the 4th verify correction — same treatment R0's
verify_session got). The old rule "any GAP event -> PARTIAL" made every clean depth day
PARTIAL: measured on 07-15/07-16, of ~78 mid-session gaps only ~60 were 3-7s CADENCE noise
on the ~200ms (5Hz) snapshot feed, the rest were pre-open (connect->first snapshot) or
post-close (feed winding down after 15:30) artifacts. The LIQUID futures
(NIFTY_FUT/BANKNIFTY_FUT — the OFI-tradeable ones) had 97-99% coverage, no in-hours gap
>60s, and zero reconnects. So the verdict now fires only on a REAL outage signal:
  * a single LIQUID in-market-hours gap > LIQUID_GAP_OUTAGE_S (clipped to 09:15-15:30, so
    pre-open AND post-close are excluded — depth's post-close gaps RESOLVE, unlike R0's
    which run open-ended, hence a two-sided window here);
  * any reconnect / disconnect;
  * liquid coverage < MIN_COVERAGE_PCT.
Non-liquid instruments (thin index futures + the 14 equities, recorded for constituent
research) legitimately go quiet — their gaps/empties are LOGGED but do not drive the
verdict, exactly like R0 scopes out thin futures + spots. Structural corruption
(unreadable / missing columns) is still a FAIL for ANY instrument.

Kept independent of R0's ``verify_session`` (different schema, different subtree); never
raises.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from recorder.depth_schema import DEPTH_COLUMNS, SIDE_ASK, SIDE_BID

log = logging.getLogger("recorder.depth_verify")

NS_PER_S = 1_000_000_000
IST = ZoneInfo("Asia/Kolkata")
# Expected recording window 09:07–15:35 (same as R0), for coverage %.
EXPECTED_SESSION_S = (15 * 3600 + 35 * 60) - (9 * 3600 + 7 * 60)
GAP_THRESHOLD_S = 10.0                          # cadence on a 5Hz feed is 3-7s (measured);
                                                # >10s reaches the observability count (not verdict).
# The verdict is SCOPED to the OFI-tradeable index futures. Thin futures
# (FINNIFTY/MIDCPNIFTY) + the 14 constituent EQUITIES legitimately go quiet and are
# recorded for research, not signals — their gaps/empties log but never drive PASS/PARTIAL.
LIQUID_INSTRUMENTS = frozenset({"NIFTY_FUT", "BANKNIFTY_FUT"})
LIQUID_GAP_OUTAGE_S = 60.0                       # a single in-hours liquid gap over this = real hole
MIN_COVERAGE_PCT = 95.0
# Market hours: gaps are clocked ONLY within [09:15, 15:30]. Pre-open (connect->09:15) and
# post-close (15:30->wind-down) gaps are no-trade artifacts, clipped to their in-hours part.
MARKET_OPEN_HHMM = (9, 15)
MARKET_CLOSE_HHMM = (15, 30)


def _market_window_ns(day_name: str) -> tuple[int | None, int | None]:
    try:
        d0 = date.fromisoformat(day_name)
    except ValueError:
        return None, None
    oh, om = MARKET_OPEN_HHMM
    ch, cm = MARKET_CLOSE_HHMM
    o = int(datetime(d0.year, d0.month, d0.day, oh, om, tzinfo=IST).timestamp() * NS_PER_S)
    c = int(datetime(d0.year, d0.month, d0.day, ch, cm, tzinfo=IST).timestamp() * NS_PER_S)
    return o, c


def _verify_instrument(path: Path) -> dict:
    res: dict = {"file": path.name, "size_bytes": path.stat().st_size, "problems": []}
    table = pq.read_table(str(path))
    res["rows"] = table.num_rows

    missing = [c for c in DEPTH_COLUMNS if c not in table.column_names]
    if missing:
        res["problems"].append(f"missing columns: {missing}")
        res["_hard"] = True
        return res

    if table.num_rows == 0:
        res["problems"].append("no rows recorded")
        return res

    sides = table.column("side").to_pylist()
    res["bid_packets"] = sum(1 for s in sides if s == SIDE_BID)
    res["ask_packets"] = sum(1 for s in sides if s == SIDE_ASK)
    if res["bid_packets"] == 0 or res["ask_packets"] == 0:
        res["problems"].append("one side missing (bid or ask never received)")

    ts = [v for v in table.column("ts_recv_ns").to_pylist() if v is not None]
    if ts:
        span_s = (max(ts) - min(ts)) / 1e9
        res["span_s"] = round(span_s, 1)
        res["coverage_pct"] = round(100.0 * span_s / EXPECTED_SESSION_S, 1)
        res["first_ts_ns"] = min(ts)
        res["last_ts_ns"] = max(ts)
    return res


def _verify_events(depth_dir: Path, open_ns: int | None, close_ns: int | None) -> dict:
    out = {"gap_count": 0, "gap_count_raw": 0, "gap_seconds_total": 0.0,
           "liquid_max_gap_s": 0.0, "liquid_max_gap_raw_s": 0.0, "liquid_gap_instrument": None,
           "reconnects": 0, "disconnects": 0, "disk_events": 0,
           "session_start": False, "session_end": False}
    ev_path = depth_dir / "events.parquet"
    if not ev_path.exists():
        out["note"] = "no events.parquet"
        return out
    t = pq.read_table(str(ev_path))
    kinds = t.column("kind").to_pylist()
    vals = t.column("value_num").to_pylist()
    details = t.column("detail").to_pylist()
    ts_col = (t.column("ts_ns").to_pylist() if "ts_ns" in t.column_names
              else [None] * len(kinds))
    for kind, val, detail, ts in zip(kinds, vals, details, ts_col):
        if kind == "GAP":
            d = str(detail or "")
            out["gap_count_raw"] += 1
            if "open-ended" in d:                 # session-end artifact: never counts
                continue
            dur = float(val or 0.0)
            sym = d.replace(" gap", "").strip()
            if dur > GAP_THRESHOLD_S:              # observability (not verdict)
                out["gap_count"] += 1
                out["gap_seconds_total"] += dur
            if sym in LIQUID_INSTRUMENTS:
                # Credit only the portion of the gap INSIDE market hours [09:15, 15:30]:
                # pre-open (ends<=open) and post-close (starts>=close) -> 0.
                eff = dur
                if ts is not None and open_ns is not None and close_ns is not None:
                    end_ns = int(ts)
                    start_ns = end_ns - int(round(dur * NS_PER_S))
                    eff = max(0.0, (min(end_ns, close_ns) - max(start_ns, open_ns)) / NS_PER_S)
                if dur > out["liquid_max_gap_raw_s"]:
                    out["liquid_max_gap_raw_s"] = dur
                if eff > out["liquid_max_gap_s"]:
                    out["liquid_max_gap_s"] = eff       # in-hours, drives the verdict
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
    out["liquid_max_gap_raw_s"] = round(out["liquid_max_gap_raw_s"], 1)
    return out


def _sym_of(file_name: str) -> str:
    return "_".join(file_name.replace(".parquet", "").split("_")[:-1])


def verify_depth(day_dir: Path) -> dict:
    """Verify a day's depth subtree; classify PASS / PARTIAL / FAIL."""
    day_dir = Path(day_dir)
    depth_dir = day_dir / "depth"
    report: dict = {"date_dir": str(depth_dir), "instruments": [], "checks": {}}
    if not depth_dir.exists():
        report["status"] = report["overall"] = "FAIL"
        report["problems"] = [f"directory {depth_dir} does not exist"]
        return report

    open_ns, close_ns = _market_window_ns(day_dir.name)
    files = sorted(p for p in depth_dir.glob("*.parquet") if p.name != "events.parquet")
    hard: list[str] = []
    soft: list[str] = []
    for f in files:
        try:
            r = _verify_instrument(f)
        except Exception as exc:  # noqa: BLE001
            r = {"file": f.name, "problems": [f"unreadable parquet: {exc}"], "_hard": True}
        report["instruments"].append(r)
        liquid = _sym_of(f.name) in LIQUID_INSTRUMENTS
        for p in r.get("problems", []):
            tag = f"{f.name}: {p}"
            if r.get("_hard") or "unreadable" in p or "missing columns" in p:
                hard.append(tag)                  # structural corruption -> FAIL (any instrument)
            elif liquid:
                soft.append(tag)                  # a LIQUID empty / one-sided -> PARTIAL
            # non-liquid soft problems: logged in the instrument entry, not verdict-driving
    report["counts"] = {"instrument_files": len(files),
                        "liquid": sum(1 for f in files if _sym_of(f.name) in LIQUID_INSTRUMENTS)}
    if not files:
        hard.append("no depth instrument parquet files found")

    events = _verify_events(depth_dir, open_ns, close_ns)
    report["checks"]["events"] = events
    # Outage rule (replaces "any gap -> PARTIAL"): a real in-hours liquid feed hole.
    if events["liquid_max_gap_s"] > LIQUID_GAP_OUTAGE_S:
        soft.append(f"liquid depth outage {events['liquid_max_gap_s']}s on "
                    f"{events['liquid_gap_instrument']} > {LIQUID_GAP_OUTAGE_S}s (real hole)")
    if events["reconnects"] or events["disconnects"]:
        soft.append(f"{events['reconnects']} reconnect(s) / "
                    f"{events['disconnects']} disconnect(s)")

    # Coverage: best span among LIQUID instruments (the ones that matter for OFI).
    liq_spans = [i["span_s"] for i in report["instruments"]
                 if i.get("span_s") is not None and _sym_of(i["file"]) in LIQUID_INSTRUMENTS]
    all_spans = [i["span_s"] for i in report["instruments"] if i.get("span_s") is not None]
    best = max(liq_spans) if liq_spans else (max(all_spans) if all_spans else 0.0)
    cov_pct = round(100.0 * best / EXPECTED_SESSION_S, 1) if best else 0.0
    report["coverage"] = {"expected_session_s": EXPECTED_SESSION_S,
                          "observed_span_s": round(best, 1), "coverage_pct": cov_pct,
                          "basis": "liquid" if liq_spans else "all"}
    if cov_pct < MIN_COVERAGE_PCT:
        soft.append(f"liquid coverage {cov_pct}% < {MIN_COVERAGE_PCT}%")

    incomplete: list[str] = []
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


def write_report(day_dir: Path, report: dict) -> Path:
    out = Path(day_dir) / "depth" / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, default=str))
    tmp.replace(out)
    return out

"""Depth session verification (Module R1).

Runs at 15:40 IST after consolidation and writes ``data/{date}/depth/report.json``.
All depth instruments are liquid NSE futures/equities, so every one is gap-checked
like R0 core (no lenient class here): an empty instrument or a coverage gap is a
PARTIAL, structural corruption is a FAIL, a full clean day is a PASS.

Kept independent of R0's ``verify_session`` (different schema, different subtree),
and never raises: a crashed/partial depth day still yields a structured report.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pyarrow.parquet as pq

from recorder.depth_schema import DEPTH_COLUMNS, SIDE_ASK, SIDE_BID

log = logging.getLogger("recorder.depth_verify")

# Expected recording window 09:07–15:35 (same as R0), for coverage %.
EXPECTED_SESSION_S = (15 * 3600 + 35 * 60) - (9 * 3600 + 7 * 60)


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


def _verify_events(depth_dir: Path) -> dict:
    out = {"gap_count": 0, "gap_seconds_total": 0.0, "reconnects": 0,
           "disconnects": 0, "disk_events": 0, "session_start": False,
           "session_end": False}
    ev_path = depth_dir / "events.parquet"
    if not ev_path.exists():
        out["note"] = "no events.parquet"
        return out
    t = pq.read_table(str(ev_path))
    for kind, val, detail in zip(t.column("kind").to_pylist(),
                                 t.column("value_num").to_pylist(),
                                 t.column("detail").to_pylist()):
        if kind == "GAP":
            out["gap_count"] += 1
            out["gap_seconds_total"] += float(val or 0.0)
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
    return out


def verify_depth(day_dir: Path) -> dict:
    """Verify a day's depth subtree; classify PASS / PARTIAL / FAIL."""
    day_dir = Path(day_dir)
    depth_dir = day_dir / "depth"
    report: dict = {"date_dir": str(depth_dir), "instruments": [], "checks": {}}
    if not depth_dir.exists():
        report["status"] = report["overall"] = "FAIL"
        report["problems"] = [f"directory {depth_dir} does not exist"]
        return report

    files = sorted(p for p in depth_dir.glob("*.parquet") if p.name != "events.parquet")
    hard: list[str] = []
    soft: list[str] = []
    for f in files:
        try:
            r = _verify_instrument(f)
        except Exception as exc:  # noqa: BLE001
            r = {"file": f.name, "problems": [f"unreadable parquet: {exc}"], "_hard": True}
        report["instruments"].append(r)
        for p in r.get("problems", []):
            tag = f"{f.name}: {p}"
            if r.get("_hard") or "unreadable" in p or "missing columns" in p:
                hard.append(tag)
            else:
                soft.append(tag)
    report["counts"] = {"instrument_files": len(files)}
    if not files:
        hard.append("no depth instrument parquet files found")

    events = _verify_events(depth_dir)
    report["checks"]["events"] = events
    if events["gap_count"] > 0:
        soft.append(f"{events['gap_count']} gap(s) totalling {events['gap_seconds_total']}s")

    spans = [i["span_s"] for i in report["instruments"] if i.get("span_s") is not None]
    best = max(spans) if spans else 0.0
    report["coverage"] = {
        "expected_session_s": EXPECTED_SESSION_S,
        "observed_span_s": round(best, 1),
        "coverage_pct": round(100.0 * best / EXPECTED_SESSION_S, 1) if best else 0.0,
    }

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

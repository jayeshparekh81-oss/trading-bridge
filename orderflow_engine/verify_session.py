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
GAP_THRESHOLD_S = 3.0


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

    # volume monotonic check (meaningful for the future; index/VIX volume=0/null)
    vols = [v for v in table.column("volume").to_pylist() if v is not None]
    if vols:
        drops = sum(1 for a, b in zip(vols, vols[1:]) if b < a)
        res["volume_monotonic"] = drops == 0
        res["volume_decrease_count"] = drops
        if "FUT" in path.name.upper() and drops > 0:
            res["problems"].append(f"future volume decreased {drops} times (non-monotonic)")
    return res


def _verify_events(day_dir: Path) -> dict:
    ev_path = day_dir / "events.parquet"
    out = {"gap_count": 0, "gap_seconds_total": 0.0, "reconnects": 0, "disconnects": 0}
    if not ev_path.exists():
        out["note"] = "no events.parquet"
        return out
    t = pq.read_table(str(ev_path))
    kinds = t.column("kind").to_pylist()
    vals = t.column("value_num").to_pylist()
    for kind, val in zip(kinds, vals):
        if kind == "GAP":
            out["gap_count"] += 1
            out["gap_seconds_total"] += float(val or 0.0)
        elif kind == "RECONNECT":
            out["reconnects"] += 1
        elif kind == "DISCONNECT":
            out["disconnects"] += 1
    out["gap_seconds_total"] = round(out["gap_seconds_total"], 1)
    return out


def verify_session(day_dir: Path) -> dict:
    day_dir = Path(day_dir)
    report: dict = {"date_dir": str(day_dir), "instruments": [], "checks": {}}
    if not day_dir.exists():
        report["overall"] = "FAIL"
        report["error"] = f"directory {day_dir} does not exist"
        return report

    manifest = _load_manifest(day_dir)
    files = sorted(p for p in day_dir.glob("*.parquet") if p.name != "events.parquet")
    problems: list[str] = []
    n_core = n_option = 0
    for f in files:
        lenient = _is_lenient(f, manifest)
        n_option += lenient
        n_core += not lenient
        try:
            r = _verify_instrument(f, lenient=lenient)
        except Exception as exc:  # noqa: BLE001
            r = {"file": f.name, "problems": [f"unreadable parquet: {exc}"]}
        report["instruments"].append(r)
        problems += [f"{f.name}: {p}" for p in r.get("problems", [])]
    report["counts"] = {"instrument_files": len(files), "core": n_core, "options_lenient": n_option}

    if not files:
        problems.append("no instrument parquet files found")

    events = _verify_events(day_dir)
    report["checks"]["events"] = events
    gap_pass = events["gap_count"] == 0
    if not gap_pass:
        problems.append(f"{events['gap_count']} gap(s) > {GAP_THRESHOLD_S}s "
                        f"totalling {events['gap_seconds_total']}s")

    report["problems"] = problems
    report["overall"] = "PASS" if not problems else "FAIL"
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
          f"reconnects={ev.get('reconnects')} disconnects={ev.get('disconnects')}")
    banner = report["overall"]
    print("\n" + ("✅ PASS" if banner == "PASS" else "❌ FAIL"))
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
    return 0 if report.get("overall") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

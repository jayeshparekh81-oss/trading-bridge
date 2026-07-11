"""CLI: replay a recorded day through the chain-analytics engine.

    python -m chain.run --date 2026-07-13 [--index NIFTY] [--no-write]

Replays the day, reconstructs each index's chain, computes IV/Greeks offline +
PCR / max-pain / ATM-IV / net-GEX / basis / buildup, writes
analysis/{date}/chain_{index}.parquet + chain_summary.json, prints a summary.
Loads R3's tape_events.parquet (if present) to also snapshot at big-print /
velocity-spike timestamps. Read-only on recorded data.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource, default_day_dir

from chain.config import load_chain_config
from chain.engine import ChainEngine
from chain.iv_history import append_daily, iv_percentile
from chain.symbols import parse_symbol
from chain.writer import analysis_dir, write_snapshots, write_summary

HERE = Path(__file__).resolve().parent.parent
log = logging.getLogger("chain.run")
_TRIGGER_KINDS = {"BIG_PRINT", "BIG_PRINT_CLUSTER", "VELOCITY_SPIKE"}


def _meta_by_id(day_dir: Path, only_index: str | None) -> dict[int, dict]:
    mf = day_dir / "manifest.json"
    if not mf.exists():
        return {}
    meta: dict[int, dict] = {}
    for e in json.loads(mf.read_text()).get("instruments", []):
        p = parse_symbol(e["symbol"])
        if p.kind == "other":
            continue
        if only_index and p.index != only_index:
            continue
        meta[int(e["security_id"])] = {"kind": p.kind, "index": p.index,
                                       "right": p.right, "strike": p.strike,
                                       "expiry": e.get("expiry", "")}
    return meta


def _event_triggers(day_dir: Path, data_dir: Path, meta: dict[int, dict]) -> dict[str, list[int]]:
    """Big-print / velocity-spike timestamps from R3 output, grouped by index."""
    ev = analysis_dir(data_dir, day_dir.name) / "tape_events.parquet"
    if not ev.exists():
        return {}
    trig: dict[str, list[int]] = defaultdict(list)
    try:
        t = pq.read_table(str(ev))
        for sid, ts, kind in zip(t.column("security_id").to_pylist(),
                                 t.column("ts_ns").to_pylist(),
                                 t.column("kind").to_pylist()):
            if kind in _TRIGGER_KINDS and sid in meta:
                trig[meta[sid]["index"]].append(int(ts))
    except Exception:  # noqa: BLE001
        return {}
    return dict(trig)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="chain.run")
    ap.add_argument("--date")
    ap.add_argument("--index", default=None)
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    ap.add_argument("--config", default=None)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv[1:])

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    day_dir = default_day_dir(Path(args.data_dir), args.date)
    if not day_dir.is_dir():
        print(f"no data at {day_dir}", file=sys.stderr)
        return 2
    dname = day_dir.name
    cfg = load_chain_config(args.config)
    meta = _meta_by_id(day_dir, args.index)
    if not meta:
        print(f"no chain instruments in manifest for {day_dir}"
              + (f" (index {args.index})" if args.index else ""), file=sys.stderr)
        return 2
    triggers = _event_triggers(day_dir, Path(args.data_dir), meta)
    engine = ChainEngine(cfg, meta, date.fromisoformat(dname), event_triggers=triggers)
    ReplayEngine(ReplaySource(day_dir)).drive(engine, speed="max")
    summary = engine.finalize()

    # IV-percentile scaffolding: append today's ATM-IV, compute percentile-to-date
    hist_dir = HERE / cfg.iv_history_dir
    for index, s in summary["per_index"].items():
        if s.get("atm_iv") is not None and not args.no_write:
            append_daily(hist_dir, index, dname, s["atm_iv"])
        s["iv_percentile"] = iv_percentile(hist_dir, index, s.get("atm_iv"), cfg.iv_min_days)

    if not args.no_write:
        out_dir = analysis_dir(Path(args.data_dir), dname)
        by_index = defaultdict(list)
        for r in engine.rows:
            by_index[r["index"]].append(r)
        for index, rows in by_index.items():
            write_snapshots(out_dir, index, rows)
        write_summary(out_dir, {"date": dname, **summary})
        log.info("wrote chain analytics -> %s", out_dir)

    _print(dname, summary)
    return 0


def _fmt(x, p=2):
    return f"{x:.{p}f}" if isinstance(x, (int, float)) else "-"


def _print(dname: str, summary: dict) -> None:
    print("=" * 68)
    print(f"CHAIN ANALYTICS — {dname}   (indices: {summary['indices']}, "
          f"snapshots: {summary['counts']['snapshots']})")
    print("=" * 68)
    for index, s in summary["per_index"].items():
        cov = f"{s['strikes_with_iv']}/{s['strikes']} strikes w/IV"
        if s["spot_missing"]:
            cov += " [SPOT MISSING]"
        print(f"\n• {index}  ({cov})")
        print(f"    PCR oi={_fmt(s['pcr_oi'])} vol={_fmt(s['pcr_volume'])}  "
              f"max_pain={s['max_pain']}  ATM_IV={_fmt(s['atm_iv'], 4)}  "
              f"pctile={s['iv_percentile']}")
        print(f"    net_GEX={_fmt(s['net_gex'], 1)} flip={_fmt(s['gamma_flip'])} "
              f"regime={s['gex_regime']}  basis={_fmt(s['basis'])}")
        if s["buildup_matrix"]:
            print(f"    buildup: {s['buildup_matrix']}")
        if s["top_doi_strikes"]:
            top = ", ".join(f"{t['right']}{t['strike']}:{t['doi_5m']:+d}"
                            for t in s["top_doi_strikes"][:3])
            print(f"    top ΔOI(5m): {top}")
    if summary.get("uncalibrated_knobs"):
        print("\nUNCALIBRATED: " + ", ".join(summary["uncalibrated_knobs"]))
    print("=" * 68)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

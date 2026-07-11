"""CLI: replay a recorded day through the tape engine and write analysis.

    python -m tape.run --date 2026-07-13 [--instruments NIFTY_FUT,BANKNIFTY_FUT] \
        [--data-dir data] [--config tape_config.yaml]

Read-only on recorded data; writes analysis/{date}/ (gitignored). This is what we
run Monday evening on the first clean recorded day.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource, default_day_dir

from tape.config import load_tape_config
from tape.engine import TapeEngine
from tape.writer import analysis_dir, write_bars, write_events, write_summary

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/
log = logging.getLogger("tape.run")


def _sym_by_id(day_dir: Path) -> dict[int, str]:
    """sid -> symbol from the recorded manifest.json, else from file stems."""
    out: dict[int, str] = {}
    mf = day_dir / "manifest.json"
    if mf.exists():
        try:
            data = json.loads(mf.read_text())
            for e in data.get("instruments", []):
                out[int(e["security_id"])] = e["symbol"]
            return out
        except Exception:  # noqa: BLE001
            pass
    for f in day_dir.glob("*.parquet"):
        if f.name == "events.parquet":
            continue
        stem = f.stem
        try:
            out[int(stem.rsplit("_", 1)[1])] = stem.rsplit("_", 1)[0]
        except (IndexError, ValueError):
            continue
    return out


def _print_summary(date: str, summary: dict) -> None:
    print("=" * 64)
    print(f"TAPE ENGINE — {date}")
    print("=" * 64)
    c = summary["counts"]
    print(f"replayed: ticks={c['ticks']:,} depth={c['depth']:,} events={c['events']:,}")
    print(f"trades extracted: {c['trades']:,}")
    t = summary["totals"]
    print(f"bars built: {t['bars']:,} | big prints: {t['big_prints']:,} | "
          f"velocity spikes: {t['velocity_spikes']:,}")
    print("-" * 64)
    for sym, s in summary["per_instrument"].items():
        if s["trades"] == 0:
            continue
        print(f"  {sym:24} trades={s['trades']:>6} bars={s['bars']:>5} "
              f"cvd={s['cvd_final']:>+9} bigprints={s['big_prints']:>3} "
              f"vspikes={s['velocity_spikes']:>3}")
    if summary.get("uncalibrated_knobs"):
        print("-" * 64)
        print("UNCALIBRATED (no output until set): "
              + ", ".join(summary["uncalibrated_knobs"]))
    print("=" * 64)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="tape.run",
                                 description="Replay a recorded day through the tape engine.")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today IST)")
    ap.add_argument("--instruments", default="", help="comma-separated name filters")
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    ap.add_argument("--config", default=None, help="tape_config.yaml path")
    ap.add_argument("--no-write", action="store_true", help="print summary only, no parquet")
    args = ap.parse_args(argv[1:])

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    day_dir = default_day_dir(Path(args.data_dir), args.date)
    date = day_dir.name
    if not day_dir.is_dir():
        print(f"no data at {day_dir}", file=sys.stderr)
        return 2

    filters = [s for s in args.instruments.split(",") if s.strip()]
    source = ReplaySource(day_dir, instruments=filters)
    config = load_tape_config(args.config)
    engine = TapeEngine(config, _sym_by_id(day_dir))
    ReplayEngine(source).drive(engine, speed="max")
    summary = engine.finalize()

    if not args.no_write:
        out_dir = analysis_dir(Path(args.data_dir), date)
        by_inst = defaultdict(list)
        for row in engine.bar_rows:
            by_inst[(row["symbol"], row["security_id"])].append(row)
        for (sym, sid), rows in by_inst.items():
            write_bars(out_dir, sym, sid, rows)
        write_events(out_dir, engine.event_rows)
        write_summary(out_dir, {"date": date, **summary})
        log.info("wrote analysis -> %s", out_dir)

    _print_summary(date, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

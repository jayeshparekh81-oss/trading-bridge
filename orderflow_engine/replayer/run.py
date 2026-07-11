"""CLI: replay a recorded day and print a summary.

    python -m replayer.run --date 2026-07-09 [--speed max|1x|10x] \
        [--instruments NIFTY,BANKNIFTY_FUT] [--data-dir data]

Read-only: never writes, never touches the recorder.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from replayer.consumer import CountingConsumer
from replayer.engine import ReplayEngine, ReplaySummary
from replayer.source import ReplaySource, default_day_dir

IST = ZoneInfo("Asia/Kolkata")
HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/


def _fmt_ist(ts_ns: int | None) -> str:
    if ts_ns is None:
        return "-"
    return datetime.fromtimestamp(ts_ns / 1e9, IST).strftime("%H:%M:%S")


def _print_summary(s: ReplaySummary) -> None:
    print("=" * 60)
    print(f"REPLAY — {s.date}  (recorder status: {s.status})")
    print("=" * 60)
    print(f"events emitted : {s.total:,}  (ticks {s.packets:,} + depth {s.depth:,} "
          f"+ events {s.events:,})")
    print(f"instruments    : {s.instruments} with data "
          f"({s.coverage.empty_instruments} empty, "
          f"{len(s.coverage.unreadable_files)} unreadable-skipped)")
    span = s.span_s
    print(f"time span      : {_fmt_ist(s.first_ts_ns)} .. {_fmt_ist(s.last_ts_ns)} IST"
          + (f"  ({span:.1f}s)" if span is not None else ""))
    if s.coverage.coverage_pct is not None:
        print(f"coverage       : {s.coverage.coverage_pct}% of expected session")
    print(f"throughput     : {s.throughput:,.0f} events/sec "
          f"(wall {s.wall_s:.3f}s)")
    print("=" * 60)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="replayer.run",
                                 description="Replay a recorded orderflow day.")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today IST)")
    ap.add_argument("--speed", default="max",
                    help="max (default), 1x, 10x, 2.5x, ...")
    ap.add_argument("--instruments", default="",
                    help="comma-separated case-insensitive name filters")
    ap.add_argument("--data-dir", default=str(HERE / "data"),
                    help="root data dir (default: orderflow_engine/data)")
    args = ap.parse_args(argv[1:])

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    day_dir = default_day_dir(Path(args.data_dir), args.date)
    filters = [s for s in args.instruments.split(",") if s.strip()]
    source = ReplaySource(day_dir, instruments=filters)
    if not source.exists():
        print(f"no data at {day_dir}", file=sys.stderr)
        return 2
    summary = ReplayEngine(source).drive(CountingConsumer(), speed=args.speed)
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

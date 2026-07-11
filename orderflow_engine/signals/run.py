"""CLI: replay a recorded day through R3+R4+R5+R6 and print the signal report.

    python -m signals.run --date 2026-07-13 [--index NIFTY] [--long-only|--short-only] [--no-write]

At inert defaults (fire_threshold 999) this evaluates + explains every candidate
but fires nothing — that is the expected pass until calibration lowers the threshold.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource, default_day_dir

from signals.config import load_signal_config
from signals.pipeline import build_pipeline
from signals.writer import analysis_dir, write_signals, write_summary

HERE = Path(__file__).resolve().parent.parent
log = logging.getLogger("signals.run")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="signals.run")
    ap.add_argument("--date")
    ap.add_argument("--index", default=None)
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    ap.add_argument("--config", default=None)
    ap.add_argument("--long-only", action="store_true")
    ap.add_argument("--short-only", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv[1:])

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    day_dir = default_day_dir(Path(args.data_dir), args.date)
    if not day_dir.is_dir():
        print(f"no data at {day_dir}", file=sys.stderr)
        return 2
    sides = ("long",) if args.long_only else ("short",) if args.short_only else ("long", "short")
    scfg = load_signal_config(args.config)
    multi, parts = build_pipeline(day_dir, scfg, config_path=args.config, sides=sides)
    sig = parts["signal"]

    source = ReplaySource(day_dir, instruments=([args.index] if args.index else None))
    ReplayEngine(source).drive(multi, speed="max")
    summary = sig.finalize()

    if not args.no_write:
        out_dir = analysis_dir(Path(args.data_dir), day_dir.name)
        write_signals(out_dir, sig.rows)
        write_summary(out_dir, {"date": day_dir.name, **summary})
        log.info("wrote signals -> %s", out_dir)

    _print(day_dir.name, summary)
    return 0


def _print(dname: str, s: dict) -> None:
    print("=" * 70)
    print(f"SIGNAL ENGINE — {dname}")
    print("=" * 70)
    c = s["counts"]
    print(f"candidates evaluated: {c['candidates']:,}   fired: {c['fired']}")
    print(f"net simulated R: {s['net_simulated_r']:+.2f}")
    if s["gate_rejects"]:
        print("gate rejections by reason:")
        for reason, n in sorted(s["gate_rejects"].items(), key=lambda x: -x[1]):
            print(f"    {n:>6}  {reason}")
    if s["fires"]:
        print("signals fired:")
        for f in s["fires"]:
            print(f"    {f['instrument']} {f['side']} @ {f['entry']:.2f} score={f['score']:.1f}")
    else:
        print("signals fired: NONE (inert threshold — evaluating-without-firing is the pass)")
    if s.get("uncalibrated_knobs"):
        print("UNCALIBRATED: " + ", ".join(s["uncalibrated_knobs"]))
    print("=" * 70)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

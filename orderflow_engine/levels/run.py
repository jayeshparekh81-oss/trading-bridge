"""CLI: replay a recorded day through the levels engine (INTRADAY) and, when the
historical daily cache is present, merge daily/pivot levels on top.

    python -m levels.run --date 2026-07-13 [--instruments NIFTY_FUT] \
        [--daily-cache cache/historical] [--require-daily] [--no-write]

By default this degrades gracefully offline (intraday-only if no daily cache).
--require-daily FAILS LOUDLY instead — use it on Monday-evening runs where a
missing cache should be an error, not a silent partial map.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource, default_day_dir

from levels.config import load_levels_config
from levels.engine import LevelsEngine
from levels.ohlcv import Bar, load_ohlcv
from levels.pivots import classic_pivots
from levels.prior_levels import classify_gap, prior_day_levels, prior_week_levels, split_prior_context
from levels.writer import analysis_dir, write_levels, write_summary, write_vwap_snapshots
from tape.run import _sym_by_id  # reuse R3's manifest/stem resolver

HERE = Path(__file__).resolve().parent.parent
log = logging.getLogger("levels.run")


def _load_daily_cache(cache_dir: Path, sid: int) -> list[Bar]:
    """Merge any cached daily OHLCV parquet for this security_id."""
    merged: dict[int, Bar] = {}
    for f in sorted(cache_dir.glob(f"*_{sid}_1d_*.parquet")):
        try:
            for b in load_ohlcv(f):
                merged[b.ts] = b
        except Exception:  # noqa: BLE001
            continue
    return [merged[k] for k in sorted(merged)]


def _merge_daily(reg, cache_dir: Path, sid: int, session_date: date, symbol: str,
                 cfg) -> bool:
    bars = _load_daily_cache(cache_dir, sid)
    if not bars:
        return False
    ctx = split_prior_context(bars, session_date)
    pday = ctx["prior_day"]
    if pday is None:
        return False
    reg.add_many(prior_day_levels(pday))
    reg.add_many(prior_week_levels(ctx["prior_week_bars"]))
    reg.add_many(classic_pivots(pday.high, pday.low, pday.close))
    open_px = reg.context.get("session_open")
    if open_px is not None:
        gap = classify_gap(open_px, pday.close, cfg.gap_threshold_pct(symbol))
        reg.set_context("gap", gap)
    return True


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="levels.run")
    ap.add_argument("--date")
    ap.add_argument("--instruments", default="")
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    ap.add_argument("--daily-cache", default=None)
    ap.add_argument("--require-daily", action="store_true",
                    help="fail if the daily historical cache is missing for an instrument")
    ap.add_argument("--config", default=None)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv[1:])

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    day_dir = default_day_dir(Path(args.data_dir), args.date)
    dname = day_dir.name
    if not day_dir.is_dir():
        print(f"no data at {day_dir}", file=sys.stderr)
        return 2
    session_date = date.fromisoformat(dname)
    cfg = load_levels_config(args.config)
    cache_dir = Path(args.daily_cache) if args.daily_cache else HERE / cfg.historical_cache_dir

    filters = [s for s in args.instruments.split(",") if s.strip()]
    source = ReplaySource(day_dir, instruments=filters)
    engine = LevelsEngine(cfg, _sym_by_id(day_dir), date=dname)
    ReplayEngine(source).drive(engine, speed="max")
    summary = engine.finalize()

    daily_merged = 0
    for sid, reg in engine.registries.items():
        ok = _merge_daily(reg, cache_dir, sid, session_date, reg.symbol, cfg)
        if ok:
            daily_merged += 1
        elif args.require_daily:
            print(f"ERROR: --require-daily set but no daily cache for "
                  f"{reg.symbol} ({sid}) in {cache_dir}", file=sys.stderr)
            return 3
    summary["daily_merged"] = daily_merged
    summary["daily_cache"] = str(cache_dir)

    out_dir = analysis_dir(Path(args.data_dir), dname)
    if not args.no_write:
        for sid, st in engine.state.items():
            reg = engine.registries[sid]
            write_levels(out_dir, reg.symbol, sid, reg.to_rows())
            if st.snapshots:
                write_vwap_snapshots(out_dir, reg.symbol, sid, st.snapshots)
        write_summary(out_dir, {"date": dname, **summary})
        log.info("wrote levels -> %s", out_dir)

    _print_summary(dname, summary, engine)
    return 0


def _print_summary(date_str: str, summary: dict, engine) -> None:
    print("=" * 64)
    print(f"LEVELS ENGINE — {date_str}   (daily merged: {summary.get('daily_merged', 0)}"
          f"/{summary['instruments']})")
    print("=" * 64)
    c = summary["counts"]
    print(f"replayed ticks={c['ticks']:,} trades={c['trades']:,}")
    for sym, s in summary["per_instrument"].items():
        if s["trades"] == 0:
            continue
        vwap = f"{s['vwap']:.2f}" if s["vwap"] is not None else "-"
        poc = f"{s['poc']:.2f}" if s["poc"] is not None else "-"
        va = (f"{s['val']:.2f}..{s['vah']:.2f}"
              if s["val"] is not None and s["vah"] is not None else "-")
        print(f"  {sym:22} vwap={vwap:>10} poc={poc:>10} VA=[{va}] levels={s['levels']}")
    # pivots + nearest-level demo for the first instrument that has daily levels
    for sid, reg in engine.registries.items():
        piv = reg.levels(["PIVOT_P", "PIVOT_R1", "PIVOT_S1"])
        if piv:
            print("-" * 64)
            print(f"  {reg.symbol} pivots: "
                  + " ".join(f"{l.level_type.replace('PIVOT_', '')}={l.price:.2f}"
                             for l in reg.levels()
                             if l.level_type.startswith("PIVOT_")))
            last = reg.context.get("session_last")
            if last is not None:
                near = reg.distance_to_nearest(last)
                if near:
                    print(f"  nearest level to last {last:.2f}: {near['level_type']} "
                          f"@ {near['level_price']:.2f} (dist {near['signed_distance']:+.2f})")
            gap = reg.context.get("gap")
            if gap:
                print(f"  gap: {gap['gap']} ({gap['gap_pct']:+.2f}%)")
            break
    if summary.get("uncalibrated_knobs"):
        print("-" * 64)
        print("UNCALIBRATED: " + ", ".join(summary["uncalibrated_knobs"]))
    print("=" * 64)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

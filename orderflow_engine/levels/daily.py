"""CLI: the DAILY/HISTORICAL path — fetch OHLCV and compute pivots/prior levels.

    python -m levels.daily --symbol NIFTY --from 2026-05-01 --to 2026-07-10
    python -m levels.daily --security-id 61093 --segment NSE_FNO --instrument FUTIDX \
        --from 2026-05-01 --to 2026-07-10

Resolves --symbol to the near-month future via the recorder scrip master (or use
--security-id directly), fetches daily OHLCV via the vendored client, and prints
the pivot table + PDH/PDL/PDC + prior-week + gap. Read-only.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from levels.config import load_levels_config
from levels.historical import DhanHistorical
from levels.pivots import classic_pivots
from levels.prior_levels import classify_gap, prior_day_levels, prior_week_levels, split_prior_context

HERE = Path(__file__).resolve().parent.parent
log = logging.getLogger("levels.daily")

_SEGMENT_INSTRUMENT = {"NSE_FNO": "FUTIDX", "BSE_FNO": "FUTIDX", "NSE_EQ": "EQUITY"}


def _resolve_symbol(symbol: str, exch: str, segment: str) -> tuple[int, str]:
    """Resolve a symbol to (security_id, exchange_segment) via the scrip master."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from recorder import scrip_master as SM
    cfg = __import__("yaml").safe_load((HERE / "config.yaml").read_text())
    sm = cfg["scrip_master"]
    csv = SM.fetch_scrip_master(HERE / sm["cache_dir"], url=sm["url"],
                                today=datetime.now(ZoneInfo("Asia/Kolkata")).date(),
                                stale_hours=int(sm["stale_hours"]))
    rows = SM.load_rows(csv)
    fut = SM.resolve_future(rows, ref_date=datetime.now(ZoneInfo("Asia/Kolkata")).date(),
                            underlying=symbol, exch=exch, segment=segment, symbol=symbol)
    return fut.security_id, fut.exchange_segment


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="levels.daily")
    ap.add_argument("--symbol")
    ap.add_argument("--security-id", type=int)
    ap.add_argument("--exchange", default="NSE")
    ap.add_argument("--segment", default="NSE_FNO")
    ap.add_argument("--instrument", default=None)
    ap.add_argument("--from", dest="frm", required=True)
    ap.add_argument("--to", dest="to", required=True)
    ap.add_argument("--timeframe", default="1d")
    ap.add_argument("--cache", default=None)
    args = ap.parse_args(argv[1:])

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = load_levels_config()
    cache_dir = Path(args.cache) if args.cache else HERE / cfg.historical_cache_dir

    segment = args.segment
    if args.symbol and args.security_id is None:
        sid, segment = _resolve_symbol(args.symbol, args.exchange, args.segment)
    elif args.security_id is not None:
        sid = args.security_id
    else:
        print("provide --symbol or --security-id", file=sys.stderr)
        return 2
    instrument = args.instrument or _SEGMENT_INSTRUMENT.get(segment, "FUTIDX")
    label = args.symbol or f"SID{sid}"

    client = DhanHistorical.from_creds(cache_dir)
    bars = client.fetch(sid, segment, instrument,
                        date.fromisoformat(args.frm), date.fromisoformat(args.to),
                        timeframe=args.timeframe)
    if len(bars) < 2:
        print(f"only {len(bars)} bar(s) returned for {label}; need >=2 for prior levels",
              file=sys.stderr)
        return 1

    ref = bars[-1]                          # reference (latest) day
    ctx = split_prior_context(bars, date.fromisoformat(args.to) + timedelta(days=1))
    pday = ctx["prior_day"] or bars[-2]
    piv = classic_pivots(pday.high, pday.low, pday.close)
    pdl = prior_day_levels(pday)
    pwl = prior_week_levels(ctx["prior_week_bars"])
    gap = classify_gap(ref.open, pday.close, cfg.gap_threshold_pct(label))

    print("=" * 56)
    print(f"DAILY LEVELS — {label}  ({len(bars)} bars, {args.frm}..{args.to})")
    print("=" * 56)
    print(f"prior day: PDH={pdl['PDH']:.2f} PDL={pdl['PDL']:.2f} PDC={pdl['PDC']:.2f}")
    if pwl:
        print(f"prior week: PWH={pwl['PWH']:.2f} PWL={pwl['PWL']:.2f}")
    print("pivots: " + " ".join(f"{k.replace('PIVOT_', '')}={v:.2f}" for k, v in piv.items()))
    print(f"gap (ref open {ref.open:.2f} vs PDC {pday.close:.2f}): "
          f"{gap['gap']} ({gap['gap_pct']:+.2f}%)")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

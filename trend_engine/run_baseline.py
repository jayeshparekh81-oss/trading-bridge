#!/usr/bin/env python3
"""Run the VWAP baseline through Module 0 for each futures symbol.

    python trend_engine/run_baseline.py

Prints an analytics summary per (symbol, variant) and saves equity PNGs.
61-day pipeline SMOKE TEST — sane-numbers check, NOT an edge read.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics import summarize  # noqa: E402
from baseline import vwap_long_only, vwap_long_short  # noqa: E402
from config import Config  # noqa: E402
from costs import CostModel, SlippageModel  # noqa: E402
from data import load  # noqa: E402
from harness import run_backtest  # noqa: E402

VARIANTS = [("long_only", vwap_long_only), ("long_short", vwap_long_short)]


def main() -> int:
    cfg = Config()
    print("TREND-ENGINE · Module 0 baseline  (VWAP, intraday, 5-min futures)")
    print(f"capital={cfg.capital:,.0f}  lots={cfg.lots}  slippage_ticks={cfg.slippage_ticks}  "
          f"square_off={cfg.square_off_time}  brokerage/order=₹{cfg.brokerage_per_order:.0f}")

    for symbol in cfg.symbols:
        spec = cfg.instruments[symbol]
        print(f"\n########## {symbol}  (lot_size={spec.lot_size}, tick={spec.tick_size}) ##########")
        df = load(symbol)
        cost_model = CostModel.default(brokerage_per_order=cfg.brokerage_per_order)
        slippage_model = SlippageModel(ticks=cfg.slippage_ticks, tick_size=spec.tick_size)
        for variant, fn in VARIANTS:
            trades, equity = run_backtest(df, fn, cost_model, slippage_model, cfg, symbol)
            summarize(symbol, variant, trades, equity, cfg)

    print("\nDone — smoke test only; do not read edge into 61 days.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

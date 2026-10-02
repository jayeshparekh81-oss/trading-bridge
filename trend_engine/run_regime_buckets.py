#!/usr/bin/env python3
"""Rung-1 done right: is "more trending → better GROSS economics" true?

    python trend_engine/run_regime_buckets.py

Instead of a hard gate (which we proved collapses to noise), we run the plain
VWAP-cross baseline, tag every trade with the self-calibrating regime_score at
its ENTRY bar, bucket trades into LOW/MID/HIGH terciles by that score, and read
GROSS expectancy/trade (cost-independent) per bucket.

The ONE question: does gross expectancy/trade rise monotonically LOW→HIGH?
A hint on 61 days — not an edge verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from baseline import vwap_long_only, vwap_long_short  # noqa: E402
from config import Config  # noqa: E402
from costs import CostModel, SlippageModel  # noqa: E402
from data import load  # noqa: E402
from harness import run_backtest  # noqa: E402
from regime import regime_score  # noqa: E402

VARIANTS = [("long_only", vwap_long_only), ("long_short", vwap_long_short)]


def main() -> int:
    cfg = Config()
    print("TREND-ENGINE · Rung-1 follow-up — regime-score tercile economics")
    print(f"score = mean of trailing percentile-ranks of (Hurst, ER, ATR), lookback={cfg.regime_lookback} bars, "
          "self-calibrating (no absolute thresholds).")
    print("Cost-independent read: GROSS expectancy/trade by LOW/MID/HIGH entry-regime tercile. 61 days — a hint.\n")

    for symbol in cfg.symbols:
        spec = cfg.instruments[symbol]
        df = load(symbol)
        score = regime_score(df, cfg)["regime_score"]

        cost_model = CostModel.default(brokerage_per_order=cfg.brokerage_per_order)
        slippage_model = SlippageModel(ticks=cfg.slippage_ticks, tick_size=spec.tick_size)

        # Pool trades from both variants for this symbol (score is direction-agnostic).
        pooled = []
        for variant, fn in VARIANTS:
            trades, _ = run_backtest(df, fn, cost_model, slippage_model, cfg, symbol)
            if not trades.empty:
                trades = trades.assign(variant=variant)
                pooled.append(trades)
        allt = pd.concat(pooled, ignore_index=True)

        # Tag each trade with regime_score at its ENTRY bar; drop trades whose
        # entry bar predates a valid score (early warm-up window).
        allt["reg"] = score.reindex(allt["entry_time"]).to_numpy()
        tagged = allt.dropna(subset=["reg"]).copy()
        dropped = len(allt) - len(tagged)

        # Terciles by entry regime_score.
        tagged["bucket"] = pd.qcut(tagged["reg"], 3, labels=["LOW", "MID", "HIGH"])

        print(f"########## {symbol}  (pooled {len(tagged)} trades; {dropped} dropped as pre-warm-up) ##########")
        print(f"  {'bucket':<6} {'trades':>7} {'win% (gross)':>13} {'GROSS exp/trade':>18} {'score range':>18}")
        exp_by_bucket = {}
        for b in ["LOW", "MID", "HIGH"]:
            sub = tagged[tagged["bucket"] == b]
            g = sub["gross_pnl"]
            exp = float(g.mean())
            exp_by_bucket[b] = exp
            win = (g > 0).mean() * 100.0
            print(f"  {b:<6} {len(sub):>7} {win:>12.1f}% {'₹' + format(exp, ',.1f'):>18} "
                  f"{sub['reg'].min():>8.2f}–{sub['reg'].max():.2f}")

        lo, mid, hi = exp_by_bucket["LOW"], exp_by_bucket["MID"], exp_by_bucket["HIGH"]
        monotone_up = lo < mid < hi
        print(f"  → LOW→MID→HIGH gross exp/trade:  ₹{lo:,.1f}  →  ₹{mid:,.1f}  →  ₹{hi:,.1f}")
        print(f"  → monotonic increase LOW→HIGH? {'YES' if monotone_up else 'NO'}   "
              f"(HIGH − LOW = ₹{hi - lo:,.1f})\n")

    print("Done — 61-day hint on 'more trending → better gross economics', not a verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

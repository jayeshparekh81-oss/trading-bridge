#!/usr/bin/env python3
"""First-look: baseline VWAP-cross + regime-score terciles on BSE & CDSL stocks.

    python trend_engine/run_equity_firstlook.py

FULL 5-year in-sample (proper sample, unlike the 61-day futures) — but an
EYES-OPEN exploration, NOT a verdict. Priors (Jayesh's v4.8.1): the edge is
BSE-exclusive; CDSL config surface is flat → expect CDSL ≈ null (a null CONFIRMS
the prior). Any BSE signal here is a DIFFERENT strategy (regime + VWAP-cross)
and is BSE-specific, not portable. Cost-independent focus (GROSS).

Runs on the corp-action-ADJUSTED series (BSE 2:1 bonus back-adjusted; CDSL
already vendor-adjusted). Do NOT tune anything. If a stock shows a clean
monotone signal, it's a walk-forward-OOS *candidate*, not a result.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from baseline import vwap_long_only, vwap_long_short  # noqa: E402
from config import Config  # noqa: E402
from costs import CostModel, SlippageModel  # noqa: E402
from data import load  # noqa: E402
from harness import run_backtest  # noqa: E402
from regime import regime_score  # noqa: E402

SYMBOLS = ["BSE", "CDSL"]
VARIANTS = [("long_only", vwap_long_only), ("long_short", vwap_long_short)]


def main() -> int:
    cfg = Config()
    print("TREND-ENGINE · Equity first-look — VWAP-cross baseline + regime terciles (5y in-sample)")
    print("GROSS / cost-independent focus. BSE ≠ portable · CDSL-null = prior confirmed. Not a verdict.\n")

    for symbol in SYMBOLS:
        spec = cfg.instruments[symbol]
        df = load(symbol)
        score = regime_score(df, cfg)["regime_score"]
        cost_model = CostModel.default(brokerage_per_order=cfg.brokerage_per_order)
        slippage_model = SlippageModel(ticks=cfg.slippage_ticks, tick_size=spec.tick_size)

        print(f"########## {symbol}  ({len(df):,} bars, {df.index.min().date()} → {df.index.max().date()}) ##########")

        pooled = []
        for variant, fn in VARIANTS:
            trades, _ = run_backtest(df, fn, cost_model, slippage_model, cfg, symbol)
            g = trades["gross_pnl"]
            print(f"  baseline {variant:<10}: {len(trades):>5} trades | "
                  f"GROSS exp/trade ₹{g.mean():>8,.1f} | win% {(g > 0).mean() * 100:4.1f}")
            pooled.append(trades.assign(variant=variant))

        allt = pd.concat(pooled, ignore_index=True)
        allt["reg"] = score.reindex(allt["entry_time"]).to_numpy()
        tagged = allt.dropna(subset=["reg"]).copy()
        dropped = len(allt) - len(tagged)
        tagged["bucket"] = pd.qcut(tagged["reg"], 3, labels=["LOW", "MID", "HIGH"])

        print(f"  ── regime terciles (pooled {len(tagged)} trades, {dropped} pre-warm-up dropped) ──")
        print(f"  {'bucket':<6} {'trades':>7} {'win% (gross)':>13} {'GROSS exp/trade':>18} {'score range':>16}")
        exp = {}
        for b in ["LOW", "MID", "HIGH"]:
            sub = tagged[tagged["bucket"] == b]
            gg = sub["gross_pnl"]
            exp[b] = float(gg.mean())
            print(f"  {b:<6} {len(sub):>7} {(gg > 0).mean() * 100:>12.1f}% "
                  f"{'₹' + format(exp[b], ',.1f'):>18} {sub['reg'].min():>7.2f}–{sub['reg'].max():.2f}")

        lo, mid, hi = exp["LOW"], exp["MID"], exp["HIGH"]
        if lo < mid < hi:
            call = "MONOTONE UP → OOS CANDIDATE (walk-forward before trusting)"
        elif lo > mid > hi:
            call = "INVERTED (more trending → worse)"
        else:
            call = "NON-MONOTONE (mixed / flat)"
        print(f"  → LOW→MID→HIGH gross exp/trade: ₹{lo:,.1f} → ₹{mid:,.1f} → ₹{hi:,.1f}")
        print(f"  → {call}   (HIGH − LOW = ₹{hi - lo:,.1f})\n")

    print("Done — 5y in-sample first read. Monotone ⇒ OOS candidate, not a verdict. CDSL-null confirms prior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

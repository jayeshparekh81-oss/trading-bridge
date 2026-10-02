#!/usr/bin/env python3
"""Same regime-score tercile test, but on a genuinely TREND-FOLLOWING entry.

    python trend_engine/run_regime_buckets_trend.py

If "more trending → better gross" is real, it should show up for a Donchian
breakout entry even if it didn't for the reversion-flavoured VWAP-cross. Also
compares Donchian vs VWAP overall gross expectancy/trade, so we can see whether
a trend entry is even less-bad here. 61 days — a hint, not a verdict.
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
from donchian_entry import make_donchian  # noqa: E402
from harness import run_backtest  # noqa: E402
from regime import regime_score  # noqa: E402


def _pool(df, variants, cost_model, slippage_model, cfg, symbol) -> pd.DataFrame:
    pooled = []
    for variant, fn in variants:
        trades, _ = run_backtest(df, fn, cost_model, slippage_model, cfg, symbol)
        if not trades.empty:
            pooled.append(trades.assign(variant=variant))
    return pd.concat(pooled, ignore_index=True) if pooled else pd.DataFrame()


def main() -> int:
    cfg = Config()
    n = cfg.donchian_n
    print("TREND-ENGINE · Rung-1 diagnostic — regime terciles on a Donchian TREND entry")
    print(f"Donchian N={n} (channel up to t-1, executed t+1). Regime score = self-calibrating "
          f"percentile-rank mean, lookback={cfg.regime_lookback}.")
    print("Cost-independent read: GROSS expectancy/trade by LOW/MID/HIGH entry-regime tercile. 61 days — a hint.\n")

    donchian_variants = [("long_only", make_donchian(n, False)), ("long_short", make_donchian(n, True))]
    vwap_variants = [("long_only", vwap_long_only), ("long_short", vwap_long_short)]

    for symbol in cfg.symbols:
        spec = cfg.instruments[symbol]
        df = load(symbol)
        score = regime_score(df, cfg)["regime_score"]
        cost_model = CostModel.default(brokerage_per_order=cfg.brokerage_per_order)
        slippage_model = SlippageModel(ticks=cfg.slippage_ticks, tick_size=spec.tick_size)

        don = _pool(df, donchian_variants, cost_model, slippage_model, cfg, symbol)
        vwap = _pool(df, vwap_variants, cost_model, slippage_model, cfg, symbol)

        # Tag Donchian trades with regime_score at entry bar; tercile split.
        don["reg"] = score.reindex(don["entry_time"]).to_numpy()
        tagged = don.dropna(subset=["reg"]).copy()
        dropped = len(don) - len(tagged)
        tagged["bucket"] = pd.qcut(tagged["reg"], 3, labels=["LOW", "MID", "HIGH"])

        print(f"########## {symbol}  (Donchian: pooled {len(tagged)} trades; {dropped} pre-warm-up dropped) ##########")
        print(f"  {'bucket':<6} {'trades':>7} {'win% (gross)':>13} {'GROSS exp/trade':>18} {'score range':>18}")
        exp = {}
        for b in ["LOW", "MID", "HIGH"]:
            sub = tagged[tagged["bucket"] == b]
            g = sub["gross_pnl"]
            exp[b] = float(g.mean()) if len(sub) else float("nan")
            win = (g > 0).mean() * 100.0 if len(sub) else float("nan")
            rng = f"{sub['reg'].min():.2f}–{sub['reg'].max():.2f}" if len(sub) else "—"
            print(f"  {b:<6} {len(sub):>7} {win:>12.1f}% {'₹' + format(exp[b], ',.1f'):>18} {rng:>18}")

        lo, mid, hi = exp["LOW"], exp["MID"], exp["HIGH"]
        if lo < mid < hi:
            call = "MONOTONE UP  (more trending → better gross)"
        elif lo > mid > hi:
            call = "INVERTED  (more trending → worse gross)"
        else:
            call = "NON-MONOTONE (mixed / flat)"
        print(f"  → LOW→MID→HIGH gross exp/trade:  ₹{lo:,.1f}  →  ₹{mid:,.1f}  →  ₹{hi:,.1f}")
        print(f"  → {call}   (HIGH − LOW = ₹{hi - lo:,.1f})")

        # Overall (un-bucketed) Donchian vs VWAP gross expectancy/trade.
        od = float(don["gross_pnl"].mean())
        ov = float(vwap["gross_pnl"].mean())
        print(f"  → overall GROSS exp/trade:  Donchian ₹{od:,.1f} ({len(don)} trades)   "
              f"vs  VWAP-cross ₹{ov:,.1f} ({len(vwap)} trades)   "
              f"→ trend entry is {'LESS-BAD' if od > ov else 'WORSE'} here\n")

    print("Done — 61-day hint: does 'more trending → better gross' appear for a trend entry? Not a verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

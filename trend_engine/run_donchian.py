#!/usr/bin/env python3
"""Final trend-thesis test: Donchian breakout (real trend entry) vs the
reversion-flavoured VWAP-cross baseline, on 5y BSE + CDSL.

    python trend_engine/run_donchian.py

The regime score was DROPPED (it failed everywhere) — not used here. Trend-
following itself has never been tested (VWAP-cross is reversion-flavoured); this
is that test. 5y in-sample, NO tuning, fixed N=20 & N=55. GROSS / cost-independent.

One question: does a genuine trend entry show positive gross edge on these
instruments, and does it beat the reversion baseline? Null ⇒ trend family parked.
A positive gross tilt (esp. BSE) is a walk-forward-OOS CANDIDATE, not a verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from baseline import vwap_long_only, vwap_long_short  # noqa: E402
from config import Config  # noqa: E402
from costs import CostModel, SlippageModel  # noqa: E402
from data import load  # noqa: E402
from donchian_entry import make_donchian  # noqa: E402
from harness import run_backtest  # noqa: E402

SYMBOLS = ["BSE", "CDSL"]


def _row(label: str, trades) -> tuple[str, int, float, float]:
    g = trades["gross_pnl"]
    return (label, len(trades), (g > 0).mean() * 100.0, float(g.mean()))


def main() -> int:
    cfg = Config()
    print("TREND-ENGINE · Donchian breakout (TREND entry) vs VWAP-cross (REVERSION) — 5y BSE/CDSL")
    print(f"Donchian N={list(cfg.donchian_lengths)} (channel up to t-1, executed t+1). "
          "GROSS / cost-independent. In-sample, no tuning. Regime score NOT used.\n")

    for symbol in SYMBOLS:
        spec = cfg.instruments[symbol]
        df = load(symbol)
        cost_model = CostModel.default(brokerage_per_order=cfg.brokerage_per_order)
        slippage_model = SlippageModel(ticks=cfg.slippage_ticks, tick_size=spec.tick_size)

        def run(fn):
            return run_backtest(df, fn, cost_model, slippage_model, cfg, symbol)[0]

        rows = [
            _row("VWAP-cross  · long_only ", run(vwap_long_only)),
            _row("VWAP-cross  · long_short", run(vwap_long_short)),
        ]
        for n in cfg.donchian_lengths:
            rows.append(_row(f"Donchian N={n:<3}· long_only ", run(make_donchian(n, False))))
            rows.append(_row(f"Donchian N={n:<3}· long_short", run(make_donchian(n, True))))

        print(f"########## {symbol}  ({len(df):,} bars, {df.index.min().date()} → {df.index.max().date()}) ##########")
        print(f"  {'strategy':<26} {'trades':>7} {'win% (gross)':>13} {'GROSS exp/trade':>18}")
        for label, n, win, exp in rows:
            marker = ""
            if "Donchian" in label and exp > 0:
                # positive gross tilt on a trend entry → flag OOS candidate
                marker = "  ◀ positive gross (OOS candidate)"
            print(f"  {label:<26} {n:>7} {win:>12.1f}% {'₹' + format(exp, ',.1f'):>18}{marker}")

        # Direct trend-vs-reversion read: best Donchian gross vs best baseline gross.
        base_best = max(rows[0][3], rows[1][3])
        don_best = max(r[3] for r in rows[2:])
        verdict = "BEATS" if don_best > base_best else "does NOT beat"
        print(f"  → best Donchian gross ₹{don_best:,.1f}  vs  best baseline gross ₹{base_best:,.1f}  "
              f"→ trend {verdict} reversion here\n")

    print("Done — 5y in-sample. Positive gross ⇒ OOS candidate, not a verdict. Null ⇒ park trend family.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

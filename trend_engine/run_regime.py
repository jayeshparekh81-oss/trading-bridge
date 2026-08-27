#!/usr/bin/env python3
"""Ablation rung 1: baseline VWAP-cross  vs  baseline + regime filter.

    python trend_engine/run_regime.py

MECHANICS check on 61 days of futures data: did the regime gate compute
causally, cut trade count, and move GROSS expectancy/trade sanely? The
cost-independent columns (trade count, gross expectancy/trade) are valid
regardless of cost-rate accuracy — those are the ones to read here. NOT an
edge verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from analytics import _max_drawdown  # noqa: E402
from baseline import vwap_long_only, vwap_long_short  # noqa: E402
from config import Config  # noqa: E402
from costs import CostModel, SlippageModel  # noqa: E402
from data import load  # noqa: E402
from harness import run_backtest  # noqa: E402
from regime import make_regime_signal  # noqa: E402

VARIANTS = [("long_only", vwap_long_only), ("long_short", vwap_long_short)]


def _metrics(trades: pd.DataFrame, equity: pd.Series) -> dict:
    if trades.empty:
        return {"trades": 0}
    g = trades["gross_pnl"]
    net = trades["net_pnl"]
    dd_inr, dd_pct = _max_drawdown(equity)
    pf_net = (net[net > 0].sum() / abs(net[net < 0].sum())) if (net < 0).any() else float("inf")
    return {
        "trades": len(trades),
        "win_rate_gross": (g > 0).mean() * 100.0,   # cost-independent
        "gross_exp": g.mean(),                        # cost-independent  ← KEY
        "gross_profit": g.sum(),                      # cost-independent
        "costs": trades["cost"].sum(),
        "avg_cost": trades["cost"].mean(),            # per-trade cost hurdle
        "net": net.sum(),
        "pf_net": pf_net,
        "dd_inr": dd_inr,
        "dd_pct": dd_pct,
    }


def _fmt(v, kind):
    if kind == "inr":
        return f"₹{v:,.0f}"
    if kind == "inr1":
        return f"₹{v:,.1f}"
    if kind == "pct":
        return f"{v:.1f}%"
    if kind == "pct2":
        return f"{v:.2f}%"
    if kind == "num":
        return f"{v:.2f}"
    if kind == "int":
        return f"{v:d}"
    return str(v)


def _print_block(symbol: str, variant: str, base: dict, reg: dict) -> None:
    print(f"\n┌── {symbol} · {variant} ── baseline  vs  +regime ──")
    if reg.get("trades", 0) == 0:
        print("│  +regime produced NO trades (regime never trending under fixed thresholds).")
    rows = [
        ("total trades", "trades", "int"),
        ("win rate (gross)", "win_rate_gross", "pct"),
        ("GROSS exp/trade  ◀ cost-indep", "gross_exp", "inr1"),
        ("GROSS profit     ◀ cost-indep", "gross_profit", "inr"),
        ("avg cost/trade (hurdle)", "avg_cost", "inr1"),
        ("total costs", "costs", "inr"),
        ("net profit", "net", "inr"),
        ("profit factor (net)", "pf_net", "num"),
        ("max drawdown", "dd_inr", "inr"),
    ]
    label_w = max(len(r[0]) for r in rows)
    print(f"│  {'metric':<{label_w}}   {'baseline':>16}   {'+regime':>16}")
    for label, key, kind in rows:
        b = _fmt(base[key], kind) if key in base else "—"
        r = _fmt(reg[key], kind) if key in reg else "—"
        print(f"│  {label:<{label_w}}   {b:>16}   {r:>16}")

    # Mechanics call-outs (cost-independent).
    if reg.get("trades", 0):
        cut = (1 - reg["trades"] / base["trades"]) * 100.0
        d_exp = reg["gross_exp"] - base["gross_exp"]
        hurdle = base["avg_cost"]
        print(f"│  → trades cut {cut:.0f}%  ({base['trades']}→{reg['trades']})")
        print(f"│  → GROSS exp/trade {_fmt(base['gross_exp'],'inr1')} → {_fmt(reg['gross_exp'],'inr1')} "
              f"(Δ {_fmt(d_exp,'inr1')})")
        print(f"│  → gross exp/trade vs ~₹{hurdle:,.0f} cost hurdle: "
              f"baseline {'CLEARS' if base['gross_exp']>hurdle else 'below'}, "
              f"+regime {'CLEARS' if reg['gross_exp']>hurdle else 'below'}")
    print("└" + "─" * 60)


def main() -> int:
    cfg = Config()
    print("TREND-ENGINE · Ablation rung 1 — regime filter on VWAP-cross baseline")
    print(f"regime: lookback={cfg.regime_lookback} bars · Hurst>{cfg.hurst_thresh} · "
          f"ER>{cfg.er_thresh} · ATR_pct>{cfg.atr_pct_thresh} · atr_period={cfg.atr_period}  (fixed)")
    print("Read the cost-independent rows (trade count, GROSS exp/trade). 61 days — mechanics, not edge.")

    for symbol in cfg.symbols:
        spec = cfg.instruments[symbol]
        print(f"\n########## {symbol}  (lot_size={spec.lot_size}, tick={spec.tick_size}) ##########")
        df = load(symbol)
        cost_model = CostModel.default(brokerage_per_order=cfg.brokerage_per_order)
        slippage_model = SlippageModel(ticks=cfg.slippage_ticks, tick_size=spec.tick_size)
        for variant, base_fn in VARIANTS:
            tb, eb = run_backtest(df, base_fn, cost_model, slippage_model, cfg, symbol)
            gated = make_regime_signal(base_fn, cfg)
            tr, er = run_backtest(df, gated, cost_model, slippage_model, cfg, symbol)
            _print_block(symbol, variant, _metrics(tb, eb), _metrics(tr, er))

    print("\nDone — mechanics check on 61 days; not an edge read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

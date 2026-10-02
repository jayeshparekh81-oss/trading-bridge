#!/usr/bin/env python3
"""Decisive test: persistent NET edge vs favourable-window trend-beta.

    python trend_engine/run_donchian_oos.py

Three honesty layers on the Donchian trend entry over 5y BSE/CDSL:
  1. %-normalized ATR sizing — constant risk per trade (1 ATR ≈ atr_risk_frac of
     capital), so results are in % / R-multiples and price-level inflation dies.
  2. REAL equity-intraday cost model (STT/txn/SEBI/stamp/GST) + bps slippage.
  3. Walk-forward OOS — 18mo burn-in, rolling 6mo test windows, concatenated.
     (Donchian N is FIXED, never tuned — so every year is effectively OOS; the
     per-year table below is the real out-of-window survival evidence.)

The harness is reused ONLY to generate causal entry/exit timing (run with zero
slippage + zero cost); this module owns sizing + costs so it can apply the
equity schedule and constant-risk sizing the futures harness doesn't.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from config import Config  # noqa: E402
from costs import CostModel, SlippageModel  # noqa: E402
from data import load  # noqa: E402
from donchian_entry import make_donchian  # noqa: E402
from harness import run_backtest  # noqa: E402

SYMBOLS = ["BSE", "CDSL"]
CONFIGS = [("N=20 LS", 20, True), ("N=55 LS", 55, True),
           ("N=20 LO", 20, False), ("N=55 LO", 55, False)]
BSE_V481_PF = 2.86  # Jayesh's existing BSE v4.8.1 honest PF (per this brief;
#                     an earlier note cited 1.633 — flagged, using the brief's figure).


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([(df["high"] - df["low"]).abs(),
                    (df["high"] - prev).abs(),
                    (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def enrich(trades: pd.DataFrame, atr: pd.Series, cfg: Config, eq_cost: CostModel) -> pd.DataFrame:
    """Apply ATR sizing (constant risk) + equity costs → per-trade net % and R."""
    if trades.empty:
        return trades
    t = trades.copy()
    t["atr_entry"] = atr.reindex(t["entry_time"]).to_numpy()
    t = t[(t["atr_entry"].notna()) & (t["atr_entry"] > 0)].copy()

    risk_inr = cfg.capital * cfg.atr_risk_frac              # constant risk / trade
    # ATR sizing, but CAP notional at 1× capital (no leverage). Without this,
    # tiny-ATR bars demand absurd size (e.g. 27k BSE shares on a 0.18-ATR bar)
    # that would never fill at a few bps — inflating the mean with un-executable
    # outliers. The cap keeps the edge honest.
    raw_qty = risk_inr / t["atr_entry"]
    cap_qty = cfg.capital / t["entry_price"]
    t["qty"] = np.minimum(raw_qty, cap_qty)
    direction = np.where(t["direction"] == "long", 1.0, -1.0)
    move = (t["entry_price"] * 0 + (t["exit_price"] - t["entry_price"])) * direction  # points
    t["R_gross"] = move / t["atr_entry"]
    gross_inr = move * t["qty"]

    buy_val = np.where(direction > 0, t["entry_price"], t["exit_price"]) * t["qty"]
    sell_val = np.where(direction > 0, t["exit_price"], t["entry_price"]) * t["qty"]
    turnover = buy_val + sell_val
    stat_cost = np.array([eq_cost.round_trip(b, s) for b, s in zip(buy_val, sell_val)])
    slip_cost = (cfg.slippage_bps_per_side / 1e4) * turnover
    t["cost_inr"] = stat_cost + slip_cost

    t["net_inr"] = gross_inr - t["cost_inr"]
    t["ret_pct"] = t["net_inr"] / cfg.capital * 100.0
    t["R_net"] = t["net_inr"] / risk_inr                   # net in R units (constant risk)
    t["year"] = pd.to_datetime(t["entry_time"]).dt.year
    return t


def _metrics(t: pd.DataFrame) -> dict:
    if t.empty:
        return {"n": 0}
    net = t["net_inr"]
    eq = cfg_capital + net.cumsum().to_numpy()
    peak = np.maximum.accumulate(eq)
    dd_pct = ((eq - peak) / peak).min() * 100.0
    pf = net[net > 0].sum() / abs(net[net < 0].sum()) if (net < 0).any() else float("inf")
    return {
        "n": len(t),
        "exp_pct": t["ret_pct"].mean(),
        "med_pct": t["ret_pct"].median(),   # typical trade — trend-following runs negative here
        "exp_R": t["R_net"].mean(),
        "pf": pf,
        "dd_pct": dd_pct,
        "win": (net > 0).mean() * 100.0,
    }


def main() -> int:
    cfg = Config()
    global cfg_capital
    cfg_capital = cfg.capital
    print("TREND-ENGINE · Donchian NET OOS — persistent edge vs favourable-window trend-beta")
    print(f"ATR sizing: 1 ATR ≈ {cfg.atr_risk_frac * 100:.2f}% capital/trade (constant risk) · "
          f"equity-intraday costs + {cfg.slippage_bps_per_side:.0f}bps/side slippage")
    print(f"Walk-forward: {cfg.wf_train_months}mo burn-in → rolling {cfg.wf_test_months}mo OOS "
          "(N fixed, not tuned).\n")

    per_year_store: dict[tuple[str, str], pd.DataFrame] = {}

    for symbol in SYMBOLS:
        df = load(symbol)
        atr = _atr(df, cfg.atr_period)
        eq_cost = CostModel.default_equity_intraday()
        zslip = SlippageModel(ticks=0, tick_size=cfg.instruments[symbol].tick_size)
        oos_start = df.index.min() + pd.DateOffset(months=cfg.wf_train_months)

        print(f"########## {symbol}  (OOS starts {oos_start.date()} after {cfg.wf_train_months}mo burn-in) ##########")
        print(f"  {'config':<9} {'OOS n':>6} {'NET mean%':>10} {'med%':>8} {'NET R/tr':>9} "
              f"{'PF':>6} {'maxDD%':>8} {'win%':>6}")
        for name, n, ls in CONFIGS:
            trades, _ = run_backtest(df, make_donchian(n, ls), CostModel.zero(), zslip, cfg, symbol)
            t = enrich(trades, atr, cfg, eq_cost)
            oos = t[t["entry_time"] >= oos_start]
            m = _metrics(oos)
            per_year_store[(symbol, name)] = t
            pf = f"{m['pf']:.2f}" if m["n"] else "—"
            print(f"  {name:<9} {m.get('n', 0):>6} {m.get('exp_pct', float('nan')):>+9.3f}% "
                  f"{m.get('med_pct', float('nan')):>+7.3f}% {m.get('exp_R', float('nan')):>9.3f} {pf:>6} "
                  f"{m.get('dd_pct', float('nan')):>7.1f}% {m.get('win', float('nan')):>5.1f}%")

        if symbol == "BSE":
            bse_pf = _metrics(per_year_store[("BSE", "N=55 LS")][
                per_year_store[("BSE", "N=55 LS")]["entry_time"] >= oos_start])["pf"]
            print(f"  → BSE Donchian N=55 LS OOS net PF = {bse_pf:.2f}  vs  v4.8.1 honest PF {BSE_V481_PF} "
                  f"→ this cruder Donchian is {'comparable' if bse_pf >= BSE_V481_PF * 0.8 else 'WELL BELOW'}")
        print()

    # ── Per-year NET %-edge survival table (the real out-of-window test) ──
    print("═" * 74)
    print("  PER-YEAR NET %-EDGE (mean net return/trade, %) — full sample, N fixed (un-tuned)")
    print("  The 2021–2023 columns are the out-of-2024-26-window survival test.")
    print("═" * 74)
    for name in ["N=55 LS", "N=20 LS"]:
        print(f"\n  ── {name} ──")
        print(f"  {'symbol':<7} " + " ".join(f"{y:>10}" for y in range(2021, 2027)))
        for symbol in SYMBOLS:
            t = per_year_store[(symbol, name)]
            cells = []
            for y in range(2021, 2027):
                sub = t[t["year"] == y]
                cells.append(f"{sub['ret_pct'].mean():>+9.3f}%" if len(sub) else f"{'—':>10}")
            print(f"  {symbol:<7} " + " ".join(cells))
        # counts row for context
        for symbol in SYMBOLS:
            t = per_year_store[(symbol, name)]
            counts = [f"{int((t['year'] == y).sum()):>10}" for y in range(2021, 2027)]
            print(f"  {symbol + ' n':<7} " + " ".join(counts))

    print("\n" + "═" * 74)
    print("  Verdict inputs: is BSE net-positive OUTSIDE 2024–26 (i.e. 2021–2023)?  See table above.")
    print("═" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

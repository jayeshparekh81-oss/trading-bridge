#!/usr/bin/env python3
"""1% CLUB — benchmark diagnostic. NOT a strategy variant, NOT a verdict input.

Computes buy-and-hold benchmarks over the EXACT Module 2 window and prints them
beside configs A and B. Reads the existing equity curves; does NOT re-run either
config and does NOT alter any registered gate.

Benchmarks
  1. NIFTY buy & hold (price index; excludes dividends, not directly investable)
  2. Universe equal-weight BUY & HOLD, no rebalancing  <- primary comparator
       Rs 10,00,000 / 188 allocated per symbol. A symbol that lists mid-window
       holds its slice in CASH at zero return until its first session, then buys
       at that session's close and holds to the end. No rebalancing, so winners
       drift up in weight -- this mirrors how configs A and B actually behave.
  3. Universe equal-weight, REBALANCED DAILY (the textbook EW index) for
       reference: each day's return is the mean daily return of every symbol
       that has both today's and yesterday's close.

CAVEAT, stated loudly: the 188-symbol universe is TODAY'S F&O list frozen in
2026. Holding it from 2015 requires 2015 knowledge of the 2026 constituents, so
benchmarks 2 and 3 are NOT achievable -- they are an upper bound. The same
selection bias flatters configs A and B.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK / "scripts"))
from module2_backtest import drawdown, START_EQUITY  # noqa: E402

PANEL = TRACK / "data" / "panel_v2"
UNI = [l.strip() for l in (TRACK / "config" / "universe_frozen.txt").read_text().splitlines() if l.strip()]


def stats(s: pd.Series, name: str, base: float | None = None) -> dict:
    mdd, longest = drawdown(s)
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    b = base if base is not None else float(s.iloc[0])
    return {"series": name, "max_dd_pct": round(100 * mdd, 2),
            "longest_dd_days": longest, "cagr_pct": round(100 * ((s.iloc[-1] / b) ** (1 / yrs) - 1), 2),
            "total_return_pct": round(100 * (s.iloc[-1] / b - 1), 1)}


def main() -> None:
    eqA = pd.read_parquet(PANEL.parent / "m2" / "module2_equity_A.parquet")["equity"]
    eqB = pd.read_parquet(PANEL.parent / "m2" / "module2_equity_B.parquet")["equity"]
    d0, d1 = eqA.index[0], eqA.index[-1]

    P = pd.read_parquet(PANEL / "module1_panel.parquet", columns=["date", "symbol", "close"])
    P["date"] = pd.to_datetime(P["date"])
    C = P.pivot(index="date", columns="symbol", values="close").sort_index()
    C = C.loc[(C.index >= d0) & (C.index <= d1), UNI]
    print(f"window {d0.date()} -> {d1.date()}   sessions {len(C)}   symbols {C.shape[1]}")

    first = C.apply(lambda s: s.first_valid_index())
    late = first[first > d0]
    print(f"symbols present on day 1: {int((first == d0).sum())}   listing mid-window: {len(late)}")
    print(f"  mid-window listers hold cash at 0% until: earliest {late.min().date()}, "
          f"latest {late.max().date()}")

    # ---- 2. EW buy & hold, no rebalancing, cash until listing
    slice_rs = START_EQUITY / len(UNI)
    held = C.ffill()
    shares = pd.Series({s: slice_rs / C[s].loc[first[s]] for s in UNI})
    val = held.mul(shares, axis=1)
    # before a symbol's first session its slice sits in cash
    not_yet = C.ffill().isna()
    val = val.where(~not_yet, slice_rs)
    ew_bh = val.sum(axis=1)

    # ---- 3. EW rebalanced daily
    r = C.pct_change()
    ew_reb = START_EQUITY * (1 + r.mean(axis=1, skipna=True).fillna(0)).cumprod()

    n = pd.read_parquet(PANEL / "nifty_daily.parquet")
    n.index = pd.DatetimeIndex(pd.to_datetime(n.index)).normalize()
    nif = n.loc[(n.index >= d0) & (n.index <= d1), "close"]

    rows = [stats(nif, "NIFTY buy & hold"),
            stats(ew_bh, "Universe EW buy & hold (no rebal)", START_EQUITY),
            stats(ew_reb, "Universe EW rebalanced daily", START_EQUITY),
            stats(eqA, "Config A (F5 in)", START_EQUITY),
            stats(eqB, "Config B (F5 out)", START_EQUITY)]
    T = pd.DataFrame(rows)
    print()
    print(T.to_string(index=False))
    T.to_parquet(PANEL.parent / "m2" / "benchmarks.parquet", index=False)
    print()
    for s, nm in ((ew_bh, "EW buy & hold"), (ew_reb, "EW rebalanced")):
        dd = s / s.cummax() - 1
        print(f"{nm}: worst trough {dd.min():.4f} on {dd.idxmin().date()}")
    return T


if __name__ == "__main__":
    main()

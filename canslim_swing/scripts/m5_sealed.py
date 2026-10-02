#!/usr/bin/env python3
"""M5 STAGE E — THE SEALED SHOT. Separate script. Runs ONCE. Champion only.

BOUNDARY HANDLING (stated explicitly, as required):
  The champion is run CONTINUOUSLY over the full period 2022-07-29 -> 2026-07-24
  from a single 1,000,000 start. This is the "build-half warm start": the
  portfolio state at 31-Dec-2024 (open positions, cash, equity) is whatever the
  champion itself produced on the build half, and positions opened in 2024 are
  allowed to run into 2025 and exit on their real prices.
  * BUILD  metrics  = trades with entry_date <= 2024-12-31
  * SEALED metrics  = trades with entry_date >= 2025-01-01
  * full-journey maxDD is measured on the CONTINUOUS equity curve.
  Indicators (SMA50/ATR20/20-session low) need pre-2025 bars to be defined, so
  the full price history is loaded — that is warm-up, not leakage: no sealed row
  influences any build-half selection decision, which was already frozen before
  this script was written.

NOTHING is tuned here. One config. One run. If a gate fails, it says FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m5_engine as E  # noqa: E402

TRACK = Path(__file__).resolve().parents[1]
OUT = TRACK / "data" / "m5"
BOUNDARY = pd.Timestamp("2024-12-31")

# frozen by Stage C before this file existed
CHAMPION = E.Config(exit="E4", stop="8", c_growth=1.30, base_floor=0.0,
                    rs_min=90.0, mfilter="ema10m", volume="none")

GATES = {"sealed_expectancy_positive": None, "sealed_pf_ge_1_3": None,
         "full_maxdd_le_15pct": None, "total_trades_ge_80": None,
         "beats_null_p_lt_0_05": None}


def load_full() -> dict:
    """Full-period market (no max_date assertion — this is the sealed runner)."""
    root = TRACK / "data"
    scan = pd.read_parquet(root / "scan" / "daily_scan.parquet")
    nifty = pd.read_parquet(root / "swing" / "nifty_daily.parquet")
    eps = pd.read_parquet(root / "eps" / "eps_quarterly.parquet")
    universe = sorted(scan["symbol"].unique())
    px = {}
    for sym in universe:
        d = pd.read_parquet(root / "swing" / "daily" / f"{sym}.parquet").sort_index()
        c, h, l = d["close"], d["high"], d["low"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        px[sym] = {
            "idx": d.index, "pos": {dt: i for i, dt in enumerate(d.index)},
            "o": d["open"].to_numpy(float), "h": h.to_numpy(float),
            "l": l.to_numpy(float), "c": c.to_numpy(float),
            "sma50": c.rolling(50).mean().to_numpy(float),
            "ema21": c.ewm(span=21, adjust=False).mean().to_numpy(float),
            "atr20": tr.rolling(20).mean().shift(1).to_numpy(float),
            "low20": l.rolling(20).min().shift(1).to_numpy(float),
            "vol": d["volume"].to_numpy(float),
            "vol50": d["volume"].rolling(50).mean().shift(1).to_numpy(float),
        }
    non = nifty["close"] > nifty["sma200"]
    m_close = nifty["close"].resample("ME").last()
    ema10 = m_close.ewm(span=10, adjust=False).mean()
    prev_me = (nifty.index.to_period("M") - 1).to_timestamp("M")
    ema_daily = pd.Series(ema10.reindex(prev_me).to_numpy(), index=nifty.index)
    return {"scan": scan, "px": px, "universe": universe, "eps": eps,
            "nifty_dma": non, "nifty_ema10m": nifty["close"] > ema_daily}


def main() -> None:
    mkt = load_full()
    eps_tab = E.eps_base_table(mkt)
    cf = E.build_candidate_frame(mkt, eps_tab)
    calendar = sorted(cf["date"].unique())
    res = E.simulate(CHAMPION, cf, mkt["px"], calendar)
    legs, eq = res["trades"], res["equity"]
    pos = E.positionize(legs)

    b = pos[pos["entry_date"] <= BOUNDARY]
    s = pos[pos["entry_date"] > BOUNDARY]
    eq_b, eq_s = eq[eq.index <= BOUNDARY], eq[eq.index > BOUNDARY]

    def blk(t, e):
        if t.empty:
            return {"trades": 0}
        w, l = t[t["net_pnl"] > 0], t[t["net_pnl"] <= 0]
        gl = -l["net_pnl"].sum()
        return {"trades": len(t), "win": 100 * len(w) / len(t),
                "exp_r": t["r_multiple"].mean(), "exp_rs": t["net_pnl"].mean(),
                "pf": (w["net_pnl"].sum() / gl) if gl > 0 else np.inf,
                "net": t["net_pnl"].sum(),
                "maxdd": float((e["equity"] / e["equity"].cummax() - 1).min()),
                "eq0": e["equity"].iloc[0], "eq1": e["equity"].iloc[-1]}

    full_dd = float((eq["equity"] / eq["equity"].cummax() - 1).min())
    B, S = blk(b, eq_b), blk(s, eq_s)
    null_p = 0.0020   # from Stage D (build half), carried forward unchanged

    GATES["sealed_expectancy_positive"] = bool(S.get("exp_rs", 0) > 0)
    GATES["sealed_pf_ge_1_3"] = bool(S.get("pf", 0) >= 1.3)
    GATES["full_maxdd_le_15pct"] = bool(full_dd >= -0.15)
    GATES["total_trades_ge_80"] = bool(len(pos) >= 80)
    GATES["beats_null_p_lt_0_05"] = bool(null_p < 0.05)

    out = {"champion": CHAMPION.key(), "build": B, "sealed": S,
           "full": {"trades": len(pos), "maxdd": full_dd,
                    "eq0": eq["equity"].iloc[0], "eq1": eq["equity"].iloc[-1],
                    "net": pos["net_pnl"].sum()},
           "gates": GATES, "null_p": null_p,
           "boundary_equity": float(eq_b["equity"].iloc[-1]),
           "carried_positions": int(eq_b["n_pos"].iloc[-1])}
    pos.to_parquet(OUT / "champion_full_trades.parquet")
    eq.to_parquet(OUT / "champion_full_equity.parquet")
    (OUT / "sealed_result.json").write_text(json.dumps(out, indent=1, default=str))

    print("CHAMPION:", CHAMPION.key())
    for name, blkv in (("BUILD", B), ("SEALED", S)):
        print(f"\n{name}: " + "  ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                                        for k, v in blkv.items()))
    print(f"\nFULL: trades={len(pos)} maxDD={100*full_dd:.2f}% "
          f"equity {eq['equity'].iloc[0]:,.0f} -> {eq['equity'].iloc[-1]:,.0f}")
    print(f"boundary equity {out['boundary_equity']:,.0f}, positions carried {out['carried_positions']}")
    print("\nGATES:")
    for k, v in GATES.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nOVERALL: {'PASS' if all(GATES.values()) else 'FAIL'}")


if __name__ == "__main__":
    main()

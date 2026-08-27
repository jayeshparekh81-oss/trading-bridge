#!/usr/bin/env python3
"""1% CLUB — NULL CORRECTNESS FIX + RE-MEASUREMENT.

This repairs a broken MEASUREMENT INSTRUMENT. It is not a new configuration and
not a re-test. No strategy parameter changes; no config is re-run. The stored
trade ledgers are read as-is and only the null is recomputed.

TWO DEFECTS FIXED (found by the adversarial audit, scripts/club1pct_audit.py):

  DEFECT 1 — the old null passed a ONE-SHARE price as the trade notional, so the
  flat Rs 15.93 DP sell fee was charged against a ~Rs 493 median notional while
  the strategy paid it on a ~Rs 1.5 lakh position: a 1,096x handicap, mean
  0.7053 R per trade. FIX: size each null trade on NOTIONAL = 10% of STARTING
  capital = Rs 1,00,000, whole shares rounded down, exactly as the strategy
  sizes at t=0, and compute P&L through the identical cost path.

  DEFECT 2 — the old null drew from `ema220 finite`, which is true from a
  symbol's first bar, so 12.0% of the pool was pre-warmup and untradeable.
  FIX: draw from the strategy's own `eligible` flag.

  DEFECT 3 — left in place deliberately, but MEASURED: the null excludes actual
  signal days, making it a "random NON-signal entry". Reported both ways.

Everything else is held identical to the old null so the comparison isolates the
fixes: same 500 iterations, same seed, same hold resampling, same skip-on-missing
price, same ONE-SIDED p-value.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK / "scripts"))
import module2_backtest as M2  # noqa: E402

NOTIONAL = M2.MAX_POS_PCT * M2.START_EQUITY      # Rs 1,00,000
N_ITER, SEED = 500, 20260816
OUT = TRACK / "data" / "m2" / "null_corrected.parquet"

LEDGERS = [
    ("M2 config A", "m2/module2_trades_A.parquet", "A"),
    ("M2 config B", "m2/module2_trades_B.parquet", "B"),
    ("M3 EMA20", "m3/module3_trades_N20.parquet", "A"),
    ("M3 EMA50", "m3/module3_trades_N50.parquet", "A"),
    ("M3 EMA150", "m3/module3_trades_N150.parquet", "A"),
    ("M3 EMA220", "m3/module3_trades_N220.parquet", "A"),
    ("M4 CONTROL", "m4/module4_trades_CONTROL.parquet", "A"),
    ("M4 SCALE-10x", "m4/module4_trades_SCALE-10x.parquet", "A"),
    ("M4 SCALE-20x", "m4/module4_trades_SCALE-20x.parquet", "A"),
]
OLD = {  # transcribed from the original runs, for the before/after column
    "M2 config A": (0.4396, 0.0480), "M2 config B": (0.5101, 0.0360),
    "M3 EMA20": (-0.6240, 0.0000), "M3 EMA50": (-0.4916, 0.0000),
    "M3 EMA150": (-0.0095, 0.0240), "M3 EMA220": (0.4396, 0.0480),
    "M4 CONTROL": (0.4396, 0.0480), "M4 SCALE-10x": (0.4396, 0.0240),
    "M4 SCALE-20x": (0.4396, 0.0260),
}


def null_fixed(pool, o, holds, n, nd, n_iter=N_ITER, seed=SEED):
    """Identical to the old null except for the two fixes. Returns iteration means."""
    rng = np.random.default_rng(seed)
    out = np.empty(n_iter)
    for it in range(n_iter):
        pick = pool[rng.integers(0, len(pool), n)]
        h = holds[rng.integers(0, len(holds), n)]
        rs = []
        for (d, col), hh in zip(pick, h):
            j = min(d + int(hh), nd - 1)
            e, x = o[d, col], o[j, col]
            if not (np.isfinite(e) and np.isfinite(x) and e > 0):
                continue
            entry, exitp = e * (1 + M2.SLIP), x * (1 - M2.SLIP)
            sh = int(NOTIONAL // entry)                     # FIX 1: real position
            if sh <= 0:
                continue
            gross_in = sh * entry
            cost_in = gross_in + M2.buy_costs(gross_in)
            gross_out = sh * exitp
            net_out = gross_out - M2.sell_costs(gross_out)
            rs.append((net_out - cost_in) / (M2.STOP_FRAC * gross_in))
        out[it] = float(np.mean(rs)) if rs else np.nan
    return out[np.isfinite(out)]


def main():
    M, sigA, sigB, dates, syms = M2.load()
    o = M["open"].to_numpy()
    nd = o.shape[0]
    P = pd.read_parquet(TRACK / "data" / "panel_v2" / "module1_panel.parquet",
                        columns=["date", "symbol", "eligible"])
    P["date"] = pd.to_datetime(P["date"])
    ELIG = (P.pivot(index="date", columns="symbol", values="eligible")
              .sort_index().reindex(columns=syms).fillna(False).to_numpy(bool))
    finite_o = np.isfinite(o)

    tr = pd.read_parquet(TRACK / "data" / "m2" / "module2_trades_A.parquet")
    print(f"NOTIONAL used for null sizing: Rs {NOTIONAL:,.0f} "
          f"(= 10% of starting capital, the strategy's sizing rule at t=0)")
    print(f"  strategy's ACTUAL notionals: median Rs {tr['notional'].median():,.0f}, "
          f"p10 Rs {tr['notional'].quantile(.1):,.0f}, p90 Rs {tr['notional'].quantile(.9):,.0f}")
    print(f"  Rs 1,00,000 is at the LOW end, so the null still carries a slightly HIGHER")
    print(f"  flat-fee burden in R than the strategy's average — conservative, i.e. it")
    print(f"  cannot flatter the null.")
    print()
    print(f"POOL SIZES")
    for tag, sg in (("A", sigA), ("B", sigB)):
        old_pool = np.isfinite(M["ema220"].to_numpy()) & finite_o & ~sg
        new_ex = ELIG & finite_o & ~sg
        new_in = ELIG & finite_o
        print(f"  sig {tag}: old {old_pool.sum():,}   new excl-signal {new_ex.sum():,}   "
              f"new incl-signal {new_in.sum():,}")
    print()

    pools = {}
    for tag, sg in (("A", sigA), ("B", sigB)):
        pools[(tag, "excl")] = np.argwhere(ELIG & finite_o & ~sg)
        pools[(tag, "incl")] = np.argwhere(ELIG & finite_o)

    rows = []
    for label, path, sigtag in LEDGERS:
        T = pd.read_parquet(TRACK / "data" / path)
        cl = T[~T["open_at_end"]]
        holds = cl["sessions_held"].to_numpy()
        holds = holds[holds > 0]
        n = len(cl)
        exp_r = float(cl["r_multiple"].mean())
        d_ex = null_fixed(pools[(sigtag, "excl")], o, holds, n, nd)
        d_in = null_fixed(pools[(sigtag, "incl")], o, holds, n, nd)
        p_ex = float((d_ex >= exp_r).mean())
        p_in = float((d_in >= exp_r).mean())
        old_mean, old_p = OLD[label]
        rows.append({"variant": label, "trades": n, "exp_r": exp_r,
                     "old_null_mean": old_mean, "old_p": old_p,
                     "new_null_mean": float(d_ex.mean()), "new_null_median": float(np.median(d_ex)),
                     "new_p": p_ex, "incl_sig_null_mean": float(d_in.mean()), "incl_sig_p": p_in,
                     "old_gate5": "PASS" if old_p < 0.05 else "FAIL",
                     "new_gate5": "PASS" if p_ex < 0.05 else "FAIL",
                     "edge_vs_new_null": exp_r - float(d_ex.mean())})
        print(f"  done {label}")
    R = pd.DataFrame(rows)
    R.to_parquet(OUT, index=False)
    print()
    print("=" * 100)
    print("CORRECTED NULL — every variant already run")
    print("=" * 100)
    print(R[["variant", "trades", "exp_r", "old_null_mean", "new_null_mean", "old_p", "new_p",
             "old_gate5", "new_gate5"]].round(4).to_string(index=False))
    print()
    print("DEFECT 3 MEASURED — excluding vs including actual signal days in the pool")
    print(R[["variant", "new_null_mean", "incl_sig_null_mean", "new_p", "incl_sig_p"]]
          .assign(tilt=lambda x: x["new_null_mean"] - x["incl_sig_null_mean"]).round(4).to_string(index=False))
    print()
    print("EDGE OVER THE CORRECTED NULL")
    print(R[["variant", "exp_r", "new_null_mean", "new_null_median", "edge_vs_new_null"]]
          .round(4).to_string(index=False))
    print(f"\nwritten: {OUT}")


if __name__ == "__main__":
    main()

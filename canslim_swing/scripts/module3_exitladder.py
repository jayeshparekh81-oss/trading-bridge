#!/usr/bin/env python3
"""MODULE 3 — EXIT LADDER. PRE-REGISTERED, SHAPE QUESTION, NOT WINNER-PICKING.

Entry = Module 2 CONFIG A exactly (F1..F5 + breakout), FROZEN. F1 and F5 keep
their EMA220 as registered in Module 1 — only EXIT leg 1 varies.

  exit leg 1 : close < EMA(N),  N in {20, 50, 150, 220}   <- the only variable
  exit leg 2 : close <= 0.85 * entry fill                 <- unchanged

Everything else is Module 2: same portfolio, slots, tie-break, costs, slippage,
exit-at-next-open, no rebalancing. The Module 2 harness is imported and called
UNMODIFIED; the only thing swapped is the matrix the exit leg reads. N=220 must
therefore reproduce Module 2 config A exactly — that is the correctness check.

DECLARED NOW: nothing here can validate any configuration. This window is burnt
for this spec. The output is a hypothesis about exit speed, to be tested forward.
No fifth N. No interpolation. No searching around a winner.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK / "scripts"))
import module2_backtest as M2  # noqa: E402

OUT = TRACK / "data" / "m3"
NS = [20, 50, 150, 220]
EW_BENCH = {"cagr": 18.70, "max_dd": -35.50}     # from data/m2/benchmarks.parquet


def cost_breakdown(T: pd.DataFrame) -> dict:
    """Recover costs from the ledger. explicit = STT/GST/exchange/SEBI/stamp/DP."""
    buy_expl = T["cost_in"] - T["notional"]
    sell_gross = T["shares"] * T["exit_px"]
    sell_expl = sell_gross - T["proceeds"]
    s = M2.SLIP
    buy_slip = T["shares"] * T["entry_px"] * (s / (1 + s))
    sell_slip = T["shares"] * T["exit_px"] * (s / (1 - s))
    return {"explicit": float(buy_expl.sum() + sell_expl.sum()),
            "slippage": float(buy_slip.sum() + sell_slip.sum()),
            "total": float(buy_expl.sum() + sell_expl.sum() + buy_slip.sum() + sell_slip.sum())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    M, sigA, sigB, dates, syms = M2.load()
    close = M["close"]

    # correctness precondition: our EMA(220) must equal the panel's stored ema220
    e220 = close.ewm(span=220, adjust=False).mean()
    delta = (e220 - M["ema220"]).abs().to_numpy()
    delta = delta[np.isfinite(delta)]
    print(f"EMA(220) recomputation vs stored panel ema220: max abs diff = {delta.max():.3e}")

    rows, store = [], {}
    for N in NS:
        Mn = dict(M)
        Mn["ema220"] = close.ewm(span=N, adjust=False).mean()
        res = M2.simulate(Mn, sigA, dates, syms, f"N{N}")
        m = M2.metrics(res)
        nl = M2.null_dist(Mn, sigA, dates, res["trades"])
        p = float((nl >= m["exp_r"]).mean())
        T = res["trades"]
        cl = T[~T["open_at_end"]]
        cb = cost_breakdown(T)
        big = cl.nlargest(1, "pnl").iloc[0]
        q = cl["sessions_held"].quantile([.25, .5, .75])
        rows.append({"N": N, "trades": m["trades_closed"], "win_rate": m["win_rate"],
                     "exp_rs": m["exp_rs"], "exp_r": m["exp_r"],
                     "profit_factor": m["profit_factor"], "cagr": m["cagr"],
                     "max_dd": m["max_dd"], "longest_dd": m["longest_dd_days"],
                     "final_equity": m["final_equity"], "hold_med": q[.5],
                     "hold_q1": q[.25], "hold_q3": q[.75],
                     "cost_total": cb["total"], "cost_explicit": cb["explicit"],
                     "cost_slippage": cb["slippage"],
                     "cost_pct_final": 100 * cb["total"] / m["final_equity"],
                     "null_mean": float(nl.mean()), "null_median": float(np.median(nl)), "p": p,
                     "big_sym": big["symbol"], "big_pnl": big["pnl"],
                     "big_pct_final": 100 * big["pnl"] / m["final_equity"],
                     "ex_ema": int((T["exit_reason"] == "ema220").sum()),
                     "ex_stop": int((T["exit_reason"] == "stop_15pct").sum()),
                     "ex_open": int((T["exit_reason"] == "open_at_end").sum()),
                     "total_trades": len(T)})
        store[N] = (res, m, p)
        T.to_parquet(OUT / f"module3_trades_N{N}.parquet", index=False)
        res["equity"].to_frame("equity").to_parquet(OUT / f"module3_equity_N{N}.parquet")

    R = pd.DataFrame(rows)
    R.to_parquet(OUT / "module3_ladder.parquet", index=False)

    # ---------------- per-N detail
    for _, r in R.iterrows():
        N = int(r["N"])
        print()
        print("=" * 78)
        print(f"EXIT LEG 1 = close < EMA({N})" + ("    [= Module 2 config A]" if N == 220 else ""))
        print("=" * 78)
        g = [("net expectancy > 0 after costs", r["exp_rs"] > 0, f"Rs {r['exp_rs']:,.0f}/trade"),
             ("profit factor >= 1.3", r["profit_factor"] >= 1.3, f"{r['profit_factor']:.3f}"),
             ("max drawdown <= 15%", r["max_dd"] >= -15.0, f"{r['max_dd']:.2f}%"),
             ("trades >= 60", r["trades"] >= 60, f"{int(r['trades'])}"),
             ("beats random-entry null, p < 0.05", r["p"] < 0.05, f"p = {r['p']:.4f}")]
        print("1. GATES")
        for nm, ok, v in g:
            print(f"     [{'PASS' if ok else 'FAIL'}]  {nm:<36} {v}")
        print(f"     OVERALL: {'PASS' if all(x[1] for x in g) else 'FAIL'}")
        print("2. HEADLINE")
        print(f"     trades {int(r['trades'])}   win rate {r['win_rate']:.2f}%   "
              f"expectancy Rs {r['exp_rs']:,.0f} = {r['exp_r']:+.3f} R")
        print(f"     profit factor {r['profit_factor']:.3f}   CAGR {r['cagr']:.2f}%   "
              f"final equity Rs {r['final_equity']:,.0f}")
        print(f"     max DD {r['max_dd']:.2f}%   longest DD {int(r['longest_dd'])} days")
        print("3. HOLDING PERIOD (sessions)")
        print(f"     median {r['hold_med']:.0f}   IQR {r['hold_q1']:.0f}..{r['hold_q3']:.0f}")
        print("4. EXIT REASONS")
        tt = r["total_trades"]
        print(f"     EMA({N}) leg   {r['ex_ema']:>5}  ({100*r['ex_ema']/tt:5.1f}%)")
        print(f"     -15% stop     {r['ex_stop']:>5}  ({100*r['ex_stop']/tt:5.1f}%)")
        print(f"     open at end   {r['ex_open']:>5}  ({100*r['ex_open']/tt:5.1f}%)")
        print("5. TOTAL COSTS PAID")
        print(f"     explicit charges Rs {r['cost_explicit']:>12,.0f}")
        print(f"     slippage (assumption) Rs {r['cost_slippage']:>7,.0f}")
        print(f"     TOTAL            Rs {r['cost_total']:>12,.0f}   "
              f"= {r['cost_pct_final']:.2f}% of final equity")
        print("6. LARGEST SINGLE WINNER")
        print(f"     {r['big_sym']}  Rs {r['big_pnl']:,.0f}  = {r['big_pct_final']:.1f}% of final equity")

    # ---------------- across
    print()
    print("=" * 78)
    print("7. THE LADDER")
    print("=" * 78)
    tab = R[["N", "exp_r", "profit_factor", "max_dd", "cagr", "hold_med", "trades", "cost_total"]].copy()
    tab.columns = ["N", "exp_R", "PF", "maxDD_%", "CAGR_%", "med_hold", "trades", "costs_Rs"]
    print(tab.round(3).to_string(index=False))
    print()
    print("9. BENCHMARK ROW (identical window, from data/m2/benchmarks.parquet)")
    print(f"     Universe EW buy & hold, no rebalancing: "
          f"CAGR {EW_BENCH['cagr']:.2f}%   maxDD {EW_BENCH['max_dd']:.2f}%")
    beats = R[R["cagr"] > EW_BENCH["cagr"]]["N"].tolist()
    print(f"     N values beating the EW universe on CAGR: {beats if beats else 'NONE'}")
    print()
    print("8. SHAPE")
    for col, lbl in (("exp_r", "expectancy R"), ("cagr", "CAGR"), ("profit_factor", "profit factor"),
                     ("max_dd", "max drawdown"), ("hold_med", "median hold"), ("trades", "trade count"),
                     ("cost_total", "total costs")):
        v = R.sort_values("N")[col].to_numpy()
        d = np.diff(v)
        mono = "MONOTONIC UP" if (d > 0).all() else ("MONOTONIC DOWN" if (d < 0).all() else "NOT monotonic")
        print(f"     {lbl:<16} across N=20,50,150,220: {np.round(v,3)}   -> {mono}")
    print()
    for N in NS:
        print(f"ledger N={N}: {OUT / f'module3_trades_N{N}.parquet'}")


if __name__ == "__main__":
    main()

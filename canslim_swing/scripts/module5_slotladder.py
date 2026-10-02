#!/usr/bin/env python3
"""MODULE 5 — SLOT / POSITION-WEIGHT LADDER. PRE-REGISTERED.

Base = Module 2 CONFIG A, unchanged in every respect except SLOT COUNT.
Entry, exits, tie-break, costs, slippage, exit-at-next-open, no rebalancing.
Capital fixed at Rs 10,00,000. N = 10, 20, 50, 80; position weight = 1/N of
CURRENT equity; one position per symbol.

The Module 2 engine is imported and called UNMODIFIED — only the two module
globals it reads at runtime are set. N=10 must therefore reproduce config A
byte-identically; that is the correctness check.

Gate 5 uses the CORRECTED null (scripts/club1pct_null_fix.py), hold-matched to
each N's own trade ledger. The old broken null is never used.

DECLARED: this window is burnt for this spec. Nothing here validates anything.
Output is a hypothesis for forward paper mode only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK / "scripts"))
import module2_backtest as M2  # noqa: E402
import club1pct_null_fix as NF  # noqa: E402

OUT = TRACK / "data" / "m5slot"
NS = [10, 20, 50, 80]
EW = {"cagr": 18.70, "max_dd": -35.50}


def costs_of(T):
    be = T["cost_in"] - T["notional"]
    se = T["shares"] * T["exit_px"] - T["proceeds"]
    s = M2.SLIP
    return float(be.sum() + se.sum()
                 + (T["shares"] * T["entry_px"] * (s / (1 + s))).sum()
                 + (T["shares"] * T["exit_px"] * (s / (1 - s))).sum())


def concurrency(T, cal, live_start):
    pos_of = {d: i for i, d in enumerate(cal)}
    cnt = np.zeros(len(cal), dtype=int)
    for r in T.itertuples():
        a = pos_of[r.entry_date]
        b = len(cal) if r.open_at_end else pos_of[r.exit_date]
        cnt[a:b] += 1
    C = pd.Series(cnt, index=pd.DatetimeIndex(cal))
    return C[C.index >= live_start]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    M, sigA, _, dates, syms = M2.load()
    o = M["open"].to_numpy()
    nd = o.shape[0]

    P = pd.read_parquet(TRACK / "data" / "panel_v2" / "module1_panel.parquet",
                        columns=["date", "symbol", "eligible", "close"])
    P["date"] = pd.to_datetime(P["date"])
    ELIG = (P.pivot(index="date", columns="symbol", values="eligible")
              .sort_index().reindex(columns=syms).fillna(False).to_numpy(bool))
    pool = np.argwhere(ELIG & np.isfinite(o) & ~sigA)
    live_start = P.loc[P["eligible"], "date"].min()
    CLOSE = P.pivot(index="date", columns="symbol", values="close").sort_index()
    late = set(CLOSE.columns[[CLOSE[c].first_valid_index() > dates[0] for c in CLOSE.columns]])
    print(f"symbols not listed on {dates[0].date()}: {len(late)}")
    print(f"null pool cells: {len(pool):,}   live window from {live_start.date()}")

    orig_n, orig_pct = M2.MAX_POSITIONS, M2.MAX_POS_PCT
    rows, store = [], {}
    for N in NS:
        M2.MAX_POSITIONS, M2.MAX_POS_PCT = N, 1 / N
        res = M2.simulate(M, sigA, dates, syms, f"N{N}")
        m = M2.metrics(res)
        T = res["trades"]
        cl = T[~T["open_at_end"]]
        holds = cl["sessions_held"].to_numpy()
        holds = holds[holds > 0]
        nulls = NF.null_fixed(pool, o, holds, len(cl), nd)
        p = float((nulls >= m["exp_r"]).mean())
        C = concurrency(T, dates, live_start)
        q = cl["sessions_held"].quantile([.25, .5, .75])
        cb = costs_of(T)
        surv = T[T["symbol"].isin(late)]["pnl"].sum()
        rows.append({"N": N, "trades": m["trades_closed"], "win_rate": m["win_rate"],
                     "exp_r": m["exp_r"], "exp_rs": m["exp_rs"], "pf": m["profit_factor"],
                     "cagr": m["cagr"], "max_dd": m["max_dd"], "longest_dd": m["longest_dd_days"],
                     "final_equity": m["final_equity"], "hold_med": q[.5],
                     "hold_q1": q[.25], "hold_q3": q[.75],
                     "conc_med": float(C.median()), "conc_q1": float(C.quantile(.25)),
                     "conc_q3": float(C.quantile(.75)), "conc_max": int(C.max()),
                     "conc_pct_of_cap": 100 * float(C.median()) / N,
                     "skip_slot": res["skip_slot"], "skip_cash": res["skip_cash"],
                     "costs": cb, "cost_pct": 100 * cb / m["final_equity"],
                     "null_mean": float(nulls.mean()), "null_med": float(np.median(nulls)),
                     "p": p, "edge": m["exp_r"] - float(nulls.mean()),
                     "surv_pnl": float(surv), "total_pnl": float(T["pnl"].sum()),
                     "surv_share": 100 * float(surv) / float(T["pnl"].sum()),
                     "avg_deployed": res["avg_deployed"]})
        store[N] = res
        T.to_parquet(OUT / f"module5_trades_N{N}.parquet", index=False)
        res["equity"].to_frame("equity").to_parquet(OUT / f"module5_equity_N{N}.parquet")
        print(f"  done N={N}")
    M2.MAX_POSITIONS, M2.MAX_POS_PCT = orig_n, orig_pct
    R = pd.DataFrame(rows)
    R.to_parquet(OUT / "module5_ladder.parquet", index=False)

    a = pd.read_parquet(TRACK / "data" / "m2" / "module2_trades_A.parquet")
    b = store[10]["trades"]
    cols = [c for c in a.columns if c in b.columns]
    ea = pd.read_parquet(TRACK / "data" / "m2" / "module2_equity_A.parquet")["equity"]
    print()
    print("=" * 78)
    print("N=10 CORRECTNESS CHECK vs Module 2 config A")
    print("=" * 78)
    print(f"  rows {len(a)} vs {len(b)}   ledger equals: "
          f"{a[cols].reset_index(drop=True).equals(b[cols].reset_index(drop=True))}")
    print(f"  equity identical: {ea.equals(store[10]['equity'])}   "
          f"max abs diff {float((ea - store[10]['equity']).abs().max()):.6f}")

    for _, r in R.iterrows():
        N = int(r["N"])
        print()
        print("=" * 78)
        print(f"N = {N}   (position weight {100/N:.2f}% of current equity)"
              + ("   [= Module 2 config A]" if N == 10 else ""))
        print("=" * 78)
        g = [("net expectancy > 0", r["exp_rs"] > 0, f"Rs {r['exp_rs']:,.0f}"),
             ("profit factor >= 1.3", r["pf"] >= 1.3, f"{r['pf']:.3f}"),
             ("max drawdown <= 15%", r["max_dd"] >= -15.0, f"{r['max_dd']:.2f}%"),
             ("trades >= 60", r["trades"] >= 60, f"{int(r['trades'])}"),
             ("beats CORRECTED null p<0.05", r["p"] < 0.05, f"p = {r['p']:.4f}")]
        print("1. GATES (corrected null)")
        for nm, ok, v in g:
            print(f"     [{'PASS' if ok else 'FAIL'}]  {nm:<32} {v}")
        print(f"     OVERALL: {'PASS' if all(x[1] for x in g) else 'FAIL'}")
        print("2. HEADLINE")
        print(f"     trades {int(r['trades'])}  win {r['win_rate']:.2f}%  "
              f"exp {r['exp_r']:+.3f} R  PF {r['pf']:.3f}  CAGR {r['cagr']:.2f}%")
        print(f"     maxDD {r['max_dd']:.2f}%  longestDD {int(r['longest_dd'])}d  "
              f"final Rs {r['final_equity']:,.0f}")
        print("3. HOLD + CONCURRENCY")
        print(f"     hold median {r['hold_med']:.0f}  IQR {r['hold_q1']:.0f}..{r['hold_q3']:.0f}")
        print(f"     concurrent held: median {r['conc_med']:.0f}  IQR {r['conc_q1']:.0f}.."
              f"{r['conc_q3']:.0f}  max {r['conc_max']}   "
              f"-> {r['conc_pct_of_cap']:.0f}% of the {N}-slot cap")
        print(f"     avg equity deployed {r['avg_deployed']:.1f}%")
        print("4. SKIPS")
        print(f"     no free slot {int(r['skip_slot']):,}   insufficient cash "
              f"{int(r['skip_cash']):,}  (symbol-days)")
        print("5. COSTS")
        print(f"     Rs {r['costs']:,.0f} = {r['cost_pct']:.2f}% of final equity")
        print("6. EDGE OVER THE HOLD-MATCHED CORRECTED NULL")
        print(f"     null mean {r['null_mean']:+.4f} R  median {r['null_med']:+.4f} R "
              f"(holds resampled from this N's own ledger, median {r['hold_med']:.0f} sessions)")
        print(f"     strategy {r['exp_r']:+.4f} R   EDGE {r['edge']:+.4f} R   p = {r['p']:.4f}")
        print("7. SURVIVORSHIP SHARE OF NET P&L")
        print(f"     Rs {r['surv_pnl']:,.0f} of Rs {r['total_pnl']:,.0f} = "
              f"{r['surv_share']:.1f}% from the {len(late)} symbols not listed 2015-01-01")

    print()
    print("=" * 78)
    print("8. THE LADDER")
    print("=" * 78)
    tab = R[["N", "exp_r", "edge", "pf", "max_dd", "cagr", "conc_med", "surv_share",
             "trades", "cost_pct"]].copy()
    tab.columns = ["N", "exp_R", "edge_R", "PF", "maxDD_%", "CAGR_%", "conc_med",
                   "surv_%", "trades", "cost_%"]
    print(tab.round(3).to_string(index=False))
    print()
    print("9. SHAPE")
    for col, lbl in (("exp_r", "expectancy R"), ("edge", "edge over null"),
                     ("cagr", "CAGR"), ("pf", "profit factor"), ("max_dd", "max drawdown"),
                     ("conc_med", "concurrent held"), ("surv_share", "survivorship share")):
        v = R.sort_values("N")[col].to_numpy()
        d = np.diff(v)
        mono = "MONOTONIC UP" if (d > 0).all() else ("MONOTONIC DOWN" if (d < 0).all() else "NOT monotonic")
        print(f"   {lbl:<20} {np.round(v,3)}  -> {mono}")
    print()
    print("10. BENCHMARK")
    print(f"   Universe EW buy & hold: CAGR {EW['cagr']:.2f}%   maxDD {EW['max_dd']:.2f}%")
    hi = R[R["N"] == max(NS)].iloc[0]
    print(f"   highest N ({int(hi['N'])}): CAGR {hi['cagr']:.2f}%  maxDD {hi['max_dd']:.2f}%  "
          f"holding a median {hi['conc_med']:.0f} of 188 = {100*hi['conc_med']/188:.1f}% of the universe")
    print(f"   gap to benchmark: CAGR {hi['cagr']-EW['cagr']:+.2f} pts   "
          f"maxDD {hi['max_dd']-EW['max_dd']:+.2f} pts")
    beat = R[R["cagr"] > EW["cagr"]]["N"].tolist()
    print(f"   N beating EW on CAGR: {beat if beat else 'NONE'}")


if __name__ == "__main__":
    main()

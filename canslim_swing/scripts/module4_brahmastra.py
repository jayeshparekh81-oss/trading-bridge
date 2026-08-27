#!/usr/bin/env python3
"""MODULE 4 — BRAHMASTRA GEAR TRAIL. PRE-REGISTERED. LAST RUN ON THIS WINDOW.

Research only. This does NOT touch the production Brahmastra trail; it is a
rescaled, daily-close reimplementation inside canslim_swing for a backtest.

BASE = Module 2 config A, unchanged. EMA220 leg and -15% stop both stay ACTIVE.
The gear trail is added ON TOP and can only ever exit EARLIER than the base.

  peak            = highest CLOSE since entry
  max_profit_pct  = peak / entry_fill - 1
  gear 1 : max_profit < G2 trigger              -> no trail, base rules only
  gear 2 : max_profit >= G2 trigger             -> exit if close <= peak*(1-G2 trail)
  gear 3 : max_profit >= G3 trigger             -> exit if close <= peak*(1-G3 trail)
  gear 3 supersedes gear 2; gears never step back down (peak is monotone, so
  the gear derived from it is monotone by construction).
  Evaluated on the CLOSE, executed at the NEXT session's OPEN. No intraday trail.

DECLARED RESCALE (shape held fixed, one scale factor, two values):
  10x : G2 +25% / trail 15%   G3 +45% / trail 4%
  20x : G2 +50% / trail 30%   G3 +90% / trail 8%

DECLARED ATTRIBUTION: when a base leg and a gear fire on the same close, the
exit is attributed to the BASE leg. So a gear count means "the gear exited
earlier than the base would have" — the only reading that answers the question.

DECLARED LIMITS (written before the run):
  1. Original gears are 15-minute intraday futures parameters. At a 133-session
     median hold they are meaningless unrescaled. The rescale above is declared,
     not chosen after seeing results.
  2. The original exits INTRABAR. This panel is daily-close only, so this is a
     WEAKENED version of the mechanism. A negative result here does NOT mean the
     original does not work.

DECLARED: nothing here validates any configuration. Last historical run.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK / "scripts"))
import module2_backtest as M2  # noqa: E402

OUT = TRACK / "data" / "m4"
EW_BENCH = {"cagr": 18.70, "max_dd": -35.50}
TRACE = ["BLUESTARCO", "TVSMOTOR", "CUMMINSIND", "DIXON", "CDSL"]

VARIANTS = {
    "CONTROL": None,
    "SCALE-10x": {"g2_trig": 0.25, "g2_trail": 0.15, "g3_trig": 0.45, "g3_trail": 0.04},
    "SCALE-20x": {"g2_trig": 0.50, "g2_trail": 0.30, "g3_trig": 0.90, "g3_trail": 0.08},
}


def simulate_gear(M, sig, dates, syms, gear):
    """Byte-identical to M2.simulate when gear is None; gear logic added on top."""
    o, c, lo = M["open"].to_numpy(), M["close"].to_numpy(), M["low"].to_numpy()
    ema, r126 = M["ema220"].to_numpy(), M["ret126"].to_numpy()
    cmark = M["close"].ffill().to_numpy()
    nd, ns = c.shape

    cash = M2.START_EQUITY
    pos, pending_exit = {}, {}
    trades, eq_curve = [], np.empty(nd)
    skip_slot = skip_cash = 0
    open_counts, deployed = [], []

    def close_trade(p, col, d, fill, reason, at_end=False):
        gross = p["shares"] * fill
        net_out = gross - M2.sell_costs(gross)
        pnl = net_out - p["cost_in"]
        return {"symbol": syms[col], "entry_date": dates[p["i"]], "exit_date": dates[d],
                "entry_px": p["fill"], "exit_px": fill, "shares": p["shares"],
                "notional": p["notional"], "cost_in": p["cost_in"], "proceeds": net_out,
                "pnl": pnl, "r_multiple": pnl / (M2.STOP_FRAC * p["notional"]),
                "ret_pct": 100 * (fill / p["fill"] - 1),
                "days_held": int((dates[d] - dates[p["i"]]).days),
                "sessions_held": d - p["i"], "exit_reason": reason,
                "touched_15_intraday": p["touched"], "open_at_end": at_end,
                "max_gear": p["gear"], "max_profit_pct": 100 * p["maxp"]}, net_out

    for d in range(nd):
        for col in list(pending_exit):
            if col not in pos:
                pending_exit.pop(col, None)
                continue
            px = o[d, col]
            if not np.isfinite(px):
                continue
            p = pos.pop(col)
            reason = pending_exit.pop(col)
            fill = px * (1 - M2.SLIP)
            rec, net_out = close_trade(p, col, d, fill, reason)
            cash += net_out
            trades.append(rec)

        if d > 0:
            cand = np.flatnonzero(sig[d - 1])
            if cand.size:
                eq_prev = cash + sum(pp["shares"] * cmark[d - 1, k] for k, pp in pos.items())
                budget = M2.MAX_POS_PCT * eq_prev
                rank = r126[d - 1, cand]
                cand = cand[np.argsort(-np.where(np.isfinite(rank), rank, -np.inf))]
                for col in cand:
                    if col in pos:
                        continue
                    px = o[d, col]
                    if not np.isfinite(px):
                        continue
                    if len(pos) >= M2.MAX_POSITIONS:
                        skip_slot += 1
                        continue
                    fill = px * (1 + M2.SLIP)
                    sh = int(budget // fill)
                    if sh <= 0:
                        skip_cash += 1
                        continue
                    notional = sh * fill
                    cost_in = notional + M2.buy_costs(notional)
                    if cost_in > cash:
                        skip_cash += 1
                        continue
                    cash -= cost_in
                    pos[col] = {"shares": sh, "fill": fill, "notional": notional,
                                "cost_in": cost_in, "i": d, "touched": False,
                                "peak": -np.inf, "maxp": -np.inf, "gear": 1}

        mtm = sum(p["shares"] * cmark[d, k] for k, p in pos.items())
        eq_curve[d] = cash + mtm
        open_counts.append(len(pos))
        deployed.append(0.0 if eq_curve[d] <= 0 else 100 * mtm / eq_curve[d])

        for col, p in pos.items():
            if np.isfinite(lo[d, col]) and lo[d, col] <= 0.85 * p["fill"]:
                p["touched"] = True
            cl = c[d, col]
            if not np.isfinite(cl):
                continue
            # peak / gear state advance on every valid close, exit pending or not
            if cl > p["peak"]:
                p["peak"] = cl
                p["maxp"] = cl / p["fill"] - 1
            if gear is not None:
                if p["maxp"] >= gear["g3_trig"]:
                    p["gear"] = 3
                elif p["maxp"] >= gear["g2_trig"] and p["gear"] < 2:
                    p["gear"] = 2
            if col in pending_exit:
                continue
            # BASE legs first — a gear may never loosen or delay a base exit
            if cl <= 0.85 * p["fill"]:
                pending_exit[col] = "stop_15pct"
            elif np.isfinite(ema[d, col]) and cl < ema[d, col]:
                pending_exit[col] = "ema220"
            elif gear is not None and p["gear"] == 3:
                if cl <= p["peak"] * (1 - gear["g3_trail"]):
                    pending_exit[col] = "gear3_trail"
            elif gear is not None and p["gear"] == 2:
                if cl <= p["peak"] * (1 - gear["g2_trail"]):
                    pending_exit[col] = "gear2_trail"

    for col, p in pos.items():
        fill = cmark[-1, col] * (1 - M2.SLIP)
        rec, _ = close_trade(p, col, nd - 1, fill, "open_at_end", at_end=True)
        trades.append(rec)

    T = pd.DataFrame(trades).sort_values("exit_date").reset_index(drop=True)
    return {"trades": T, "equity": pd.Series(eq_curve, index=dates),
            "skip_slot": skip_slot, "skip_cash": skip_cash,
            "avg_open": float(np.mean(open_counts)), "avg_deployed": float(np.mean(deployed))}


def costs_of(T):
    buy_e = T["cost_in"] - T["notional"]
    sell_e = T["shares"] * T["exit_px"] - T["proceeds"]
    s = M2.SLIP
    return float(buy_e.sum() + sell_e.sum()
                 + (T["shares"] * T["entry_px"] * (s / (1 + s))).sum()
                 + (T["shares"] * T["exit_px"] * (s / (1 - s))).sum())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    M, sigA, _, dates, syms = M2.load()
    res, rows = {}, []
    for name, gear in VARIANTS.items():
        r = simulate_gear(M, sigA, dates, syms, gear)
        m = M2.metrics(r)
        nl = M2.null_dist(M, sigA, dates, r["trades"])
        p = float((nl >= m["exp_r"]).mean())
        T, cl = r["trades"], r["trades"][~r["trades"]["open_at_end"]]
        q = cl["sessions_held"].quantile([.25, .5, .75])
        vc = T["exit_reason"].value_counts()
        rows.append({"variant": name, "trades": m["trades_closed"], "win_rate": m["win_rate"],
                     "exp_rs": m["exp_rs"], "exp_r": m["exp_r"], "pf": m["profit_factor"],
                     "cagr": m["cagr"], "max_dd": m["max_dd"], "longest_dd": m["longest_dd_days"],
                     "final_equity": m["final_equity"], "hold_med": q[.5], "hold_q1": q[.25],
                     "hold_q3": q[.75], "p": p, "costs": costs_of(T),
                     "cost_pct": 100 * costs_of(T) / m["final_equity"],
                     "ex_ema": int(vc.get("ema220", 0)), "ex_stop": int(vc.get("stop_15pct", 0)),
                     "ex_g2": int(vc.get("gear2_trail", 0)), "ex_g3": int(vc.get("gear3_trail", 0)),
                     "ex_open": int(vc.get("open_at_end", 0)), "total": len(T),
                     "reached_g2": int((T["max_gear"] >= 2).sum()),
                     "reached_g3": int((T["max_gear"] >= 3).sum())})
        res[name] = (r, m, p)
        T.to_parquet(OUT / f"module4_trades_{name}.parquet", index=False)
        r["equity"].to_frame("equity").to_parquet(OUT / f"module4_equity_{name}.parquet")
    R = pd.DataFrame(rows)
    R.to_parquet(OUT / "module4_summary.parquet", index=False)

    # ---- CONTROL correctness check
    a = pd.read_parquet(TRACK / "data" / "m2" / "module2_trades_A.parquet")
    b = res["CONTROL"][0]["trades"]
    cols = [c for c in a.columns if c in b.columns]
    ident = a[cols].reset_index(drop=True).equals(b[cols].reset_index(drop=True))
    ea = pd.read_parquet(TRACK / "data" / "m2" / "module2_equity_A.parquet")["equity"]
    print("=" * 78)
    print("CONTROL CORRECTNESS CHECK vs Module 2 config A")
    print("=" * 78)
    print(f"  rows {len(a)} vs {len(b)}   ledger equals: {ident}")
    print(f"  equity curve identical: {ea.equals(res['CONTROL'][0]['equity'])}   "
          f"max abs diff {float((ea - res['CONTROL'][0]['equity']).abs().max()):.6f}")
    print(f"  (gear columns max_gear / max_profit_pct are ADDITIONS; compared on the "
          f"{len(cols)} shared columns)")

    print()
    print("=" * 78)
    print("1-6. SIDE BY SIDE")
    print("=" * 78)
    for _, r in R.iterrows():
        print(f"\n--- {r['variant']} ---")
        g = [("expectancy > 0", r["exp_rs"] > 0, f"Rs {r['exp_rs']:,.0f}"),
             ("profit factor >= 1.3", r["pf"] >= 1.3, f"{r['pf']:.3f}"),
             ("max drawdown <= 15%", r["max_dd"] >= -15.0, f"{r['max_dd']:.2f}%"),
             ("trades >= 60", r["trades"] >= 60, f"{int(r['trades'])}"),
             ("beats null p<0.05", r["p"] < 0.05, f"p={r['p']:.4f}")]
        print("  1. GATES: " + "  ".join(f"[{'P' if ok else 'F'}]{nm}={v}" for nm, ok, v in g))
        print(f"     OVERALL {'PASS' if all(x[1] for x in g) else 'FAIL'}")
        print(f"  2. trades {int(r['trades'])}  win {r['win_rate']:.2f}%  "
              f"exp Rs {r['exp_rs']:,.0f} = {r['exp_r']:+.3f}R  PF {r['pf']:.3f}  "
              f"CAGR {r['cagr']:.2f}%  maxDD {r['max_dd']:.2f}%  "
              f"longestDD {int(r['longest_dd'])}d  final Rs {r['final_equity']:,.0f}")
        print(f"  3. hold median {r['hold_med']:.0f}  IQR {r['hold_q1']:.0f}..{r['hold_q3']:.0f}")
        print(f"  4. exits: ema220 {r['ex_ema']}  stop15 {r['ex_stop']}  "
              f"gear2 {r['ex_g2']}  gear3 {r['ex_g3']}  open {r['ex_open']}  (of {r['total']})")
        print(f"  5. costs Rs {r['costs']:,.0f} = {r['cost_pct']:.2f}% of final equity")
        print(f"  6. trades ever reaching gear2 {r['reached_g2']} / {r['total']}   "
              f"gear3 {r['reached_g3']} / {r['total']}")

    print()
    print("=" * 78)
    print("7. THE FIVE TRADES THAT CARRY CONFIG A")
    print("=" * 78)
    for sym in TRACE:
        print(f"\n  {sym}")
        for name in VARIANTS:
            T = res[name][0]["trades"]
            sub = T[T["symbol"] == sym]
            if not len(sub):
                print(f"    {name:<10} — no trade taken")
                continue
            for _, t in sub.iterrows():
                print(f"    {name:<10} {t['entry_date'].date()} -> {t['exit_date'].date()}  "
                      f"{t['exit_reason']:<12} {t['ret_pct']:+8.1f}%  Rs {t['pnl']:>10,.0f}  "
                      f"[peak +{t['max_profit_pct']:.0f}%, gear {int(t['max_gear'])}]")

    print()
    print("=" * 78)
    print("8/9. SHAPE + BENCHMARK")
    print("=" * 78)
    tab = R[["variant", "exp_r", "pf", "max_dd", "cagr", "hold_med", "trades", "costs"]]
    print(tab.round(3).to_string(index=False))
    print(f"\n  Universe EW buy & hold : CAGR {EW_BENCH['cagr']:.2f}%   maxDD {EW_BENCH['max_dd']:.2f}%")
    beat = R[R["cagr"] > EW_BENCH["cagr"]]["variant"].tolist()
    print(f"  variants beating EW on CAGR: {beat if beat else 'NONE'}")
    ctrl = R[R["variant"] == "CONTROL"].iloc[0]
    print()
    for col, lbl in (("exp_r", "expectancy R"), ("cagr", "CAGR"), ("pf", "profit factor"),
                     ("max_dd", "max drawdown")):
        d10 = R[R["variant"] == "SCALE-10x"].iloc[0][col] - ctrl[col]
        d20 = R[R["variant"] == "SCALE-20x"].iloc[0][col] - ctrl[col]
        same = (d10 > 0 and d20 > 0) or (d10 < 0 and d20 < 0) or (d10 == 0 and d20 == 0)
        print(f"  {lbl:<16} vs control: 10x {d10:+.3f}   20x {d20:+.3f}   "
              f"-> {'SAME DIRECTION' if same else 'OPPOSITE / NOISE'}")
    print()
    for n in VARIANTS:
        print(f"ledger {n}: {OUT / f'module4_trades_{n}.parquet'}")


if __name__ == "__main__":
    main()

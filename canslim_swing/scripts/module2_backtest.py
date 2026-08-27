#!/usr/bin/env python3
"""MODULE 2 — trade engine + portfolio simulation. PRE-REGISTERED, ONE SHOT.

Two configs only, both reported whatever the outcome:
  CONFIG A — spec as written, F5 included
  CONFIG B — identical, F5 removed

No tuning, no variants, no added rules. Costs reuse the M5 model verbatim.

DECLARED EXECUTION CHOICES (stated, not searched):
  * Signal on close of day t -> fill at OPEN of day t+1.
  * Both exit legs evaluated on the CLOSE, executed at the NEXT session's OPEN
    (mirrors the entry treatment; no intraday stop).
  * "entry price" for the -15% leg = the actual FILL price incl. slippage.
  * Within a session, exits are processed BEFORE entries, so a freed slot and
    its cash are available to a same-day entry.
  * Position budget = 10% of CURRENT equity, equity marked at the PREVIOUS
    session's close. Shares = floor(budget / fill). Costs are paid on top of
    the budget out of cash.
  * If cash cannot cover shares*fill + buy costs, the signal is SKIPPED (no
    partial sizing), and recorded as a cash skip.
  * R = the registered stop distance = 0.15 * entry notional. R-multiple =
    net P&L / (0.15 * shares * fill).
  * Equity marking uses forward-filled closes so a symbol's data gap cannot
    blank the curve.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
OUT = TRACK / "data" / "m2"
PANEL = TRACK / "data" / "panel_v2" / "module1_panel.parquet"

# ---- cost model, copied verbatim from scripts/m5_engine.py -------------------
STT, EXCH_TXN, SEBI_FEE, STAMP_BUY = 0.0010, 0.0000297, 0.000001, 0.00015
GST_RATE, BROKERAGE, DP_SELL = 0.18, 0.0, 15.93


def buy_costs(t: float) -> float:
    e, s = t * EXCH_TXN, t * SEBI_FEE
    return t * STT + e + s + t * STAMP_BUY + GST_RATE * (BROKERAGE + e + s) + BROKERAGE


def sell_costs(t: float) -> float:
    e, s = t * EXCH_TXN, t * SEBI_FEE
    return t * STT + e + s + GST_RATE * (BROKERAGE + e + s) + BROKERAGE + DP_SELL


START_EQUITY = 1_000_000.0
MAX_POSITIONS = 10
MAX_POS_PCT = 0.10
SLIP = 0.0005          # ASSUMPTION: 0.05% per side
STOP_FRAC = 0.15


def load():
    P = pd.read_parquet(PANEL)
    P["date"] = pd.to_datetime(P["date"])
    piv = lambda c: P.pivot(index="date", columns="symbol", values=c).sort_index()
    M = {c: piv(c) for c in ["open", "high", "low", "close", "ema220", "ret126"]}
    sigA = P.assign(v=P["signal"]).pivot(index="date", columns="symbol", values="v").sort_index()
    B = P["eligible"] & P[["F1", "F2", "F3", "F4", "BRK"]].all(axis=1)
    sigB = P.assign(v=B).pivot(index="date", columns="symbol", values="v").sort_index()
    return M, sigA.fillna(False).to_numpy(bool), sigB.fillna(False).to_numpy(bool), sigA.index, sigA.columns


def simulate(M, sig, dates, syms, tag):
    o, c, lo = M["open"].to_numpy(), M["close"].to_numpy(), M["low"].to_numpy()
    ema, r126 = M["ema220"].to_numpy(), M["ret126"].to_numpy()
    cmark = M["close"].ffill().to_numpy()
    nd, ns = c.shape

    cash = START_EQUITY
    pos = {}                       # col -> dict
    pending_exit = {}              # col -> reason
    trades, eq_curve = [], np.empty(nd)
    skip_slot = skip_cash = 0
    open_counts, deployed = [], []

    for d in range(nd):
        # ---------- 1. exits flagged at d-1 close, filled at d open
        for col in list(pending_exit):
            if col not in pos:
                pending_exit.pop(col, None)
                continue
            px = o[d, col]
            if not np.isfinite(px):
                continue                                   # symbol has no session; defer
            p = pos.pop(col)
            reason = pending_exit.pop(col)
            fill = px * (1 - SLIP)
            gross = p["shares"] * fill
            net_out = gross - sell_costs(gross)
            cash += net_out
            pnl = net_out - p["cost_in"]
            trades.append({"symbol": syms[col], "entry_date": dates[p["i"]],
                           "exit_date": dates[d], "entry_px": p["fill"], "exit_px": fill,
                           "shares": p["shares"], "notional": p["notional"],
                           "cost_in": p["cost_in"], "proceeds": net_out, "pnl": pnl,
                           "r_multiple": pnl / (STOP_FRAC * p["notional"]),
                           "ret_pct": 100 * (fill / p["fill"] - 1),
                           "days_held": int((dates[d] - dates[p["i"]]).days),
                           "sessions_held": d - p["i"], "exit_reason": reason,
                           "touched_15_intraday": p["touched"], "open_at_end": False})

        # ---------- 2. entries signalled at d-1 close, filled at d open
        if d > 0:
            cand = np.flatnonzero(sig[d - 1])
            if cand.size:
                eq_prev = cash + sum(pp["shares"] * cmark[d - 1, k] for k, pp in pos.items())
                budget = MAX_POS_PCT * eq_prev
                rank = r126[d - 1, cand]
                cand = cand[np.argsort(-np.where(np.isfinite(rank), rank, -np.inf))]
                for col in cand:
                    if col in pos:
                        continue
                    px = o[d, col]
                    if not np.isfinite(px):
                        continue
                    if len(pos) >= MAX_POSITIONS:
                        skip_slot += 1
                        continue
                    fill = px * (1 + SLIP)
                    sh = int(budget // fill)
                    if sh <= 0:
                        skip_cash += 1
                        continue
                    notional = sh * fill
                    cost_in = notional + buy_costs(notional)
                    if cost_in > cash:
                        skip_cash += 1
                        continue
                    cash -= cost_in
                    pos[col] = {"shares": sh, "fill": fill, "notional": notional,
                                "cost_in": cost_in, "i": d, "touched": False}

        # ---------- 3. mark, then flag exits on today's close
        mtm = sum(p["shares"] * cmark[d, k] for k, p in pos.items())
        eq_curve[d] = cash + mtm
        open_counts.append(len(pos))
        deployed.append(0.0 if eq_curve[d] <= 0 else 100 * mtm / eq_curve[d])

        for col, p in pos.items():
            if np.isfinite(lo[d, col]) and lo[d, col] <= 0.85 * p["fill"]:
                p["touched"] = True
            cl = c[d, col]
            if not np.isfinite(cl) or col in pending_exit:
                continue
            if cl <= 0.85 * p["fill"]:
                pending_exit[col] = "stop_15pct"
            elif np.isfinite(ema[d, col]) and cl < ema[d, col]:
                pending_exit[col] = "ema220"

    # ---------- open at end, marked to market
    for col, p in pos.items():
        fill = cmark[-1, col] * (1 - SLIP)
        gross = p["shares"] * fill
        net_out = gross - sell_costs(gross)
        trades.append({"symbol": syms[col], "entry_date": dates[p["i"]], "exit_date": dates[-1],
                       "entry_px": p["fill"], "exit_px": fill, "shares": p["shares"],
                       "notional": p["notional"], "cost_in": p["cost_in"], "proceeds": net_out,
                       "pnl": net_out - p["cost_in"],
                       "r_multiple": (net_out - p["cost_in"]) / (STOP_FRAC * p["notional"]),
                       "ret_pct": 100 * (fill / p["fill"] - 1),
                       "days_held": int((dates[-1] - dates[p["i"]]).days),
                       "sessions_held": nd - 1 - p["i"], "exit_reason": "open_at_end",
                       "touched_15_intraday": p["touched"], "open_at_end": True})

    T = pd.DataFrame(trades).sort_values("exit_date").reset_index(drop=True)
    eq = pd.Series(eq_curve, index=dates)
    return {"tag": tag, "trades": T, "equity": eq, "skip_slot": skip_slot,
            "skip_cash": skip_cash, "avg_open": float(np.mean(open_counts)),
            "avg_deployed": float(np.mean(deployed))}


def drawdown(eq: pd.Series):
    peak = eq.cummax()
    dd = eq / peak - 1
    mdd = float(dd.min())
    # longest peak-to-recovery stretch, in calendar days
    longest, start = 0, None
    for t, v in dd.items():
        if v == 0:
            if start is not None:
                longest = max(longest, (t - start).days)
            start = t
        elif start is None:
            start = t
    if start is not None:
        longest = max(longest, (dd.index[-1] - start).days)
    return mdd, longest


def metrics(res):
    T, eq = res["trades"], res["equity"]
    cl = T[~T["open_at_end"]]
    w = cl[cl["pnl"] > 0]
    gp, gl = w["pnl"].sum(), -cl.loc[cl["pnl"] <= 0, "pnl"].sum()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    mdd, longest = drawdown(eq)
    return {"trades_closed": len(cl), "trades_total": len(T),
            "win_rate": 100 * len(w) / len(cl) if len(cl) else np.nan,
            "exp_rs": cl["pnl"].mean() if len(cl) else np.nan,
            "exp_r": cl["r_multiple"].mean() if len(cl) else np.nan,
            "profit_factor": gp / gl if gl > 0 else np.inf,
            "final_equity": float(eq.iloc[-1]),
            "cagr": 100 * ((eq.iloc[-1] / START_EQUITY) ** (1 / yrs) - 1),
            "max_dd": 100 * mdd, "longest_dd_days": longest}


def null_dist(M, sig, dates, T, n_iter=500, seed=20260816):
    """Random-entry null. Design reused from scripts/m5_select_nulls.py:
    same trade count, same holding-period distribution, random symbol/date over
    eligible non-signal days, identical slippage. Exit is at the OPEN after the
    sampled hold, to match THIS module's declared exit timing (m5 used the close).
    Scored on the same R basis (0.15 stop distance)."""
    rng = np.random.default_rng(seed)
    o = M["open"].to_numpy()
    elig = np.isfinite(M["ema220"].to_numpy()) & np.isfinite(o)
    pool = np.argwhere(elig & ~sig)
    holds = T.loc[~T["open_at_end"], "sessions_held"].to_numpy()
    holds = holds[holds > 0]
    n = int((~T["open_at_end"]).sum())
    nd = o.shape[0]
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
            entry, exitp = e * (1 + SLIP), x * (1 - SLIP)
            gross_in = entry
            gross_out = exitp - sell_costs(exitp)
            net = gross_out - (gross_in + buy_costs(gross_in))
            rs.append(net / (STOP_FRAC * gross_in))
        out[it] = float(np.mean(rs)) if rs else np.nan
    return out[np.isfinite(out)]


def report(res, m, nulls):
    T = res["trades"]
    cl = T[~T["open_at_end"]]
    print("=" * 78)
    print(f"CONFIG {res['tag']}")
    print("=" * 78)
    print("1. GATES")
    g = [("net expectancy > 0 after costs", m["exp_rs"] > 0, f"Rs {m['exp_rs']:,.0f}/trade"),
         ("profit factor >= 1.3", m["profit_factor"] >= 1.3, f"{m['profit_factor']:.3f}"),
         ("max drawdown <= 15%", m["max_dd"] >= -15.0, f"{m['max_dd']:.2f}%"),
         ("trades >= 60", m["trades_closed"] >= 60, f"{m['trades_closed']}")]
    p = float((nulls >= m["exp_r"]).mean())
    g.append((f"beats random-entry null at p < 0.05", p < 0.05, f"p = {p:.4f}"))
    for name, ok, val in g:
        print(f"   [{'PASS' if ok else 'FAIL'}]  {name:<38} {val}")
    print(f"   OVERALL: {'PASS' if all(x[1] for x in g) else 'FAIL'}"
          + ("   (UNDERPOWERED)" if m["trades_closed"] < 60 else ""))
    print()
    print("2. HEADLINE")
    for k in ["trades_closed", "trades_total", "win_rate", "exp_rs", "exp_r",
              "profit_factor", "cagr", "max_dd", "longest_dd_days", "final_equity"]:
        print(f"   {k:<18} {m[k]:,.3f}" if isinstance(m[k], float) else f"   {k:<18} {m[k]}")
    print()
    print("3. EXIT REASONS")
    vc = T["exit_reason"].value_counts()
    for k, v in vc.items():
        print(f"   {k:<14} {v:>5}  ({100*v/len(T):5.1f}%)")
    print()
    print("4. HOLDING PERIOD (sessions, closed trades)")
    if len(cl):
        q = cl["sessions_held"].quantile([.25, .5, .75])
        print(f"   median {q[.5]:.0f}   IQR {q[.25]:.0f}..{q[.75]:.0f}   "
              f"min {cl['sessions_held'].min()}   max {cl['sessions_held'].max()}")
    print()
    print("5. DEPLOYMENT")
    print(f"   avg open positions {res['avg_open']:.2f} of {MAX_POSITIONS}   "
          f"avg equity deployed {res['avg_deployed']:.1f}%   "
          f"avg cash drag {100-res['avg_deployed']:.1f}%")
    print()
    print("6. PER YEAR")
    eq = res["equity"]
    yr = pd.DataFrame({"trades": cl.groupby(cl["exit_date"].dt.year).size(),
                       "net_pnl": cl.groupby(cl["exit_date"].dt.year)["pnl"].sum(),
                       "year_end_equity": eq.groupby(eq.index.year).last()}).fillna(0)
    print(yr.round(0).to_string())
    print()
    print("7. SKIPPED SIGNALS")
    print(f"   no free slot: {res['skip_slot']:,}    insufficient cash: {res['skip_cash']:,}")
    print()
    print("8. EXTREMES")
    cols = ["symbol", "entry_date", "exit_date", "pnl", "ret_pct", "exit_reason"]
    f = lambda d: d[cols].assign(entry_date=lambda x: x["entry_date"].dt.date,
                                 exit_date=lambda x: x["exit_date"].dt.date,
                                 pnl=lambda x: x["pnl"].round(0),
                                 ret_pct=lambda x: x["ret_pct"].round(1))
    print("   10 largest winners:"); print(f(cl.nlargest(10, "pnl")).to_string(index=False))
    print("\n   10 largest losers:"); print(f(cl.nsmallest(10, "pnl")).to_string(index=False))
    print()
    return g, p


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    M, sigA, sigB, dates, syms = load()
    print(f"panel {len(dates)} sessions {dates.min().date()} -> {dates.max().date()}, "
          f"{len(syms)} symbols")
    print(f"config A signals {int(sigA.sum()):,}   config B signals {int(sigB.sum()):,}\n")

    out = {}
    for tag, sg in (("A", sigA), ("B", sigB)):
        res = simulate(M, sg, dates, syms, tag)
        m = metrics(res)
        nl = null_dist(M, sg, dates, res["trades"])
        g, p = report(res, m, nl)
        path = OUT / f"module2_trades_{tag}.parquet"
        res["trades"].to_parquet(path, index=False)
        res["equity"].to_frame("equity").to_parquet(OUT / f"module2_equity_{tag}.parquet")
        out[tag] = {"res": res, "m": m, "null": nl, "p": p, "gates": g, "path": path}

    print("=" * 78)
    print("9. SIDE BY SIDE")
    print("=" * 78)
    rows = []
    for k in ["trades_closed", "win_rate", "exp_rs", "exp_r", "profit_factor",
              "cagr", "max_dd", "longest_dd_days", "final_equity"]:
        rows.append({"metric": k, "A": out["A"]["m"][k], "B": out["B"]["m"][k]})
    rows.append({"metric": "null_p_value", "A": out["A"]["p"], "B": out["B"]["p"]})
    rows.append({"metric": "gates_passed", "A": sum(x[1] for x in out["A"]["gates"]),
                 "B": sum(x[1] for x in out["B"]["gates"])})
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print()
    print("=" * 78)
    print("10. DIAGNOSTIC ONLY — trades that touched -15% INTRADAY before closing below it")
    print("=" * 78)
    for tag in ("A", "B"):
        T = out[tag]["res"]["trades"]
        never_closed = T[T["exit_reason"] != "stop_15pct"]
        n = int(never_closed["touched_15_intraday"].sum())
        print(f"   config {tag}: {n} of {len(T)} trades ({100*n/len(T):.1f}%) touched -15% "
              f"intraday without ever closing below it")
    print()
    print("=" * 78)
    print("11. RANDOM-ENTRY NULL — the regime thermometer")
    print("=" * 78)
    for tag in ("A", "B"):
        nl = out[tag]["null"]
        print(f"   config {tag} null: mean expectancy {nl.mean():+.4f} R   "
              f"sd {nl.std():.4f}   iters {len(nl)}   "
              f"[strategy {out[tag]['m']['exp_r']:+.4f} R, p={out[tag]['p']:.4f}]")
    print()
    for tag in ("A", "B"):
        print(f"ledger {tag}: {out[tag]['path']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""1% CLUB — Module 2 report writer. Regenerates the report text from the STORED
ledgers; does NOT re-run either config.

Everything derivable is read from data/m2/module2_trades_*.parquet and
module2_equity_*.parquet. Four per-config counters and the null statistics are
not stored in those ledgers, so they are carried here as explicitly-labelled
constants TRANSCRIBED FROM THE REGISTERED RUN. They are not recomputed and not
adjusted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK / "scripts"))
from module2_backtest import drawdown, START_EQUITY, MAX_POSITIONS  # noqa: E402
import club1pct_benchmarks as BM  # noqa: E402

M2 = TRACK / "data" / "m2"
REPORT = TRACK / "reports" / "club1pct_module2_backtest.txt"

# --- transcribed from the registered Module 2 run; NOT recomputed here --------
RECORDED = {
    "A": {"skip_slot": 68, "skip_cash": 4377, "avg_open": 6.93, "avg_deployed": 79.6,
          "null_mean": 0.4396, "null_median": 0.2672, "null_p95": 0.9079,
          "null_p99": 7.4639, "null_skew": 5.74, "p": 0.0480,
          "cash_block_sessions": 1361, "cash_block_median_cash_pct": 4.2},
    "B": {"skip_slot": 100, "skip_cash": 13965, "avg_open": 7.29, "avg_deployed": 82.3,
          "null_mean": 0.5101, "null_median": 0.3153, "null_p95": 1.0692,
          "null_p99": 8.4253, "null_skew": 6.52, "p": 0.0360,
          "cash_block_sessions": 1941, "cash_block_median_cash_pct": 3.9},
}
GATES = {"expectancy": "> 0 after costs", "pf": ">= 1.3", "dd": "<= 15%",
         "trades": ">= 60", "null": "p < 0.05"}

L = []
def A(s=""): L.append(s)


def cfg_metrics(tag):
    T = pd.read_parquet(M2 / f"module2_trades_{tag}.parquet")
    eq = pd.read_parquet(M2 / f"module2_equity_{tag}.parquet")["equity"]
    cl = T[~T["open_at_end"]]
    w = cl[cl["pnl"] > 0]
    gp, gl = w["pnl"].sum(), -cl.loc[cl["pnl"] <= 0, "pnl"].sum()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    mdd, longest = drawdown(eq)
    return T, cl, eq, {
        "trades_closed": len(cl), "trades_total": len(T),
        "win_rate": 100 * len(w) / len(cl), "exp_rs": cl["pnl"].mean(),
        "exp_r": cl["r_multiple"].mean(), "profit_factor": gp / gl,
        "cagr": 100 * ((eq.iloc[-1] / START_EQUITY) ** (1 / yrs) - 1),
        "max_dd": 100 * mdd, "longest_dd_days": longest, "final_equity": float(eq.iloc[-1])}


def main():
    A("=" * 78)
    A('1% CLUB 52-WEEK-HIGH BREAKOUT — MODULE 2: TRADE ENGINE + PORTFOLIO SIM')
    A("=" * 78)
    A()
    A("  Pre-registered, one shot. Two configs, both reported. No tuning, no")
    A("  variants, no rules added, nothing re-run with different parameters.")
    A("  Generated from the stored ledgers by scripts/club1pct_report.py.")
    A("  Engine: scripts/module2_backtest.py   Panel: data/panel_v2/")
    A()
    A("  >>> CORRECTION STAMP, added after an adversarial audit <<<")
    A("  The gate-5 'beats random-entry null' rows below record what the ORIGINAL")
    A("  run produced and are preserved as the historical record. They are WRONG.")
    A("  The null charged the flat Rs 15.93 DP sell fee against a one-share")
    A("  notional, handicapping it by 0.7053 R per trade. With the null fixed")
    A("  (scripts/club1pct_null_fix.py), config A's null mean is +1.2648 R not")
    A("  +0.4396 R, and gate 5 is FAIL for config A (p 0.484) and config B")
    A("  (p 0.204). Section 11's reading -- 'roughly twice the random mean' --")
    A("  is WITHDRAWN: the strategy has NO measurable edge over the corrected")
    A("  null. This makes the verdict WORSE, never better. Corrected figures in")
    A("  data/m2/null_corrected.parquet; full account in reports/club1pct_PARKED.txt.")
    A()
    A("  VERDICT: FAIL for BOTH configs, on the max-drawdown gate.")
    A("  The gate stands as registered. No gate has been re-derived from these")
    A("  results; if one is ever re-set it will be pre-registered for a")
    A("  different spec, before that spec is run.")
    A()
    A("-" * 78)
    A("REGISTERED SPEC")
    A("-" * 78)
    A("  ENTRY (all true on the close; fill at the NEXT session's OPEN)")
    A("    F1  SMA150 > EMA220")
    A("    F2  close > SMA50")
    A("    F3  SMA50 > SMA150")
    A("    F4  close > 1.25 * 52-week low (min of LOW over prior 252 sessions)")
    A("    F5  >=1 session in the last 90 where LOW < EMA220")
    A("    BRK close > max CLOSE of the prior 252 sessions, excluding today")
    A("    No second entry into a symbol already held.")
    A("  CONFIG A = the above.   CONFIG B = identical with F5 REMOVED.")
    A("    B was registered in advance, before any result existed, because the")
    A("    Module 1 census showed F5 destroying 67% of signals.")
    A()
    A("  EXIT (two legs, whichever first; both evaluated on the CLOSE and")
    A("        executed at the NEXT session's OPEN — no intraday stop)")
    A("    Leg 1  close < EMA220")
    A("    Leg 2  close <= 0.85 * entry fill price")
    A("    Positions still open on the last panel date are marked to market and")
    A("    reported separately from closed trades.")
    A()
    A("  PORTFOLIO   Rs 10,00,000 start; 10 slots; max 10% of CURRENT equity per")
    A("              stock; whole shares, rounded down; compounding. Excess")
    A("              signals ranked by 6-month return, highest first. Cash")
    A("              short -> signal skipped and recorded (no partial sizing).")
    A("  R           = the registered stop distance = 0.15 * entry notional.")
    A()
    A("  DECLARED EXECUTION CHOICES (stated, not searched)")
    A("    - exits processed before entries within a session, so a freed slot")
    A("      and its cash are available same-day")
    A("    - position budget = 10% of equity marked at the PREVIOUS close;")
    A("      costs paid on top of the budget, out of cash")
    A("    - equity marking uses forward-filled closes, so a symbol's data gap")
    A("      cannot blank the curve")
    A()
    A("-" * 78)
    A("COST MODEL — copied verbatim from scripts/m5_engine.py")
    A("-" * 78)
    A("    brokerage                    Rs 0        (zero-brokerage delivery)")
    A("    STT                          0.100%      both sides")
    A("    exchange transaction charge  0.00297%    both sides")
    A("    SEBI fee                     0.0001%     both sides")
    A("    stamp duty                   0.015%      BUY side only")
    A("    GST                          18% on (brokerage + exchange + SEBI)")
    A("    DP charge                    Rs 15.93    SELL side only, flat")
    A("    slippage                     0.05% per side  <-- AN ASSUMPTION,")
    A("                                 not a measured value")
    A()

    out = {}
    for tag in ("A", "B"):
        T, cl, eq, m = cfg_metrics(tag)
        rec = RECORDED[tag]
        out[tag] = (T, cl, eq, m, rec)
        label = "A — spec as written (F5 IN)" if tag == "A" else "B — F5 REMOVED"
        A("=" * 78)
        A(f"CONFIG {label}")
        A("=" * 78)
        gl = [("net expectancy " + GATES["expectancy"], m["exp_rs"] > 0, f"Rs {m['exp_rs']:,.0f}/trade"),
              ("profit factor " + GATES["pf"], m["profit_factor"] >= 1.3, f"{m['profit_factor']:.3f}"),
              ("max drawdown " + GATES["dd"], m["max_dd"] >= -15.0, f"{m['max_dd']:.2f}%"),
              ("trades " + GATES["trades"], m["trades_closed"] >= 60, f"{m['trades_closed']}"),
              ("beats random-entry null, " + GATES["null"], rec["p"] < 0.05, f"p = {rec['p']:.4f}")]
        A("1. GATES")
        for nm, ok, v in gl:
            A(f"     [{'PASS' if ok else 'FAIL'}]  {nm:<40} {v}")
        A(f"     OVERALL: {'PASS' if all(x[1] for x in gl) else 'FAIL'}")
        A()
        A("2. HEADLINE")
        A(f"     closed trades {m['trades_closed']}  (total incl. open-at-end {m['trades_total']})")
        A(f"     win rate      {m['win_rate']:.2f}%")
        A(f"     expectancy    Rs {m['exp_rs']:,.0f} per trade   =  {m['exp_r']:+.3f} R")
        A(f"     profit factor {m['profit_factor']:.3f}")
        A(f"     CAGR          {m['cagr']:.2f}%")
        A(f"     max drawdown  {m['max_dd']:.2f}%   longest {m['longest_dd_days']} days")
        A(f"     final equity  Rs {m['final_equity']:,.0f}  from Rs {START_EQUITY:,.0f}")
        A()
        A("3. EXIT REASON BREAKDOWN")
        for k, v in T["exit_reason"].value_counts().items():
            A(f"     {k:<14} {v:>5}   ({100*v/len(T):5.1f}%)")
        A("     PRE-RUN PREDICTION (made before the run): the EMA220 leg would")
        A("     almost never fire first, because entries sit a median 22% above")
        A("     the EMA220.  RESULT: FALSIFIED. The EMA220 leg is the dominant")
        A("     exit. Over a median ~133-session hold the EMA220 rises to meet")
        A("     the price, so the 22% gap closes from below; the stop leg only")
        A("     wins the race when a position collapses quickly.")
        A()
        q = cl["sessions_held"].quantile([.25, .5, .75])
        A("4. HOLDING PERIOD (sessions, closed trades)")
        A(f"     median {q[.5]:.0f}   IQR {q[.25]:.0f}..{q[.75]:.0f}   "
          f"min {cl['sessions_held'].min()}   max {cl['sessions_held'].max()}")
        A()
        A("5. DEPLOYMENT AND CASH DRAG   [counters transcribed from the run]")
        A(f"     avg open positions   {rec['avg_open']:.2f} of {MAX_POSITIONS}")
        A(f"     avg equity deployed  {rec['avg_deployed']:.1f}%")
        A(f"     avg cash drag        {100-rec['avg_deployed']:.1f}%")
        A()
        A("6. PER CALENDAR YEAR")
        A("     net P&L is REALISED (booked at exit); year-end equity is")
        A("     mark-to-market. They do not reconcile year by year.")
        yr = pd.DataFrame({"trades": cl.groupby(cl["exit_date"].dt.year).size(),
                           "net_pnl": cl.groupby(cl["exit_date"].dt.year)["pnl"].sum(),
                           "year_end_equity": eq.groupby(eq.index.year).last()}).fillna(0)
        for ln in yr.round(0).to_string().splitlines():
            A("     " + ln)
        A()
        A("7. SKIPPED SIGNALS   [counters transcribed from the run]")
        A(f"     no free slot        {rec['skip_slot']:,} symbol-days")
        A(f"     insufficient cash   {rec['skip_cash']:,} symbol-days, on "
          f"{rec['cash_block_sessions']:,} distinct sessions")
        A(f"     when cash blocked, the median state was 8 positions open with")
        A(f"     {rec['cash_block_median_cash_pct']:.1f}% of equity in cash — the book is")
        A(f"     capital-bound at 8-9 positions, not slot-bound at 10, because")
        A(f"     winners drift well past their 10% entry weight and no")
        A(f"     rebalancing rule is registered.")
        A()
        A("8. EXTREMES")
        cols = ["symbol", "entry_date", "exit_date", "pnl", "ret_pct", "exit_reason"]
        fmt = lambda d: d[cols].assign(entry_date=lambda x: x["entry_date"].dt.date,
                                       exit_date=lambda x: x["exit_date"].dt.date,
                                       pnl=lambda x: x["pnl"].round(0),
                                       ret_pct=lambda x: x["ret_pct"].round(1))
        A("   10 largest winners:")
        for ln in fmt(cl.nlargest(10, "pnl")).to_string(index=False).splitlines():
            A("     " + ln)
        A("   10 largest losers:")
        for ln in fmt(cl.nsmallest(10, "pnl")).to_string(index=False).splitlines():
            A("     " + ln)
        A()

    A("=" * 78)
    A("9. SIDE BY SIDE")
    A("=" * 78)
    rows = []
    for k in ["trades_closed", "win_rate", "exp_rs", "exp_r", "profit_factor",
              "cagr", "max_dd", "longest_dd_days", "final_equity"]:
        rows.append({"metric": k, "A": out["A"][3][k], "B": out["B"][3][k]})
    rows.append({"metric": "null_p_value", "A": RECORDED["A"]["p"], "B": RECORDED["B"]["p"]})
    rows.append({"metric": "gates_passed_of_5", "A": 4, "B": 4})
    for ln in pd.DataFrame(rows).round(3).to_string(index=False).splitlines():
        A("   " + ln)
    A()
    A("   Removing F5 buys +0.34 R of expectancy and one point of CAGR, and pays")
    A("   for it with 12 more points of drawdown and a drawdown lasting three")
    A("   years instead of eighteen months. Profit factor moves the OTHER way.")
    A()
    A("=" * 78)
    A("10. DIAGNOSTIC COUNT ONLY — not a verdict input")
    A("=" * 78)
    for tag in ("A", "B"):
        T = out[tag][0]
        n = int(T.loc[T["exit_reason"] != "stop_15pct", "touched_15_intraday"].sum())
        A(f"   config {tag}: {n} of {len(T)} trades ({100*n/len(T):.1f}%) touched -15% "
          f"intraday without ever closing below it")
    A("   No intraday stop was simulated. Count only.")
    A()
    A("=" * 78)
    A("11. RANDOM-ENTRY NULL — the regime thermometer")
    A("=" * 78)
    A("   Design reused from scripts/m5_select_nulls.random_entry_null: matched")
    A("   trade count, holding periods resampled from the strategy's own")
    A("   distribution, random symbol on random eligible NON-signal days,")
    A("   identical costs and slippage, 500 iterations, seed 20260816.")
    A("   Reimplemented against this module's data structures; one deliberate")
    A("   change — the null exits at the OPEN after the sampled hold, to match")
    A("   this module's declared exit timing (m5 exited at the close).")
    A()
    for tag in ("A", "B"):
        r, m = RECORDED[tag], out[tag][3]
        A(f"   config {tag}:  NULL MEAN {r['null_mean']:+.4f} R    median {r['null_median']:+.4f} R")
        A(f"              p95 {r['null_p95']:+.4f}   p99 {r['null_p99']:+.4f}   skew {r['null_skew']:.2f}")
        A(f"              strategy {m['exp_r']:+.4f} R   ->   p = {r['p']:.4f}")
    A()
    A("   READING: a RANDOM entry into this universe over this period earned")
    A("   +0.44 R per trade — about +6.6% net on a median six-month hold, with no")
    A("   rule at all. That is what the window was. The null distribution is also")
    A("   violently right-skewed (median only +0.27 R, p99 +7.46 R), so the")
    A("   strategy's +0.98 R sits barely above the 95th percentile of +0.91.")
    A("   Both p-values sit a hair under 0.05 and are decided by a handful of")
    A("   extreme tail draws. The gate is recorded as PASS because that is what")
    A("   the frozen rule says; the honest reading is that the entry edge is not")
    A("   distinguishable from luck at any comfortable margin.")
    A()

    # ---------------- benchmarks
    A("=" * 78)
    A("12. BENCHMARK DIAGNOSTIC — added after the verdict, changes nothing")
    A("=" * 78)
    A("   Identical window, 2015-01-01 -> 2026-08-14, 2,879 sessions.")
    A()
    A("   How mid-window listings are handled in the equal-weight benchmarks:")
    A("     130 of the 188 symbols exist on day 1; 58 list later (earliest")
    A("     2015-04-09, latest 2024-12-18).")
    A("     EW BUY & HOLD (primary): Rs 10,00,000 / 188 is allocated per symbol.")
    A("       A late lister holds its slice in CASH at 0% return until its first")
    A("       session, then buys at that close and holds to the end. No")
    A("       rebalancing — winners drift up in weight, which mirrors how")
    A("       configs A and B actually behave. The cash held for late listers is")
    A("       a genuine drag on this benchmark's return.")
    A("     EW REBALANCED DAILY (reference): each day's return is the mean daily")
    A("       return of every symbol having both today's and yesterday's close.")
    A()
    T = BM.main()
    A()
    for ln in T.to_string(index=False).splitlines():
        A("   " + ln)
    A()
    A("   CAVEAT, and it is a large one: the 188-symbol universe is TODAY'S F&O")
    A("   list frozen in 2026. Holding it from 2015 requires 2015 knowledge of")
    A("   the 2026 constituents, so both equal-weight rows are NOT achievable —")
    A("   they are an upper bound, not a portfolio anyone could have run. The")
    A("   same selection bias flatters configs A and B, which drew their trades")
    A("   from that same forward-looking list.")
    A()
    A("   READING: both configs UNDERPERFORM the equal-weight universe on CAGR")
    A("   (A 15.88%, B 16.95%, versus 18.70% held and 20.42% rebalanced). Config")
    A("   A does buy a materially better drawdown (-25.4% against -35.5%) and has")
    A("   the best return-per-unit-drawdown of anything in the table, so it is")
    A("   not strictly dominated. Config B is: worse CAGR, worse drawdown, and a")
    A("   drawdown lasting 1,147 days against 424, than simply buying the whole")
    A("   universe and doing nothing.")
    A()
    A("   ON THE GATE: the -15% ceiling was not reachable by any fully-invested")
    A("   long-only book in this window. NIFTY itself drew down 38.4%, the")
    A("   equal-weight universe 35.5%, both on the same day — 2020-03-23. A")
    A("   strategy averaging 80% deployed with a median 133-session hold had no")
    A("   mechanism to be flat into that crash. The gate looks mis-set. It")
    A("   nevertheless STANDS as registered, and both configs remain FAIL.")
    A()
    A("=" * 78)
    A("ARTEFACTS")
    A("=" * 78)
    A("   data/m2/module2_trades_A.parquet     125 rows")
    A("   data/m2/module2_trades_B.parquet     129 rows")
    A("   data/m2/module2_equity_A.parquet     2,879 rows")
    A("   data/m2/module2_equity_B.parquet     2,879 rows")
    A("   data/m2/benchmarks.parquet           5 rows")
    A("   data/panel_v2/module1_panel.parquet  474,065 rows")
    A("   data/panel_v2/module1_signals.parquet  5,467 rows")
    A()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L) + "\n")
    print(f"\nwritten: {REPORT}  ({len(L)} lines)")


if __name__ == "__main__":
    main()

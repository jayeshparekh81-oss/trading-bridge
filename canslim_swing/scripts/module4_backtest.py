#!/usr/bin/env python3
"""canslim-swing MODULE 4 — trade engine + portfolio simulation (frozen v1 defaults).

No tuning. No network. Deterministic. Full-period run; verdict-reading is M5's job.

Inputs (local, read-only):
  canslim_swing/data/scan/daily_scan.parquet     (M3)
  canslim_swing/data/swing/daily/<SYM>.parquet   (M1)
  canslim_swing/data/swing/nifty_daily.parquet   (M1, context only)

Outputs:
  canslim_swing/data/backtest/trades_v1.parquet
  canslim_swing/data/backtest/equity_v1.parquet
  canslim_swing/reports/swing_module4_backtest.txt

PRE-REGISTERED MODELLING CHOICES (stated, not discovered later):
  * Intraday path is unknown from OHLC. On the FILL day we still check the stop
    using that day's low, even though the low may have occurred BEFORE the
    breakout trigger was hit. This is deliberately PESSIMISTIC. (Implemented at
    the point of fill — the day's exit sweep runs before the position exists.)
  * Same-day stop-and-target conflict resolves STOP FIRST (pessimistic).
  * A trend-break exit signalled at D's close executes at D+1's open. If that
    open is already at/below the stop, the trade is labelled a stop (same price,
    honest label).
  * Position sizing uses equity known BEFORE the entry day's own price action
    (cash after today's exits + still-open positions marked at the PRIOR close),
    so sizing never reads the day it trades into.
  * No margin: an entry is cut down (or skipped) if cash cannot fund it.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
DAILY_DIR = TRACK / "data" / "swing" / "daily"
SCAN_PARQUET = TRACK / "data" / "scan" / "daily_scan.parquet"
NIFTY_PARQUET = TRACK / "data" / "swing" / "nifty_daily.parquet"
OUT_DIR = TRACK / "data" / "backtest"
TRADES_PARQUET = OUT_DIR / "trades_v1.parquet"
EQUITY_PARQUET = OUT_DIR / "equity_v1.parquet"
REPORT_PATH = TRACK / "reports" / "swing_module4_backtest.txt"

# ------------------------------------------------------------------ FROZEN v1
START_EQUITY = 1_000_000.0
MAX_POSITIONS = 6
RISK_PER_TRADE = 0.01           # 1% of current equity
MAX_POSITION_PCT = 0.25         # position value cap
TRIGGER_MULT = 1.001            # buy-stop = pivot x this
CHASE_CAP = 1.05                # open > pivot x this  -> cancel
STOP_MULT = 0.92                # hard stop = entry x this  (8%)
TARGET_MULT = 1.25              # profit target = entry x this
SLIPPAGE = 0.0005               # 0.05% per side — LABELED ASSUMPTION (M5 sweeps)
VOL_AVG_W = 50                  # breakout volume ratio denominator
SMA_EXIT = 50

# costs (per side), all named
STT = 0.0010                    # 0.10% both sides
EXCH_TXN = 0.0000297            # 0.00297%
SEBI_FEE = 0.000001             # 0.0001%
STAMP_BUY = 0.00015             # 0.015% buy only
GST_RATE = 0.18                 # on brokerage + exchange + SEBI
BROKERAGE = 0.0                 # Dhan delivery
DP_SELL = 15.93                 # per scrip on sell

BUILD_END = pd.Timestamp("2024-12-31")
SEALED_START = pd.Timestamp("2025-01-01")


def buy_costs(turnover: float) -> float:
    exch = turnover * EXCH_TXN
    sebi = turnover * SEBI_FEE
    gst = GST_RATE * (BROKERAGE + exch + sebi)
    return turnover * STT + exch + sebi + turnover * STAMP_BUY + gst + BROKERAGE


def sell_costs(turnover: float) -> float:
    exch = turnover * EXCH_TXN
    sebi = turnover * SEBI_FEE
    gst = GST_RATE * (BROKERAGE + exch + sebi)
    return turnover * STT + exch + sebi + gst + BROKERAGE + DP_SELL


# ------------------------------------------------------------------ simulation
def load_prices(symbols) -> dict:
    px = {}
    for sym in symbols:
        d = pd.read_parquet(DAILY_DIR / f"{sym}.parquet")
        d = d.sort_index()
        d["sma50"] = d["close"].rolling(SMA_EXIT).mean()
        # previous-50-session average volume: shifted so the breakout day itself
        # is not part of its own benchmark
        d["vol50"] = d["volume"].rolling(VOL_AVG_W).mean().shift(1)
        px[sym] = d
    return px


def run() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    scan = pd.read_parquet(SCAN_PARQUET)
    universe = sorted(scan["symbol"].unique())
    px = load_prices(universe)

    cands = scan[scan["candidate"]][["date", "symbol", "pivot", "rs_pct"]]
    cand_by_day = {d: g.sort_values("rs_pct", ascending=False)
                   for d, g in cands.groupby("date")}

    # calendar: union of all symbol sessions from the first scan day onward
    all_days = sorted({d for s in universe for d in px[s].index})
    first = scan["date"].min()
    calendar = [d for d in all_days if d >= first]
    day_index = {d: i for i, d in enumerate(calendar)}

    cash = START_EQUITY
    positions: dict[str, dict] = {}
    trades: list[dict] = []
    equity_rows: list[dict] = []
    pending: list[dict] = []          # working buy-stops for the NEXT session
    outcomes = {k: 0 for k in ("filled", "cancel_chase", "no_trigger", "skip_no_slot",
                               "skip_already_open", "skip_size_zero", "skip_cash",
                               "skip_no_session", "exit_on_fill_day")}
    cancels_log: list[dict] = []

    prev_day = None
    for di, day in enumerate(calendar):
        # ---------------- 1. exits on today's prices ----------------
        for sym in list(positions):
            p = positions[sym]
            d = px[sym]
            if day not in d.index:
                continue
            row = d.loc[day]
            o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
            exit_price = exit_reason = None
            if p["trend_exit_armed"]:
                # signalled at yesterday's close -> execute at today's open.
                # Price is the open either way; the LABEL follows spec precedence
                # (stop, then target, else the trend break) so exit-reason
                # attribution that M5 reads is not silently wrong.
                exit_price = o
                exit_reason = ("stop" if o <= p["stop"]
                               else "target" if o >= p["target"] else "sma50_break")
            else:
                if o <= p["stop"]:
                    exit_price, exit_reason = o, "stop"          # gap through the stop
                elif l <= p["stop"]:
                    exit_price, exit_reason = p["stop"], "stop"  # stop first (pessimistic)
                elif o >= p["target"]:
                    exit_price, exit_reason = o, "target"
                elif h >= p["target"]:
                    exit_price, exit_reason = p["target"], "target"
            if exit_price is not None:
                cash += close_trade(trades, p, sym, day, exit_price, exit_reason,
                                    cash, positions, px, prev_day)
                del positions[sym]

        # ---------------- 2. entries from yesterday's working orders ----------------
        if pending:
            # equity reference: cash after today's exits + open positions marked at
            # the PRIOR close. Never reads today's price action.
            mtm_prev = 0.0
            for s, p in positions.items():
                dser = px[s]
                pc = dser["close"].reindex(dser.index[dser.index <= prev_day])
                mtm_prev += p["qty"] * float(pc.iloc[-1]) if len(pc) else 0.0
            equity_ref = cash + mtm_prev
            for od in pending:
                sym = od["symbol"]
                d = px[sym]
                if day not in d.index:
                    outcomes["skip_no_session"] += 1
                    continue
                row = d.loc[day]
                o, h = float(row["open"]), float(row["high"])
                trigger, pivot = od["trigger"], od["pivot"]
                # PRICE TEST FIRST, portfolio constraints second. Bucketing the
                # slot/already-open cases before the trigger test would let those
                # buckets silently absorb orders that never traded through the
                # trigger, inverting the order-flow accounting (the fill SET is
                # identical either way — this ordering only makes the counters true).
                if o >= trigger:
                    if o > pivot * CHASE_CAP:
                        outcomes["cancel_chase"] += 1
                        cancels_log.append({"date": day, "symbol": sym, "open": o,
                                            "pivot": pivot, "gap_pct": 100 * (o / pivot - 1)})
                        continue
                    raw_fill = o
                elif h >= trigger:
                    raw_fill = trigger
                else:
                    outcomes["no_trigger"] += 1
                    continue
                if len(positions) >= MAX_POSITIONS:
                    outcomes["skip_no_slot"] += 1
                    continue
                if sym in positions:
                    outcomes["skip_already_open"] += 1
                    continue
                entry = raw_fill * (1 + SLIPPAGE)
                stop = entry * STOP_MULT
                risk_amt = RISK_PER_TRADE * equity_ref
                qty = int(math.floor(risk_amt / (entry - stop)))
                cap_qty = int(math.floor(MAX_POSITION_PCT * equity_ref / entry))
                qty = min(qty, cap_qty)
                if qty >= 1:                      # no margin: fit inside cash
                    while qty >= 1 and qty * entry + buy_costs(qty * entry) > cash:
                        qty -= 1
                    if qty < 1:
                        outcomes["skip_cash"] += 1
                        continue
                else:
                    outcomes["skip_size_zero"] += 1
                    continue
                turnover = qty * entry
                cost = buy_costs(turnover)
                cash -= turnover + cost
                vol50 = row.get("vol50", np.nan)
                positions[sym] = {
                    "qty": qty, "entry": entry, "stop": stop, "target": entry * TARGET_MULT,
                    "entry_date": day, "entry_cost": cost, "risk_amt": risk_amt,
                    "rs_at_entry": od["rs_pct"], "equity_before": equity_ref,
                    "vol_ratio": (float(row["volume"]) / float(vol50)
                                  if vol50 and not pd.isna(vol50) and vol50 > 0 else np.nan),
                    "trend_exit_armed": False,
                }
                outcomes["filled"] += 1
                # SPEC ITEM 6: the stop is live from the FILL DAY onward. The day's
                # exit sweep already ran before this position existed, so it must be
                # tested here or the fill day is silently exempt from its own stop.
                # (open <= stop is unreachable on the fill day: entry >= open, and
                # stop = entry*0.92 < open.) Stop before target, per spec item 9.
                lo, hi = float(row["low"]), float(row["high"])
                fd_price = fd_reason = None
                if lo <= positions[sym]["stop"]:
                    fd_price, fd_reason = positions[sym]["stop"], "stop"
                elif hi >= positions[sym]["target"]:
                    fd_price, fd_reason = positions[sym]["target"], "target"
                if fd_price is not None:
                    p_new = positions[sym]
                    cash += close_trade(trades, p_new, sym, day, fd_price, fd_reason,
                                        cash, positions, px, prev_day)
                    del positions[sym]
                    outcomes["exit_on_fill_day"] += 1
        pending = []

        # ---------------- 3. mark-to-market + arm trend-break ----------------
        mtm = 0.0
        for sym, p in positions.items():
            d = px[sym]
            if day in d.index:
                row = d.loc[day]
                c = float(row["close"])
                p["last_close"] = c
                sma50 = row["sma50"]
                p["trend_exit_armed"] = bool(not pd.isna(sma50) and c < float(sma50))
            mtm += p["qty"] * p.get("last_close", p["entry"])
        equity = cash + mtm
        equity_rows.append({"date": day, "equity": equity, "cash": cash,
                            "deployed": mtm, "n_positions": len(positions)})

        # ---------------- 4. build tomorrow's working orders ----------------
        g = cand_by_day.get(day)
        if g is not None:
            pending = [{"symbol": r.symbol, "pivot": float(r.pivot),
                        "trigger": float(r.pivot) * TRIGGER_MULT, "rs_pct": float(r.rs_pct)}
                       for r in g.itertuples()]
        prev_day = day

    # ---------------- close survivors at the last available close ----------------
    last_day = calendar[-1]
    for sym in list(positions):
        p = positions[sym]
        d = px[sym]
        sub = d.index[d.index <= last_day]
        lc = float(d.loc[sub[-1], "close"])
        cash += close_trade(trades, p, sym, sub[-1], lc, "end-of-data", cash, positions, px,
                            last_day)
        del positions[sym]

    tdf = pd.DataFrame(trades)
    edf = pd.DataFrame(equity_rows).set_index("date")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tdf.to_parquet(TRADES_PARQUET)
    edf.to_parquet(EQUITY_PARQUET)
    return tdf, edf, {"outcomes": outcomes, "cancels": pd.DataFrame(cancels_log)}


def close_trade(trades, p, sym, day, raw_exit, reason, cash, positions, px,
                prev_day=None) -> float:
    exit_price = raw_exit * (1 - SLIPPAGE)
    turnover = p["qty"] * exit_price
    cost = sell_costs(turnover)
    proceeds = turnover - cost
    gross = p["qty"] * (exit_price - p["entry"])
    net = gross - p["entry_cost"] - cost
    # equity_after must be PORTFOLIO EQUITY on the same basis as equity_before
    # (cash + open positions marked at the prior close), not free cash — otherwise
    # the two ledger columns are incomparable and equity_after understates by the
    # value of every other position still held.
    others = 0.0
    for s2, p2 in positions.items():
        if s2 == sym:
            continue
        mark = p2.get("last_close", p2["entry"])
        others += p2["qty"] * mark
    trades.append({
        "symbol": sym, "entry_date": p["entry_date"], "exit_date": day,
        "entry_price": p["entry"], "exit_price": exit_price, "qty": p["qty"],
        "gross_pnl": gross, "net_pnl": net,
        "r_multiple": net / p["risk_amt"] if p["risk_amt"] else np.nan,
        "exit_reason": reason, "vol_ratio": p["vol_ratio"], "rs_at_entry": p["rs_at_entry"],
        "days_held": int(np.busday_count(p["entry_date"].date(), day.date())),
        "equity_before": p["equity_before"], "equity_after": cash + proceeds + others,
        "pct_return": 100 * (exit_price / p["entry"] - 1),
        "stop": p["stop"], "target": p["target"],
    })
    return proceeds


# ------------------------------------------------------------------ reporting
def perf_block(t: pd.DataFrame, e: pd.DataFrame) -> dict:
    """Performance of a trade set `t` against an equity segment `e`."""
    if t.empty:
        return {"trades": 0}
    wins, losses = t[t["net_pnl"] > 0], t[t["net_pnl"] <= 0]
    gp, gl = wins["net_pnl"].sum(), -losses["net_pnl"].sum()
    eq = e["equity"]
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (365.25 / days) - 1 if eq.iloc[0] > 0 else np.nan
    dd = (eq / eq.cummax() - 1.0)
    return {
        "trades": len(t), "win_pct": 100 * len(wins) / len(t),
        "avg_win": wins["net_pnl"].mean() if len(wins) else 0.0,
        "avg_loss": losses["net_pnl"].mean() if len(losses) else 0.0,
        "avg_win_pct": wins["pct_return"].mean() if len(wins) else 0.0,
        "avg_loss_pct": losses["pct_return"].mean() if len(losses) else 0.0,
        "expectancy_rs": t["net_pnl"].mean(), "expectancy_r": t["r_multiple"].mean(),
        "profit_factor": (gp / gl) if gl > 0 else np.inf,
        "cagr": cagr, "max_dd": dd.min(),
        "exposure": (e["deployed"] / e["equity"]).mean(),
        "avg_days_held": t["days_held"].mean(),
        "start_eq": eq.iloc[0], "end_eq": eq.iloc[-1],
        "net_pnl": t["net_pnl"].sum(),
    }


def fmt_block(b: dict, indent="    ") -> list[str]:
    if not b.get("trades"):
        return [f"{indent}(no trades)"]
    return [
        f"{indent}{'trades':<22}{b['trades']:>12,}      {'win %':<18}{b['win_pct']:>8.1f}%",
        f"{indent}{'avg win':<22}{b['avg_win']:>12,.0f} Rs  {'avg win %':<18}{b['avg_win_pct']:>8.2f}%",
        f"{indent}{'avg loss':<22}{b['avg_loss']:>12,.0f} Rs  {'avg loss %':<18}{b['avg_loss_pct']:>8.2f}%",
        f"{indent}{'expectancy/trade':<22}{b['expectancy_rs']:>12,.0f} Rs  {'expectancy R':<18}{b['expectancy_r']:>8.3f}",
        f"{indent}{'profit factor':<22}{b['profit_factor']:>12.2f}      {'avg days held':<18}{b['avg_days_held']:>8.1f}",
        f"{indent}{'CAGR':<22}{100 * b['cagr']:>11.2f}%      {'max drawdown':<18}{100 * b['max_dd']:>7.2f}%",
        f"{indent}{'exposure (avg)':<22}{100 * b['exposure']:>11.1f}%      {'net PnL':<18}{b['net_pnl']:>8,.0f} Rs",
        f"{indent}{'equity':<22}{b['start_eq']:>12,.0f} -> {b['end_eq']:,.0f} Rs",
    ]


def write_report(t: pd.DataFrame, e: pd.DataFrame, meta: dict) -> None:
    oc = meta["outcomes"]
    L, A = [], None
    A = L.append
    A("=" * 78)
    A("canslim-swing MODULE 4 — TRADE ENGINE + PORTFOLIO SIMULATION (frozen v1)")
    A(f"ledger: {TRADES_PARQUET}")
    A(f"equity: {EQUITY_PARQUET}")
    A("No tuning in this module. Verdict-reading belongs to M5.")
    A("=" * 78)
    A("")
    A("0. ORDER-FLOW ACCOUNTING (what happened to every candidate-day signal)")
    # exit_on_fill_day is a SUB-COUNT of `filled`, not a signal disposition —
    # excluded from the total so the dispositions sum to the candidate-day count.
    disp = {k: v for k, v in oc.items() if k != "exit_on_fill_day"}
    tot = sum(disp.values())
    for k, v in disp.items():
        A(f"    {k:<22}{v:>8,}  ({100 * v / max(tot, 1):5.1f}%)")
    A(f"    {'TOTAL signals':<22}{tot:>8,}   (= candidate-day rows in the M3 scan)")
    A(f"    {'  of which: exited on fill day':<30}{oc.get('exit_on_fill_day', 0):>2,}"
      f"  (subset of `filled`)")
    A("")
    A("    filled              = a working buy-stop that triggered and was sized")
    A("    cancel_chase        = opened above pivot x1.05, order cancelled unfilled")
    A("    no_trigger          = day's high never reached pivot x1.001")
    A("    skip_no_slot        = all 6 portfolio slots already occupied")
    A("    skip_already_open   = position in that symbol already held")
    if not meta["cancels"].empty:
        A("")
        A("    chase-cap cancellations:")
        A(fmt_table(meta["cancels"].round(2)))
    A("")
    A("-" * 78)
    A("1. FULL-PERIOD TOTALS  (" + f"{e.index[0]:%d-%b-%Y} -> {e.index[-1]:%d-%b-%Y})")
    A("")
    for line in fmt_block(perf_block(t, e)):
        A(line)
    A("")
    A("-" * 78)
    A("2. PER-YEAR")
    rows = []
    for y, g in t.groupby(t["entry_date"].dt.year):
        seg = e[e.index.year == y]
        b = perf_block(g, seg)
        rows.append({"year": y, "trades": b["trades"], "win%": round(b["win_pct"], 1),
                     "net_pnl": round(b["net_pnl"]), "exp_R": round(b["expectancy_r"], 3),
                     "PF": round(b["profit_factor"], 2), "maxDD%": round(100 * b["max_dd"], 1),
                     "expo%": round(100 * b["exposure"], 1),
                     "eq_end": round(b["end_eq"])})
    A(fmt_table(pd.DataFrame(rows).set_index("year")))
    A("  (trades grouped by ENTRY year; drawdown/exposure/equity are that calendar")
    A("   year's slice of the continuous curve)")
    A("")
    A("-" * 78)
    A("3. PER-EXIT-REASON")
    er = t.groupby("exit_reason").agg(
        count=("net_pnl", "size"), win_pct=("net_pnl", lambda s: 100 * (s > 0).mean()),
        avg_R=("r_multiple", "mean"), total_pnl=("net_pnl", "sum"),
        avg_days=("days_held", "mean"), avg_pct=("pct_return", "mean"))
    er = er.round({"win_pct": 1, "avg_R": 3, "total_pnl": 0, "avg_days": 1, "avg_pct": 2})
    A(fmt_table(er))
    A("-" * 78)
    A("4. R-MULTIPLE DISTRIBUTION")
    q = t["r_multiple"].quantile([.1, .2, .3, .4, .5, .6, .7, .8, .9]).round(3)
    A("  deciles: " + "  ".join(f"p{int(100 * k)}={v}" for k, v in q.items()))
    bins = [-np.inf, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0, np.inf]
    labels = ["<-1.5", "-1.5..-1", "-1..-0.5", "-0.5..0", "0..0.5", "0.5..1", "1..2", "2..3", ">3"]
    hist = pd.cut(t["r_multiple"], bins=bins, labels=labels).value_counts().reindex(labels)
    A("")
    for lab, n in hist.items():
        A(f"    {lab:>10} | {'#' * int(n)} {n}")
    A("")
    A("-" * 78)
    A("5. TOP-10 / BOTTOM-10 TRADES (by net PnL)")
    cols = ["symbol", "entry_date", "exit_date", "qty", "entry_price", "exit_price",
            "net_pnl", "r_multiple", "pct_return", "exit_reason", "days_held"]
    show = t[cols].copy()
    show["entry_date"] = show["entry_date"].dt.date
    show["exit_date"] = show["exit_date"].dt.date
    show = show.round({"entry_price": 2, "exit_price": 2, "net_pnl": 0,
                       "r_multiple": 2, "pct_return": 1})
    A("  TOP-10:")
    A(fmt_table(show.nlargest(10, "net_pnl").reset_index(drop=True)))
    A("  BOTTOM-10:")
    A(fmt_table(show.nsmallest(10, "net_pnl").reset_index(drop=True)))
    A("-" * 78)
    A("6. BREAKOUT-DAY VOLUME RATIO (vol / prior-50-session avg) — NOT a gate in v1")
    A("   Recorded so M5 can judge volume-confirmation variants from real fills.")
    v = t.dropna(subset=["vol_ratio"])
    A(f"   fills with a usable ratio: {len(v)}/{len(t)}")
    if len(v):
        A(f"   overall deciles: " + "  ".join(
            f"p{int(100 * k)}={round(val, 2)}"
            for k, val in v['vol_ratio'].quantile([.1, .25, .5, .75, .9]).items()))
        grp = v.assign(outcome=np.where(v["net_pnl"] > 0, "winner", "loser")).groupby("outcome")
        vr = grp["vol_ratio"].agg(["count", "mean", "median",
                                   lambda s: (s >= 1.5).mean() * 100]).round(2)
        vr.columns = ["count", "mean", "median", "pct_with_ratio>=1.5"]
        A(fmt_table(vr))
        by_exit = v.groupby("exit_reason")["vol_ratio"].agg(["count", "median"]).round(2)
        A("   by exit reason:")
        A(fmt_table(by_exit))
    A("-" * 78)
    A("7. BUILD HALF (29-Jul-2022 -> 31-Dec-2024)")
    tb = t[t["entry_date"] <= BUILD_END]
    eb = e[e.index <= BUILD_END]
    A("")
    for line in fmt_block(perf_block(tb, eb)):
        A(line)
    A("")
    A("~" * 78)
    A("   SEALED HALF — READ-ONLY, VERDICT BELONGS TO M5")
    A("~" * 78)
    A("   (01-Jan-2025 -> 24-Jul-2026. Printed for completeness only. Do not tune")
    A("    anything against these numbers; that is what makes them sealed.)")
    ts = t[t["entry_date"] >= SEALED_START]
    es = e[e.index >= SEALED_START]
    A("")
    for line in fmt_block(perf_block(ts, es)):
        A(line)
    A("")
    A("   sealed-half exit mix: " + str(ts["exit_reason"].value_counts().to_dict()))
    A("")
    A("-" * 78)
    A("8. FROZEN v1 CONSTANTS + COST MODEL (echoed)")
    A(f"   equity {START_EQUITY:,.0f} | max {MAX_POSITIONS} positions | risk {100 * RISK_PER_TRADE:.0f}%/trade"
      f" | position cap {100 * MAX_POSITION_PCT:.0f}%")
    A(f"   trigger pivot x{TRIGGER_MULT} | chase-cap pivot x{CHASE_CAP} | stop x{STOP_MULT}"
      f" | target x{TARGET_MULT} | SMA{SMA_EXIT} break")
    A(f"   STT {100 * STT:.2f}% both | exch {100 * EXCH_TXN:.5f}% | SEBI {100 * SEBI_FEE:.4f}%"
      f" | stamp {100 * STAMP_BUY:.3f}% buy | GST {100 * GST_RATE:.0f}% | DP {DP_SELL} sell")
    A(f"   SLIPPAGE {100 * SLIPPAGE:.2f}% per side  <-- LABELED ASSUMPTION (M5 sweeps 0.05/0.10/0.20)")
    A("   Market filter blocks NEW entries only; it never force-closes (v1 choice).")
    A("")
    A("-" * 78)
    A("9. WHAT THE MACHINE ACTUALLY DID (description, not verdict)")
    A("")
    full = perf_block(t, e)
    # exit_on_fill_day is a SUB-COUNT of `filled`, not a disposition — excluding it
    # keeps this total equal to the M3 candidate-day count (and to section 0).
    nsig = sum(v for k, v in oc.items() if k != "exit_on_fill_day")
    A(f"  Over {len(e)} sessions the engine turned {nsig:,} candidate-day signals into")
    A(f"  {oc['filled']} fills — roughly {oc['filled'] / max(len(e), 1) * 21:.1f} entries per trading month. The")
    A(f"  dominant reason a signal never became a trade was the BREAKOUT ITSELF: {oc['no_trigger']:,}")
    A(f"  signals ({100 * oc['no_trigger'] / max(nsig, 1):.0f}%) never traded through pivot x{TRIGGER_MULT}, against {oc['skip_no_slot']:,}")
    A(f"  ({100 * oc['skip_no_slot'] / max(nsig, 1):.0f}%) that would have filled but met a full 6-slot book and {oc['skip_already_open']:,}")
    A(f"  already held in that symbol. The chase-cap almost never bound ({oc['cancel_chase']} cancellations),")
    A("  so gap-aways were not a practical constraint at these settings.")
    A("")
    A("  NOTE ON THESE COUNTERS: the price test is evaluated BEFORE the portfolio")
    A("  constraints, so `skip_no_slot` contains only orders that genuinely would")
    A("  have filled. An earlier build bucketed slot-blocked orders first, which")
    A("  inflated that bucket to 1,958 and made the 6-slot cap look like the binding")
    A("  constraint; it is not. The fill SET is identical under either ordering —")
    A("  only the accounting differed — but the conclusion drawn from it inverted.")
    A("")
    A(f"  Capital sat about {100 * full['exposure']:.0f}% deployed on average, with all six slots")
    A(f"  occupied on {int((e['n_positions'] == 6).sum())} of {len(e)} sessions and the book completely empty on")
    A(f"  {int((e['n_positions'] == 0).sum())}. Because the market filter gates entries but never forces an exit,")
    A("  positions opened before a nifty_off stretch simply ran on through it; the")
    A("  book drains during those stretches only as individual exits fire, which is")
    A("  why exposure decays rather than steps down when the market filter flips.")
    A("")
    er2 = t.groupby("exit_reason")["net_pnl"].sum()
    A(f"  Where the money moved, by exit reason: " + ", ".join(
        f"{k} {v:+,.0f} Rs ({int((t['exit_reason'] == k).sum())} trades)" for k, v in er2.items()) + ".")
    A(f"  The trend-break exit did most of the work by count ({int((t['exit_reason'] == 'sma50_break').sum())} of {len(t)} exits)")
    A(f"  while the 25% target fired {int((t['exit_reason'] == 'target').sum())} times and the 8% stop {int((t['exit_reason'] == 'stop').sum())} times. Win rate")
    A(f"  was {full['win_pct']:.1f}% against an average win of {full['avg_win']:,.0f} Rs and an average loss of")
    A(f"  {full['avg_loss']:,.0f} Rs, i.e. the arithmetic depends on the win/loss SIZE ratio rather")
    A("  than on hit rate — the loss-cutting rules, not the entry, set the shape of")
    A("  the R distribution.")
    A("")
    fd = oc.get("exit_on_fill_day", 0)
    A(f"  The stop is live from the fill day onward, as specified: {fd} trades were")
    A(f"  stopped or targeted on their own entry day. That check is worth {225675 - int(full['net_pnl']):,} Rs of")
    A("  reported profit — an earlier build ran the day's exit sweep before entries")
    A("  existed, so fill-day stops were silently skipped and net PnL read 225,675 Rs")
    A("  instead of the figure above. It was caught by adversarial review, not by the")
    A("  self-audit that build printed, which counted same-day round-trips with a")
    A("  statistic that was zero by construction under the very ordering it excused.")
    A("")
    A("  These are descriptions of one frozen parameter set on one universe. Nothing")
    A("  here has been swept, and no significance is claimed or implied.")
    A("")
    A("=" * 78)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(L) + "\n")


def fmt_table(df: pd.DataFrame) -> str:
    if df is None or len(df) == 0:
        return "  (none)\n"
    with pd.option_context("display.max_rows", len(df) + 5, "display.width", 220):
        return df.to_string() + "\n"


if __name__ == "__main__":
    t, e, meta = run()
    print(f"trades: {len(t)}  outcomes: {meta['outcomes']}")
    print(f"final equity: {e['equity'].iloc[-1]:,.0f}")
    write_report(t, e, meta)
    print(f"\nREPORT: {REPORT_PATH}")

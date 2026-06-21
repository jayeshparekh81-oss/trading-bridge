#!/usr/bin/env python3
"""Generate backend/scripts/showcase_backtest.json — a committable, public-facing
STATIC display artifact built from the isolated SQLite store (read-only).

Honesty doctrine (enforced structurally):
  * Size-independent per-trade metrics ONLY. NO INR, NO qty/value, NO compounded
    totals. The non-compounded cumulative series is a simple SUM of per-trade %
    on a constant 1-unit (NOT compounding) — it is NOT a return; framing/curve
    is a frontend decision (we only expose the data).
  * 4-state labels per SHOWCASE_BACKEND_DESIGN.md: backtest = in-sample for all;
    live-status: BSE = LIVE_REAL, CDSL = FORWARD_TEST, ANGELONE = PAPER.
  * Both gross and net cumulative series are exposed so the gross/net choice is
    NOT decided here.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest_backtest_trade_list as base

# 4-state live labelling (per Jayesh's Batch-2 spec). These are FRAMING labels.
LIVE_STATE = {
    "BSE": ("LIVE_REAL", "Live (real money)",
            "Live real-money results. Past performance is not a guarantee of future results."),
    "CDSL": ("FORWARD_TEST", "Forward test (out-of-sample)",
             "Forward test — out-of-sample, limited sample, not a track record."),
    "ANGELONE": ("PAPER", "Paper (simulated)",
                 "Paper / simulated — no real money traded; backtest-only candidate."),
}
DISPLAY = {"BSE": "NSE:BSE Futures", "CDSL": "NSE:CDSL Futures", "ANGELONE": "NSE:ANGELONE Futures"}
BACKTEST_DISCLAIMER = ("In-sample backtest, not a guarantee of future results. "
                       "Charges estimated; slippage excluded.")


def rows_for(cur, label):
    q = """SELECT trade_number, direction, entry_dt, exit_signal, is_open,
                  net_pnl_pct, est_cost_pct, est_net_pct
           FROM backtest_trades WHERE strategy_label=? ORDER BY trade_number"""
    return [{"trade_number": r[0], "direction": r[1], "entry_dt": r[2],
             "exit_signal": r[3], "is_open": r[4], "net_pnl_pct": r[5],
             "est_cost_pct": r[6], "est_net_pct": r[7], "anomaly": None}
            for r in cur.execute(q, (label,))]


def cum_series(values):
    out, s = [], 0.0
    for v in values:
        s += v
        out.append(round(s, 3))
    return out


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "backend/backtest_signal_history.sqlite3"
    conn = sqlite3.connect(db)
    cur = conn.cursor()

    strategies = []
    for label in ["BSE", "CDSL", "ANGELONE"]:
        trades = rows_for(cur, label)
        closed = [t for t in trades if t["is_open"] == 0 and t["net_pnl_pct"] is not None]
        a = base.analyze(trades, label, 1_500_000)
        dr = cur.execute("SELECT min(entry_dt), max(entry_dt) FROM backtest_trades WHERE strategy_label=?",
                         (label,)).fetchone()
        gross_series = cum_series([t["net_pnl_pct"] for t in closed])           # TV % (gross of real charges)
        net_series = cum_series([t["est_net_pct"] for t in closed if t["est_net_pct"] is not None])
        lt, llabel, ldisc = LIVE_STATE[label]
        strategies.append({
            "key": label.lower(),
            "instrument": label,
            "display_name": DISPLAY[label],
            "backtest": {
                "track_type": "BACKTEST_IN_SAMPLE",
                "label": "Backtest (in-sample)",
                "disclaimer": BACKTEST_DISCLAIMER,
                "strategy_version": "v4.8.1",
                "source": "tv_trade_list",
                "in_sample_range": {"from": dr[0][:7], "to": dr[1][:7]},
                "metrics": {
                    "closed_trades": a["n_closed"],
                    "open_excluded": a["n_open"],
                    "wins": a["wins"], "losses": a["losses"], "flats": a["flats"],
                    "win_rate_pct": round(a["win_rate"], 2),
                    "avg_gross_pct_per_trade": round(a["avg_g"], 3),
                    "avg_net_pct_per_trade": round(a["avg_net"], 3),
                    "median_net_pct_per_trade": round(a["median_net"], 3),
                    "best_trade_pct": round(a["best"], 2),
                    "worst_trade_pct": round(a["worst"], 2),
                    "profit_factor": round(a["pf"], 3),
                    "longest_losing_streak": a["longest_loss_streak"],
                    "max_drawdown_pct": round(a["mdd_gross"], 2),
                },
                "cumulative_series": {
                    "basis": "non_compounded_constant_unit_sum_of_per_trade_pct",
                    "note": ("Running SUM of per-trade % on a constant 1-unit. NOT compounded, "
                             "NOT a return — for chart SHAPE only. Endpoint is a large sum and "
                             "must NOT be presented as a percentage return."),
                    "order": "chronological_by_trade_number_closed_only",
                    "cum_gross_pct": gross_series,
                    "cum_net_pct": net_series,
                },
            },
            "live_status": {
                "track_type": lt, "label": llabel, "disclaimer": ldisc,
                "note": ("Live/forward/paper record is served separately by the read-only live "
                         "endpoint and shown honestly even when thin/empty. Not merged with backtest."),
            },
        })
    conn.close()

    doc = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "kind": "DRAFT — review-only showcase display data",
            "strategy_version": "v4.8.1",
            "source": "tv_trade_list",
            "store": "isolated SQLite backtest_trades (read-only)",
            "drawdown_basis": "non_compounded_constant_notional",
            "cost_model": {"estimated": True, "segment": "NFO",
                           "basis": "fixed representative notional -> size-independent cost %",
                           "est_cost_pct_per_round_trip": 0.030,
                           "note": "Charges only — slippage/impact excluded. Published-rate model; no INR P&L."},
            "excluded_artifacts": ["compounded_cumulative", "inr_pnl", "position_qty", "position_value"],
            "caveats": [
                "IN-SAMPLE backtests — not a guarantee of future results.",
                "Charges only, NOT slippage; real slippage would reduce the net edge.",
                "No out-of-sample / walk-forward validation; curve-fit risk applies.",
                "Backtest is not a track record. Live/forward/paper records are separate.",
                "ANGELONE is PAPER — no live real-money deployment.",
                "Compounded totals are forbidden and never present in this file.",
            ],
        },
        "strategies": strategies,
    }

    out = "backend/scripts/showcase_backtest.json"
    with open(out, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"wrote {out}  ({os.path.getsize(out)//1024} KB)")
    for s in strategies:
        m = s["backtest"]["metrics"]
        cs = s["backtest"]["cumulative_series"]
        print(f"  {s['instrument']:8} live={s['live_status']['track_type']:11} "
              f"closed={m['closed_trades']:4} win={m['win_rate_pct']}% net/trade={m['avg_net_pct_per_trade']}% "
              f"maxDD={m['max_drawdown_pct']}% series_pts={len(cs['cum_net_pct'])} "
              f"(net endpoint {cs['cum_net_pct'][-1]})")


if __name__ == "__main__":
    main()

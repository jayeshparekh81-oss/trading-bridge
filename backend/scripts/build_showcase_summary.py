#!/usr/bin/env python3
"""Generate backend/scripts/SHOWCASE_BACKTEST_SUMMARY.md — a consolidated, HONEST,
size-independent backtest summary for BSE / CDSL / ANGELONE, read from the
isolated SQLite store (source of truth). Reuses the EXACT metric logic of
ingest_backtest_trade_list.analyze().

Honesty doctrine: NO compounded/cumulative totals. Size-independent per-trade
metrics only. Backtest = labelled in-sample, NOT a guarantee. ANGELONE = paper.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest_backtest_trade_list as base

STRATS = ["BSE", "CDSL", "ANGELONE"]
LABELS = {  # honest deployment context for the showcase (read-only facts)
    "BSE": "live-real strategy (89423ecc) — separately verified; backtest is in-sample",
    "CDSL": "live-real strategy (0252e82c) — separately verified; backtest is in-sample",
    "ANGELONE": "PAPER candidate — no live real-money deployment; backtest is in-sample",
}


def rows_for(cur, label):
    q = """SELECT trade_number, direction, entry_dt, exit_signal, is_open,
                  net_pnl_pct, est_cost_pct, est_net_pct
           FROM backtest_trades WHERE strategy_label=? ORDER BY trade_number"""
    out = []
    for r in cur.execute(q, (label,)):
        out.append({
            "trade_number": r[0], "direction": r[1], "entry_dt": r[2],
            "exit_signal": r[4] if False else r[3], "is_open": r[4],
            "net_pnl_pct": r[5], "est_cost_pct": r[6], "est_net_pct": r[7],
            "anomaly": None,
        })
    return out


def date_range(cur, label):
    r = cur.execute("SELECT min(entry_dt), max(entry_dt) FROM backtest_trades WHERE strategy_label=?",
                    (label,)).fetchone()
    return r[0], r[1]


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "backend/backtest_signal_history.sqlite3"
    notional = 1_500_000
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    analyses = {}
    ranges = {}
    for s in STRATS:
        analyses[s] = base.analyze(rows_for(cur, s), s, notional)
        ranges[s] = date_range(cur, s)
    conn.close()

    def cell(a, key, fmt):
        v = a.get(key)
        return "n/a" if v is None else fmt.format(v)

    lines = []
    lines.append("# TRADETRI — Backtest Showcase Summary (HONEST, size-independent)\n")
    lines.append(f"_Generated {datetime.now(timezone.utc).date()} from the isolated backtest store "
                 f"(`backend/backtest_signal_history.sqlite3`, table `backtest_trades`). "
                 f"Strategy version **v4.8.1**, source `tv_trade_list`._\n")
    lines.append("> **These are IN-SAMPLE backtests, not a guarantee of future results.** "
                 "All figures are size-independent per-trade metrics. "
                 "TradingView's compounded cumulative (a %-of-equity-compounding + oversized-position "
                 "artifact) is **deliberately excluded everywhere** — it is fantasy and never surfaced.\n")

    # consolidated table
    lines.append("## Consolidated metrics\n")
    hdr = ["Metric", "BSE", "CDSL", "ANGELONE"]
    lines.append("| " + " | ".join(hdr) + " |")
    lines.append("|" + "---|" * len(hdr))

    def row(name, key, fmt):
        return "| " + name + " | " + " | ".join(cell(analyses[s], key, fmt) for s in STRATS) + " |"

    lines.append("| Instrument | NSE:BSE fut | NSE:CDSL fut | NSE:ANGELONE fut |")
    lines.append("| Deployment context | live-real* | live-real* | **PAPER** |")
    lines.append("| Date range (in-sample) | " + " | ".join(
        f"{ranges[s][0][:7]}→{ranges[s][1][:7]}" for s in STRATS) + " |")
    lines.append(row("Closed trades", "n_closed", "{:,}"))
    lines.append("| Open/unrealized (excluded) | " + " | ".join(str(analyses[s]["n_open"]) for s in STRATS) + " |")
    lines.append("| Wins / Losses / Flat | " + " | ".join(
        f"{analyses[s]['wins']}/{analyses[s]['losses']}/{analyses[s]['flats']}" for s in STRATS) + " |")
    lines.append(row("Win rate", "win_rate", "{:.2f}%"))
    lines.append(row("Avg per-trade (gross)", "avg_g", "{:+.3f}%"))
    lines.append(row("Median per-trade (gross)", "median_g", "{:+.3f}%"))
    lines.append("| Best / worst trade | " + " | ".join(
        f"{analyses[s]['best']:+.2f}% / {analyses[s]['worst']:+.2f}%" for s in STRATS) + " |")
    lines.append(row("Profit factor (Σwin% / |Σloss%|)", "pf", "{:.2f}"))
    lines.append(row("Longest losing streak", "longest_loss_streak", "{} trades"))
    lines.append(row("Max drawdown (non-compounded†)", "mdd_gross", "{:.2f}%"))
    lines.append(row("Avg est. cost / round-trip", "avg_cost", "{:+.3f}%"))
    lines.append(row("Avg per-trade (NET of est. cost)", "avg_net", "{:+.3f}%"))
    lines.append("")

    # footnotes / labelling
    lines.append("\\* **live-real**: BSE/CDSL are deployed live-real-money strategies; their *live track record* "
                 "is a SEPARATE artifact (read-only from the live system) and is NOT shown here. This table is "
                 "their **backtest** only. ANGELONE has **no** live deployment — paper/backtest only.\n")
    lines.append("† **Max drawdown basis (stated):** NON-compounded, **constant notional** per trade — "
                 "per-trade % returns are *added* (not compounded) onto an equity normalized to 1.0. "
                 "This is NOT %-of-equity compounding. It deliberately avoids the oversized-position artifact.\n")
    lines.append("‡ **Cost basis:** the existing Indian F&O cost model (`pnl_reconciler/costs.py`, **NFO** segment) "
                 f"at a fixed notional ₹{notional:,}/round-trip, 2 orders. Costs are **ESTIMATED** "
                 "(published-rate model, not broker contract-note) — STT-dominated, ~0.03%/round-trip.\n")

    # caveats
    lines.append("## Mandatory caveats (read before trusting any number)\n")
    lines.append("- **In-sample.** These are each strategy's own historical signals — no out-of-sample / "
                 "walk-forward validation. Curve-fit / over-optimization risk applies.")
    lines.append("- **Charges only — NOT slippage.** The cost model covers exchange/tax/brokerage charges. "
                 "Real **slippage/market-impact** on a ₹15L single-stock-futures order is typically *larger* than "
                 "the charges and would reduce the net edge. TradingView fills at the exact signal price.")
    lines.append("- **No walk-forward / no regime split.** Performance is not segmented by market regime; a single "
                 "blended edge can hide regime-dependent behaviour.")
    lines.append("- **TV 'Net PnL %' treated as gross** of real charges (assumes the Pine backtest ran "
                 "commission/slippage ≈ 0, standard for signal research).")
    lines.append("- **ANGELONE is PAPER.** No live real-money track record exists for it. It must be labelled "
                 "**PAPER / backtest-only** anywhere it is shown — never implied as live or verified.")
    lines.append("- **Backtest ≠ live.** A backtest is a hypothesis about edge, not a track record. BSE/CDSL live "
                 "results are a separate, read-only artifact and are not represented in this table.")
    lines.append("- **Compounded totals are forbidden.** The TradingView compounded cumulative (BSE 109,001%, "
                 "CDSL 3,470%, ANGELONE 16,242%) is an un-executable artifact and is never computed or shown.\n")

    out_path = "backend/scripts/SHOWCASE_BACKTEST_SUMMARY.md"
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out_path}")
    # also echo the key table to stdout for the overnight log
    for s in STRATS:
        a = analyses[s]
        print(f"  {s:8} closed={a['n_closed']:5} win={a['win_rate']:.1f}% avg_g={a['avg_g']:+.3f}% "
              f"avg_net={a['avg_net']:+.3f}% PF={a['pf']:.2f} maxDD={a['mdd_gross']:.2f}% "
              f"streak={a['longest_loss_streak']} open={a['n_open']}")


if __name__ == "__main__":
    main()

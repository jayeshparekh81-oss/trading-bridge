#!/usr/bin/env python3
"""Parse TradingView 'List of trades' CSVs (v4.8.1 BSE + CDSL) into the ISOLATED
backtest store and compute an HONEST, SIZE-INDEPENDENT edge analysis.

ISOLATION / HONESTY (read first):
  * Writes ONLY to the standalone SQLite store (same file as the signal history).
    NEVER touches the app Postgres / live strategies / positions / final_pnl.
  * Every row tagged is_backtest=1, is_live=0, source='tv_trade_list',
    strategy_version='v4.8.1'. strategy_label ('BSE'/'CDSL') is a LABEL, not an FK.
  * DELIBERATELY DROPS TradingView's compounded artifacts: 'Size (qty)',
    'Size (value)', 'Net PnL INR', and the compounded 'Cumulative PnL %/INR'
    (BSE 109,001% / CDSL 3,470%). Those are a %-of-equity-compounding +
    oversized-position artifact (un-executable) and are never stored or surfaced.
  * Works in SIZE-INDEPENDENT terms only: per-trade 'Net PnL %', a non-compounded
    constant-notional equity curve, and an ESTIMATED NFO cost stack.
  * NO compounded total is computed or displayed.

Reuses the EXISTING Indian F&O cost model (app/domains/pnl_reconciler/costs.py),
loaded by file path so the app package is not imported.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from decimal import Decimal

TABLE = "backtest_trades"
NFO = "NFO"
ORDERS_PER_TRIP = 2  # 1 entry leg + 1 exit leg (clean backtest round trip)


def load_cost_model(repo_root: str):
    path = os.path.join(repo_root, "backend/app/domains/pnl_reconciler/costs.py")
    spec = importlib.util.spec_from_file_location("_costs", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # py3.9 dataclass needs the module registered
    spec.loader.exec_module(mod)
    return mod


CREATE_SQL = f"""
CREATE TABLE {TABLE} (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_label    TEXT    NOT NULL,           -- 'BSE' | 'CDSL' (label, not FK)
    strategy_version  TEXT    NOT NULL,           -- 'v4.8.1'
    source            TEXT    NOT NULL,           -- 'tv_trade_list'
    is_backtest       INTEGER NOT NULL DEFAULT 1,
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    is_live           INTEGER NOT NULL DEFAULT 0,
    trade_number      INTEGER NOT NULL,
    direction         TEXT    NOT NULL,           -- 'long' | 'short'
    entry_dt          TEXT    NOT NULL,
    exit_dt           TEXT,
    entry_price       REAL    NOT NULL,
    exit_price        REAL,
    entry_signal      TEXT,
    exit_signal       TEXT,
    net_pnl_pct       REAL,                        -- TV per-trade % (gross of real charges)
    fav_excursion_pct REAL,
    adv_excursion_pct REAL,
    is_open           INTEGER NOT NULL DEFAULT 0,  -- 1 = unrealized (exit signal 'Open')
    est_cost_pct      REAL,                        -- ESTIMATED NFO cost at fixed notional
    est_net_pct       REAL,                        -- net_pnl_pct - est_cost_pct
    cost_estimated    INTEGER NOT NULL DEFAULT 1,
    source_file       TEXT,
    ingested_at       TEXT    NOT NULL
);
"""

COLS = [
    "strategy_label", "strategy_version", "source", "is_backtest", "is_simulated",
    "is_live", "trade_number", "direction", "entry_dt", "exit_dt", "entry_price",
    "exit_price", "entry_signal", "exit_signal", "net_pnl_pct", "fav_excursion_pct",
    "adv_excursion_pct", "is_open", "est_cost_pct", "est_net_pct", "cost_estimated",
    "source_file", "ingested_at",
]


def fnum(s):
    s = (s or "").strip().replace(",", "")
    return float(s) if s not in ("", "—", "-") else None


def parse_file(path, label, costs, notional, ingested_at):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    by_trade = {}
    for r in rows:
        by_trade.setdefault(int(r["Trade number"]), []).append(r)

    trades = []
    for tnum, rs in sorted(by_trade.items()):
        entry = next((x for x in rs if x["Type"].startswith("Entry")), None)
        exit_ = next((x for x in rs if x["Type"].startswith("Exit")), None)
        if entry is None:
            trades.append({"trade_number": tnum, "anomaly": "no-entry-row"})
            continue
        direction = "long" if entry["Type"].endswith("long") else "short"
        exit_sig = (exit_["Signal"].strip() if exit_ else None)
        is_open = 1 if exit_sig == "Open" else 0
        ep = fnum(entry["Price INR"])
        xp = fnum(exit_["Price INR"]) if exit_ else None
        gross_pct = fnum(exit_["Net PnL %"]) if exit_ else fnum(entry["Net PnL %"])

        # --- ESTIMATED NFO cost at a FIXED NOTIONAL (size-independent) ---
        est_cost_pct = None
        if ep and xp and notional:
            N = Decimal(str(notional))
            ratio = Decimal(str(xp)) / Decimal(str(ep))
            if direction == "long":
                buy_t, sell_t = N, N * ratio          # buy@entry, sell@exit
            else:
                sell_t, buy_t = N, N * ratio          # sell@entry, buy@exit
            cb = costs.compute_costs(buy_turnover=buy_t, sell_turnover=sell_t,
                                     orders=ORDERS_PER_TRIP, segment=NFO)
            est_cost_pct = float(cb.total / N * 100)
        est_net_pct = (gross_pct - est_cost_pct) if (gross_pct is not None and est_cost_pct is not None) else None

        trades.append({
            "strategy_label": label, "strategy_version": "v4.8.1",
            "source": "tv_trade_list", "is_backtest": 1, "is_simulated": 1, "is_live": 0,
            "trade_number": tnum, "direction": direction,
            "entry_dt": entry["Date and time"].strip(),
            "exit_dt": exit_["Date and time"].strip() if exit_ else None,
            "entry_price": ep, "exit_price": xp,
            "entry_signal": entry["Signal"].strip(), "exit_signal": exit_sig,
            "net_pnl_pct": gross_pct,
            "fav_excursion_pct": fnum(exit_["Favorable excursion %"]) if exit_ else None,
            "adv_excursion_pct": fnum(exit_["Adverse excursion %"]) if exit_ else None,
            "is_open": is_open, "est_cost_pct": est_cost_pct, "est_net_pct": est_net_pct,
            "cost_estimated": 1, "source_file": os.path.basename(path),
            "ingested_at": ingested_at, "anomaly": None,
        })
    return trades


def analyze(trades, label, notional):
    closed = [t for t in trades if not t.get("anomaly") and t["is_open"] == 0 and t["net_pnl_pct"] is not None]
    open_t = [t for t in trades if t.get("is_open") == 1]
    anomalies = [t for t in trades if t.get("anomaly")]

    g = [t["net_pnl_pct"] for t in closed]          # gross per-trade %
    wins = [x for x in g if x > 0]
    losses = [x for x in g if x < 0]
    flats = [x for x in g if x == 0]

    # longest losing streak (consecutive <0), chronological
    streak = best_streak = 0
    for x in g:
        if x < 0:
            streak += 1; best_streak = max(best_streak, streak)
        else:
            streak = 0

    pf = (sum(wins) / abs(sum(losses))) if losses else float("inf")

    # non-compounded, constant-notional equity curve: E_k = 1 + cumsum(r)
    def max_dd(series_pct):
        eq = 1.0; peak = 1.0; mdd = 0.0; cum = 0.0; trough_at = 0
        for i, x in enumerate(series_pct):
            cum += x / 100.0
            eq = 1.0 + cum
            peak = max(peak, eq)
            dd = (peak - eq) / peak
            if dd > mdd:
                mdd = dd; trough_at = i
        return mdd * 100.0, cum * 100.0, trough_at  # maxDD%, final non-compounded sum%, idx

    mdd_g, sum_g, dd_idx = max_dd(g)
    net = [t["est_net_pct"] for t in closed if t["est_net_pct"] is not None]
    mdd_n, sum_n, _ = max_dd(net) if net else (None, None, None)
    cost = [t["est_cost_pct"] for t in closed if t["est_cost_pct"] is not None]

    return {
        "label": label, "n_closed": len(closed), "n_open": len(open_t),
        "anomalies": anomalies, "open_trades": open_t,
        "wins": len(wins), "losses": len(losses), "flats": len(flats),
        "win_rate": len(wins) / len(closed) * 100,
        "avg_g": statistics.mean(g), "median_g": statistics.median(g),
        "best": max(g), "worst": min(g),
        "pf": pf, "longest_loss_streak": best_streak,
        "mdd_gross": mdd_g, "sum_gross": sum_g, "dd_idx": dd_idx,
        "avg_cost": statistics.mean(cost) if cost else None,
        "avg_net": statistics.mean(net) if net else None,
        "median_net": statistics.median(net) if net else None,
        "mdd_net": mdd_n, "sum_net": sum_n,
        "net_wins": sum(1 for x in net if x > 0), "net_losses": sum(1 for x in net if x < 0),
        "pf_net": (sum(x for x in net if x > 0) / abs(sum(x for x in net if x < 0))) if any(x < 0 for x in net) else float("inf"),
        "notional": notional,
    }


def store(conn, all_trades):
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
    cur.executescript(CREATE_SQL)
    cur.execute(f"CREATE INDEX idx_{TABLE}_strat ON {TABLE}(strategy_label)")
    ins = [t for t in all_trades if not t.get("anomaly")]
    cur.executemany(
        f"INSERT INTO {TABLE} ({','.join(COLS)}) VALUES ({','.join(['?']*len(COLS))})",
        [tuple(t.get(c) for c in COLS) for t in ins],
    )
    conn.commit()
    return len(ins)


def pct(x):
    return "n/a" if x is None else f"{x:+.3f}%"


def report(a):
    print(f"\n================  {a['label']}  (v4.8.1, NFO)  ================")
    print(f"  closed trades        : {a['n_closed']}   (wins {a['wins']} / losses {a['losses']} / flat {a['flats']})")
    print(f"  open/unrealized      : {a['n_open']}  -> {[(t['trade_number'], t['exit_signal'], t['net_pnl_pct']) for t in a['open_trades']] or 'none'}")
    if a["anomalies"]:
        print(f"  ANOMALIES            : {[(t['trade_number'], t['anomaly']) for t in a['anomalies']]}")
    print(f"  -- 1. EDGE (size-independent, per-trade Net PnL %) --")
    print(f"  win rate             : {a['win_rate']:.2f}%")
    print(f"  avg / median per-trade: {pct(a['avg_g'])} / {pct(a['median_g'])}")
    print(f"  best / worst trade   : {pct(a['best'])} / {pct(a['worst'])}")
    print(f"  profit factor (gross%): {a['pf']:.3f}   (Σwin% / |Σloss%|)")
    print(f"  longest losing streak: {a['longest_loss_streak']} trades")
    print(f"  -- 2. DRAWDOWN (NON-compounded, constant notional; equity=1.0 base, returns ADDED) --")
    print(f"  max drawdown (gross) : {a['mdd_gross']:.2f}%   (of running peak of the 1+Σr curve)")
    print(f"  equity-curve endpoint: 1.000 -> {1 + a['sum_gross']/100:.3f}  (Σ per-trade % = {a['sum_gross']:+.1f}%, NON-compounded)")
    print(f"  -- 3. COST IMPACT (ESTIMATED NFO @ fixed notional ₹{a['notional']:,}/trip, {ORDERS_PER_TRIP} orders) --")
    print(f"  avg est cost / trip  : {pct(a['avg_cost'])}   [ESTIMATED — rate model, not contract-note]")
    print(f"  avg GROSS / trade    : {pct(a['avg_g'])}")
    print(f"  avg NET   / trade    : {pct(a['avg_net'])}   (gross - est cost)")
    print(f"  median NET / trade   : {pct(a['median_net'])}")
    print(f"  net win/loss         : {a['net_wins']} / {a['net_losses']}   profit factor(net%): {a['pf_net']:.3f}")
    print(f"  max drawdown (net)   : {a['mdd_net']:.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bse", required=True)
    ap.add_argument("--cdsl", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--notional", type=int, default=1_500_000,
                    help="fixed notional ₹/trade for cost%% (≈1 BSE lot at recent price)")
    args = ap.parse_args()

    low = args.db.lower()
    if "://" in low or low.startswith(("postgres", "mysql")):
        raise SystemExit("Refusing: --db must be a local SQLite path, not a DSN.")

    costs = load_cost_model(args.repo_root)
    ingested_at = datetime.now(timezone.utc).isoformat()

    bse = parse_file(args.bse, "BSE", costs, args.notional, ingested_at)
    cdsl = parse_file(args.cdsl, "CDSL", costs, args.notional, ingested_at)

    conn = sqlite3.connect(args.db)
    try:
        n = store(conn, bse + cdsl)
    finally:
        conn.close()
    print(f"stored {n} backtest trades into {args.db} (table {TABLE})")

    report(analyze(bse, "BSE", args.notional))
    report(analyze(cdsl, "CDSL", args.notional))
    print("\n[NOTE] TV 'Net PnL %' is treated as GROSS of real charges (Pine commission≈0).")
    print("[NOTE] Compounded cumulative (BSE 109,001% / CDSL 3,470%) intentionally NOT computed/stored.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Append ANGELONE (NSE:ANGELONE single-stock futures) TradingView trade-list
into the ISOLATED backtest store, reusing ingest_backtest_trade_list's EXACT
parse + NFO cost pattern.

APPEND-ONLY: never DROPs or re-ingests the existing BSE/CDSL rows. Idempotent —
re-running refreshes ONLY the ANGELONE rows (BSE/CDSL left byte-untouched).

Tags (per Jayesh's overnight spec): source='tv_trade_list',
strategy_version='v4.8.1', broker='ANGELONE', is_backtest=1, is_live=0,
is_paper=1.

Honesty doctrine: stores ONLY size-independent per-trade fields. Deliberately
EXCLUDES TradingView's two Cumulative PnL columns and all qty/value/Net-PnL-INR
artifacts (handled by the reused parse_file, which never reads them).

NOTE: writes ONLY to the standalone SQLite store — never the app Postgres, never
the live strategies/positions. 'is_paper' here is a backtest-store LABEL, wholly
unrelated to the live strategies.is_paper flag.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest_backtest_trade_list as base  # reuse the EXACT parse + cost pattern

TABLE = base.TABLE  # 'backtest_trades'
EXTRA_COLS = ["broker", "is_paper"]


def ensure_columns(cur):
    existing = {d[1] for d in cur.execute(f"PRAGMA table_info({TABLE})")}
    added = []
    if "broker" not in existing:
        cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN broker TEXT")
        added.append("broker")
    if "is_paper" not in existing:
        cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN is_paper INTEGER")
        added.append("is_paper")
    return added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--notional", type=int, default=1_500_000)
    args = ap.parse_args()

    low = args.db.lower()
    if "://" in low or low.startswith(("postgres", "mysql")):
        raise SystemExit("Refusing: --db must be a local SQLite path, not a DSN.")
    if not os.path.isfile(args.db):
        raise SystemExit(f"Store not found (expected existing isolated DB): {args.db}")
    if not os.path.isfile(args.csv):
        raise SystemExit(f"CSV not found: {args.csv}")

    costs = base.load_cost_model(args.repo_root)
    ingested_at = datetime.now(timezone.utc).isoformat()

    trades = base.parse_file(args.csv, "ANGELONE", costs, args.notional, ingested_at)
    recs = [t for t in trades if not t.get("anomaly")]
    anomalies = [t for t in trades if t.get("anomaly")]
    for t in recs:
        t["broker"] = "ANGELONE"
        t["is_paper"] = 1

    conn = sqlite3.connect(args.db)
    try:
        cur = conn.cursor()
        before = {r[0]: r[1] for r in cur.execute(
            f"SELECT strategy_label, count(*) FROM {TABLE} GROUP BY strategy_label")}
        if TABLE not in {r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            raise SystemExit(f"Refusing: table {TABLE} not present — run base ingest first.")

        added = ensure_columns(cur)
        existing_ang = cur.execute(
            f"SELECT count(*) FROM {TABLE} WHERE strategy_label='ANGELONE'").fetchone()[0]
        if existing_ang:  # idempotent: refresh ANGELONE only
            cur.execute(f"DELETE FROM {TABLE} WHERE strategy_label='ANGELONE'")

        cols = base.COLS + EXTRA_COLS
        cur.executemany(
            f"INSERT INTO {TABLE} ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
            [tuple(t.get(c) for c in cols) for t in recs],
        )
        conn.commit()
        after = {r[0]: r[1] for r in cur.execute(
            f"SELECT strategy_label, count(*) FROM {TABLE} GROUP BY strategy_label")}
    finally:
        conn.close()

    longs = sum(1 for t in recs if t["direction"] == "long")
    shorts = sum(1 for t in recs if t["direction"] == "short")
    n_open = sum(1 for t in recs if t["is_open"] == 1)

    print("================  ANGELONE append summary  ================")
    print(f"  csv                  : {os.path.basename(args.csv)}")
    print(f"  columns added        : {added or 'none (already present)'}")
    print(f"  parsed ANGELONE      : {len(recs)} trades  (long {longs} / short {shorts} / open {n_open})")
    print(f"  anomalies (skipped)  : {[(t['trade_number'], t['anomaly']) for t in anomalies] or 'none'}")
    print(f"  ANGELONE before/after: {existing_ang} -> {after.get('ANGELONE')}")
    print(f"  BSE   unchanged?     : {before.get('BSE')} -> {after.get('BSE')}  {'OK' if before.get('BSE')==after.get('BSE') else 'CHANGED!!'}")
    print(f"  CDSL  unchanged?     : {before.get('CDSL')} -> {after.get('CDSL')}  {'OK' if before.get('CDSL')==after.get('CDSL') else 'CHANGED!!'}")
    print(f"  tags                 : source=tv_trade_list version=v4.8.1 broker=ANGELONE "
          f"is_backtest=1 is_live=0 is_paper=1")
    print(f"  store                : {args.db} (isolated SQLite — no prod/app-DB touch)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

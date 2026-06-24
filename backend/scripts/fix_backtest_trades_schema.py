#!/usr/bin/env python3
"""Apply Jayesh's approved fixes to the ISOLATED backtest store (SQLite only).

1. Rename column  broker -> instrument  (holds the NSE instrument name
   BSE / CDSL / ANGELONE — NOT a brokerage). Backfilled = strategy_label for all
   rows (a factual mapping, not a guess: the instrument for 'BSE'-labelled rows
   is 'BSE').
2. is_paper -> NULL on ALL backtest rows. A backtest is neither paper nor real;
   ANGELONE's earlier is_paper=1 is cleared too. BSE/CDSL are NOT backfilled as
   live-real (their live status is a separate, live-record concern, not a
   property of backtest rows).

Idempotent. Writes ONLY to the isolated SQLite — never the app Postgres / live
strategies. Prints before/after schema.
"""
from __future__ import annotations

import sqlite3
import sys

TABLE = "backtest_trades"


def schema(cur):
    return [(d[1], d[2]) for d in cur.execute(f"PRAGMA table_info({TABLE})")]


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "backend/backtest_signal_history.sqlite3"
    low = db.lower()
    if "://" in low or low.startswith(("postgres", "mysql")):
        raise SystemExit("Refusing: must be a local SQLite path, not a DSN.")
    conn = sqlite3.connect(db)
    try:
        cur = conn.cursor()
        cols = {c for c, _ in schema(cur)}
        print("BEFORE:", [c for c, _ in schema(cur)])

        # 1. broker -> instrument (rename if needed)
        if "broker" in cols and "instrument" not in cols:
            cur.execute(f"ALTER TABLE {TABLE} RENAME COLUMN broker TO instrument")
        elif "instrument" not in cols:  # neither present (shouldn't happen)
            cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN instrument TEXT")
        # backfill instrument = strategy_label (factual; column now holds NSE names)
        cur.execute(f"UPDATE {TABLE} SET instrument = strategy_label")

        # 2. is_paper -> NULL on ALL backtest rows
        cur.execute(f"UPDATE {TABLE} SET is_paper = NULL")

        conn.commit()
        print("AFTER :", [c for c, _ in schema(cur)])
        print("\nper-strategy instrument / is_paper after fix:")
        for r in cur.execute(
            f"SELECT strategy_label, group_concat(DISTINCT instrument) instr, "
            f"group_concat(DISTINCT COALESCE(is_paper,'NULL')) paper, count(*) n "
            f"FROM {TABLE} GROUP BY strategy_label"
        ):
            print(f"  {r[0]:8} instrument={r[1]:8} is_paper={r[2]:5} n={r[3]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

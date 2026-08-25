#!/usr/bin/env python3
"""Ingest a Pine alert-signal CSV export into a STANDALONE, ISOLATED SQLite
backtest signal-history store.

SAFETY / ISOLATION (read first):
  * This script NEVER connects to the application Postgres database.
  * It writes ONLY to a standalone SQLite file (default:
    backend/backtest_signal_history.sqlite3, which is git-ignored).
  * The data is BACKTEST / SIMULATED signal history. Every row is tagged
    source='backtest_signal_log' and flagged is_backtest=1 / is_simulated=1 /
    is_live=0.
  * strategy_label is a LABEL ONLY (default 'BSE'). It is NOT a foreign key and
    deliberately does NOT reference the live real-money strategy (89423ecc) or
    any live strategy / position / final_pnl record.
  * NO P&L is computed or stored. This is an entries-only log (no exit/stop
    signals), so per-trade P&L is not accurately derivable. Signal + feature
    data only.
  * Reversible: delete the SQLite file (or DROP TABLE backtest_signal_history).

Re-runnable / idempotent: drops & recreates the table, then re-ingests the CSV.

Usage:
    python3 backend/scripts/ingest_backtest_signal_log.py \
        --csv "/path/to/pine-logs ... .csv" \
        --db  backend/backtest_signal_history.sqlite3 \
        --strategy-label BSE
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime, timezone

TABLE = "backtest_signal_history"

# message-key -> column. Main (AI_LONG / AI_SHORT) payload half.
MAIN_FIELDS = {
    "Price": "price",
    "RSI": "rsi",
    "ATR": "atr",
    "RVOL": "rvol",
    "Delta": "delta",
}
# message-key -> column. Paired _MORE payload half (same timestamp).
MORE_FIELDS = {
    "GaussL": "gauss_l",
    "GaussS": "gauss_s",
    "DeltaPwr": "delta_pwr",
    "OFInten": "of_inten",
    "VWAPDist": "vwap_dist",
    "FastMA": "fast_ma",
    "SlowMA": "slow_ma",
    "LongMA": "long_ma",
    "BodyPct": "body_pct",
    "Squeeze": "squeeze",
    "PriceSpd": "price_spd",
    "BearGap": "bear_gap",
    "BullGap": "bull_gap",
    "IndiaVIX": "india_vix",
    "Vol": "vol",  # stored INTEGER; everything else REAL
}

CREATE_SQL = f"""
CREATE TABLE {TABLE} (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    -- provenance / isolation flags ------------------------------------------
    strategy_label    TEXT    NOT NULL,          -- LABEL ONLY, not an FK to any live strategy
    source            TEXT    NOT NULL,          -- 'backtest_signal_log'
    is_backtest       INTEGER NOT NULL DEFAULT 1,
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    is_live           INTEGER NOT NULL DEFAULT 0,
    is_verified_fill  INTEGER NOT NULL DEFAULT 0, -- never a real broker fill
    -- signal identity -------------------------------------------------------
    signal_ts         TEXT    NOT NULL,          -- ISO8601 w/ +05:30 (from CSV Date col)
    signal_ts_utc     TEXT    NOT NULL,          -- normalized UTC
    direction         TEXT    NOT NULL,          -- 'long' | 'short'
    raw_signal_type   TEXT    NOT NULL,          -- 'AI_LONG' | 'AI_SHORT'
    pine_date_field   TEXT,                      -- 'Date:' echoed inside the main message
    -- main payload features -------------------------------------------------
    price             REAL,
    rsi               REAL,
    atr               REAL,
    rvol              REAL,
    delta             REAL,
    -- _MORE payload features ------------------------------------------------
    gauss_l           REAL,
    gauss_s           REAL,
    delta_pwr         REAL,
    of_inten          REAL,
    vwap_dist         REAL,
    fast_ma           REAL,
    slow_ma           REAL,
    long_ma           REAL,
    body_pct          REAL,
    squeeze           REAL,
    price_spd         REAL,
    bear_gap          REAL,
    bull_gap          REAL,
    india_vix         REAL,
    vol               INTEGER,
    -- raw provenance (Glass Box) -------------------------------------------
    raw_message_main  TEXT,
    raw_message_more  TEXT,
    source_file       TEXT,
    ingested_at       TEXT    NOT NULL
);
"""

COLUMNS = [
    "strategy_label", "source", "is_backtest", "is_simulated", "is_live",
    "is_verified_fill", "signal_ts", "signal_ts_utc", "direction",
    "raw_signal_type", "pine_date_field",
    "price", "rsi", "atr", "rvol", "delta",
    "gauss_l", "gauss_s", "delta_pwr", "of_inten", "vwap_dist", "fast_ma",
    "slow_ma", "long_ma", "body_pct", "squeeze", "price_spd", "bear_gap",
    "bull_gap", "india_vix", "vol",
    "raw_message_main", "raw_message_more", "source_file", "ingested_at",
]


def parse_message(message: str):
    """Split 'AI_LONG | Key: Val | ...' -> (head, {Key: Val})."""
    parts = [p.strip() for p in message.split("|")]
    head = parts[0]
    fields = {}
    for token in parts[1:]:
        if ":" not in token:
            continue
        key, val = token.split(":", 1)
        fields[key.strip()] = val.strip()
    return head, fields


def to_utc(iso_ts: str) -> str:
    """'2019-12-03T13:30:00.000+05:30' -> UTC ISO8601."""
    return (
        datetime.fromisoformat(iso_ts)
        .astimezone(timezone.utc)
        .isoformat()
    )


def num(val):
    if val is None or val == "":
        return None
    return float(val)


def load_rows(csv_path: str):
    """Return ordered list of {ts, head, base, kind, fields, raw}."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if [h.strip().lower() for h in header[:2]] != ["date", "message"]:
            raise SystemExit(f"Unexpected header: {header!r}")
        for raw in reader:
            if not raw or len(raw) < 2:
                continue
            ts = raw[0].strip()
            # message itself contains no commas, but rejoin defensively
            message = ",".join(raw[1:]).strip()
            head, fields = parse_message(message)
            is_more = head.endswith("_MORE")
            base = head[:-5] if is_more else head
            rows.append({
                "ts": ts,
                "head": head,
                "base": base,
                "kind": "more" if is_more else "main",
                "fields": fields,
                "raw": message,
            })
    return rows


def pair_signals(rows):
    """Pair each main row with its immediately-following _MORE row (same ts +
    same base type). Returns (pairs, problems)."""
    pairs = []
    problems = []
    current_main = None
    for r in rows:
        if r["kind"] == "main":
            if current_main is not None:
                problems.append(("main-without-more", current_main["ts"], current_main["head"]))
            current_main = r
        else:  # more
            if current_main is None:
                problems.append(("more-without-main", r["ts"], r["head"]))
                continue
            if r["ts"] != current_main["ts"] or r["base"] != current_main["base"]:
                problems.append(("mismatched-pair", current_main["ts"], r["ts"]))
                # still consume the main so we don't cascade
                current_main = None
                continue
            pairs.append((current_main, r))
            current_main = None
    if current_main is not None:
        problems.append(("main-without-more", current_main["ts"], current_main["head"]))
    return pairs, problems


def build_record(main, more, strategy_label, source_file, ingested_at):
    base = main["base"]  # AI_LONG / AI_SHORT
    direction = "long" if base == "AI_LONG" else "short" if base == "AI_SHORT" else "unknown"
    mf = main["fields"]
    rf = more["fields"]
    rec = {
        "strategy_label": strategy_label,
        "source": "backtest_signal_log",
        "is_backtest": 1,
        "is_simulated": 1,
        "is_live": 0,
        "is_verified_fill": 0,
        "signal_ts": main["ts"],
        "signal_ts_utc": to_utc(main["ts"]),
        "direction": direction,
        "raw_signal_type": base,
        "pine_date_field": mf.get("Date"),
        "raw_message_main": main["raw"],
        "raw_message_more": more["raw"],
        "source_file": source_file,
        "ingested_at": ingested_at,
    }
    for key, col in MAIN_FIELDS.items():
        rec[col] = num(mf.get(key))
    for key, col in MORE_FIELDS.items():
        v = num(rf.get(key))
        rec[col] = int(v) if (col == "vol" and v is not None) else v
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True, help="path to pine-logs CSV")
    ap.add_argument("--db", required=True, help="standalone SQLite file (NOT the app Postgres)")
    ap.add_argument("--strategy-label", default="BSE", help="LABEL only; not an FK")
    args = ap.parse_args()

    if not os.path.isfile(args.csv):
        raise SystemExit(f"CSV not found: {args.csv}")

    # Hard guard: refuse anything that looks like a Postgres/MySQL DSN.
    low = args.db.lower()
    if "://" in low or low.startswith(("postgres", "postgresql", "mysql")):
        raise SystemExit("Refusing: --db must be a local SQLite file path, not a DSN.")

    ingested_at = datetime.now(timezone.utc).isoformat()
    source_file = os.path.basename(args.csv)

    rows = load_rows(args.csv)
    mains = [r for r in rows if r["kind"] == "main"]
    mores = [r for r in rows if r["kind"] == "more"]
    pairs, problems = pair_signals(rows)

    records = [
        build_record(m, mo, args.strategy_label, source_file, ingested_at)
        for (m, mo) in pairs
    ]

    conn = sqlite3.connect(args.db)
    try:
        cur = conn.cursor()
        cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cur.executescript(CREATE_SQL)
        cur.execute(
            f"CREATE INDEX idx_{TABLE}_ts ON {TABLE}(signal_ts)"
        )
        cur.execute(
            f"CREATE INDEX idx_{TABLE}_dir ON {TABLE}(direction)"
        )
        placeholders = ",".join(["?"] * len(COLUMNS))
        cur.executemany(
            f"INSERT INTO {TABLE} ({','.join(COLUMNS)}) VALUES ({placeholders})",
            [tuple(rec.get(c) for c in COLUMNS) for rec in records],
        )
        conn.commit()
    finally:
        conn.close()

    longs = sum(1 for r in records if r["direction"] == "long")
    shorts = sum(1 for r in records if r["direction"] == "short")
    dup_keys = len(
        [1 for _ in records]
    ) - len({(r["signal_ts"], r["direction"]) for r in records})

    print("=== ingestion summary ===")
    print(f"csv                : {args.csv}")
    print(f"sqlite db          : {args.db}")
    print(f"raw data rows      : {len(rows)}  (main={len(mains)}, _MORE={len(mores)})")
    print(f"paired signals     : {len(pairs)}")
    print(f"inserted records   : {len(records)}")
    print(f"  long  (AI_LONG)  : {longs}")
    print(f"  short (AI_SHORT) : {shorts}")
    print(f"duplicate (ts,dir) : {dup_keys}")
    if records:
        print(f"date range (IST)   : {min(r['signal_ts'] for r in records)}  ->  {max(r['signal_ts'] for r in records)}")
    print(f"pairing problems   : {len(problems)}")
    for p in problems[:10]:
        print(f"   ! {p}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())

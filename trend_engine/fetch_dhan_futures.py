#!/usr/bin/env python3
"""Fetch continuous NEAR-MONTH index-FUTURES 5-min OHLCV (real volume) from Dhan.

Companion to ``fetch_dhan_history.py`` — reuses its auth, 90-day pagination,
backoff/retry, dedup, tz handling, quality-report and save code. The only new
logic here is: resolve the *live* index-future contracts (FUTIDX / NSE_FNO),
fetch each, and stitch a continuous near-month series by rolling on expiry.

Why: index *spot* has no traded volume (~all-zero), so RVOL / VWAP / volume-
expansion layers can't use it. Near-month futures carry real volume. Dhan only
serves the ~3 currently-listed monthly contracts (the master is forward-only —
see the futures probe), so this brings the trend-engine up on CORRECT data for
a *preliminary* baseline. It is NOT enough history to validate edge.

Writes data/NIFTY_FUT.parquet/.csv and data/BANKNIFTY_FUT.parquet/.csv, kept
separate from the index-spot files. Creds: env / gitignored .env (same as spot).

    python trend_engine/fetch_dhan_futures.py
    python trend_engine/fetch_dhan_futures.py --symbols NIFTY --days 95
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, date, datetime, time as dtime, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_dhan_history import (  # noqa: E402
    HERE,
    IST,
    Resolved,
    _download_scrip_master,
    fetch_5min,
    load_dotenv,
    quality_report,
    save,
)

# Dhan API enums for NSE index futures.
FNO_SEGMENT = "NSE_FNO"
FUT_INSTRUMENT = "FUTIDX"

# Sanity cross-check only (resolution is DYNAMIC; these are never used to fetch).
KNOWN_IDS = {
    "NIFTY": {"61093", "58072", "68407"},
    "BANKNIFTY": {"61088", "58067", "68390"},
}

SESSION_START = dtime(9, 15)
SESSION_END = dtime(15, 30)


# ── Resolve live futures contracts ─────────────────────────────────────────


def resolve_live_futures(df: pd.DataFrame, root: str, today: date) -> list[Resolved]:
    """All non-expired FUTIDX contracts for ``root``, sorted by expiry ascending.

    Each Resolved carries the contract's own securityId + tradingSymbol; the
    expiry date is stashed on ``source_name`` (ISO) so the roll logic can read it.
    """
    fut = df[df["SEM_INSTRUMENT_NAME"].astype(str) == "FUTIDX"].copy()
    tsym = fut["SEM_TRADING_SYMBOL"].astype(str)
    mine = fut[tsym.str.upper().str.startswith(root.upper() + "-")].copy()
    mine["expiry"] = pd.to_datetime(mine["SEM_EXPIRY_DATE"], errors="coerce")
    mine = mine[mine["expiry"].dt.date >= today].sort_values("expiry")

    out: list[Resolved] = []
    print(f"\n[resolve] {root}: live FUTIDX contracts (non-expired, sorted by expiry):")
    for _, r in mine.iterrows():
        sec_id = str(r["SEM_SMST_SECURITY_ID"]).strip()
        ts = str(r["SEM_TRADING_SYMBOL"]).strip()
        exp = r["expiry"].date()
        known = KNOWN_IDS.get(root, set())
        flag = "OK" if sec_id in known else "⚠ not in known set (verify)"
        print(f"[resolve]   {ts:<24} securityId={sec_id:<7} expiry={exp}  [{flag}]")
        out.append(
            Resolved(
                symbol=ts,
                security_id=sec_id,
                exchange_segment=FNO_SEGMENT,
                instrument=FUT_INSTRUMENT,
                source_trading_symbol=ts,
                source_name=exp.isoformat(),
            )
        )
    if not out:
        raise LookupError(f"no live FUTIDX contracts found for {root}")
    return out


# ── Continuous near-month roll-stitch ──────────────────────────────────────


def fetch_continuous_near_month(
    session: requests.Session,
    headers: dict,
    contracts: list[Resolved],
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Stitch a continuous near-month series: at each date use the nearest
    non-expired contract, rolling to the next on its expiry date.

    Each contract contributes only the bars in its *front-month window*
    ``(prev_expiry, this_expiry]`` — so far-month bars (thin volume) that a
    contract also trades while it's the back month are excluded.
    """
    frames: list[pd.DataFrame] = []
    prev_exp = start.date() - timedelta(days=1)  # first contract's window opens at `start`
    for c in contracts:
        exp = date.fromisoformat(c.source_name)
        # Fetch window: front-window ∩ overall [start, end]. Contract has no
        # data before it was listed / after expiry, so empty edges skip cleanly.
        fetch_start = max(start, datetime.combine(prev_exp + timedelta(days=1), dtime(0, 0), IST))
        fetch_end = min(end, datetime.combine(exp, SESSION_END, IST))
        if fetch_start > fetch_end:
            prev_exp = exp
            continue
        print(f"\n---- contract {c.source_trading_symbol} (front window {prev_exp + timedelta(days=1)} → {exp}) ----")
        df_c = fetch_5min(session, headers, c, fetch_start, fetch_end)
        if not df_c.empty:
            bd = df_c["timestamp"].dt.date
            front = df_c[(bd > prev_exp) & (bd <= exp)]
            print(f"     front-month bars kept: {len(front):,} / {len(df_c):,} fetched")
            frames.append(front)
        prev_exp = exp

    if not frames:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


# ── Strict session filter (fixes out-of-session leakage) ───────────────────


def session_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # Diagnostic: show the pre-filter hour spread so we can SEE any leakage /
    # tz mis-handling rather than silently dropping real bars.
    hours = df["timestamp"].dt.hour.value_counts().sort_index()
    print("  [session] pre-filter bars per hour (IST):")
    print("    " + "  ".join(f"{h:02d}:{n}" for h, n in hours.items()))
    t = df["timestamp"].dt.time
    kept = df[(t >= SESSION_START) & (t <= SESSION_END)].reset_index(drop=True)
    print(f"  [session] kept {len(kept):,} / {len(df):,} bars within {SESSION_START}–{SESSION_END} IST")
    return kept


# ── main ───────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch continuous near-month index-futures 5-min OHLCV from Dhan.")
    p.add_argument("--symbols", nargs="+", default=["NIFTY", "BANKNIFTY"], choices=["NIFTY", "BANKNIFTY"])
    p.add_argument("--days", type=int, default=95, help="lookback window (default ~90 days)")
    p.add_argument("--out", type=Path, default=HERE / "data")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    load_dotenv(HERE / ".env")
    end = datetime.now(UTC).replace(microsecond=0)
    start = end - timedelta(days=args.days)
    today = datetime.now(IST).date()
    print(f"range: {start.astimezone(IST).date()} → {end.astimezone(IST).date()} ({args.days}d)  interval=5m")
    print(f"symbols: {', '.join(args.symbols)}   out: {args.out}")

    df_master = _download_scrip_master()

    client_id = os.environ.get("DHAN_CLIENT_ID")
    access_token = os.environ.get("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token:
        print(
            "\nERROR: DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN must be set (env or "
            "trend_engine/.env). See trend_engine/.env.example.",
            file=sys.stderr,
        )
        return 2
    headers = {
        "client-id": client_id,
        "access-token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    rc = 0
    with requests.Session() as session:
        for root in args.symbols:
            contracts = resolve_live_futures(df_master, root, today)
            print(f"\n==== FETCH {root} near-month continuous ({len(contracts)} live contract(s)) ====")
            df = fetch_continuous_near_month(session, headers, contracts, start, end)
            df = session_filter(df)
            out_symbol = f"{root}_FUT"
            quality_report(out_symbol, df)
            if not df.empty:
                sample = df["volume"].tolist()
                print(f"  volume sample   : head {sample[:5]}  …  tail {sample[-5:]}")
                save(out_symbol, df, args.out)
            else:
                print(f"  {out_symbol}: empty — not written.")
                rc = 1
    print("\nDone.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""PROBE: can Dhan serve multi-year index-FUTURES intraday, incl. EXPIRED contracts?

Read-mostly reconnaissance for the trend-engine volume layers (RVOL/VWAP/vol
expansion) which the volume-less index *spot* series can't feed. Does NOT build
the roll-stitcher — it only reports what Dhan exposes.

Part A (no auth): list NIFTY/BANKNIFTY index-future contracts from the already
    -downloaded scrip master (instrument FUTIDX, NSE derivatives segment),
    sorted by expiry; report the earliest expiry present.
Part B (auth):    fetch a ~1-week 5-min window for one or more contracts via
    POST /v2/charts/intraday and report bar count, first/last ts, sample volume.
    Use --secid/--from/--to to probe an arbitrary (e.g. expired) contract.

Reuses helpers from fetch_dhan_history.py (same dir). Creds: env / gitignored
.env, same as the fetcher.

    python trend_engine/probe_futures.py                 # Part A + near-month probe if creds
    python trend_engine/probe_futures.py --list-only     # Part A only, never touches auth
    python trend_engine/probe_futures.py --secid 12345 --symbol NIFTY-Xxx-FUT \
        --from "2024-07-15 09:15:00" --to "2024-07-19 15:30:00"   # probe a specific contract
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_dhan_history import (  # noqa: E402
    DHAN_BASE_URL,
    HERE,
    INTRADAY_PATH,
    IST,
    HTTP_TIMEOUT_S,
    _download_scrip_master,
    _parse_response,
    load_dotenv,
)
import os  # noqa: E402

# Dhan API enum for NSE F&O; instrument label for index futures.
FNO_SEGMENT = "NSE_FNO"
FUT_INSTRUMENT = "FUTIDX"


# ── Part A: list index futures from the master (no auth) ───────────────────


def list_index_futures(df: pd.DataFrame) -> pd.DataFrame:
    fut = df[df["SEM_INSTRUMENT_NAME"].astype(str) == "FUTIDX"].copy()
    tsym = fut["SEM_TRADING_SYMBOL"].astype(str).str.upper()
    nb = fut[tsym.str.startswith("NIFTY-") | tsym.str.startswith("BANKNIFTY-")].copy()
    nb["expiry"] = pd.to_datetime(nb["SEM_EXPIRY_DATE"], errors="coerce")
    nb = nb.sort_values("expiry")

    print(f"\n──── PART A · NIFTY/BANKNIFTY index-future contracts in current master ({len(nb)}) ────")
    print(f"{'tradingSymbol':<24} {'securityId':>10} {'segment':>8}  expiry")
    for _, r in nb.iterrows():
        print(
            f"{str(r['SEM_TRADING_SYMBOL']):<24} {str(r['SEM_SMST_SECURITY_ID']):>10} "
            f"{str(r['SEM_SEGMENT']):>8}  {r['SEM_EXPIRY_DATE']}"
        )
    if not nb.empty:
        print(f"\n  EARLIEST expiry present : {nb['expiry'].min()}")
        print(f"  LATEST   expiry present : {nb['expiry'].max()}")
        print(f"  distinct expiries       : {sorted(nb['expiry'].dt.strftime('%Y-%m-%d').unique())}")
    return nb


# ── Part B: intraday probe for one contract (auth) ─────────────────────────


def probe_contract(
    session: requests.Session,
    headers: dict,
    label: str,
    security_id: str,
    from_str: str,
    to_str: str,
    segment: str = FNO_SEGMENT,
    instrument: str = FUT_INSTRUMENT,
) -> None:
    payload = {
        "securityId": str(security_id),
        "exchangeSegment": segment,
        "instrument": instrument,
        "interval": "5",
        "fromDate": from_str,
        "toDate": to_str,
    }
    print(f"\n──── PART B · probe {label} (securityId={security_id}) ────")
    print(f"  window {from_str} → {to_str}  seg={segment} instr={instrument}")
    try:
        resp = session.post(DHAN_BASE_URL + INTRADAY_PATH, json=payload, headers=headers, timeout=HTTP_TIMEOUT_S)
    except requests.RequestException as exc:
        print(f"  TRANSPORT ERROR: {exc}")
        return
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}: {resp.text[:300]}")
        return
    df = _parse_response(resp.json())
    print(f"  bars returned : {len(df)}")
    if df.empty:
        print("  → EMPTY (no data for this contract/window)")
        return
    print(f"  first / last  : {df['timestamp'].min()}  →  {df['timestamp'].max()}")
    vols = df["volume"].tolist()
    print(f"  volume sample : {vols[:5]}  …  {vols[-3:]}")
    print(f"  volume stats  : nonzero={int((df['volume'] > 0).sum())}/{len(df)}  "
          f"min={df['volume'].min()} max={df['volume'].max()}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Probe Dhan for index-futures intraday (incl. expired).")
    p.add_argument("--list-only", action="store_true", help="Part A only; never touch auth")
    p.add_argument("--secid", help="probe this specific securityId (e.g. an expired contract)")
    p.add_argument("--symbol", default="CONTRACT", help="label for --secid probe")
    p.add_argument("--from", dest="from_str", help='window start "YYYY-MM-DD HH:MM:SS" (IST)')
    p.add_argument("--to", dest="to_str", help='window end   "YYYY-MM-DD HH:MM:SS" (IST)')
    p.add_argument("--segment", default=FNO_SEGMENT)
    p.add_argument("--instrument", default=FUT_INSTRUMENT)
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    load_dotenv(HERE / ".env")
    df = _download_scrip_master()
    nb = list_index_futures(df)

    if args.list_only:
        return 0

    client_id = os.environ.get("DHAN_CLIENT_ID")
    access_token = os.environ.get("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token:
        print(
            "\n[Part B skipped] DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN not set "
            "(env or trend_engine/.env). Part A above needs no auth.",
            file=sys.stderr,
        )
        return 2
    headers = {
        "client-id": client_id,
        "access-token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    with requests.Session() as session:
        if args.secid:
            if not (args.from_str and args.to_str):
                print("ERROR: --secid requires --from and --to", file=sys.stderr)
                return 1
            probe_contract(session, headers, args.symbol, args.secid, args.from_str, args.to_str,
                           args.segment, args.instrument)
            return 0

        # Default: probe the NEAR-MONTH NIFTY future for a recent ~1-week window
        # inside its life. (No expired securityId is available from the current
        # master — see the report; pass one explicitly via --secid to test expiry.)
        near = nb[nb["SEM_TRADING_SYMBOL"].astype(str).str.upper().str.startswith("NIFTY-")]
        if near.empty:
            print("no NIFTY future in master to probe", file=sys.stderr)
            return 1
        row = near.iloc[0]  # earliest expiry = near month
        expiry = pd.to_datetime(row["SEM_EXPIRY_DATE"])
        # 1-week window ending the day before expiry (safely inside contract life).
        w_end = (expiry - timedelta(days=1)).replace(hour=15, minute=30, second=0)
        w_start = (w_end - timedelta(days=6)).replace(hour=9, minute=15, second=0)
        probe_contract(
            session, headers, str(row["SEM_TRADING_SYMBOL"]), str(row["SEM_SMST_SECURITY_ID"]),
            w_start.strftime("%Y-%m-%d %H:%M:%S"), w_end.strftime("%Y-%m-%d %H:%M:%S"),
        )
        time.sleep(0.7)
        print(
            "\n[note] No EXPIRED index-future securityId is discoverable from the "
            "current (forward-only) master, and Dhan's expired-data product covers "
            "OPTIONS only (/charts/rollingoption). To empirically test an expired "
            "future, pass a known historical securityId via --secid/--from/--to."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

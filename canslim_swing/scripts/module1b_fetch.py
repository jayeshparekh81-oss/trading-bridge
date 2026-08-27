#!/usr/bin/env python3
"""MODULE 1B step 3 — single-source daily panel fetch (188 universe + NIFTY).

Read-only market data only (POST /v2/charts/historical). No orders, no account
endpoints. ~1 req/s. Atomic + resumable.

WRITES ONLY under data/panel_v2/. Never touches data/round2, data/swing, or the
pine_replica habitat store.

Source of truth: the Dhan DAILY endpoint, falsified as corp-action adjusted in
module1b_probe.py (RECLTD 1:3 bonus ex-2022-08-17 absent; 1691/1691 days
identical to the M6b fetch).

Data only — no indicators, no signals, no strategy logic.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m6a_probe_prices as PP  # noqa: E402  (creds/throttle/sids/to_frame reuse)

TRACK = Path(__file__).resolve().parents[1]
PANEL = TRACK / "data" / "panel_v2"
DAILY = PANEL / "daily"
RAW = PANEL / "_raw"
UNIVERSE_FILE = TRACK / "config" / "universe_frozen.txt"
BASE = "https://api.dhan.co/v2/charts/historical"
FROM = "2015-01-01"
TO = dt.date.today().isoformat()


def fetch_one(tok, cid, name, body):
    """Cached, atomic, 3 tries on transient failure. HTTP 401 aborts the run."""
    p = RAW / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text())
    hdr = {"access-token": tok, "client-id": cid,
           "Content-Type": "application/json", "Accept": "application/json"}
    last = None
    for attempt in range(3):
        PP.throttle()
        try:
            r = requests.post(BASE, json=body, headers=hdr, timeout=60)
        except requests.RequestException as exc:
            last = repr(exc)
        else:
            if r.status_code == 200:
                try:
                    j = r.json()
                except ValueError:
                    j = {"_error": f"non-json {r.text[:200]}"}
                RAW.mkdir(parents=True, exist_ok=True)
                tmp = p.with_suffix(".tmp")
                tmp.write_text(json.dumps(j))
                os.replace(tmp, p)
                return j
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code == 401:
                raise SystemExit(f"\nABORT — token died mid-run on {name}: {last}")
        time.sleep(3 * (attempt + 1))
    return {"_error": last}


def write_atomic(df, path):
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp)
    os.replace(tmp, path)


def main() -> None:
    DAILY.mkdir(parents=True, exist_ok=True)
    tok, cid = PP.creds()
    sids = PP.sids()
    universe = [l.strip() for l in UNIVERSE_FILE.read_text().splitlines() if l.strip()]
    print(f"window {FROM} -> {TO} | {len(universe)} symbols + NIFTY | dest {DAILY}")

    rows, failed = [], []
    for i, sym in enumerate(universe, 1):
        s = sids.get(sym)
        if not s:
            failed.append({"symbol": sym, "error": "NO-SID-IN-MANIFEST"})
            continue
        j = fetch_one(tok, cid, sym, {"securityId": str(s), "exchangeSegment": "NSE_EQ",
                                      "instrument": "EQUITY", "expiryCode": 0, "oi": False,
                                      "fromDate": FROM, "toDate": TO})
        d = PP.to_frame(j)
        if d.empty:
            failed.append({"symbol": sym, "error": str(j.get("_error"))[:180]})
            print(f"[{i}/{len(universe)}] {sym} FAILED {str(j.get('_error'))[:70]}", flush=True)
            continue
        dupes = int(d.index.duplicated().sum())
        d = d[~d.index.duplicated()].sort_index()
        d.index.name = "date"
        write_atomic(d, DAILY / f"{sym}.parquet")
        rows.append({"symbol": sym, "rows": len(d), "dupes_dropped": dupes,
                     "first": d.index.min().date(), "last": d.index.max().date()})
        if i % 25 == 0:
            print(f"[{i}/{len(universe)}] ok — last {sym}: {len(d)} rows", flush=True)

    # NIFTY index, raw OHLCV only (no derived columns — data-only module)
    j = fetch_one(tok, cid, "_NIFTY", {"securityId": "13", "exchangeSegment": "IDX_I",
                                       "instrument": "INDEX", "expiryCode": 0, "oi": False,
                                       "fromDate": FROM, "toDate": TO})
    n = PP.to_frame(j)
    if n.empty:
        failed.append({"symbol": "NIFTY(IDX)", "error": str(j.get("_error"))[:180]})
    else:
        n = n[~n.index.duplicated()].sort_index()
        n.index.name = "date"
        write_atomic(n, PANEL / "nifty_daily.parquet")
        print(f"NIFTY {len(n)} rows {n.index.min().date()} -> {n.index.max().date()}")

    inv = pd.DataFrame(rows)
    write_atomic(inv, PANEL / "fetch_inventory.parquet")
    fail = pd.DataFrame(failed, columns=["symbol", "error"])
    write_atomic(fail, PANEL / "fetch_failed.parquet")
    print(f"\nfetched {len(inv)} / {len(universe)} | failed {len(fail)}")
    if len(fail):
        print(fail.to_string(index=False))


if __name__ == "__main__":
    main()

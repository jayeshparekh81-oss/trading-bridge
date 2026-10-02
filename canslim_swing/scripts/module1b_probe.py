#!/usr/bin/env python3
"""MODULE 1B step 1-2 — token probe + seam falsification test.

Read-only market data only (POST /v2/charts/historical). No orders, no account
endpoints. 1 req/s. Writes ONLY under data/panel_v2/_raw/ — never touches
data/round2, data/swing, or the habitat store.

Step 1: RELIANCE 2015-01-01 -> today. Report status/rows/first/last.
Step 2: RECLTD  2015-01-01 -> today. Falsification test for option (c):
        does the DAILY endpoint carry the raw -23.1% cliff on 2022-08-17?
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m6a_probe_prices as PP  # noqa: E402  (creds/throttle/sids/to_frame reuse)

TRACK = Path(__file__).resolve().parents[1]
RAW = TRACK / "data" / "panel_v2" / "_raw"
BASE = "https://api.dhan.co/v2/charts/historical"
FROM = "2015-01-01"
TO = dt.date.today().isoformat()


def fetch_one(tok, cid, name, sid):
    """One call, no silent retry. Returns (json, http_status_text)."""
    p = RAW / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text()), "CACHED"
    body = {"securityId": str(sid), "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY", "expiryCode": 0, "oi": False,
            "fromDate": FROM, "toDate": TO}
    hdr = {"access-token": tok, "client-id": cid,
           "Content-Type": "application/json", "Accept": "application/json"}
    PP.throttle()
    r = requests.post(BASE, json=body, headers=hdr, timeout=60)
    status = f"HTTP {r.status_code}"
    if r.status_code != 200:
        return {"_error": f"{status}: {r.text[:400]}"}, status
    j = r.json()
    RAW.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(j))
    os.replace(tmp, p)
    return j, status


def main() -> None:
    tok, cid = PP.creds()
    sids = PP.sids()
    print(f"request window: {FROM} -> {TO}")
    print("=" * 74)
    print("STEP 1 — TOKEN PROBE (RELIANCE)")
    print("=" * 74)
    j, status = fetch_one(tok, cid, "RELIANCE", sids["RELIANCE"])
    print(f"  http status : {status}")
    if "_error" in j:
        print(f"  ERROR       : {j['_error']}")
        print("\nSTOPPING — auth/request failed. No retry, no alternate token.")
        return
    rel = PP.to_frame(j)
    print(f"  rows        : {len(rel)}")
    print(f"  first date  : {rel.index.min().date()}")
    print(f"  last date   : {rel.index.max().date()}")
    print(f"  columns     : {list(rel.columns)}")
    print(f"  last 3 closes:\n{rel['close'].tail(3).to_string()}")

    print()
    print("=" * 74)
    print("STEP 2 — SEAM FALSIFICATION TEST (RECLTD)")
    print("=" * 74)
    j, status = fetch_one(tok, cid, "RECLTD", sids["RECLTD"])
    print(f"  http status : {status}")
    if "_error" in j:
        print(f"  ERROR       : {j['_error']}")
        print("\nSTOPPING.")
        return
    new = PP.to_frame(j)
    print(f"  rows        : {len(new)}   {new.index.min().date()} -> {new.index.max().date()}")
    print()

    # (a) named closes
    print("  (a) closes on the three named dates (NEW daily-endpoint series):")
    for d in ["2021-10-29", "2022-08-16", "2022-08-17"]:
        ts = pd.Timestamp(d)
        v = new["close"].get(ts, None)
        print(f"        {d}: {v if v is not None else 'ABSENT'}")

    # (b) cliff present or absent
    print()
    print("  (b) cliff test at 2022-08-17:")
    r = np.log(new["close"]).diff()
    ts = pd.Timestamp("2022-08-17")
    if ts in r.index:
        pct = 100 * (np.exp(r.loc[ts]) - 1)
        print(f"        close-to-close move = {pct:+.2f}%")
        print(f"        VERDICT: cliff {'PRESENT (option c is WRONG)' if pct < -15 else 'ABSENT (option c holds)'}")
    else:
        print("        2022-08-17 not in the new series")
    print("        context 2022-08-10 .. 2022-08-24:")
    ctx = new.loc["2022-08-10":"2022-08-24", ["close"]].copy()
    ctx["pct_chg"] = 100 * new["close"].pct_change().loc[ctx.index]
    print(ctx.to_string())

    # (c) ratio vs data/round2/daily/RECLTD.parquet
    print()
    print("  (c) ratio  NEW / round2  over overlapping dates:")
    old = pd.read_parquet(TRACK / "data" / "round2" / "daily" / "RECLTD.parquet")
    old.index = pd.DatetimeIndex(pd.to_datetime(old.index)).normalize()
    i = new.index.intersection(old.index)
    ratio = new.loc[i, "close"] / old.loc[i, "close"]
    print(f"        overlap days : {len(i)}  ({i.min().date()} -> {i.max().date()})")
    print(f"        median ratio : {ratio.median():.6f}")
    print(f"        std  ratio   : {ratio.std():.6f}")
    print(f"        min/max ratio: {ratio.min():.6f} / {ratio.max():.6f}")
    print(f"        days |ratio-1| > 0.5%: {int((ratio.sub(1).abs() > 0.005).sum())} / {len(i)}")

    # extra context: ratio vs the 15m rollup (swing), which we know is raw here
    sw = pd.read_parquet(TRACK / "data" / "swing" / "daily" / "RECLTD.parquet")
    sw.index = pd.DatetimeIndex(pd.to_datetime(sw.index)).normalize()
    j2 = new.index.intersection(sw.index)
    r2 = new.loc[j2, "close"] / sw.loc[j2, "close"]
    pre = r2[j2 < pd.Timestamp("2022-08-17")]
    post = r2[j2 >= pd.Timestamp("2022-08-17")]
    print()
    print("  (extra) ratio  NEW / swing(15m rollup), split at the 2022-08-17 ex-date:")
    print(f"        overlap days : {len(j2)}  ({j2.min().date()} -> {j2.max().date()})")
    print(f"        BEFORE ex-date: n={len(pre):4d}  median={pre.median():.6f}  std={pre.std():.6f}")
    print(f"        ON/AFTER      : n={len(post):4d}  median={post.median():.6f}  std={post.std():.6f}")


if __name__ == "__main__":
    main()

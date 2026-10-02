#!/usr/bin/env python3
"""M6b step 1 + 5 — Round-2A price fetch (188 universe + NIFTY), 2015 -> Oct-2021.

Read-only market data (POST /v2/charts/historical). 1 req/s, atomic, resumable.
SCOPE: fetch range != test range. The sealed window is Jan-2018 -> Jul-2021;
prices reach back to 2015 only for indicator warmup and cross-checks.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m6a_probe_prices as PP  # noqa: E402  (creds/throttle/to_frame reuse)

TRACK = Path(__file__).resolve().parents[1]
R2 = TRACK / "data" / "round2"
DAILY = R2 / "daily"
RAW = R2 / "_raw"
UNIVERSE_FILE = TRACK / "config" / "universe_frozen.txt"
FROM, TO = "2015-01-01", "2021-10-31"
BASE = "https://api.dhan.co/v2/charts/historical"


def fetch_one(tok, cid, name, body):
    p = RAW / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text())
    hdr = {"access-token": tok, "client-id": cid,
           "Content-Type": "application/json", "Accept": "application/json"}
    last = None
    for a in range(3):
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
            last = f"HTTP {r.status_code}: {r.text[:160]}"
            if r.status_code == 401:
                return {"_error": last}          # token dead: stop, don't burn
        time.sleep(4 * (a + 1))
    return {"_error": last}


def main() -> None:
    DAILY.mkdir(parents=True, exist_ok=True)
    tok, cid = PP.creds()
    sids = PP.sids()
    universe = [l.strip() for l in UNIVERSE_FILE.read_text().splitlines() if l.strip()]
    rows, parked = [], []
    for i, sym in enumerate(universe, 1):
        s = sids.get(sym)
        if not s:
            parked.append((sym, "no-sid"))
            continue
        j = fetch_one(tok, cid, sym, {"securityId": str(s), "exchangeSegment": "NSE_EQ",
                                      "instrument": "EQUITY", "expiryCode": 0, "oi": False,
                                      "fromDate": FROM, "toDate": TO})
        d = PP.to_frame(j)
        if d.empty:
            parked.append((sym, str(j.get("_error"))[:60]))
            print(f"[{i}/{len(universe)}] {sym} PARKED {str(j.get('_error'))[:50]}", flush=True)
            continue
        d = d[~d.index.duplicated()].sort_index()
        d.to_parquet(DAILY / f"{sym}.parquet")
        py = d.groupby(d.index.year).size().to_dict()
        rows.append({"symbol": sym, "bars": len(d), "first": str(d.index.min().date()),
                     "last": str(d.index.max().date()),
                     **{f"y{y}": py.get(y, 0) for y in range(2015, 2022)}})
        if i % 25 == 0:
            print(f"[{i}/{len(universe)}] ok, last {sym} {len(d)} bars", flush=True)

    # NIFTY index + derived market-filter columns (step 5)
    j = fetch_one(tok, cid, "_NIFTY", {"securityId": "13", "exchangeSegment": "IDX_I",
                                       "instrument": "INDEX", "expiryCode": 0, "oi": False,
                                       "fromDate": FROM, "toDate": TO})
    n = PP.to_frame(j)
    if not n.empty:
        n = n[~n.index.duplicated()].sort_index()
        n["sma200"] = n["close"].rolling(200).mean()
        m_close = n["close"].resample("ME").last()
        ema10 = m_close.ewm(span=10, adjust=False).mean()
        # M5-corrected SINGLE lag: day D uses the EMA through the previous
        # completed calendar month (no shift+ffill double-lag).
        prev_me = (n.index.to_period("M") - 1).to_timestamp("M")
        n["ema10m"] = pd.Series(ema10.reindex(prev_me).to_numpy(), index=n.index)
        n.to_parquet(R2 / "nifty_daily.parquet")
        py = n.groupby(n.index.year).size().to_dict()
        rows.append({"symbol": "NIFTY(IDX)", "bars": len(n), "first": str(n.index.min().date()),
                     "last": str(n.index.max().date()),
                     **{f"y{y}": py.get(y, 0) for y in range(2015, 2022)}})
        print(f"NIFTY {len(n)} bars {n.index.min().date()} -> {n.index.max().date()}, "
              f"sma200 from {n['sma200'].first_valid_index().date()}, "
              f"ema10m from {n['ema10m'].first_valid_index().date()}")
    else:
        parked.append(("NIFTY(IDX)", str(j.get("_error"))[:60]))

    df = pd.DataFrame(rows)
    df.to_parquet(R2 / "price_depth.parquet")
    pd.DataFrame(parked, columns=["symbol", "reason"]).to_parquet(R2 / "price_parked.parquet")
    print(f"\nfetched {len(rows)} | parked {len(parked)}")
    if parked:
        print("parked:", parked[:10])


if __name__ == "__main__":
    main()

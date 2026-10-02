#!/usr/bin/env python3
"""M6a step 1-2 — Dhan DAILY depth probe + old-era adjustment spot-check.

Read-only market data only (POST /v2/charts/historical). No orders, no account
endpoints. 1 req/s. Atomic + resumable cache under data/round2_probe/.

The habitat fetcher's ~5yr ceiling is an INTRADAY limit; whether the DAILY
endpoint reaches back to 2014 is precisely the go/no-go this probe answers.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

TRACK = Path(__file__).resolve().parents[1]
CACHE = TRACK / "data" / "round2_probe" / "dhan_daily"
PINE = Path("/Users/jayeshparekh/tradetri-strategies/pine_replica")
MANIFEST = PINE / "data" / "habitat" / "_manifest.jsonl"

SYMBOLS = ["HDFCBANK", "BAJFINANCE", "SBILIFE", "SBIN", "BPCL", "RELIANCE",
           "TITAN", "SUNPHARMA", "TATASTEEL", "PERSISTENT", "CDSL", "DIXON"]
FROM, TO = "2014-01-01", "2021-12-31"
BASE = "https://api.dhan.co/v2/charts/historical"
_last = [0.0]


def creds() -> tuple[str, str]:
    env = {}
    for line in (PINE / ".env").read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env["DHAN_ACCESS_TOKEN"], env["DHAN_CLIENT_ID"]


def throttle(gap=1.05):
    w = _last[0] + gap - time.monotonic()
    if w > 0:
        time.sleep(w)
    _last[0] = time.monotonic()


def sids() -> dict:
    out = {}
    for line in MANIFEST.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["symbol"]] = r.get("sid")
    return out


def fetch(tok: str, cid: str, name: str, body: dict) -> dict:
    p = CACHE / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text())
    hdr = {"access-token": tok, "client-id": cid,
           "Content-Type": "application/json", "Accept": "application/json"}
    last = None
    for attempt in range(3):
        throttle()
        try:
            r = requests.post(BASE, json=body, headers=hdr, timeout=45)
        except requests.RequestException as exc:
            last = repr(exc)
        else:
            if r.status_code == 200:
                try:
                    j = r.json()
                except ValueError:
                    j = {"_error": f"non-json {r.text[:200]}"}
                p.parent.mkdir(parents=True, exist_ok=True)
                tmp = p.with_suffix(".tmp")
                tmp.write_text(json.dumps(j))
                os.replace(tmp, p)
                return j
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        time.sleep(3 * (attempt + 1))
    return {"_error": last}


def to_frame(j: dict) -> pd.DataFrame:
    if not j or "_error" in j or not j.get("timestamp"):
        return pd.DataFrame()
    idx = pd.to_datetime(pd.Series(j["timestamp"]), unit="s", utc=True) \
        .dt.tz_convert("Asia/Kolkata").dt.tz_localize(None).dt.normalize()
    return pd.DataFrame({"open": j["open"], "high": j["high"], "low": j["low"],
                         "close": j["close"], "volume": j["volume"]}, index=idx).sort_index()


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    tok, cid = creds()
    sid = sids()
    rows = []
    for sym in SYMBOLS:
        s = sid.get(sym)
        if not s:
            rows.append({"symbol": sym, "status": "NO-SID-IN-MANIFEST"})
            print(f"{sym}: no sid", flush=True)
            continue
        j = fetch(tok, cid, sym, {"securityId": str(s), "exchangeSegment": "NSE_EQ",
                                  "instrument": "EQUITY", "expiryCode": 0,
                                  "oi": False, "fromDate": FROM, "toDate": TO})
        d = to_frame(j)
        if d.empty:
            rows.append({"symbol": sym, "status": str(j.get("_error"))[:80]})
            print(f"{sym}: EMPTY {str(j.get('_error'))[:60]}", flush=True)
            continue
        per_year = d.groupby(d.index.year).size().to_dict()
        rows.append({"symbol": sym, "status": "ok", "bars": len(d),
                     "first": str(d.index.min().date()), "last": str(d.index.max().date()),
                     **{f"y{y}": per_year.get(y, 0) for y in range(2014, 2022)}})
        print(f"{sym}: {len(d)} bars {d.index.min().date()} -> {d.index.max().date()}", flush=True)

    # NIFTY index daily
    j = fetch(tok, cid, "_NIFTY", {"securityId": "13", "exchangeSegment": "IDX_I",
                                   "instrument": "INDEX", "expiryCode": 0, "oi": False,
                                   "fromDate": FROM, "toDate": TO})
    n = to_frame(j)
    if not n.empty:
        py = n.groupby(n.index.year).size().to_dict()
        rows.append({"symbol": "NIFTY(IDX)", "status": "ok", "bars": len(n),
                     "first": str(n.index.min().date()), "last": str(n.index.max().date()),
                     **{f"y{y}": py.get(y, 0) for y in range(2014, 2022)}})
        print(f"NIFTY: {len(n)} bars {n.index.min().date()} -> {n.index.max().date()}")
    else:
        rows.append({"symbol": "NIFTY(IDX)", "status": str(j.get("_error"))[:80]})
        print(f"NIFTY: EMPTY {str(j.get('_error'))[:80]}")

    df = pd.DataFrame(rows)
    df.to_parquet(TRACK / "data" / "round2_probe" / "price_depth.parquet")
    print("\n" + df.to_string(index=False))


if __name__ == "__main__":
    main()

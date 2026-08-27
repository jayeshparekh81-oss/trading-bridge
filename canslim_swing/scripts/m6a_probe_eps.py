#!/usr/bin/env python3
"""M6a steps 3-4 — NSE old-regime EPS depth (back to 2014) + old XBRL tag sanity.

Reuses M2b's session pattern and its taxonomy-aware EPS recovery chain. NSE only,
1 req/s, atomic + resumable cache under data/round2_probe/.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

TRACK = Path(__file__).resolve().parents[1]
CACHE = TRACK / "data" / "round2_probe"
sys.path.insert(0, str(Path(__file__).resolve().parent))

SYMBOLS = ["HDFCBANK", "BAJFINANCE", "SBILIFE", "SBIN", "BPCL", "RELIANCE",
           "TITAN", "SUNPHARMA", "TATASTEEL", "PERSISTENT", "CDSL", "DIXON"]
WINDOW_FIRST = datetime(2014, 7, 1)     # 2014-Q3 warmup start (period ends >= Sep-2014)
WINDOW_LAST = datetime(2021, 7, 31)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
NSE = "https://www.nseindia.com"
WARM = f"{NSE}/companies-listing/corporate-filings-financial-results"
_last = [0.0]

EPS_BASIC = ("re_basic_eps_for_cont_dic_opr", "re_basic_eps", "re_bsc_eps_bfr_exi")
EPS_DIL = ("re_dilut_eps_for_cont_dic_opr", "re_diluted_eps", "re_dil_eps_bfr_exi")


def throttle(gap=1.1):
    w = _last[0] + gap - time.monotonic()
    if w > 0:
        time.sleep(w)
    _last[0] = time.monotonic()


def warm(s):
    for u in (NSE, WARM):
        throttle()
        try:
            s.get(u, headers=H, timeout=20)
        except requests.RequestException:
            pass


def get(s, url, retries=3):
    for a in range(retries):
        throttle()
        try:
            r = s.get(url, headers={**H, "Referer": WARM}, timeout=45)
        except requests.RequestException:
            r = None
        if r is not None and r.status_code == 200:
            return r
        if r is not None and r.status_code in (401, 403):
            warm(s)
        time.sleep(6 * (a + 1))
    return None


def cached(name, fn):
    p = CACHE / name
    if p.exists():
        return json.loads(p.read_text())
    v = fn()
    if v is None:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(v))
    os.replace(tmp, p)
    return v


def pdate(d):
    d = (d or "").strip()
    for f in ("%d-%b-%Y", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            return datetime.strptime(d.title() if d.isupper() else d, f)
        except ValueError:
            continue
    return None


def fnum(v):
    if v is None:
        return None
    t = str(v).strip().replace(",", "")
    if t in ("", "-", "--", "NA", "null"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def main() -> None:
    s = requests.Session()
    warm(s)
    q = requests.utils.quote
    rows, detail_probe = [], []
    for sym in SYMBOLS:
        lst = cached(f"eps_list/{sym}.json", lambda: (
            (lambda r: r.json() if r is not None and r.content else None)(
                get(s, f"{NSE}/api/corporates-financial-results?index=equities"
                       f"&symbol={q(sym, safe='')}&period=Quarterly"))))
        if not lst:
            rows.append({"symbol": sym, "status": "NO-LIST-ROWS", "list_rows": 0})
            print(f"{sym}: no list rows", flush=True)
            continue
        dated = [(pdate(x.get("toDate")), x) for x in lst]
        dated = [(d, x) for d, x in dated if d]
        in_win = [(d, x) for d, x in dated if WINDOW_FIRST <= d <= WINDOW_LAST]
        quarters = sorted({d for d, _ in in_win})
        earliest_all = min((d for d, _ in dated), default=None)
        rows.append({"symbol": sym, "status": "ok", "list_rows": len(lst),
                     "earliest_any": str(earliest_all.date()) if earliest_all else "-",
                     "quarters_in_window": len(quarters),
                     "first_in_window": str(quarters[0].date()) if quarters else "-",
                     "last_in_window": str(quarters[-1].date()) if quarters else "-",
                     "expected_28": 28})
        print(f"{sym}: {len(lst)} rows, {len(quarters)} quarters in 2014Q3-2021Q2, "
              f"earliest {earliest_all.date() if earliest_all else '-'}", flush=True)
        # step 4 fodder: one 2015-2017 filing per symbol, detail API + xbrl fallback
        old = [(d, x) for d, x in in_win if datetime(2015, 1, 1) <= d <= datetime(2017, 12, 31)]
        if old:
            d0, row = min(old, key=lambda kv: kv[0])   # dicts aren't orderable
            det = cached(f"eps_detail/{sym}.json", lambda: (
                (lambda r: (r.json() if r is not None and r.text.strip().startswith("{") else
                            {"_nonjson": (r.text[:120] if r is not None else "fail")}))(
                    get(s, f"{NSE}/api/corporates-financial-results-data?index=equities"
                           f"&params={q(row['params'], safe='')}&seq_id={row['seqNumber']}"
                           f"&industry={q(row.get('industry') or '-', safe='')}"
                           f"&ind={q(row.get('indAs') or '', safe='')}"
                           f"&format={row.get('format') or ''}"))))
            rd = (det or {}).get("resultsData2") or (det or {}).get("resultsData") or {}
            eps = {k: rd.get(k) for k in set(EPS_BASIC) | set(EPS_DIL)} if isinstance(rd, dict) else {}
            got = next((k for k in EPS_BASIC if fnum(eps.get(k)) is not None), None)
            detail_probe.append({"symbol": sym, "quarter": str(d0.date()),
                                 "indAs": row.get("indAs"), "format": row.get("format"),
                                 "detail_kind": ("resultsData2" if (det or {}).get("resultsData2")
                                                 else "resultsData" if (det or {}).get("resultsData")
                                                 else "none"),
                                 "eps_tag_used": got or "NONE",
                                 "eps_value": fnum(eps.get(got)) if got else None,
                                 "xbrl_url": row.get("xbrl") or ""})
    pd.DataFrame(rows).to_parquet(CACHE / "eps_depth.parquet")
    pd.DataFrame(detail_probe).to_parquet(CACHE / "eps_tag_probe.parquet")
    print("\n=== EPS DEPTH ===")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n=== OLD-FILING TAG PROBE (2015-2017) ===")
    print(pd.DataFrame(detail_probe).to_string(index=False))


if __name__ == "__main__":
    main()

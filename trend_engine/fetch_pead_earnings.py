#!/usr/bin/env python3
"""PEAD module-0 · earnings-date harness (Nifty-100).

Fetches historical quarterly-results board-meeting dates for the Nifty-100
(Nifty-50 + Nifty Next-50 — the exact 100 symbols already in the delivery
parquets) from NSE's corporate-board-meetings feed, filtered to results
meetings. Read-only public data; no creds, no order paths.

Getting clean historical results dates is the MAIN RISK of this whole module, so
the fetcher is deliberately conservative and the coverage report is printed loud:
per-symbol event counts + any symbol that looks short.

Source: https://www.nseindia.com/api/corporate-board-meetings — one compact
request per symbol (~20-28 rows spanning the window, no truncation). We keep rows
whose bm_purpose mentions "Financial Result" and take bm_date as the announcement
date d (the day the board meets and results are released). Raw JSON is cached per
symbol (resumable); a cached symbol is never re-fetched.

  TODO(point-in-time): the universe is the CURRENT Nifty-100 → survivorship bias.
  TODO(EPS surprise): a later module can join actual EPS vs seasonal-random-walk
       for the fundamental-PEAD version; this module uses the price reaction only.

Run:
    python trend_engine/fetch_pead_earnings.py
    python trend_engine/fetch_pead_earnings.py --refresh   # ignore cache, re-fetch
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fetch_nse_delivery import NIFTY50  # noqa: E402
from run_delivery_module2_confirm import NEXT50  # noqa: E402

DATA_DIR = HERE / "data"
RAW_DIR = DATA_DIR / "pead_bm_raw"

# Nifty-100 = the two delivery universes, combined. Auditable + guaranteed to
# match the price data we already have.
UNIVERSE = tuple(NIFTY50) + tuple(NEXT50)
assert len(UNIVERSE) == 100, f"expected 100 symbols, got {len(UNIVERSE)}"
assert len(set(UNIVERSE)) == 100, "universe has duplicates"

WINDOW = (date(2023, 7, 31), date(2026, 7, 28))

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA, "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"}
_HOME = "https://www.nseindia.com"
_WARM = "https://www.nseindia.com/companies-listing/corporate-filings-board-meetings"
_API = "https://www.nseindia.com/api/corporate-board-meetings"

REQUEST_SLEEP = 0.5
MAX_RETRIES = 4
BACKOFF_BASE = 1.6


def _warm_up(s: requests.Session) -> None:
    try:
        s.get(_HOME, headers=_HEADERS, timeout=15)
        s.get(_WARM, headers=_HEADERS, timeout=15)
    except requests.RequestException as exc:
        print(f"[warmup] WARN {exc!r}", file=sys.stderr)


def _fetch_symbol(s: requests.Session, sym: str) -> list[dict]:
    fr, to = WINDOW[0].strftime("%d-%m-%Y"), WINDOW[1].strftime("%d-%m-%Y")
    # URL-encode the symbol: a raw '&' (e.g. M&M) would split the query string.
    url = f"{_API}?index=equities&symbol={quote(sym, safe='')}&from_date={fr}&to_date={to}"
    headers = {**_HEADERS, "Referer": _WARM}
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = s.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            last = exc
        else:
            if r.status_code == 200:
                return r.json() if r.content else []
            if r.status_code in (401, 403):
                _warm_up(s)
            last = RuntimeError(f"HTTP {r.status_code}")
        time.sleep(BACKOFF_BASE ** attempt)
    raise RuntimeError(f"{sym}: giving up after {MAX_RETRIES} tries ({last!r})")


def _extract(sym: str, rows: list[dict]) -> list[dict]:
    """Keep results board-meetings; one event per (symbol, date)."""
    events: dict[date, dict] = {}
    for row in rows:
        purpose = (row.get("bm_purpose") or "").strip()
        if "financial result" not in purpose.lower():
            continue
        raw_d = (row.get("bm_date") or "").strip()
        try:
            d = datetime.strptime(raw_d, "%d-%b-%Y").date()
        except ValueError:
            continue
        if not (WINDOW[0] <= d <= WINDOW[1]):
            continue
        # first-seen wins; keep the intimation timestamp for eyeballing after/before-hours.
        events.setdefault(d, {
            "symbol": sym, "ann_date": d, "bm_purpose": purpose,
            "bm_timestamp": (row.get("bm_timestamp") or "").strip(),
        })
    return sorted(events.values(), key=lambda e: e["ann_date"])


def build(refresh: bool) -> pd.DataFrame:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(_HEADERS)
    _warm_up(s)

    all_events: list[dict] = []
    per_symbol: dict[str, int] = {}
    fetched = cached = 0
    for i, sym in enumerate(UNIVERSE):
        cache = RAW_DIR / f"{sym.replace('&', '_')}.json"
        if cache.exists() and not refresh:
            rows = json.loads(cache.read_text())
            cached += 1
        else:
            rows = _fetch_symbol(s, sym)
            cache.write_text(json.dumps(rows))
            fetched += 1
            time.sleep(REQUEST_SLEEP)
        ev = _extract(sym, rows)
        per_symbol[sym] = len(ev)
        all_events.extend(ev)
        if (i + 1) % 20 == 0 or (i + 1) == len(UNIVERSE):
            print(f"[fetch] {i + 1}/{len(UNIVERSE)} symbols  (new {fetched}, cached {cached})")

    df = pd.DataFrame(all_events).sort_values(["symbol", "ann_date"]).reset_index(drop=True)
    df["ann_date"] = pd.to_datetime(df["ann_date"])
    out = DATA_DIR / "pead_earnings.parquet"
    df.to_parquet(out, index=False)
    df.to_csv(DATA_DIR / "pead_earnings.csv", index=False)

    # ── Coverage (the risk report) ──────────────────────────────────────────
    counts = pd.Series(per_symbol)
    print(f"\n[build] wrote {out}  ({len(df):,} events, {df['symbol'].nunique()} symbols, "
          f"{df['ann_date'].min().date()} → {df['ann_date'].max().date()})")
    print(f"[coverage] events/symbol: median {counts.median():.0f}, min {counts.min()}, max {counts.max()}")
    short = counts[counts < 8].sort_values()
    if len(short):
        print(f"[coverage] ⚠ {len(short)} symbol(s) with < 8 results events over ~3y (expect ~11-12):")
        for sym, c in short.items():
            print(f"           {sym:<12} {c}")
    else:
        print("[coverage] all symbols have >= 8 events — healthy.")
    zero = counts[counts == 0]
    if len(zero):
        print(f"[coverage] ⚠⚠ {len(zero)} symbol(s) with ZERO events: {list(zero.index)}")
    return df


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PEAD earnings-date harness (Nifty-100, module-0).")
    p.add_argument("--refresh", action="store_true", help="ignore cache, re-fetch all symbols")
    args = p.parse_args(argv)
    build(refresh=args.refresh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

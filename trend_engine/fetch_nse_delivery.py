#!/usr/bin/env python3
"""Module-0 · NSE daily security-wise DELIVERY data harness (Nifty-50 universe).

Read-only public-archive pull. No creds, no app imports, no order paths, no
strategy logic — this only ACQUIRES data and assembles a tidy table.

Source: NSE daily "sec_bhavdata_full_DDMMYYYY.csv" archive, which carries per
symbol per trading day:
    SYMBOL, SERIES, PREV_CLOSE, OPEN_PRICE, CLOSE_PRICE,
    TTL_TRD_QNTY, DELIV_QTY, DELIV_PER
NSE blocks non-browser clients, so we warm up a cookie via www.nseindia.com and
send browser-like headers + a Referer. Each day's raw CSV is cached to disk;
a cached day is never re-fetched. Holidays / missing days 404 and are logged +
skipped (the trading calendar is discovered, not hardcoded).

Corp-action hygiene note: NSE's PREV_CLOSE is ALREADY split/bonus/dividend
adjusted on the ex-date, so the adjusted daily return lives in
delivery_feature.py as close[t]/prev_close[t]-1 — authoritative, no ratio guess.
We therefore keep raw CLOSE_PRICE + PREV_CLOSE here and adjust downstream.

Run:
    python trend_engine/fetch_nse_delivery.py                 # last 3 years
    python trend_engine/fetch_nse_delivery.py --years 5       # extend the window
    python trend_engine/fetch_nse_delivery.py --start 2023-01-01 --end 2023-06-30
    python trend_engine/fetch_nse_delivery.py --dry-run       # plan only, no fetch

Outputs (gitignored data/):
    data/nse_bhav_raw/DDMMYYYY.csv   — per-day raw archive cache (resumable)
    data/nse_delivery.parquet        — tidy universe table (+ .csv sibling)
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
RAW_DIR = DATA_DIR / "nse_bhav_raw"

# ── Universe ────────────────────────────────────────────────────────────────
# Nifty-50 constituents, hand-maintained SNAPSHOT as of the module date
# (2026-07). Hardcoded so the universe is auditable and fixed (no cherry-pick).
#
# TODO(module-later): POINT-IN-TIME membership. This is the CURRENT list, so the
# sample carries survivorship bias — names that were in the index earlier in the
# window but got dropped are absent, and current members are back-filled for the
# whole window. Accepted for module-0. The coverage report validates every
# ticker against the archive, so a mistyped / delisted symbol shows up as
# missing rather than silently corrupting the pool.
#
# Known mid-window ticker casualty: TATAMOTORS stopped trading under this symbol
# after the 2025-26 demerger/rename, so its series ends part-way through the
# window (expect a SHORT row-count in coverage, not a bug). Kept because it was a
# genuine Nifty-50 member for most of the 3y window.
NIFTY50 = (
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BEL", "BHARTIARTL",
    "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB",
    "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK",
    "INDUSINDBK", "INFY", "ITC", "JSWSTEEL", "KOTAKBANK",
    "LT", "M&M", "MARUTI", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN",
    "SHRIRAMFIN", "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
    "TCS", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO",
)
assert len(NIFTY50) == 50, f"universe must be 50, got {len(NIFTY50)}"

# ── HTTP ────────────────────────────────────────────────────────────────────
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_BASE_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}
_ARCHIVE = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d}.csv"
_WARMUP = "https://www.nseindia.com/"

REQUEST_SLEEP = 0.4     # polite pause between archive hits (s)
MAX_RETRIES = 4         # per-day retry budget on 403/429/5xx/network
BACKOFF_BASE = 1.5      # exponential backoff base (s)
WARMUP_EVERY = 150      # refresh the cookie jar every N fetched days


def _warm_up(session: requests.Session) -> None:
    """Hit the NSE home page so the archive CDN accepts us (sets cookies)."""
    try:
        session.get(_WARMUP, headers=_BASE_HEADERS, timeout=15)
    except requests.RequestException as exc:  # non-fatal; archive may still 200
        print(f"[warmup] WARN {exc!r}", file=sys.stderr)


def _fetch_day(session: requests.Session, d: date) -> bytes | None:
    """Fetch one day's raw CSV bytes. None = legitimately absent (404 holiday).

    Raises on exhausting retries for a transient error so the caller can decide
    whether to abort — a silent gap would corrupt the coverage picture.
    """
    ddmmyyyy = d.strftime("%d%m%Y")
    url = _ARCHIVE.format(d=ddmmyyyy)
    headers = {**_BASE_HEADERS, "Referer": _WARMUP}
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, headers=headers, timeout=25)
        except requests.RequestException as exc:
            last_exc = exc
        else:
            if r.status_code == 200 and r.content:
                return r.content
            if r.status_code == 404:
                return None  # holiday / not-yet-published — expected, skip
            if r.status_code in (401, 403):
                _warm_up(session)  # cookie likely stale — re-arm and retry
            last_exc = RuntimeError(f"HTTP {r.status_code}")
        sleep_s = BACKOFF_BASE ** attempt
        time.sleep(sleep_s)
    raise RuntimeError(f"{ddmmyyyy}: giving up after {MAX_RETRIES} tries ({last_exc!r})")


# ── Parse + assemble ────────────────────────────────────────────────────────
# Archive columns arrive with leading spaces (" SERIES", " DELIV_PER"), so every
# column name and string cell is stripped before use.
_NUM_COLS = ["PREV_CLOSE", "OPEN_PRICE", "CLOSE_PRICE", "TTL_TRD_QNTY", "DELIV_QTY", "DELIV_PER"]


def _parse_day(raw: bytes, d: date, universe: set[str]) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), dtype=str)
    df.columns = [c.strip() for c in df.columns]
    for c in ("SYMBOL", "SERIES"):
        df[c] = df[c].str.strip()
    # EQ series only (the tradable common-equity line; drops BE/BZ/derivative rows).
    df = df[(df["SYMBOL"].isin(universe)) & (df["SERIES"] == "EQ")].copy()
    if df.empty:
        return df
    for c in _NUM_COLS:
        # DELIV_QTY/DELIV_PER are '-' on days a symbol had no delivery reporting.
        df[c] = pd.to_numeric(df[c].str.strip().replace({"-": None}), errors="coerce")
    df["date"] = pd.Timestamp(d)
    out = df[["date", "SYMBOL", *_NUM_COLS]].rename(
        columns={
            "SYMBOL": "symbol",
            "PREV_CLOSE": "prev_close",
            "OPEN_PRICE": "open",
            "CLOSE_PRICE": "close",
            "TTL_TRD_QNTY": "ttl_trd_qnty",
            "DELIV_QTY": "deliv_qty",
            "DELIV_PER": "deliv_per",
        }
    )
    return out


def _trading_day_candidates(start: date, end: date):
    """Yield weekdays start→end. Weekends never publish; NSE holidays 404."""
    d = start
    one = timedelta(days=1)
    while d <= end:
        if d.weekday() < 5:  # Mon–Fri
            yield d
        d += one


def build(
    start: date,
    end: date,
    *,
    dry_run: bool,
    universe: tuple[str, ...] = NIFTY50,
    out_stem: str = "nse_delivery",
) -> pd.DataFrame | None:
    """Assemble the tidy delivery table for `universe` over [start, end].

    The raw per-day archive cache (data/nse_bhav_raw/) is the WHOLE market and is
    universe-independent, so a second universe (e.g. Nifty Next-50) re-parses the
    same cached CSVs with no re-download. `out_stem` isolates each universe's
    output parquet/csv so they never clobber each other.
    """
    uni = set(universe)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    candidates = list(_trading_day_candidates(start, end))
    print(
        f"[plan] window {start} → {end}  |  {len(candidates)} weekday candidates "
        f"|  universe {len(universe)} symbols (EQ series) → {out_stem}.parquet"
    )
    if dry_run:
        cached = sum((RAW_DIR / f"{d.strftime('%d%m%Y')}.csv").exists() for d in candidates)
        print(f"[plan] {cached} already cached, {len(candidates) - cached} would be fetched. (dry-run)")
        return None

    session = requests.Session()
    session.headers.update(_BASE_HEADERS)
    _warm_up(session)

    frames: list[pd.DataFrame] = []
    fetched = holidays = cached_hits = 0
    for i, d in enumerate(candidates):
        cache = RAW_DIR / f"{d.strftime('%d%m%Y')}.csv"
        if cache.exists():
            raw = cache.read_bytes()
            cached_hits += 1
        else:
            if fetched and fetched % WARMUP_EVERY == 0:
                _warm_up(session)
            raw = _fetch_day(session, d)
            time.sleep(REQUEST_SLEEP)
            if raw is None:
                holidays += 1
                continue
            cache.write_bytes(raw)  # cache ONLY confirmed-good days
            fetched += 1

        day_df = _parse_day(raw, d, uni)
        if not day_df.empty:
            frames.append(day_df)

        if (i + 1) % 50 == 0 or (i + 1) == len(candidates):
            print(
                f"[fetch] {i + 1}/{len(candidates)} days  "
                f"(new {fetched}, cached {cached_hits}, holidays {holidays})"
            )

    if not frames:
        print("[build] no rows assembled — nothing written.", file=sys.stderr)
        return None

    tidy = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )
    out_pq = DATA_DIR / f"{out_stem}.parquet"
    tidy.to_parquet(out_pq, index=False)
    tidy.to_csv(DATA_DIR / f"{out_stem}.csv", index=False)
    print(
        f"\n[build] wrote {out_pq}  ({len(tidy):,} rows, "
        f"{tidy['symbol'].nunique()} symbols, {tidy['date'].nunique()} trading days)"
    )
    return tidy


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NSE delivery-data harness (Nifty-50, module-0).")
    p.add_argument("--years", type=float, default=3.0, help="lookback window if --start omitted (default 3)")
    p.add_argument("--start", type=str, default=None, help="YYYY-MM-DD (overrides --years)")
    p.add_argument("--end", type=str, default=None, help="YYYY-MM-DD (default today)")
    p.add_argument("--dry-run", action="store_true", help="print the plan, fetch nothing")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else date.today()
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        start = end - timedelta(days=round(365.25 * args.years))
    build(start, end, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

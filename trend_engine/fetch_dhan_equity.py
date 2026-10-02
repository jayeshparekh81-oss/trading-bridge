#!/usr/bin/env python3
"""Fetch 5y of 5-min EQUITY (cash) OHLCV for BSE Ltd + CDSL, corp-action-adjusted.

Eyes-open exploration only. DATA PULL ONLY — CDSL is live-traded; this never
touches any live setup, it only reads historical candles.

Reuses fetch_dhan_history.py (auth/pagination/backoff/dedup/quality/save) and
fetch_dhan_futures.session_filter. Adds:
  * dynamic EQUITY resolution (NSE_EQ) from the scrip master, and
  * CORPORATE-ACTION HYGIENE — detect >15% overnight gaps, back-adjust clean
    split/bonus ratios, FLAG ambiguous gaps. The test is invalid without this.

Writes data/BSE.parquet/.csv and data/CDSL.parquet/.csv (ADJUSTED series).
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_dhan_history import (  # noqa: E402
    HERE,
    Resolved,
    _download_scrip_master,
    fetch_5min,
    load_dotenv,
    quality_report,
    save,
)
from fetch_dhan_futures import session_filter  # noqa: E402

EQ_SEGMENT = "NSE_EQ"
EQ_INSTRUMENT = "EQUITY"

TARGETS_EQ = {
    "BSE": {"match": {"BSE"}, "known_id": "19585"},      # BSE LIMITED (NSE)
    "CDSL": {"match": {"CDSL"}, "known_id": "21174"},    # CENTRAL DEPO SER (I) LTD (NSE)
}

# Corp-action detection.
GAP_THRESHOLD = 0.15          # |overnight open/close - 1| beyond this = suspicious
RATIO_TOL = 0.05              # relative tolerance to call a gap a "clean" round ratio
# Plausible split/bonus PRICE ratios (prior_close / next_open); inverses cover reverse splits.
CANDIDATE_RATIOS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0, 11.0]


# ── Resolve equity ─────────────────────────────────────────────────────────


def resolve_equity(df: pd.DataFrame, symbols: list[str]) -> dict[str, Resolved]:
    eq = df[df["SEM_INSTRUMENT_NAME"].astype(str) == "EQUITY"].copy()
    tsym = eq["SEM_TRADING_SYMBOL"].astype(str).str.upper()
    exch = eq["SEM_EXM_EXCH_ID"].astype(str).str.upper()
    out: dict[str, Resolved] = {}
    print("[resolve] EQUITY (NSE_EQ) resolutions:")
    for sym in symbols:
        spec = TARGETS_EQ[sym]
        mask = tsym.isin({m.upper() for m in spec["match"]}) & (exch == "NSE")
        cand = eq[mask]
        if cand.empty:
            raise LookupError(f"could not resolve equity {sym} on NSE")
        row = cand.iloc[0]
        sec_id = str(row["SEM_SMST_SECURITY_ID"]).strip()
        flag = "OK" if sec_id == spec["known_id"] else f"⚠ expected {spec['known_id']}"
        print(f"[resolve]   {sym:<6} securityId={sec_id:<8} name={str(row['SM_SYMBOL_NAME'])!r}  [{flag}]")
        out[sym] = Resolved(
            symbol=sym, security_id=sec_id, exchange_segment=EQ_SEGMENT,
            instrument=EQ_INSTRUMENT, source_trading_symbol=str(row["SEM_TRADING_SYMBOL"]),
            source_name=str(row["SM_SYMBOL_NAME"]),
        )
    return out


# ── Corporate-action hygiene ───────────────────────────────────────────────


def _classify_ratio(ratio: float) -> tuple[bool, float]:
    """Is `ratio` (prior_close/next_open) a clean round split/bonus ratio?
    Returns (is_clean, inferred_ratio). Checks the ratio and its inverse."""
    for c in CANDIDATE_RATIOS:
        if abs(ratio / c - 1.0) <= RATIO_TOL:
            return True, c
        if abs((1.0 / ratio) / c - 1.0) <= RATIO_TOL:
            return True, 1.0 / c
    return False, ratio


def detect_and_adjust(symbol: str, df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Detect >15% overnight gaps; back-adjust clean corp actions, flag ambiguous.

    Back-adjustment: pre-event OHLC ×= factor (=next_open/prior_close), volume
    ×= 1/factor, so the series is price-continuous at the CURRENT scale and
    traded-value is preserved. Multiple events compound (each multiplies every
    bar dated before it)."""
    # fetch_5min/session_filter return `timestamp` as a COLUMN (RangeIndex).
    ts = df["timestamp"]
    bar_date = ts.dt.date
    day = ts.dt.normalize()
    first_open = df.groupby(day)["open"].first()
    last_close = df.groupby(day)["close"].last()
    days = last_close.index

    events: list[dict] = []
    for i in range(1, len(days)):
        prior_close = float(last_close.iloc[i - 1])
        next_open = float(first_open.iloc[i])
        if prior_close <= 0:
            continue
        factor = next_open / prior_close
        if abs(factor - 1.0) <= GAP_THRESHOLD:
            continue
        ratio = prior_close / next_open
        is_clean, inferred = _classify_ratio(ratio)
        events.append({
            "date": days[i].date(),
            "prior_close": prior_close,
            "next_open": next_open,
            "gap_pct": (factor - 1.0) * 100.0,
            "ratio": ratio,
            "inferred_ratio": inferred,
            "factor": factor,
            "clean": is_clean,
        })

    adj = df.copy()
    for ev in events:
        if not ev["clean"]:
            continue  # ambiguous → flagged only, never auto-adjusted
        before = bar_date < ev["date"]
        for c in ("open", "high", "low", "close"):
            adj.loc[before, c] = adj.loc[before, c] * ev["factor"]
        adj.loc[before, "volume"] = (adj.loc[before, "volume"] / ev["factor"]).round().astype("int64")

    # Report
    print(f"\n──── CORP-ACTION SCAN · {symbol} ────")
    if not events:
        print("  no overnight gaps > 15% — no adjustments.")
    for ev in events:
        kind = f"CORP ACTION ~{ev['inferred_ratio']:.2f}× → back-adjust" if ev["clean"] \
            else "AMBIGUOUS (news-gap?) → FLAGGED, NOT adjusted"
        print(f"  {ev['date']}  gap {ev['gap_pct']:+.1f}%  "
              f"(close {ev['prior_close']:.1f} → open {ev['next_open']:.1f}, ratio {ev['ratio']:.3f})  {kind}")
    applied = [e for e in events if e["clean"]]
    print(f"  → {len(applied)} adjustment(s) applied, {len(events) - len(applied)} flagged for manual review.")
    return adj, events


# ── main ───────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    symbols = ["BSE", "CDSL"]
    years = 5
    load_dotenv(HERE / ".env")
    end = datetime.now(UTC).replace(microsecond=0)
    start = end - timedelta(days=365 * years)
    out_dir = HERE / "data"
    print(f"EQUITY fetch: {', '.join(symbols)}  range {start.date()} → {end.date()} ({years}y) interval=5m")

    df_master = _download_scrip_master()
    resolved = resolve_equity(df_master, symbols)

    client_id = os.environ.get("DHAN_CLIENT_ID")
    access_token = os.environ.get("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token:
        print("\nERROR: DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN not set (trend_engine/.env).", file=sys.stderr)
        return 2
    headers = {"client-id": client_id, "access-token": access_token,
               "Content-Type": "application/json", "Accept": "application/json"}

    rc = 0
    with requests.Session() as session:
        for sym in symbols:
            r = resolved[sym]
            print(f"\n==== FETCH {sym} (securityId={r.security_id}, {EQ_SEGMENT}) ====")
            df = fetch_5min(session, headers, r, start, end)
            df = session_filter(df)
            if df.empty:
                print(f"  {sym}: empty — not written."); rc = 1; continue
            df, _events = detect_and_adjust(sym, df)
            quality_report(sym, df)
            save(sym, df, out_dir)

    print("\nDone — ADJUSTED equity series saved.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

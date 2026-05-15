#!/usr/bin/env python3
"""Phase C — verify Dhan scrip-master segment label for BSE futures.

The futures_resolver hardcodes segment ``"NSE_FNO"`` as the filter for
BSE-prefixed monthly futures (BSE Ltd is an NSE-listed company; its F&O
contracts trade on NSE F&O, not on BSE Ltd's own derivatives segment).

This script downloads the live Dhan scrip-master CSV and prints what
segment label Dhan actually publishes for ``BSE-*-FUT`` rows. If it's
``NSE_FNO``, the resolver is correct. If it's anything else (e.g.
``BSE_FNO``), the resolver will silently find zero contracts and
fall back to passthrough — which means BSE futures orders never get
their TradingView ticker normalized.

Usage
    Run from the backend dir, with a Python that has httpx installed
    (the project venv works):

        cd backend && python scripts/verify_bse_fut_segment.py

Output
    Prints one row per ``BSE-*-FUT`` contract found, plus a SUMMARY
    block at the end with the segment-label distribution.

Safety
    Read-only — downloads a public CSV and prints to stdout. No
    credentials, no DB access, no order placement, no Dhan API auth.
"""

from __future__ import annotations

import csv
import io
import sys
from collections import Counter
from typing import Any

import httpx

DHAN_SCRIP_MASTER_URL = (
    "https://images.dhan.co/api-data/api-scrip-master.csv"
)


def _segment_for(exchange_code: str, segment_code: str) -> str:
    """Mirror of :data:`app.brokers.dhan._SEGMENT_FOR`.

    Kept inline so this script can run standalone without dragging the
    full app config bootstrap (which requires ENCRYPTION_KEY etc. at
    import time).
    """
    table = {
        ("NSE", "E"): "NSE_EQ",
        ("NSE", "D"): "NSE_FNO",
        ("NSE", "I"): "IDX_I",
        ("NSE", "C"): "NSE_CURRENCY",
        ("BSE", "E"): "BSE_EQ",
        ("BSE", "D"): "BSE_FNO",
        ("BSE", "I"): "IDX_I",
        ("BSE", "C"): "BSE_CURRENCY",
        ("MCX", "M"): "MCX_COMM",
    }
    return table.get((exchange_code.upper(), segment_code.upper()), "UNKNOWN")


def fetch_scrip_master() -> str:
    """Download the public CSV. ~40 MB, 30 s timeout."""
    print(f"Downloading {DHAN_SCRIP_MASTER_URL} ...", file=sys.stderr)
    with httpx.Client(timeout=30.0) as http:
        response = http.get(DHAN_SCRIP_MASTER_URL)
        response.raise_for_status()
    print(
        f"  → received {len(response.text):,} bytes",
        file=sys.stderr,
    )
    return response.text


def find_bse_fut_rows(csv_text: str) -> list[dict[str, Any]]:
    """Return every row whose trading symbol matches ``BSE-*-FUT``."""
    reader = csv.DictReader(io.StringIO(csv_text))
    out: list[dict[str, Any]] = []
    for raw in reader:
        normalised = {
            k.strip().upper(): (v or "").strip() for k, v in raw.items()
        }
        symbol = (
            normalised.get("SEM_TRADING_SYMBOL")
            or normalised.get("TRADING_SYMBOL")
            or normalised.get("SM_SYMBOL_NAME")
            or ""
        )
        if not symbol.upper().startswith("BSE-"):
            continue
        if not symbol.upper().endswith("-FUT"):
            continue
        sec_id = (
            normalised.get("SEM_SMST_SECURITY_ID")
            or normalised.get("SECURITY_ID")
            or ""
        )
        exchange_code = (
            normalised.get("SEM_EXM_EXCH_ID")
            or normalised.get("EXCH_ID")
            or normalised.get("EXM_EXCH_ID")
            or ""
        ).upper()
        segment_code = normalised.get("SEM_SEGMENT", "").upper()
        instrument = normalised.get("SEM_INSTRUMENT_NAME", "").upper()
        lot_str = normalised.get("SEM_LOT_UNITS", "")
        try:
            lot_size = int(float(lot_str)) if lot_str else None
        except ValueError:
            lot_size = None
        out.append(
            {
                "symbol": symbol,
                "security_id": sec_id,
                "exchange_code": exchange_code,
                "segment_code": segment_code,
                "segment_label": _segment_for(exchange_code, segment_code),
                "instrument": instrument,
                "lot_size": lot_size,
            }
        )
    return out


def print_report(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print(
            "\nFOUND ZERO ``BSE-*-FUT`` ROWS in the scrip master.\n"
            "This is itself a deploy-blocker — investigate before "
            "deploying futures_resolver.",
            file=sys.stderr,
        )
        sys.exit(2)

    print(
        f"\nFound {len(rows)} ``BSE-*-FUT`` rows in the scrip master.\n"
    )
    header = (
        f"{'symbol':<28} {'sec_id':<10} {'exch':<5} "
        f"{'seg':<4} {'segment_label':<16} {'instrument':<12} {'lot':<6}"
    )
    print(header)
    print("-" * len(header))
    for row in sorted(rows, key=lambda r: r["symbol"]):
        print(
            f"{row['symbol']:<28} {row['security_id']:<10} "
            f"{row['exchange_code']:<5} {row['segment_code']:<4} "
            f"{row['segment_label']:<16} {row['instrument']:<12} "
            f"{str(row['lot_size'] or '-'):<6}"
        )

    label_counts: Counter[str] = Counter(r["segment_label"] for r in rows)
    print("\nSEGMENT LABEL DISTRIBUTION:")
    for label, n in label_counts.most_common():
        marker = (
            "  ← futures_resolver expects THIS"
            if label == "NSE_FNO"
            else "  ← UNEXPECTED — resolver will MISS these contracts"
        )
        print(f"  {label:<16} = {n} rows{marker}")

    expected = label_counts.get("NSE_FNO", 0)
    other = sum(label_counts.values()) - expected
    print(
        f"\nVERDICT: {expected} match the resolver's expected segment, "
        f"{other} do NOT."
    )
    if other > 0:
        print(
            "\nDEPLOY BLOCKER: at least one BSE futures contract lives "
            "in an unexpected segment. The resolver will silently fail "
            "to resolve that contract and the order will be placed "
            "with the unmodified TradingView ticker. INVESTIGATE before "
            "deploy.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("\nGREEN: every BSE-*-FUT row carries the NSE_FNO segment label.")


def main() -> None:
    try:
        csv_text = fetch_scrip_master()
    except httpx.HTTPError as exc:
        print(f"\nFAILED to download scrip master: {exc}", file=sys.stderr)
        sys.exit(3)
    rows = find_bse_fut_rows(csv_text)
    print_report(rows)


if __name__ == "__main__":
    main()

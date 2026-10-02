#!/usr/bin/env python3
"""M5 STAGE A.1 — physically partition data into build/ and sealed/.

The sweep harness may import ONLY canslim_swing/data/build/. Keeping the sealed
rows in a different directory (rather than filtering at read time) means a
harness bug cannot silently read the future: the rows are not in the files it
opens at all.

build/  : every row with date <= 2024-12-31
sealed/ : every row with date  > 2024-12-31
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
BOUNDARY = pd.Timestamp("2024-12-31")
BUILD = TRACK / "data" / "build"
SEALED = TRACK / "data" / "sealed"


def split_indexed(df: pd.DataFrame):
    return df[df.index <= BOUNDARY], df[df.index > BOUNDARY]


def main() -> None:
    for d in (BUILD, SEALED):
        (d / "daily").mkdir(parents=True, exist_ok=True)

    scan = pd.read_parquet(TRACK / "data" / "scan" / "daily_scan.parquet")
    sb, ss = scan[scan["date"] <= BOUNDARY], scan[scan["date"] > BOUNDARY]
    sb.to_parquet(BUILD / "daily_scan.parquet")
    ss.to_parquet(SEALED / "daily_scan.parquet")

    nifty = pd.read_parquet(TRACK / "data" / "swing" / "nifty_daily.parquet")
    nb, ns = split_indexed(nifty)
    nb.to_parquet(BUILD / "nifty_daily.parquet")
    ns.to_parquet(SEALED / "nifty_daily.parquet")

    n = 0
    for p in sorted((TRACK / "data" / "swing" / "daily").glob("*.parquet")):
        d = pd.read_parquet(p)
        db, ds = split_indexed(d)
        db.to_parquet(BUILD / "daily" / p.name)
        ds.to_parquet(SEALED / "daily" / p.name)
        n += 1

    # EPS is filing-level, not price-level: split on ANNOUNCEMENT time, because a
    # filing announced in 2025 must not be visible to the build half even if the
    # quarter it reports on ended in 2024.
    eps = pd.read_parquet(TRACK / "data" / "eps" / "eps_quarterly.parquet")
    eb = eps[eps["announce_ts"] <= BOUNDARY + pd.Timedelta(days=1)]
    es = eps[eps["announce_ts"] > BOUNDARY + pd.Timedelta(days=1)]
    eb.to_parquet(BUILD / "eps_quarterly.parquet")
    es.to_parquet(SEALED / "eps_quarterly.parquet")

    print(f"build/  scan {len(sb):,} rows | nifty {len(nb):,} | daily {n} files | eps {len(eb):,}")
    print(f"sealed/ scan {len(ss):,} rows | nifty {len(ns):,} | daily {n} files | eps {len(es):,}")
    print(f"boundary: {BOUNDARY.date()}")


if __name__ == "__main__":
    main()

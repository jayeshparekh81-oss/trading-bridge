#!/usr/bin/env python3
"""MODULE 1B part A — general stacked-series resolver, applied to EVERY symbol.

Dhan's daily endpoint sometimes returns two distinct price series for the same
dates in one response (same date, same volume, prices differing by a near-constant
factor: two adjustment vintages of the same instrument). Response ordering is NOT
stable between fetches, so keep-first silently lands on the wrong series for some
rows. This module resolves it from the data's own structure instead.

Rule, applied to every symbol regardless of whether it is currently affected:

  1. Separate the candidates ORDER-INDEPENDENTLY: within each duplicated date,
     rank the rows by close. Candidate LO takes the lowest-close row, candidate HI
     the highest. Response position is never consulted.
  2. Build two complete candidate series (dates with a single row are shared).
  3. Pick the ADJUSTED one by CONTINUITY: a correctly back-adjusted history must
     join smoothly onto the symbol's own single-row (current-basis) prices. The
     wrong candidate injects a jump equal to the series ratio at every boundary
     between a duplicated and a single-row region. Score = sum of squared log
     returns over the whole series; lower wins.
  4. If a symbol is duplicated across its ENTIRE history there is no single-row
     anchor, so the test cannot discriminate. That case is reported as AMBIGUOUS
     and the symbol is left untouched — it is not resolved by guessing.

Rebuilds data/panel_v2/daily in place from the cached raw JSON. No network calls.
Never touches data/round2, data/swing, or the habitat store.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
PANEL = TRACK / "data" / "panel_v2"
RAW = PANEL / "_raw"
DAILY = PANEL / "daily"
COLS = ["open", "high", "low", "close", "volume"]


def raw_frame(j: dict) -> pd.DataFrame:
    """Raw response -> frame, WITHOUT sorting or deduping (order preserved)."""
    idx = pd.to_datetime(pd.Series(j["timestamp"]), unit="s", utc=True) \
        .dt.tz_convert("Asia/Kolkata").dt.tz_localize(None).dt.normalize()
    df = pd.DataFrame({c: j[c] for c in COLS}, index=pd.DatetimeIndex(idx))
    df.index.name = "date"
    return df


def roughness(s: pd.Series) -> float:
    r = np.log(s.sort_index()).diff().dropna()
    return float((r ** 2).sum())


def resolve(df: pd.DataFrame):
    """Returns (clean_df, report_dict)."""
    dup_mask = df.index.duplicated(keep=False)
    n_dup_dates = int(df.index[dup_mask].nunique())
    if n_dup_dates == 0:
        return df.sort_index(), {"stacked": False}

    dup_idx = pd.DatetimeIndex(sorted(set(df.index[dup_mask])))
    singles = df[~dup_mask].sort_index()

    # --- (1) order-independent separation: rank by close within each date
    d = df[dup_mask].copy()
    d["_rank"] = d.groupby(level=0)["close"].rank(method="first")
    lo = d[d["_rank"] == 1].drop(columns="_rank")
    hi = d[d["_rank"] == d.groupby(level=0)["_rank"].transform("max")].drop(columns="_rank")
    lo, hi = lo[~lo.index.duplicated()].sort_index(), hi[~hi.index.duplicated()].sort_index()

    ratio = (hi["close"] / lo["close"])
    vol_ok = bool((hi["volume"] == lo["volume"]).all())

    # --- (2) two complete candidates
    cand_lo = pd.concat([singles, lo]).sort_index()
    cand_hi = pd.concat([singles, hi]).sort_index()

    rep = {"stacked": True, "n_dup_dates": n_dup_dates,
           "dup_first": dup_idx.min().date(), "dup_last": dup_idx.max().date(),
           "ratio_hi_over_lo_med": float(ratio.median()),
           "ratio_hi_over_lo_std": float(ratio.std()),
           "same_volume": vol_ok, "n_single_anchor": len(singles)}

    # --- (4) no anchor -> refuse to choose
    if len(singles) == 0:
        rep.update({"choice": "AMBIGUOUS", "reason": "no single-row anchor dates"})
        return None, rep

    # --- (3) continuity: smoother path wins
    s_lo, s_hi = roughness(cand_lo["close"]), roughness(cand_hi["close"])
    rep.update({"roughness_lo": round(s_lo, 4), "roughness_hi": round(s_hi, 4)})
    if abs(ratio.median() - 1) <= 1e-9:
        rep.update({"choice": "EITHER", "reason": "series identical (ratio 1.0)"})
        return cand_lo, rep
    chosen, rep["choice"] = (cand_lo, "LO") if s_lo <= s_hi else (cand_hi, "HI")
    rep["margin"] = round(abs(s_lo - s_hi), 4)
    return chosen, rep


def main() -> None:
    before, after, reports = {}, {}, []
    files = sorted(RAW.glob("*.json"))
    for p in files:
        name = p.stem
        j = json.loads(p.read_text())
        if "_error" in j or not j.get("timestamp"):
            continue
        df = raw_frame(j)
        clean, rep = resolve(df)
        rep["symbol"] = "NIFTY" if name == "_NIFTY" else name
        reports.append(rep)
        if clean is None:
            print(f"  {rep['symbol']}: AMBIGUOUS — left untouched ({rep['reason']})")
            continue
        dest = (PANEL / "nifty_daily.parquet") if name == "_NIFTY" else (DAILY / f"{name}.parquet")
        if dest.exists():
            old = pd.read_parquet(dest)
            old.index = pd.DatetimeIndex(pd.to_datetime(old.index)).normalize()
            before[rep["symbol"]] = old["close"]
        tmp = dest.with_suffix(".tmp")
        clean.to_parquet(tmp)
        os.replace(tmp, dest)
        after[rep["symbol"]] = clean["close"]

    R = pd.DataFrame(reports)
    st = R[R["stacked"]].copy()
    print("=" * 78)
    print("STACKED-SERIES DETECTION — every symbol scanned")
    print("=" * 78)
    print(f"symbols scanned: {len(R)}   affected: {len(st)}   clean: {int((~R['stacked']).sum())}")
    print()
    if len(st):
        print(st[["symbol", "n_dup_dates", "dup_first", "dup_last", "ratio_hi_over_lo_med",
                  "ratio_hi_over_lo_std", "same_volume", "n_single_anchor",
                  "roughness_lo", "roughness_hi", "choice"]].to_string(index=False))
    R.to_parquet(PANEL / "stacked_series_report.parquet")

    print()
    print("=" * 78)
    print("BEFORE vs AFTER (rows whose close changed in the rebuild)")
    print("=" * 78)
    any_change = False
    for s in sorted(set(before) & set(after)):
        a, b = before[s], after[s]
        i = a.index.intersection(b.index)
        diff = (a.loc[i] != b.loc[i])
        n = int(diff.sum())
        if n:
            any_change = True
            ch = pd.DataFrame({"before": a.loc[i][diff], "after": b.loc[i][diff]})
            ch["pct"] = (100 * (ch["after"] / ch["before"] - 1)).round(2)
            print(f"--- {s}: {n} rows changed (of {len(i)})")
            print(ch.to_string())
        extra = b.index.difference(a.index)
        if len(extra):
            print(f"--- {s}: {len(extra)} rows added")
    if not any_change:
        print("(no close values changed)")


if __name__ == "__main__":
    main()

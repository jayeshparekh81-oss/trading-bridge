#!/usr/bin/env python3
"""Module-0 · FIRST HONEST LOOK at the NSE delivery-% feature (EDA, NOT a verdict).

Consumes data/delivery_feature.parquet and prints a plain-text report:

  1. Coverage — rows / missing-days / DELIV_PER min·median·max per symbol.
  2. Pooled spike (deliv_pct_60 >= 0.90) vs non-spike forward-return comparison
     for fwd 1-day and fwd 5-day ADJUSTED returns: mean, median, hit-rate, n.
  3. Decile bucket table (DELIV_PER trailing-percentile decile → mean fwd ret).
  4. EARLY vs LATE chronological halves — the same comparison on each half, to
     see whether any early-half gap survives out-of-sample or evaporates (the
     classic overfit signature).

Deliberately NOT computed here: Sharpe, PF, cost model, position sizing, any
threshold search or strategy. This is a look, not a claim of edge.

  TODO(module-later): (a) point-in-time universe (survivorship);
  (b) real transaction costs; (c) shuffle / cross-sectional-neutral null test
  (is any gap just market beta on high-delivery days?); (d) strategy logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

SPIKE_PCT = 0.90
HORIZONS = [("fwd_ret_1d", "forward 1-day"), ("fwd_ret_5d", "forward 5-day")]


def _bps(x: float) -> str:
    return f"{x * 1e4:+.1f} bps" if pd.notna(x) else "   n/a"


def _stats(r: pd.Series) -> dict:
    r = r.dropna()
    return {
        "n": int(r.size),
        "mean": float(r.mean()) if r.size else np.nan,
        "median": float(r.median()) if r.size else np.nan,
        "hit": float((r > 0).mean()) if r.size else np.nan,  # fraction positive
    }


def _compare_block(sub: pd.DataFrame, ret_col: str, label: str) -> None:
    valid = sub[sub["spike"].notna() & sub[ret_col].notna()]
    sp = _stats(valid.loc[valid["spike"], ret_col])
    ns = _stats(valid.loc[~valid["spike"], ret_col])
    print(f"\n  {label} · {ret_col}   (n={len(valid):,} usable obs)")
    print(f"    {'group':<12}{'n':>8}{'mean':>16}{'median':>16}{'hit-rate':>12}")
    for name, s in (("spike", sp), ("non-spike", ns)):
        print(f"    {name:<12}{s['n']:>8}{_bps(s['mean']):>16}{_bps(s['median']):>16}"
              f"{(f'{s['hit'] * 100:.1f}%' if pd.notna(s['hit']) else 'n/a'):>12}")
    d_mean = sp["mean"] - ns["mean"] if pd.notna(sp["mean"]) and pd.notna(ns["mean"]) else np.nan
    d_hit = sp["hit"] - ns["hit"] if pd.notna(sp["hit"]) and pd.notna(ns["hit"]) else np.nan
    print(f"    {'Δ(spike−non)':<12}{'':>8}{_bps(d_mean):>16}{'':>16}"
          f"{(f'{d_hit * 100:+.1f}pp' if pd.notna(d_hit) else 'n/a'):>12}")


def coverage_report(df: pd.DataFrame) -> None:
    all_days = df["date"].nunique()
    print("=" * 78)
    print(f"1. COVERAGE  ({df['symbol'].nunique()} symbols, {all_days} distinct trading days, "
          f"{df['date'].min().date()} → {df['date'].max().date()})")
    print("=" * 78)
    print(f"  {'symbol':<12}{'rows':>7}{'miss':>7}{'deliv% min':>12}{'deliv% med':>12}{'deliv% max':>12}")
    g = df.groupby("symbol")
    rows = []
    for sym, sub in g:
        rows.append((
            sym, len(sub), all_days - len(sub),
            sub["deliv_per"].min(), sub["deliv_per"].median(), sub["deliv_per"].max(),
        ))
    for sym, n, miss, lo, med, hi in sorted(rows):
        flag = "  ⚠SHORT" if miss > all_days * 0.10 else ""
        print(f"  {sym:<12}{n:>7}{miss:>7}{lo:>12.1f}{med:>12.1f}{hi:>12.1f}{flag}")
    tot_miss = sum(r[2] for r in rows)
    print(f"  ── {len(rows)} symbols, {sum(r[1] for r in rows):,} rows, "
          f"{tot_miss:,} symbol-days missing vs a full grid "
          f"({'⚠ mostly the known TATAMOTORS mid-window rename' if tot_miss else 'none'}).")


def bucket_table(df: pd.DataFrame, ret_col: str) -> None:
    valid = df[df["deliv_pct_60"].notna() & df[ret_col].notna()].copy()
    if valid.empty:
        return
    valid["decile"] = np.clip((valid["deliv_pct_60"] * 10).astype(int), 0, 9)
    print(f"\n  DECILE BUCKETS · {ret_col}  (deliv_per trailing-percentile decile → mean fwd ret)")
    print(f"    {'decile':<8}{'pctile range':>16}{'n':>8}{'mean fwd':>16}{'hit-rate':>12}")
    for dec in range(10):
        r = valid.loc[valid["decile"] == dec, ret_col]
        if r.empty:
            continue
        s = _stats(r)
        lo, hi = dec / 10, (dec + 1) / 10
        print(f"    {dec:<8}{f'[{lo:.1f},{hi:.1f})':>16}{s['n']:>8}{_bps(s['mean']):>16}"
              f"{f'{s['hit'] * 100:.1f}%':>12}")


def main(argv: list[str] | None = None) -> int:
    src = DATA_DIR / "delivery_feature.parquet"
    if not src.exists():
        print(f"ERROR: {src} not found — run delivery_feature.py first.", file=sys.stderr)
        return 2
    df = pd.read_parquet(src)
    df["date"] = pd.to_datetime(df["date"])

    coverage_report(df)

    print("\n" + "=" * 78)
    print(f"2. POOLED — spike (trailing-60d DELIV_PER percentile ≥ {SPIKE_PCT:.2f}) vs non-spike")
    print("=" * 78)
    for ret_col, label in HORIZONS:
        _compare_block(df, ret_col, "POOLED (all symbols, full window)")

    print("\n" + "=" * 78)
    print("3. DECILE BUCKETS — monotonic? or noise?")
    print("=" * 78)
    for ret_col, _label in HORIZONS:
        bucket_table(df, ret_col)

    # ── 4. Chronological split (median date). Overfit test: early gap → late?
    valid_dates = df.loc[df["spike"].notna(), "date"]
    split = valid_dates.quantile(0.5)
    early = df[df["date"] <= split]
    late = df[df["date"] > split]
    print("\n" + "=" * 78)
    print(f"4. EARLY vs LATE (split at {pd.Timestamp(split).date()}) — does an early gap survive OOS?")
    print("=" * 78)
    for ret_col, _label in HORIZONS:
        _compare_block(early, ret_col, f"EARLY half (≤{pd.Timestamp(split).date()})")
        _compare_block(late, ret_col, f"LATE  half (>{pd.Timestamp(split).date()})")

    print("\n" + "=" * 78)
    print("PLAIN-TEXT SUMMARY (first look — descriptive only, NOT a verdict)")
    print("=" * 78)
    for ret_col, label in HORIZONS:
        for tag, seg in (("POOLED", df), ("EARLY", early), ("LATE", late)):
            v = seg[seg["spike"].notna() & seg[ret_col].notna()]
            sp = _stats(v.loc[v["spike"], ret_col])
            ns = _stats(v.loc[~v["spike"], ret_col])
            dm = (sp["mean"] - ns["mean"]) if pd.notna(sp["mean"]) and pd.notna(ns["mean"]) else np.nan
            print(f"  {label:<15} {tag:<7} Δmean(spike−non) = {_bps(dm)}"
                  f"   (spike n={sp['n']}, non n={ns['n']})")
    print("\n  Read the EARLY vs LATE Δ side by side: a gap that holds sign and rough")
    print("  size in BOTH halves is worth a next module; one that flips or vanishes")
    print("  in the LATE half is the overfit signature. No edge is claimed here.")
    print("  NOT computed by design: Sharpe / PF / costs / thresholds / strategy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

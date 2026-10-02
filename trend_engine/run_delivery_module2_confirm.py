#!/usr/bin/env python3
"""Module-2 · Pre-registered FRESH-DATA confirmation of the up-spike continuation lead.

SEALED PRE-REGISTERED HYPOTHESIS (fixed before results — do not edit after seeing them):
    "On an up-move day (r_t > 0), a delivery-% spike (own-history trailing-60d
     percentile >= 0.90) predicts positive forward 5-day return, AND that return
     exceeds the forward 5-day return of up-move days WITHOUT a spike, net of a
     25 bps round-trip cost. Confirmation universe: Nifty Next-50 (not used in
     discovery)."

WHY A FRESH UNIVERSE: module-1's pooled continuation test failed on cost, but its
pre-registered secondary diagnostic surfaced an up-move/down-move asymmetry
(up-move + spike continued ~+42 bps/5d, LATE-consistent). That lead was found by
LOOKING at the Nifty-50 data, so it CANNOT be confirmed on that same data. This
module re-tests it on the Nifty NEXT-50 — disjoint from module-0/1's Nifty-50.

This is module-2 ONLY: the confirmation + its null. NO strategy, sizing,
portfolio, equity curve, Sharpe or PF. STOP after the report.

  TODO(point-in-time): NEXT50 below is a current snapshot → survivorship bias.
  TODO(short side, PARKED): down-move-spike reversal/short implies SLB borrow /
       hard-to-borrow feasibility in India — out of scope until a long side passes.
  TODO(module-3, ONLY IF this passes): real strategy + walk-forward + sizing.

Reuses the module-0 fetcher (raw archive cache is universe-independent → no
re-download) and the SAME corp-action adjustment + feature logic.

Run:
    python trend_engine/run_delivery_module2_confirm.py
    python trend_engine/run_delivery_module2_confirm.py --cost-bps 25 --nperm 2000 --seed 0
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from delivery_feature import build as build_feature  # noqa: E402
from fetch_nse_delivery import NIFTY50  # noqa: E402
from fetch_nse_delivery import build as build_delivery  # noqa: E402

DATA_DIR = HERE / "data"

# ── Fresh confirmation universe: Nifty Next-50 ──────────────────────────────
# Hand-maintained snapshot (2026-07), VALIDATED against the bhav EQ series and
# confirmed DISJOINT from the module-0/1 Nifty-50 (the discovery universe).
# Survivorship accepted for now; TODO point-in-time membership.
NEXT50 = (
    "ABB", "ADANIENSOL", "ADANIGREEN", "ADANIPOWER", "AMBUJACEM",
    "DMART", "BAJAJHLDNG", "BANKBARODA", "BERGEPAINT", "BOSCHLTD",
    "CANBK", "CHOLAFIN", "COLPAL", "DABUR", "DLF",
    "GAIL", "GODREJCP", "HAVELLS", "HAL", "ICICIGI",
    "ICICIPRULI", "INDIGO", "IOC", "IRFC", "JINDALSTEL",
    "JSWENERGY", "LICI", "LODHA", "MARICO", "MOTHERSON",
    "NAUKRI", "PIDILITIND", "PFC", "PNB", "RECLTD",
    "SIEMENS", "SRF", "TATAPOWER", "TORNTPHARM", "TVSMOTOR",
    "UNITDSPR", "VBL", "VEDL", "ZYDUSLIFE", "GODREJPROP",
    "INDUSTOWER", "MANKIND", "POLYCAB", "MAXHEALTH", "HDFCAMC",
)
assert len(NEXT50) == 50, f"Next-50 must be 50, got {len(NEXT50)}"
assert not (set(NEXT50) & set(NIFTY50)), "Next-50 must be disjoint from the discovery Nifty-50"

WINDOW = (date(2023, 7, 31), date(2026, 7, 28))  # SAME window as module-0
HORIZONS = [("fwd_ret_5d", 5), ("fwd_ret_1d", 1)]  # fwd-5 is the pre-registered PRIMARY


def _bps(x: float) -> str:
    return f"{x * 1e4:+.1f}" if pd.notna(x) else "   n/a"


# ── data plumbing (reuse, no re-fetch) ───────────────────────────────────────


def ensure_next50_feature() -> pd.DataFrame:
    feat_pq = DATA_DIR / "nse_delivery_next50_feature.parquet"
    if feat_pq.exists():
        print(f"[data] reusing {feat_pq.name}")
        return pd.read_parquet(feat_pq)
    tidy_pq = DATA_DIR / "nse_delivery_next50.parquet"
    if not tidy_pq.exists():
        print("[data] assembling Next-50 tidy table from cached raw archive (no re-download)…")
        build_delivery(*WINDOW, dry_run=False, universe=NEXT50, out_stem="nse_delivery_next50")
    tidy = pd.read_parquet(tidy_pq)
    feat, _events = build_feature(tidy)
    feat.to_parquet(feat_pq, index=False)
    print(f"[data] wrote {feat_pq.name}  ({len(feat):,} rows, {feat['symbol'].nunique()} symbols)")
    return feat


# ── the up-day test ──────────────────────────────────────────────────────────


def _prep(feat: pd.DataFrame) -> pd.DataFrame:
    df = feat.copy()
    df["date"] = pd.to_datetime(df["date"])
    split = df.loc[df["spike"].notna(), "date"].quantile(0.5)
    df["half"] = np.where(df["date"] <= split, "EARLY", "LATE")
    df.attrs["split"] = pd.Timestamp(split)
    return df


def _up_valid(df: pd.DataFrame, ret_col: str) -> pd.DataFrame:
    """UP-days only (r_t > 0) with a defined spike label and a valid forward return."""
    m = df["spike"].notna() & df["ret_1d"].notna() & (df["ret_1d"] > 0) & df[ret_col].notna()
    return df.loc[m]


def _marginal(sub: pd.DataFrame, ret_col: str) -> dict:
    r = sub[ret_col].to_numpy(dtype=float)
    sp = (sub["spike"] == True).to_numpy()  # noqa: E712
    rs, rn = r[sp], r[~sp]
    sm = float(rs.mean()) if rs.size else np.nan
    nm = float(rn.mean()) if rn.size else np.nan
    return {
        "spike_n": int(rs.size), "non_n": int(rn.size),
        "spike_mean": sm, "non_mean": nm,
        "diff": sm - nm if rs.size and rn.size else np.nan,
        "spike_hit": float((rs > 0).mean()) if rs.size else np.nan,
        "non_hit": float((rn > 0).mean()) if rn.size else np.nan,
    }


def _shuffle_null(sub: pd.DataFrame, ret_col: str, real_diff: float, nperm: int,
                  rng: np.random.Generator) -> dict:
    """Among UP-days only, permute the spike labels (count preserved), recompute
    the up-spike − up-nonspike mean-difference nperm times, locate real_diff."""
    r = sub[ret_col].to_numpy(dtype=float)
    k = int((sub["spike"] == True).sum())  # noqa: E712
    m = r.size
    if k == 0 or k == m or not np.isfinite(real_diff):
        return {"p_ge": np.nan, "pctile": np.nan, "null_mean": np.nan, "null_sd": np.nan}
    total = r.sum()
    idx = np.arange(m)
    null = np.empty(nperm, dtype=float)
    for i in range(nperm):
        s = r[rng.choice(idx, size=k, replace=False)].sum()
        null[i] = s / k - (total - s) / (m - k)
    return {
        "p_ge": float((null >= real_diff).mean()),      # one-sided: lead is POSITIVE
        "pctile": float((null < real_diff).mean() * 100),
        "null_mean": float(null.mean()), "null_sd": float(null.std(ddof=1)),
    }


def analyse(feat: pd.DataFrame, cost: float, nperm: int, seed: int) -> dict:
    df = _prep(feat)
    rng = np.random.default_rng(seed)
    out: dict = {"split": df.attrs["split"], "core": {}, "null": {}}
    for ret_col, n in HORIZONS:
        for split in ("POOLED", "EARLY", "LATE"):
            sub = _up_valid(df if split == "POOLED" else df[df["half"] == split], ret_col)
            d = _marginal(sub, ret_col)
            d["spike_net"] = d["spike_mean"] - cost if pd.notna(d["spike_mean"]) else np.nan
            out["core"][(n, split)] = d
        for split in ("POOLED", "LATE"):
            sub = _up_valid(df if split == "POOLED" else df[df["half"] == split], ret_col)
            out["null"][(n, split)] = _shuffle_null(sub, ret_col, out["core"][(n, split)]["diff"], nperm, rng)
    return out


# ── printing ─────────────────────────────────────────────────────────────────


def print_core(tag: str, res: dict) -> None:
    print(f"\n  ┌─ {tag}   (chronological split {res['split'].date()}) ─")
    for _col, n in HORIZONS:
        star = "  ← PRE-REGISTERED PRIMARY" if n == 5 else ""
        print(f"  │  forward {n}-day{star}")
        print(f"  │    {'split':<7}{'up-spk n':>9}{'up-non n':>9}{'spk R̄':>11}{'non R̄':>11}"
              f"{'Δ marg':>10}{'spk net':>10}{'spk hit':>9}{'non hit':>9}")
        for split in ("POOLED", "EARLY", "LATE"):
            d = res["core"][(n, split)]
            net = _bps(d["spike_net"]) if split in ("POOLED", "LATE") else "   ·"
            print(f"  │    {split:<7}{d['spike_n']:>9}{d['non_n']:>9}"
                  f"{_bps(d['spike_mean']):>11}{_bps(d['non_mean']):>11}{_bps(d['diff']):>10}"
                  f"{net:>10}{d['spike_hit'] * 100:>8.1f}%{d['non_hit'] * 100:>8.1f}%")


def print_null(tag: str, res: dict, nperm: int) -> None:
    print(f"\n  {tag}:")
    print(f"    {'horizon':<9}{'split':<8}{'real Δ':>10}{'null μ':>9}{'null σ':>9}{'pctile':>9}{'p(≥)':>9}")
    for _col, n in HORIZONS:
        for split in ("POOLED", "LATE"):
            d = res["core"][(n, split)]
            nd = res["null"][(n, split)]
            print(f"    fwd {n:<5}{split:<8}{_bps(d['diff']):>10}{_bps(nd['null_mean']):>9}"
                  f"{nd['null_sd'] * 1e4:>8.1f}{nd['pctile']:>8.1f}%{nd['p_ge']:>9.3f}")


def verdict(res: dict, cost: float) -> None:
    print("\n" + "=" * 88)
    print("VERDICT — Next-50 (fresh universe) ONLY, against the pre-registered bar")
    print("=" * 88)
    print("  PASS requires ALL THREE on the LATE (out-of-sample) half, fwd 5-day (primary):")
    print("    (a) marginal Δ (up-spike − up-nonspike) POSITIVE")
    print(f"    (b) beats the shuffle-null (p < 0.05)")
    print(f"    (c) absolute up-spike-long NET (after {cost * 1e4:.0f} bps) POSITIVE")
    d = res["core"][(5, "LATE")]
    p = res["null"][(5, "LATE")]["p_ge"]
    a = pd.notna(d["diff"]) and d["diff"] > 0
    b = pd.notna(p) and p < 0.05
    c = pd.notna(d["spike_net"]) and d["spike_net"] > 0
    print(f"\n  fwd 5-day (LATE):  Δmarg={_bps(d['diff'])} bps   p(null)={p:.3f}   "
          f"spike-net={_bps(d['spike_net'])} bps")
    print(f"    (a) Δ>0: {'yes' if a else 'NO':<4}   (b) p<0.05: {'yes' if b else 'NO':<4}   "
          f"(c) net>0: {'yes' if c else 'NO':<4}")
    passed = a and b and c
    print("\n  " + "-" * 84)
    if passed:
        print("  RESULT: PASS. The up-spike continuation lead REPLICATES out-of-sample on a fresh")
        print("  universe, clears the null, and the long leg is net-positive after cost. Delivery-%")
        print("  earns a module-3 (real strategy + walk-forward + sizing). NOT yet an edge.")
    else:
        fails = [n for n, ok in (("positive Δ", a), ("beats null", b), ("net>0 after cost", c)) if not ok]
        print(f"  RESULT: FAIL — on the fresh Next-50 universe the pre-registered bar breaks on: "
              f"{', '.join(fails)}.")
        print("  The up-spike lead did NOT survive confirmation on data it was not discovered on.")
        print("  On this evidence, delivery-% is DEAD for this hypothesis. Next door: OI or PEAD.")
    print("  NOT computed by design: Sharpe / PF / sizing / portfolio / equity curve.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Module-2 fresh-universe confirmation (Next-50).")
    p.add_argument("--cost-bps", type=float, default=25.0)
    p.add_argument("--nperm", type=int, default=2000, help=">=1000; default 2000")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)
    cost = args.cost_bps / 1e4

    ref_pq = DATA_DIR / "delivery_feature.parquet"
    if not ref_pq.exists():
        print(f"ERROR: {ref_pq} not found — run module-0 (delivery_feature.py) first.", file=sys.stderr)
        return 2

    next50 = ensure_next50_feature()
    nifty50 = pd.read_parquet(ref_pq)

    n50 = analyse(next50, cost, args.nperm, args.seed)
    ref = analyse(nifty50, cost, args.nperm, args.seed)

    print("\n" + "#" * 88)
    print("MODULE-2 · FRESH-UNIVERSE CONFIRMATION of the up-move delivery-spike continuation lead")
    print(f"  confirmation: Nifty NEXT-50 ({next50['symbol'].nunique()} symbols) — disjoint from discovery")
    print(f"  reference:    Nifty-50 ({nifty50['symbol'].nunique()} symbols) — IN-SAMPLE, comparison only")
    print(f"  window {WINDOW[0]} → {WINDOW[1]} | cost {args.cost_bps:.0f} bps | null {args.nperm} perms seed {args.seed}")
    print(f"  test restricted to UP-DAYS (r_t > 0); no magnitude threshold (a later refinement).")
    print("#" * 88)

    print("\n" + "=" * 88)
    print("1-3. CORE TEST — mean forward return R_N on UP-days: up-SPIKE vs up-NON-spike (bps)")
    print("      Δ marg = delivery's marginal value beyond simply being an up-day. net = spike−cost.")
    print("=" * 88)
    print_core("Nifty NEXT-50  (FRESH — the actual confirmation)", n50)
    print("  └" + "─" * 40)
    print_core("Nifty-50  (in-sample reference — expect ~+42bps echo, NOT part of the verdict)", ref)

    print("\n" + "=" * 88)
    print("4. SHUFFLE-NULL on the marginal Δ (up-days only, spike labels permuted)")
    print("=" * 88)
    print_null("Nifty NEXT-50 (FRESH)", n50, args.nperm)
    print_null("Nifty-50 (in-sample reference)", ref, args.nperm)

    verdict(n50, cost)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Module-1 · Delivery-as-CONTINUATION test (corrected diagnostic + shuffle-null).

Module-0 tested a delivery spike against the SIGNED forward return and found a
null — but that structurally cancels the hypothesis. The real claim: a delivery-%
spike CONFIRMS the concurrent move (strong hands took delivery → the day's move
is real → it CONTINUES). So we test CONTINUATION, conditioned on the sign of the
spike day's own move.

Reuses module-0's cached parquets — NO re-fetch. Everything is on corp-action
ADJUSTED prices with no look-ahead:

  r_t   = adjusted close-to-close return on the spike day t (feature: ret_1d).
          Known at close of day t.
  R_N   = adjusted forward return over t+1..t+N (feature: fwd_ret_1d/fwd_ret_5d).
          Strictly future.
  c_N   = R_N * sign(r_t)   — CONTINUATION return. >0 = the day-t move continued.
  spike = module-0 flag (own-history top-decile DELIV_PER percentile >= 0.90).
          non-spike = every other row with a valid, non-zero r_t and a valid R_N.

This is module-1 ONLY: the diagnostic + the null. NO strategy, sizing, portfolio,
equity curve, Sharpe or PF. See the honest read for the explicit go/no-go bar.

  TODO(module-2, only if this passes): actual strategy + walk-forward + portfolio.
  TODO(short side): a down-move-spike continuation implies SHORTING in India —
  SLB availability / borrow cost / hard-to-borrow constraints must be modelled
  before any down-side result is treated as tradable.

Run:
    python trend_engine/run_delivery_continuation.py
    python trend_engine/run_delivery_continuation.py --cost-bps 25 --nperm 2000 --seed 0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
HORIZONS = [("fwd_ret_1d", 1), ("fwd_ret_5d", 5)]


def _bps(x: float) -> str:
    return f"{x * 1e4:+.1f}" if pd.notna(x) else "   n/a"


def _prep(feat: pd.DataFrame) -> pd.DataFrame:
    """Attach c_1/c_5 and the early/late tag. Rows with r_t==0 (undefined move
    direction) or NaN r_t are dropped per-horizon downstream, not here."""
    df = feat.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["sign_rt"] = np.sign(df["ret_1d"])
    for col, n in HORIZONS:
        df[f"c_{n}"] = df[col] * df["sign_rt"]
    # Same chronological split as module-0: median date over spike-defined rows.
    split = df.loc[df["spike"].notna(), "date"].quantile(0.5)
    df["half"] = np.where(df["date"] <= split, "EARLY", "LATE")
    df.attrs["split"] = pd.Timestamp(split)
    return df


def _valid(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Rows usable for horizon N: defined spike label, non-zero known r_t, valid
    forward continuation return."""
    m = df["spike"].notna() & df["ret_1d"].notna() & (df["ret_1d"] != 0) & df[f"c_{n}"].notna()
    return df.loc[m]


def _diff(sub: pd.DataFrame, n: int) -> dict:
    """spike vs non-spike continuation stats for one row-subset + one horizon."""
    c = sub[f"c_{n}"].to_numpy(dtype=float)
    sp = (sub["spike"] == True).to_numpy()  # noqa: E712 — nullable bool → plain mask
    cs, cn = c[sp], c[~sp]
    sm = float(cs.mean()) if cs.size else np.nan
    nm = float(cn.mean()) if cn.size else np.nan
    return {
        "spike_n": int(cs.size), "non_n": int(cn.size),
        "spike_mean": sm, "non_mean": nm,
        "diff_gross": sm - nm if cs.size and cn.size else np.nan,
        "spike_hit": float((cs > 0).mean()) if cs.size else np.nan,   # sign(R_N)==sign(r_t)
        "non_hit": float((cn > 0).mean()) if cn.size else np.nan,
    }


def _shuffle_null(sub: pd.DataFrame, n: int, real_diff: float, nperm: int, rng: np.random.Generator) -> dict:
    """Permute spike labels across rows (count preserved), recompute the
    spike−non continuation-return difference nperm times, locate real_diff."""
    c = sub[f"c_{n}"].to_numpy(dtype=float)
    k = int((sub["spike"] == True).sum())  # noqa: E712
    total = c.sum()
    m = c.size
    if k == 0 or k == m:
        return {"p_ge": np.nan, "pctile": np.nan, "null_mean": np.nan, "null_sd": np.nan}
    idx = np.arange(m)
    null = np.empty(nperm, dtype=float)
    for i in range(nperm):
        pick = rng.choice(idx, size=k, replace=False)
        s = c[pick].sum()
        # diff = mean(spike) - mean(non) = s/k - (total - s)/(m - k)
        null[i] = s / k - (total - s) / (m - k)
    p_ge = float((null >= real_diff).mean())        # one-sided: continuation POSITIVE
    pctile = float((null < real_diff).mean() * 100)  # where real sits in the null
    return {"p_ge": p_ge, "pctile": pctile, "null_mean": float(null.mean()), "null_sd": float(null.std(ddof=1))}


# ── report sections ─────────────────────────────────────────────────────────


def section_primary(df: pd.DataFrame, cost: float) -> dict:
    print("=" * 84)
    print("1. CONTINUATION RETURN  c_N = R_N · sign(r_t)   — spike vs non-spike  (mean, bps)")
    print(f"   NET charges the {cost * 1e4:.0f} bps round-trip to the acting (spike) leg once per position.")
    print("=" * 84)
    results: dict = {}
    for _col, n in HORIZONS:
        print(f"\n  ── forward {n}-day ──")
        print(f"    {'split':<7}{'spike n':>9}{'non n':>9}{'spike c̄':>12}{'non c̄':>12}"
              f"{'Δ gross':>12}{'Δ net':>12}")
        for split in ("POOLED", "EARLY", "LATE"):
            sub = _valid(df if split == "POOLED" else df[df["half"] == split], n)
            d = _diff(sub, n)
            d["diff_net"] = d["diff_gross"] - cost if pd.notna(d["diff_gross"]) else np.nan
            results[(n, split)] = d
            print(f"    {split:<7}{d['spike_n']:>9}{d['non_n']:>9}"
                  f"{_bps(d['spike_mean']):>12}{_bps(d['non_mean']):>12}"
                  f"{_bps(d['diff_gross']):>12}{_bps(d['diff_net']):>12}")
    return results


def section_hitrate(results: dict) -> None:
    print("\n" + "=" * 84)
    print("2. CONTINUATION HIT-RATE  P( sign(R_N) == sign(r_t) )   — spike vs non-spike")
    print("=" * 84)
    for _col, n in HORIZONS:
        print(f"\n  ── forward {n}-day ──")
        print(f"    {'split':<7}{'spike hit':>12}{'non hit':>12}{'Δ (pp)':>10}")
        for split in ("POOLED", "EARLY", "LATE"):
            d = results[(n, split)]
            dpp = (d["spike_hit"] - d["non_hit"]) * 100 if pd.notna(d["spike_hit"]) else np.nan
            print(f"    {split:<7}{d['spike_hit'] * 100:>11.1f}%{d['non_hit'] * 100:>11.1f}%"
                  f"{(f'{dpp:+.1f}' if pd.notna(dpp) else 'n/a'):>10}")


def section_null(df: pd.DataFrame, results: dict, nperm: int, rng: np.random.Generator) -> dict:
    print("\n" + "=" * 84)
    print(f"3. SHUFFLE-NULL on the spike−non continuation-return DIFFERENCE ({nperm} permutations)")
    print("   One-sided p = P(null Δ >= real Δ). Small p ⇒ real continuation gap unlikely by chance.")
    print("=" * 84)
    print(f"    {'horizon':<10}{'split':<8}{'real Δ gross':>14}{'null μ':>10}{'null σ':>10}"
          f"{'pctile':>9}{'p(≥)':>9}")
    null_res: dict = {}
    for _col, n in HORIZONS:
        for split in ("POOLED", "LATE"):
            sub = _valid(df if split == "POOLED" else df[df["half"] == split], n)
            real = results[(n, split)]["diff_gross"]
            nd = _shuffle_null(sub, n, real, nperm, rng)
            null_res[(n, split)] = nd
            print(f"    fwd {n:<6}{split:<8}{_bps(real):>14}{_bps(nd['null_mean']):>10}"
                  f"{nd['null_sd'] * 1e4:>9.1f}{nd['pctile']:>8.1f}%{nd['p_ge']:>9.3f}")
    return null_res


def section_secondary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 84)
    print("4. SECONDARY DIAGNOSTIC (report-only, NOT a filter) — up-move vs down-move spikes")
    print("   accumulation (up-spike) vs distribution (down-spike). Down-spike continuation")
    print("   = the move kept FALLING ⇒ a short. Mean continuation return c_N, bps.")
    print("=" * 84)
    for _col, n in HORIZONS:
        print(f"\n  ── forward {n}-day ──")
        print(f"    {'split':<8}{'dir':<12}{'n':>8}{'mean c̄':>12}{'hit':>9}")
        for split in ("POOLED", "LATE"):
            base = df if split == "POOLED" else df[df["half"] == split]
            sub = _valid(base, n)
            sp = sub[sub["spike"] == True]  # noqa: E712
            for label, mask in (("up-spike", sp["sign_rt"] > 0), ("down-spike", sp["sign_rt"] < 0)):
                c = sp.loc[mask, f"c_{n}"].to_numpy(dtype=float)
                mean = _bps(float(c.mean())) if c.size else "   n/a"
                hit = f"{(c > 0).mean() * 100:.1f}%" if c.size else "n/a"
                print(f"    {split:<8}{label:<12}{c.size:>8}{mean:>12}{hit:>9}")


def honest_read(results: dict, null_res: dict, cost: float) -> None:
    print("\n" + "=" * 84)
    print("HONEST READ — against the explicit bar (descriptive, NOT a verdict of 'edge')")
    print("=" * 84)
    print("  Bar: pursue ONLY IF, for a horizon, the LATE-half continuation Δ is (a) POSITIVE,")
    print(f"  (b) beats the shuffle-null (low p), AND (c) survives the {cost * 1e4:.0f} bps cost (Δnet > 0).")
    any_pass = False
    for _col, n in HORIZONS:
        late = results[(n, "LATE")]
        p = null_res[(n, "LATE")]["p_ge"]
        dnet = late["diff_gross"] - cost
        a = pd.notna(late["diff_gross"]) and late["diff_gross"] > 0
        b = pd.notna(p) and p < 0.05
        c = pd.notna(dnet) and dnet > 0
        verdict = "PASS" if (a and b and c) else "FAIL"
        any_pass = any_pass or (a and b and c)
        print(f"\n  fwd {n}-day (LATE):  Δgross={_bps(late['diff_gross'])} bps  "
              f"p(null)={p:.3f}  Δnet={_bps(dnet)} bps")
        print(f"     (a) positive Δ: {'yes' if a else 'NO':<4}  "
              f"(b) beats null p<0.05: {'yes' if b else 'NO':<4}  "
              f"(c) Δnet>0 after cost: {'yes' if c else 'NO':<4}  →  {verdict}")
    print("\n  " + "-" * 80)
    if any_pass:
        print("  READ: at least one horizon clears all three rails in the LATE (out-of-sample)")
        print("  half. Delivery-% continuation is worth a module-2 walk-forward test — NOT yet")
        print("  an edge, and NOT yet costed as a portfolio. Proceed cautiously.")
    else:
        print("  READ: NO horizon clears all three rails in the LATE half. The corrected")
        print("  continuation hypothesis also FAILS out-of-sample once measured against the")
        print("  shuffle-null and the round-trip cost. On this evidence, delivery-% is DEAD")
        print("  for this hypothesis — do not build a strategy on it.")
    print("  NOT computed by design: Sharpe / PF / sizing / portfolio / equity curve.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Delivery-as-continuation test (module-1).")
    p.add_argument("--cost-bps", type=float, default=25.0, help="round-trip cost, bps (default 25)")
    p.add_argument("--nperm", type=int, default=2000, help="shuffle-null permutations (default 2000, >=1000)")
    p.add_argument("--seed", type=int, default=0, help="RNG seed for a reproducible null (default 0)")
    args = p.parse_args(argv)

    src = DATA_DIR / "delivery_feature.parquet"
    if not src.exists():
        print(f"ERROR: {src} not found — run delivery_feature.py (module-0) first.", file=sys.stderr)
        return 2
    cost = args.cost_bps / 1e4
    rng = np.random.default_rng(args.seed)
    df = _prep(pd.read_parquet(src))

    print("#" * 84)
    print("MODULE-1 · DELIVERY-AS-CONTINUATION TEST")
    print(f"  source: delivery_feature.parquet ({len(df):,} rows, {df['symbol'].nunique()} symbols)")
    print(f"  window: {df['date'].min().date()} → {df['date'].max().date()}   "
          f"chronological split: {df.attrs['split'].date()} (same as module-0)")
    print(f"  cost: {args.cost_bps:.0f} bps round-trip | null: {args.nperm} perms, seed {args.seed}")
    print(f"  rows with r_t==0 (undefined direction) are excluded per horizon.")
    print("#" * 84 + "\n")

    results = section_primary(df, cost)
    section_hitrate(results)
    null_res = section_null(df, results, args.nperm, rng)
    section_secondary(df)
    honest_read(results, null_res, cost)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

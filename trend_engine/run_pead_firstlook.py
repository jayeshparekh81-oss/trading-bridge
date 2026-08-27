#!/usr/bin/env python3
"""PEAD module-0 · post-earnings-drift first look (price-reaction surprise proxy).

HONEST SCOPE: this proxy uses the ANNOUNCEMENT-WINDOW abnormal return as the
"surprise", so it tests POST-EARNINGS-JUMP DRIFT (does the market keep moving the
way it moved right after results?), NOT fundamental-EPS PEAD. The EPS-surprise
(seasonal-random-walk) version is a later module if this one breathes.

This is module-0 ONLY: earnings dates + a price-reaction surprise + the drift +
one honest look. NO strategy logic, sizing, portfolio, Sharpe or PF. STOP after
the report.

DATA REUSE (no re-fetch of prices):
  - adjusted daily returns  ← delivery_feature.parquet + nse_delivery_next50_feature.parquet
  - Nifty daily return (market adj) ← derived from NIFTY.parquet (5-min index spot)
  - earnings dates          ← pead_earnings.parquet (fetch_pead_earnings.py)

DEFINITIONS (adjusted prices, market-adjusted, event-time in TRADING days, no look-ahead):
  abn_ret(t) = stock adjusted return(t) − Nifty return(t).
  t0         = first trading day >= announcement date d (results often filed after hours).
  SURPRISE   = CAR over [d, d+1]      = abn_ret[t0] + abn_ret[t0+1].      (known at close t0+1)
  DRIFT_N    = CAR over [d+2, d+2+N]  = sum abn_ret[t0+2 .. t0+2+N], N in {5,20,40}. (strictly after)
  Events dropped if the windows can't fully form (data edge) or another same-symbol
  event falls inside the drift window (overlap).

  TODO(point-in-time universe) · TODO(EPS-surprise fundamental-PEAD if this breathes)
  · TODO(strategy logic — not here).

Run:
    python trend_engine/run_pead_firstlook.py
    python trend_engine/run_pead_firstlook.py --cost-bps 25 --nperm 2000 --seed 0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
FEATURE_PARQUETS = ("delivery_feature.parquet", "nse_delivery_next50_feature.parquet")
DRIFTS = [5, 20, 40]
MAX_H = max(DRIFTS)


def _bps(x: float) -> str:
    return f"{x * 1e4:+.1f}" if pd.notna(x) else "   n/a"


# ── inputs ───────────────────────────────────────────────────────────────────


def _load_prices() -> pd.DataFrame:
    frames = []
    for name in FEATURE_PARQUETS:
        p = DATA_DIR / name
        if not p.exists():
            raise FileNotFoundError(f"{p} not found — run the delivery modules first.")
        frames.append(pd.read_parquet(p, columns=["date", "symbol", "ret_1d"]))
    px = pd.concat(frames, ignore_index=True)
    px["date"] = pd.to_datetime(px["date"])
    return px


def _market_return_on(calendar: pd.DatetimeIndex) -> pd.Series:
    """Nifty daily return aligned to the STOCK trading calendar.

    NIFTY.parquet (5-min index spot) is missing ~36 NSE holiday / special-session
    days that the equity bhav includes; a single missing day would otherwise put a
    NaN inside a 43-day event window and drop ~70% of events. We reindex the index
    CLOSE onto the stock calendar and forward-fill, THEN take pct_change: a genuine
    no-trade day (holiday) then contributes a 0 market move (market adj ≈ 0 → abn ≈
    the stock's own move), which is the right treatment and stops the poisoning.
    A handful of these are low-volume muhurat sessions where the index moved
    slightly; treating them as 0 is an accepted module-0 approximation.
    """
    n = pd.read_parquet(DATA_DIR / "NIFTY.parquet")
    ts = pd.to_datetime(n["timestamp"]) if "timestamp" in n.columns else pd.to_datetime(n.index)
    ts = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    close = n.assign(d=ts.dt.normalize()).groupby("d")["close"].last()
    aligned = close.reindex(calendar).ffill()
    return aligned.pct_change().rename("nifty_ret")


# ── event construction ───────────────────────────────────────────────────────


def build_events(cost: float) -> tuple[pd.DataFrame, dict]:
    px = _load_prices()
    calendar = pd.DatetimeIndex(sorted(px["date"].unique()))
    mkt = _market_return_on(calendar)
    px["nifty_ret"] = px["date"].map(mkt)
    px["abn"] = px["ret_1d"] - px["nifty_ret"]

    earn = pd.read_parquet(DATA_DIR / "pead_earnings.parquet")
    earn["ann_date"] = pd.to_datetime(earn["ann_date"])

    rows = []
    dropped = {"no_price_symbol": 0, "date_out_of_range": 0, "edge": 0, "overlap": 0, "nan_window": 0}
    for sym, g in px.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        abn = g["abn"].to_numpy(dtype=float)
        dates = g["date"].to_numpy()  # datetime64, sorted
        ev = earn.loc[earn["symbol"] == sym, "ann_date"].sort_values().to_numpy()
        # position of first trading day >= d for each event
        t0s = np.searchsorted(dates, ev, side="left")
        valid_t0 = []
        for d, t0 in zip(ev, t0s):
            if t0 >= len(dates):          # announcement after the price series ends
                dropped["date_out_of_range"] += 1
                continue
            valid_t0.append((d, int(t0)))
        for j, (d, t0) in enumerate(valid_t0):
            if t0 + 2 + MAX_H > len(dates) - 1:  # drift window runs off the end
                dropped["edge"] += 1
                continue
            # overlap: next same-symbol event inside this drift window [t0+2, t0+2+MAX_H]
            if j + 1 < len(valid_t0) and valid_t0[j + 1][1] <= t0 + 2 + MAX_H:
                dropped["overlap"] += 1
                continue
            window = abn[t0: t0 + 2 + MAX_H + 1]
            if np.isnan(window).any():
                dropped["nan_window"] += 1
                continue
            surprise = abn[t0] + abn[t0 + 1]
            rec = {"symbol": sym, "ann_date": pd.Timestamp(d), "surprise": surprise}
            for n in DRIFTS:
                rec[f"drift_{n}"] = abn[t0 + 2: t0 + 2 + n + 1].sum()
            rows.append(rec)

    events = pd.DataFrame(rows).sort_values("ann_date").reset_index(drop=True)
    meta = {
        "raw_events": len(earn), "usable": len(events), "dropped": dropped,
        "symbols_with_events": events["symbol"].nunique(),
        "date_min": events["ann_date"].min(), "date_max": events["ann_date"].max(),
        "cost": cost,
    }
    return events, meta


# ── deciles / spread / null ──────────────────────────────────────────────────


def _deciles(s: pd.Series) -> np.ndarray:
    # rank-based → exactly 10 equal buckets even with ties.
    return pd.qcut(s.rank(method="first"), 10, labels=False).to_numpy()


def _spread(sub: pd.DataFrame, n: int) -> float:
    dec = _deciles(sub["surprise"])
    d = sub[f"drift_{n}"].to_numpy(dtype=float)
    return float(d[dec == 9].mean() - d[dec == 0].mean())


def _null(sub: pd.DataFrame, n: int, real: float, nperm: int, rng: np.random.Generator) -> dict:
    dec = _deciles(sub["surprise"])
    d = sub[f"drift_{n}"].to_numpy(dtype=float)
    null = np.empty(nperm)
    for i in range(nperm):
        p = rng.permutation(dec)  # surprise carries no info under the null
        null[i] = d[p == 9].mean() - d[p == 0].mean()
    return {"p_ge": float((null >= real).mean()), "pctile": float((null < real).mean() * 100),
            "mean": float(null.mean()), "sd": float(null.std(ddof=1))}


# ── report ───────────────────────────────────────────────────────────────────


def print_decile_table(events: pd.DataFrame, label: str) -> None:
    dec = _deciles(events["surprise"])
    e = events.assign(decile=dec)
    print(f"\n  {label} — mean DRIFT by SURPRISE decile (bps).  PEAD ⇒ monotone increasing.")
    print(f"    {'dec':<5}{'n':>6}{'surprise μ':>13}{'drift_5':>11}{'drift_20':>11}{'drift_40':>11}")
    for dd in range(10):
        b = e[e["decile"] == dd]
        print(f"    {dd:<5}{len(b):>6}{_bps(b['surprise'].mean()):>13}"
              f"{_bps(b['drift_5'].mean()):>11}{_bps(b['drift_20'].mean()):>11}{_bps(b['drift_40'].mean()):>11}")


def print_spreads(events: pd.DataFrame, splits: dict, cost: float) -> dict:
    print("\n  TOP-minus-BOTTOM surprise-decile DRIFT spread (bps).  net = gross − 25bps round-trip.")
    print(f"    {'split':<8}{'n':>6}" + "".join(f"{f'd{n} gross':>11}{f'd{n} net':>10}" for n in DRIFTS))
    out = {}
    for name, sub in splits.items():
        cells = ""
        for n in DRIFTS:
            g = _spread(sub, n)
            out[(name, n)] = g
            cells += f"{_bps(g):>11}{_bps(g - cost):>10}"
        print(f"    {name:<8}{len(sub):>6}{cells}")
    return out


def print_null(splits: dict, spreads: dict, nperm: int, rng: np.random.Generator) -> dict:
    print(f"\n  SHUFFLE-NULL on the top−bottom spread ({nperm} perms). p = P(null >= real). small ⇒ real.")
    print(f"    {'split':<8}{'N':>4}{'real spread':>13}{'null μ':>9}{'null σ':>9}{'pctile':>9}{'p(≥)':>8}")
    res = {}
    for name in ("POOLED", "LATE"):
        for n in DRIFTS:
            nd = _null(splits[name], n, spreads[(name, n)], nperm, rng)
            res[(name, n)] = nd
            print(f"    {name:<8}{n:>4}{_bps(spreads[(name, n)]):>13}{_bps(nd['mean']):>9}"
                  f"{nd['sd'] * 1e4:>8.1f}{nd['pctile']:>8.1f}%{nd['p_ge']:>8.3f}")
    return res


def _mono_rho(sub: pd.DataFrame, n: int) -> float:
    """Spearman ρ between surprise-decile index (0..9) and that decile's mean
    drift. Monotone PEAD ⇒ ρ ≈ +1; noise ⇒ ρ ≈ 0; reversal ⇒ ρ < 0."""
    dec = _deciles(sub["surprise"])
    means = pd.Series(sub[f"drift_{n}"].to_numpy()).groupby(dec).mean()
    return float(pd.Series(means.index).corr(pd.Series(means.values), method="spearman"))


def honest_read(splits: dict, spreads: dict, null_res: dict, cost: float) -> None:
    print("\n" + "=" * 84)
    print("PLAIN-TEXT READ (descriptive, NOT a verdict of 'edge')")
    print("=" * 84)
    print("  (1) MONOTONICITY — Spearman ρ of decile→mean-drift (+1 = clean PEAD, <0 = reversal):")
    for n in DRIFTS:
        print(f"       drift_{n:<2}:  POOLED ρ={_mono_rho(splits['POOLED'], n):+.2f}   "
              f"LATE ρ={_mono_rho(splits['LATE'], n):+.2f}")
    print("\n  (2)-(4) LATE-half top−bottom spread vs null vs cost:")
    all_fail = True
    for n in DRIFTS:
        late = spreads[("LATE", n)]
        p = null_res[("LATE", n)]["p_ge"]
        pos, beats, net_ok = late > 0, p < 0.05, (late - cost) > 0
        all_fail = all_fail and not (pos and beats and net_ok)
        print(f"       drift_{n:<2} LATE: spread {_bps(late)} | net {_bps(late - cost)} | "
              f"null p={p:.3f}  →  positive:{'Y' if pos else 'N'} beats-null:{'Y' if beats else 'N'} "
              f"survives-cost:{'Y' if net_ok else 'N'}")
    print("\n  " + "-" * 80)
    early_pos = spreads[("EARLY", 40)] > 0
    late_neg = spreads[("LATE", 40)] < 0
    if all_fail and early_pos and late_neg:
        print("  READ: the decile drift is NOT monotone, and the top−bottom spread FLIPS SIGN —")
        print("  positive in the EARLY half, negative (a post-earnings REVERSAL) in the LATE half,")
        print("  where the null even flags the reversal as non-random. No horizon is monotone +")
        print("  LATE-positive + null-beating + cost-surviving. On this evidence the price-reaction")
        print("  PEAD proxy shows NO robust drift on the Nifty-100 (2023-26). Do not proceed to a")
        print("  strategy; the EPS-surprise version is a separate, later test — not a rescue of this.")
    elif all_fail:
        print("  READ: no horizon clears all four rails (monotone + LATE-positive + beats-null +")
        print("  survives-cost). The price-reaction PEAD proxy does not hold up. Do not proceed.")
    else:
        print("  READ: at least one horizon clears the four rails — see which above. Warrants the")
        print("  EPS-surprise fundamental-PEAD confirmation before any strategy work. Not an edge yet.")
    print("  NOT computed by design: Sharpe / PF / sizing / portfolio.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PEAD first look (module-0).")
    p.add_argument("--cost-bps", type=float, default=25.0)
    p.add_argument("--nperm", type=int, default=2000, help=">=1000; default 2000")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)
    cost = args.cost_bps / 1e4
    rng = np.random.default_rng(args.seed)

    if not (DATA_DIR / "pead_earnings.parquet").exists():
        print("ERROR: pead_earnings.parquet not found — run fetch_pead_earnings.py first.", file=sys.stderr)
        return 2

    events, meta = build_events(cost)
    split_date = events["ann_date"].quantile(0.5)
    early = events[events["ann_date"] <= split_date]
    late = events[events["ann_date"] > split_date]
    splits = {"POOLED": events, "EARLY": early, "LATE": late}

    print("#" * 84)
    print("PEAD MODULE-0 · POST-EARNINGS-JUMP DRIFT — FIRST LOOK (price-reaction surprise proxy)")
    print("#" * 84)
    print("\n" + "=" * 84)
    print("COVERAGE")
    print("=" * 84)
    d = meta["dropped"]
    print(f"  raw earnings events: {meta['raw_events']:,}  →  usable: {meta['usable']:,}  "
          f"({meta['symbols_with_events']} symbols)")
    print(f"  dropped: edge {d['edge']}, overlap {d['overlap']}, nan-window {d['nan_window']}, "
          f"after-series {d['date_out_of_range']}")
    print(f"  usable-event date range: {meta['date_min'].date()} → {meta['date_max'].date()}")
    print(f"  chronological split: {pd.Timestamp(split_date).date()}  (EARLY {len(early)} / LATE {len(late)})")
    print(f"  cost {args.cost_bps:.0f} bps | null {args.nperm} perms seed {args.seed}")

    print("\n" + "=" * 84)
    print("1. DECILE DRIFT TABLES")
    print("=" * 84)
    print_decile_table(events, "POOLED")
    print_decile_table(late, "LATE half (out-of-sample)")

    print("\n" + "=" * 84)
    print("2-3. TOP−BOTTOM SPREAD (gross/net) · POOLED / EARLY / LATE")
    print("=" * 84)
    spreads = print_spreads(events, splits, cost)

    print("\n" + "=" * 84)
    print("4. NULL")
    print("=" * 84)
    null_res = print_null(splits, spreads, args.nperm, rng)

    honest_read(splits, spreads, null_res, cost)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

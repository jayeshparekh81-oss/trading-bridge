#!/usr/bin/env python3
"""MODULE 1B steps 4-6 — verify panel_v2 against the old stores. READ ONLY.

Step 4: panel_v2 vs data/round2/daily, and vs data/swing/daily.
        Ratio mismatches split into corp-action-explained (simple rational
        factor = split/bonus) vs irregular (no obvious explanation).
Step 5: cliff scan on panel_v2, single-day close-to-close beyond -15%.
Step 6: coverage report.

Reads data/round2 and data/swing; writes nothing to them. No indicators,
no signals, no strategy logic.
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
NEW = TRACK / "data" / "panel_v2" / "daily"
R2 = TRACK / "data" / "round2" / "daily"
SW = TRACK / "data" / "swing" / "daily"
UNI = [l.strip() for l in (TRACK / "config" / "universe_frozen.txt").read_text().splitlines() if l.strip()]
TEN = ["RECLTD", "PNBHOUSING", "SUZLON", "ITC", "UPL", "BHARTIARTL",
       "HINDUNILVR", "INOXWIND", "TATACONSUM", "BEL"]
IPO15 = ["DELHIVERY", "HYUNDAI", "IREDA", "JIOFIN", "KAYNES", "KFINTECH", "LICI",
         "MANKIND", "NUVAMA", "NYKAA", "PAYTM", "PREMIERENE", "SWIGGY", "VMM",
         "WAAREEENER"]


def load(p):
    d = pd.read_parquet(p)
    d.index = pd.DatetimeIndex(pd.to_datetime(d.index)).normalize()
    return d


def explain_ratio(x, max_den=12, tol=0.002):
    """Simple rational near x => split/bonus factor. Else irregular."""
    f = Fraction(float(x)).limit_denominator(max_den)
    if f.numerator == 0:
        return None, np.inf
    err = abs(float(f) - x) / x
    return (f"{f.numerator}/{f.denominator} = {float(f):.6f}", err) if err <= tol else (None, err)


def compare(tag, other_dir, restrict=None):
    rows = []
    for s in UNI:
        pa, pb = NEW / f"{s}.parquet", other_dir / f"{s}.parquet"
        if not (pa.exists() and pb.exists()):
            continue
        a, b = load(pa), load(pb)
        i = a.index.intersection(b.index)
        if restrict is not None:
            i = i[(i >= restrict[0]) & (i <= restrict[1])]
        if len(i) < 3:
            rows.append({"symbol": s, "n": len(i), "too_few": True})
            continue
        ca, cb = a.loc[i, "close"], b.loc[i, "close"]
        r = ca / cb
        rel = (ca - cb).abs() / cb
        rows.append({"symbol": s, "n": len(i), "too_few": False,
                     "first": i.min().date(), "last": i.max().date(),
                     "pct_exact": 100 * float((rel == 0).mean()),
                     "pct_within_0p5": 100 * float((rel <= 0.005).mean()),
                     "ratio_med": float(r.median()), "ratio_std": float(r.std())})
    d = pd.DataFrame(rows)
    print("=" * 78)
    print(f"STEP 4 — panel_v2  vs  {tag}")
    print("=" * 78)
    ok = d[~d["too_few"]]
    print(f"symbols compared      : {len(ok)}   (too few overlap days: "
          f"{sorted(d.loc[d['too_few'], 'symbol'])})")
    print(f"total overlapping days: {int(ok['n'].sum()):,}")
    print(f"  closes EXACTLY equal      : mean {ok['pct_exact'].mean():.2f}%  "
          f"median {ok['pct_exact'].median():.2f}%  "
          f"(symbols at 100%: {int((ok['pct_exact'] == 100).sum())}/{len(ok)})")
    print(f"  closes within 0.5%        : mean {ok['pct_within_0p5'].mean():.2f}%  "
          f"median {ok['pct_within_0p5'].median():.2f}%  "
          f"(symbols at 100%: {int((ok['pct_within_0p5'] == 100).sum())}/{len(ok)})")
    print(f"  median ratio: min {ok['ratio_med'].min():.6f}  max {ok['ratio_med'].max():.6f}")
    print(f"  ratio std   : min {ok['ratio_std'].min():.6f}  max {ok['ratio_std'].max():.6f}")
    off = ok[(ok["ratio_med"] - 1).abs() > 0.005].sort_values("ratio_med")
    print()
    print(f"  symbols whose MEDIAN RATIO is NOT within 0.5% of 1.0: {len(off)}")
    if len(off):
        out = []
        for _, r in off.iterrows():
            expl, err = explain_ratio(r["ratio_med"])
            out.append({"symbol": r["symbol"], "n": r["n"], "ratio_med": round(r["ratio_med"], 6),
                        "ratio_std": round(r["ratio_std"], 6),
                        "offset_pct": round(100 * (r["ratio_med"] - 1), 3),
                        "verdict": "CORP-ACTION" if expl else "IRREGULAR",
                        "factor": expl if expl else f"no simple fraction (best-fit err {err:.2%})"})
        o = pd.DataFrame(out)
        for v in ("CORP-ACTION", "IRREGULAR"):
            sub = o[o["verdict"] == v]
            print(f"\n  --- {v} ({len(sub)}) ---")
            print(sub.to_string(index=False) if len(sub) else "  (none)")
    print()
    return d


def main() -> None:
    files = sorted(NEW.glob("*.parquet"))
    print(f"panel_v2: {len(files)} symbol parquets\n")

    d_r2 = compare("data/round2/daily  (2015 -> 2021-10-29)", R2)
    d_sw = compare("data/swing/daily   (15m rollup, 2021-08 -> 2026-07)", SW)

    # the ten known offset symbols — does the split-at-ex-date story hold?
    print("=" * 78)
    print("STEP 4b — the 10 offset symbols: is the explanation now consistent?")
    print("=" * 78)
    print("If panel_v2 is the adjusted truth and the 15m rollup is raw before an")
    print("unadjusted ex-date, the panel_v2/swing ratio must be a STEP: a constant")
    print("!=1 before the ex-date and ~1.0 after it.\n")
    rows = []
    for s in TEN:
        a, b = load(NEW / f"{s}.parquet"), load(SW / f"{s}.parquet")
        i = a.index.intersection(b.index)
        r = (a.loc[i, "close"] / b.loc[i, "close"]).dropna()
        lr = np.log(r)
        step = lr.diff().abs()
        k = int(step.values[1:].argmax()) + 1 if len(step) > 1 else 0
        exd = r.index[k]
        pre, post = r.iloc[:k], r.iloc[k:]
        rows.append({"symbol": s,
                     "step_date": exd.date(),
                     "n_pre": len(pre), "ratio_pre": round(float(pre.median()), 6),
                     "n_post": len(post), "ratio_post": round(float(post.median()), 6),
                     "pre_factor": (explain_ratio(float(pre.median()))[0] or "irregular"),
                     "post_is_1": bool(abs(float(post.median()) - 1) <= 0.005)})
    print(pd.DataFrame(rows).to_string(index=False))
    print()

    # ---------------- STEP 5
    print("=" * 78)
    print("STEP 5 — CLIFF SCAN on panel_v2: single-day close-to-close beyond -15%")
    print("=" * 78)
    hits, ups = [], 0
    for s in UNI:
        d = load(NEW / f"{s}.parquet")
        pc = d["close"].pct_change()
        ups += int((pc >= 0.15).sum())
        for dt_, v in pc[pc <= -0.15].items():
            hits.append({"symbol": s, "date": dt_.date(), "pct": round(100 * v, 2),
                         "close_before": float(d["close"].shift(1).loc[dt_]),
                         "close_after": float(d["close"].loc[dt_])})
    H = pd.DataFrame(hits).sort_values(["date", "symbol"])
    print(f"total hits below -15%: {len(H)}  across {H['symbol'].nunique()} symbols")
    print(f"(for context only, not requested: single-day moves >= +15%: {ups})")
    print()
    vc = H["date"].value_counts()
    print("dates where >=5 symbols fell >=15% on the same day (market-wide, for your triage):")
    print(vc[vc >= 5].sort_index().to_string())
    print()
    print("FULL LIST (nothing excluded), chronological:")
    print(H.to_string(index=False))
    print()

    # ---------------- STEP 6
    print("=" * 78)
    print("STEP 6 — COVERAGE REPORT")
    print("=" * 78)
    cal = None
    info = {}
    for s in UNI:
        d = load(NEW / f"{s}.parquet")
        info[s] = d
        cal = d.index if cal is None else cal.union(d.index)
    print(f"panel union calendar: {len(cal)} sessions   "
          f"FIRST {cal.min().date()}   LAST {cal.max().date()}")

    rec = []
    for s, d in info.items():
        inr = cal[(cal >= d.index.min()) & (cal <= d.index.max())]
        missing = len(inr.difference(d.index))
        pos = np.searchsorted(cal, d.index.values)
        maxgap = int(np.diff(pos).max() - 1) if len(pos) > 1 else 0
        pre2017 = int((d.index < pd.Timestamp("2017-01-01")).sum())
        rec.append({"symbol": s, "first": d.index.min().date(), "last": d.index.max().date(),
                    "sessions": len(d), "missing": missing, "max_gap": maxgap,
                    "sess_before_2017": pre2017})
    C = pd.DataFrame(rec)
    n300 = int((C["sess_before_2017"] >= 300).sum())
    print(f"symbols with >=300 sessions of history before 2017-01-01: "
          f"{n300} / {len(C)}  ({100*n300/len(C):.1f}%)")
    print()
    print(f"panel-wide: total in-range missing sessions = {int(C['missing'].sum())}; "
          f"symbols with zero missing = {int((C['missing'] == 0).sum())}/{len(C)}; "
          f"largest internal gap anywhere = {int(C['max_gap'].max())} sessions "
          f"({C.loc[C['max_gap'].idxmax(), 'symbol']})")
    print()
    named = ["NBCC", "PATANJALI", "ADANIENSOL", "CDSL"] + IPO15
    N = C[C["symbol"].isin(named)].copy()
    N["order"] = N["symbol"].map({s: i for i, s in enumerate(named)})
    N = N.sort_values("order").drop(columns="order")
    N["usable_252"] = np.where((N["sessions"] >= 252) & (N["max_gap"] <= 5), "YES",
                               np.where(N["sessions"] < 252, "NO - too short",
                                        "NO - internal gap"))
    print("NAMED SYMBOLS:")
    print(N.to_string(index=False))
    print()
    print("worst 10 by missing sessions, whole panel:")
    print(C.nlargest(10, "missing").to_string(index=False))
    C.to_parquet(TRACK / "data" / "panel_v2" / "coverage.parquet")
    H.to_parquet(TRACK / "data" / "panel_v2" / "cliffs.parquet")


if __name__ == "__main__":
    main()

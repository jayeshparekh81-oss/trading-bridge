"""Big-print threshold calibration — measurement tool (research, read-only).

Founder's question (2026-07-16): `bigprint.notional_threshold` is 0 (INERT), so the
big_print component (weight 20 of 60) contributes ZERO on every candidate. Big prints
are the institutional footprint (D1 metaorder), and tonight's cost analysis says we need
BIGGER moves — exactly what follows real institutional prints. So: what print size, if
any, precedes a move worth trading (>= min_viable_R)?

This tool, per recorded day, PURELY MEASURES (never sets config):
  1. DISTRIBUTION — trade notional (price*size) and size, per instrument CLASS
     (index futures, ATM+/-2 options, the 5 BANKNIFTY-constituent equities): min /
     median / p75 / p90 / p95 / p99 / p99.5 / max, and the count above each percentile.
     Reported in Rupee notional AND in lots (lot size DERIVED from the data as the GCD of
     traded quantities, not copied from chain config — which for these days disagrees).
  2. PREDICTIVE (index futures only) — for each candidate threshold (p90/p95/p99/p99.5):
     prints/day, and the price move in the NEXT 5/15/30/60s after a print, vs the
     all-trades baseline: directional hit-rate (sign(move)==sign(aggressor)) + mean |move|.
  3. COST-LINK — the real question. After a print above each threshold, what fraction of
     the time does price move (in the aggressor's direction) >= min_viable_R within 60s
     (NIFTY 20pt / BANKNIFTY 50pt), vs the all-trades base rate?

LEAK-PROOF (mirrors research/gex_predictive): the two forward-outcome primitives
(`forward_point_move`, `max_favorable_excursion`) are HARD-bounded at t+horizon — a tick
one nanosecond past the horizon is invisible. Trade extraction itself is causal (volume
delta uses only past volume). Percentile thresholds are measured on the same 2 days they
are tested on, so every number here is IN-SAMPLE and labelled HYPOTHESIS-FROM-2-DAYS:
N=2 is a first look + a tool, NEVER a conclusion. The 15-day sweep decides the threshold.

Read-only: consumes data/<date>/<instrument>.parquet (R0 ticks). No config touched.
"""

from __future__ import annotations

import bisect
from math import gcd
from pathlib import Path
from typing import Optional

import pyarrow.parquet as pq

from tape.classify import BUY
from tape.trades import Trade, TradeExtractor

NS = 1_000_000_000

INDEX_FUT = {"NIFTY": "NIFTY_FUT_61093", "BANKNIFTY": "BANKNIFTY_FUT_61088"}
SPOT = {"NIFTY": "NIFTY_SPOT_13", "BANKNIFTY": "BANKNIFTY_SPOT_25"}
# The 5 BANKNIFTY-constituent equities recorded (bare-symbol files).
BANK_EQUITIES = ["HDFCBANK_1333", "ICICIBANK_4963", "SBIN_3045", "AXISBANK_5900", "KOTAKBANK_1922"]
# tonight's cost floor (min_viable_R), in index points, per underlying.
MIN_VIABLE_R = {"NIFTY": 20.0, "BANKNIFTY": 50.0}

PCTS = [50, 75, 90, 95, 99, 99.5]
CANDIDATE_PCTS = [90, 95, 99, 99.5]
HORIZONS_S = [5, 15, 30, 60]

_LOAD_COLS = ["ts_recv_ns", "ltp", "ltq", "volume", "bid_price_1", "ask_price_1"]


# -- primitives (leak-proof, unit-tested) -----------------------------------
def percentile(sorted_vals: list[float], p: float) -> float:
    """Nearest-rank percentile (no interpolation). ``sorted_vals`` must be ascending."""
    if not sorted_vals:
        return 0.0
    k = max(1, min(len(sorted_vals), int(-(-p / 100.0 * len(sorted_vals) // 1))))  # ceil
    return sorted_vals[k - 1]


def forward_point_move(ts: list[int], price: list[float], i: int, horizon_ns: int) -> Optional[float]:
    """Signed price change from trade ``i`` to the LAST tick at/before t_i+horizon.

    HARD no-look-ahead: uses only ticks with ts <= ts[i]+horizon_ns. Returns None if no
    later tick falls inside the window (so the horizon is genuinely observed, not padded).
    """
    cutoff = ts[i] + horizon_ns
    j = bisect.bisect_right(ts, cutoff) - 1     # last index with ts <= cutoff
    if j <= i:
        return None
    return price[j] - price[i]


def max_favorable_excursion(ts: list[int], price: list[float], side: int, i: int,
                            horizon_ns: int) -> Optional[float]:
    """Best move IN THE AGGRESSOR'S DIRECTION over (t_i, t_i+horizon]. HARD-bounded.

    A tick past the horizon cannot affect the result. Returns None if the window is empty.
    """
    cutoff = ts[i] + horizon_ns
    hi = bisect.bisect_right(ts, cutoff)        # exclusive upper bound
    if hi <= i + 1:
        return None
    p0 = price[i]
    best = None
    for k in range(i + 1, hi):
        m = side * (price[k] - p0)
        if best is None or m > best:
            best = m
    return best


# -- loading ----------------------------------------------------------------
def load_trades(path: Path, size_mode: str = "volume_delta") -> list[Trade]:
    """Extract classified Trades from an R0 tick file using the PRODUCTION extractor."""
    if not path.exists():
        return []
    t = pq.read_table(str(path), columns=[c for c in _LOAD_COLS if c in pq.read_schema(str(path)).names])
    cols = {c: t.column(c).to_pylist() for c in t.column_names}
    n = t.num_rows
    ex = TradeExtractor(size_mode=size_mode)
    out: list[Trade] = []
    for r in range(n):
        row = {c: cols[c][r] for c in cols}
        tr = ex.on_tick(row)
        if tr is not None:
            out.append(tr)
    return out


def derive_lot_size(trades: list[Trade]) -> int:
    """Lot size = GCD of traded sizes (F&O trades only in whole lots)."""
    g = 0
    for tr in trades:
        g = gcd(g, int(tr.size))
    return g or 1


# -- 1. distribution --------------------------------------------------------
def distribution(trades: list[Trade], lot_size: int) -> dict:
    if not trades:
        return {"n": 0}
    notionals = sorted(tr.notional for tr in trades)
    sizes = sorted(int(tr.size) for tr in trades)
    pcts_notional = {p: percentile(notionals, p) for p in PCTS}
    out = {
        "n": len(trades),
        "lot_size": lot_size,
        "notional_min": notionals[0], "notional_max": notionals[-1],
        "size_min": sizes[0], "size_max": sizes[-1],
        "notional_pct": pcts_notional,
        "size_pct": {p: percentile(sizes, p) for p in PCTS},
        "lots_pct": {p: percentile(sizes, p) / lot_size for p in PCTS},
        # count of prints at/above each percentile notional
        "count_ge": {p: sum(1 for x in notionals if x >= pcts_notional[p]) for p in PCTS},
    }
    return out


# -- 2/3. predictive + cost-link (index futures) ----------------------------
def _stats_for_subset(idx: list[int], ts, price, sides, horizons_ns, r_points) -> dict:
    """Directional hit-rate + mean|move| per horizon, and P(favorable MFE60 >= R)."""
    per_h = {}
    for h_s, h_ns in horizons_ns:
        hits = absmoves = obs = 0
        hit_ct = 0
        for i in idx:
            m = forward_point_move(ts, price, i, h_ns)
            if m is None:
                continue
            obs += 1
            absmoves += abs(m)
            if sides[i] * m > 0:
                hit_ct += 1
        per_h[h_s] = {
            "obs": obs,
            "dir_hit": round(hit_ct / obs, 3) if obs else None,
            "mean_abs_move": round(absmoves / obs, 2) if obs else None,
        }
    # cost-link: favorable excursion within 60s >= R
    h60 = 60 * NS
    reach = obs60 = 0
    for i in idx:
        mfe = max_favorable_excursion(ts, price, sides[i], i, h60)
        if mfe is None:
            continue
        obs60 += 1
        if mfe >= r_points:
            reach += 1
    per_h["cost_link"] = {"obs": obs60, "p_reach_R": round(reach / obs60, 4) if obs60 else None,
                          "reach_count": reach}
    return per_h


def predictive_futures(trades_by_day: dict[str, list[Trade]], underlying: str) -> dict:
    """Pool the days' trades; threshold on pooled notional percentiles; measure forward
    outcomes conditional on threshold vs the all-trades baseline. All in-sample (N=2)."""
    all_trades = [tr for day in trades_by_day.values() for tr in day]
    if len(all_trades) < 2:
        return {"n": 0}
    lot = derive_lot_size(all_trades)
    notionals = sorted(tr.notional for tr in all_trades)
    thresholds = {p: percentile(notionals, p) for p in CANDIDATE_PCTS}
    r_points = MIN_VIABLE_R[underlying]
    horizons_ns = [(s, s * NS) for s in HORIZONS_S]

    # Build per-day arrays (forward windows must NOT cross a day boundary), then measure
    # per day and pool the counts. ts within a day are ascending after sort.
    baseline_acc = {h: {"obs": 0, "hit": 0, "abs": 0.0} for h in HORIZONS_S}
    baseline_cost = {"obs": 0, "reach": 0}
    cond_acc = {p: {h: {"obs": 0, "hit": 0, "abs": 0.0} for h in HORIZONS_S} for p in CANDIDATE_PCTS}
    cond_cost = {p: {"obs": 0, "reach": 0} for p in CANDIDATE_PCTS}
    prints_per_day = {p: {} for p in CANDIDATE_PCTS}

    for day, trades in trades_by_day.items():
        if len(trades) < 2:
            continue
        trades = sorted(trades, key=lambda x: x.ts_ns)
        ts = [tr.ts_ns for tr in trades]
        price = [tr.price for tr in trades]
        sides = [tr.side for tr in trades]
        all_idx = list(range(len(trades)))
        # baseline (every trade)
        b = _stats_for_subset(all_idx, ts, price, sides, horizons_ns, r_points)
        for h_s, _ in horizons_ns:
            st = b[h_s]
            if st["obs"]:
                baseline_acc[h_s]["obs"] += st["obs"]
                baseline_acc[h_s]["hit"] += round(st["dir_hit"] * st["obs"])
                baseline_acc[h_s]["abs"] += st["mean_abs_move"] * st["obs"]
        baseline_cost["obs"] += b["cost_link"]["obs"]
        baseline_cost["reach"] += b["cost_link"]["reach_count"]
        # conditional per threshold
        for p, thr in thresholds.items():
            idx = [i for i in all_idx if trades[i].notional >= thr]
            prints_per_day[p][day] = len(idx)
            c = _stats_for_subset(idx, ts, price, sides, horizons_ns, r_points)
            for h_s, _ in horizons_ns:
                st = c[h_s]
                if st["obs"]:
                    cond_acc[p][h_s]["obs"] += st["obs"]
                    cond_acc[p][h_s]["hit"] += round(st["dir_hit"] * st["obs"])
                    cond_acc[p][h_s]["abs"] += st["mean_abs_move"] * st["obs"]
            cond_cost[p]["obs"] += c["cost_link"]["obs"]
            cond_cost[p]["reach"] += c["cost_link"]["reach_count"]

    def _fold(acc):
        return {h: {"obs": acc[h]["obs"],
                    "dir_hit": round(acc[h]["hit"] / acc[h]["obs"], 3) if acc[h]["obs"] else None,
                    "mean_abs_move": round(acc[h]["abs"] / acc[h]["obs"], 2) if acc[h]["obs"] else None}
                for h in HORIZONS_S}

    return {
        "n": len(all_trades), "lot_size": lot, "r_points": r_points,
        "thresholds": thresholds, "thresholds_lots": {p: thresholds[p] for p in CANDIDATE_PCTS},
        "baseline": _fold(baseline_acc),
        "baseline_cost": {"obs": baseline_cost["obs"],
                          "p_reach_R": round(baseline_cost["reach"] / baseline_cost["obs"], 4)
                          if baseline_cost["obs"] else None},
        "conditional": {p: _fold(cond_acc[p]) for p in CANDIDATE_PCTS},
        "conditional_cost": {p: {"obs": cond_cost[p]["obs"],
                                 "p_reach_R": round(cond_cost[p]["reach"] / cond_cost[p]["obs"], 4)
                                 if cond_cost[p]["obs"] else None} for p in CANDIDATE_PCTS},
        "prints_per_day": prints_per_day,
    }


# -- option ATM+/-2 selection ----------------------------------------------
def _spot_atm(root: Path, dates: list[str], underlying: str) -> Optional[float]:
    vals = []
    for d in dates:
        p = root / "data" / d / f"{SPOT[underlying]}.parquet"
        if p.exists():
            vals += [x for x in pq.read_table(str(p), columns=["ltp"]).column("ltp").to_pylist() if x]
    if not vals:
        return None
    vals.sort()
    return vals[len(vals) // 2]


def _atm_option_files(root: Path, dates: list[str], underlying: str) -> list[str]:
    """The ATM+/-2 CE+PE strike files (data-derived strike step + spot-median ATM)."""
    atm = _spot_atm(root, dates, underlying)
    if atm is None:
        return []
    prefix = underlying + "_"
    strikes = set()
    seen = set()
    for d in dates:
        dd = root / "data" / d
        if not dd.exists():
            continue
        for f in dd.glob(f"{prefix}[CP]E_*.parquet"):
            parts = f.stem.split("_")           # e.g. NIFTY CE 24800 57375
            if len(parts) >= 4 and parts[1] in ("CE", "PE"):
                try:
                    strikes.add(int(parts[2]))
                except ValueError:
                    pass
                seen.add(f.stem)
    if not strikes:
        return []
    sstrikes = sorted(strikes)
    step = min((b - a for a, b in zip(sstrikes, sstrikes[1:])), default=50) or 50
    atm_k = round(atm / step) * step
    want = {atm_k + step * o for o in (-2, -1, 0, 1, 2)}
    files = [s for s in seen if int(s.split("_")[2]) in want]
    return sorted(set(files))


# -- assembly + CLI ---------------------------------------------------------
def _load_class(root: Path, dates: list[str], files: list[str]) -> dict[str, list[Trade]]:
    by_day: dict[str, list[Trade]] = {}
    for d in dates:
        acc: list[Trade] = []
        for f in files:
            acc += load_trades(root / "data" / d / f"{f}.parquet")
        by_day[d] = acc
    return by_day


def _fmt_inr(x: float) -> str:
    if x >= 1e7:
        return f"Rs{x/1e7:.2f}Cr"
    if x >= 1e5:
        return f"Rs{x/1e5:.2f}L"
    return f"Rs{x/1e3:.1f}k"


def _print_distribution(label: str, dist: dict):
    if not dist.get("n"):
        print(f"  {label:26s}  (no trades)")
        return
    lot = dist["lot_size"]
    print(f"  {label}  — n={dist['n']} trades, lot_size={lot} (data-derived)")
    hdr = f"    {'pct':>6s} {'notional_Rs':>13s} {'size_qty':>9s} {'lots':>7s} {'count>=':>8s}"
    print(hdr)
    for p in PCTS:
        nv = dist["notional_pct"][p]
        print(f"    {p:>6} {_fmt_inr(nv):>13s} {dist['size_pct'][p]:>9.0f} "
              f"{dist['lots_pct'][p]:>7.1f} {dist['count_ge'][p]:>8d}")
    print(f"    {'min':>6s} {_fmt_inr(dist['notional_min']):>13s} {dist['size_min']:>9d} "
          f"{dist['size_min']/lot:>7.1f}")
    print(f"    {'max':>6s} {_fmt_inr(dist['notional_max']):>13s} {dist['size_max']:>9d} "
          f"{dist['size_max']/lot:>7.1f}")


def _print_predictive(underlying: str, pr: dict):
    if not pr.get("n"):
        print(f"  {underlying}_FUT: insufficient data")
        return
    lot = pr["lot_size"]
    R = pr["r_points"]
    print(f"\n  {underlying}_FUT — predictive (lot={lot}, min_viable_R={R:.0f}pt). "
          f"IN-SAMPLE N=2 -> HYPOTHESIS ONLY.")
    print(f"    prints/day above each threshold: "
          + "; ".join(f"{p}%={'/'.join(str(v) for v in pr['prints_per_day'][p].values())}"
                      for p in CANDIDATE_PCTS))
    hdr = (f"    {'level':>7s} {'thr_notional':>13s}  "
           + " ".join(f"{'h'+str(h)+'_hit':>8s} {'h'+str(h)+'_|mv|':>8s}" for h in HORIZONS_S)
           + f" {'P(>=R/60s)':>11s}")
    print(hdr)
    # baseline row
    b = pr["baseline"]
    base_cells = " ".join(f"{(b[h]['dir_hit'] or 0):>8.3f} {(b[h]['mean_abs_move'] or 0):>8.2f}"
                          for h in HORIZONS_S)
    print(f"    {'ALL':>7s} {'-':>13s}  {base_cells} {(pr['baseline_cost']['p_reach_R'] or 0):>11.4f}")
    for p in CANDIDATE_PCTS:
        c = pr["conditional"][p]
        thr = pr["thresholds"][p]
        cells = " ".join(f"{(c[h]['dir_hit'] or 0):>8.3f} {(c[h]['mean_abs_move'] or 0):>8.2f}"
                         for h in HORIZONS_S)
        pr_reach = pr["conditional_cost"][p]["p_reach_R"]
        print(f"    {str(p)+'%':>7s} {_fmt_inr(thr):>13s}  {cells} {(pr_reach or 0):>11.4f}")


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", default="2026-07-15,2026-07-16")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    root = Path(args.root)
    dates = [d for d in args.dates.split(",") if d.strip()]

    print(f"BIG-PRINT calibration — trade-size distribution + forward-outcome measurement")
    print(f"dates={dates}  (min_viable_R: NIFTY 20pt / BANKNIFTY 50pt)\n")

    print("== 1. TRADE-SIZE DISTRIBUTION (per class, pooled across days) ==")
    # index futures
    for u, fut in INDEX_FUT.items():
        by_day = _load_class(root, dates, [fut])
        allt = [t for day in by_day.values() for t in day]
        _print_distribution(f"{u}_FUT", distribution(allt, derive_lot_size(allt) if allt else 1))
    # options ATM+/-2
    for u in ("NIFTY", "BANKNIFTY"):
        files = _atm_option_files(root, dates, u)
        by_day = _load_class(root, dates, files)
        allt = [t for day in by_day.values() for t in day]
        _print_distribution(f"{u} options ATM+/-2 ({len(files)} strikes)",
                            distribution(allt, derive_lot_size(allt) if allt else 1))
    # equities
    by_day = _load_class(root, dates, BANK_EQUITIES)
    allt = [t for day in by_day.values() for t in day]
    _print_distribution("BANKNIFTY 5 equities", distribution(allt, derive_lot_size(allt) if allt else 1))

    print("\n== 2+3. PREDICTIVE + COST-LINK (index futures) ==")
    print("  h{5,15,30,60}_hit = directional hit-rate sign(move)==sign(aggressor); "
          "|mv| = mean |move| pts;\n  P(>=R/60s) = fraction whose favorable excursion "
          "reaches min_viable_R within 60s. Compare each\n  threshold row to the ALL "
          "(baseline) row — lift over baseline is the signal.")
    for u, fut in INDEX_FUT.items():
        by_day = _load_class(root, dates, [fut])
        _print_predictive(u, predictive_futures(by_day, u))

    print("\n" + "=" * 70)
    print("N=2 IS NOT A CONCLUSION. Every threshold above is HYPOTHESIS-FROM-2-DAYS and")
    print("IN-SAMPLE. Config is NOT touched. The 15-day out-of-sample sweep decides.")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))

"""BANKNIFTY constituent lead-lag + big-print footprint (research, read-only).

Founder hypothesis: to MOVE BankNifty you must move its constituent stocks — the index
is an effect, the cash basket is the cause. BANKNIFTY_FUT is more liquid, so on a normal
day the FUTURE may lead the basket (cheapest way to express a view) = arbitrage, no edge.
But to genuinely DRIVE the index you must go through cash, so the causality may FLIP to
cash-leads-future in windows where the index is being pushed. If that flip is detectable,
the flip itself is the footprint.

FRAMING (must be explicit, incl. any customer-facing text): we are NOT replicating the
Jane Street pattern — that is manipulation and illegal. We DETECT its footprint —
observation, not participation. This is I1 "trade the machine's shadow."

Read-only on data/<date>/<bank>.parquet + BANKNIFTY_FUT. Descriptive lead-lag only — no
component, no config, no look-ahead. 3 days is a first look, NEVER a conclusion.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

# BANKNIFTY constituent weights — approximate, from the niftyindices.com index factsheet
# (~2026). HYPOTHESIS-grade (weights drift monthly); we record only these 5 of ~12
# constituents. Renormalized over the recorded 5 for the basket.
RAW_WEIGHTS = {"HDFCBANK": 0.285, "ICICIBANK": 0.245, "SBIN": 0.090,
               "AXISBANK": 0.085, "KOTAKBANK": 0.080}   # sum ~0.785 of the full index
BANK_SID = {"HDFCBANK": 1333, "ICICIBANK": 4963, "SBIN": 3045,
            "AXISBANK": 5900, "KOTAKBANK": 1922}
FUT = ("BANKNIFTY_FUT", 61088)
# Full-index weight we DON'T record (the ~22% gap): IndusInd, BankBaroda, PNB, Federal,
# IDFCFirst, AU Small Fin, Canara, etc. — quantified in universe_gap().
RECORDED_WEIGHT = sum(RAW_WEIGHTS.values())
NS = 1_000_000_000


def _load(path: Path):
    if not path.exists():
        return None
    t = pq.read_table(str(path))
    ts = np.array(t.column("ts_recv_ns").to_pylist(), dtype="float64")
    ltp = np.array(t.column("ltp").to_pylist(), dtype="float64")
    vol = np.array(t.column("volume").to_pylist(), dtype="float64")
    m = ~(np.isnan(ts) | np.isnan(ltp)) & (ltp > 0)
    ts, ltp, vol = ts[m], ltp[m], vol[m]
    o = np.argsort(ts, kind="stable")
    return ts[o], ltp[o], vol[o]


def gridded_price(ts, ltp, grid_s, t0, t1):
    """Last price in each grid_s bucket over [t0,t1], forward-filled. No look-ahead:
    a bucket's value is the last tick at or before its right edge."""
    edges = np.arange(t0, t1 + grid_s * NS, grid_s * NS)
    idx = np.searchsorted(ts, edges, side="right") - 1     # last tick <= edge
    out = np.where(idx >= 0, ltp[np.clip(idx, 0, len(ltp) - 1)], np.nan)
    # forward-fill leading NaNs handled by returns dropping them
    return edges, out


def _log_returns(prices):
    r = np.full(len(prices), np.nan)
    for i in range(1, len(prices)):
        a, b = prices[i - 1], prices[i]
        if a > 0 and b > 0 and not (math.isnan(a) or math.isnan(b)):
            r[i] = math.log(b / a)
    return r


def crosscorr(x, y, max_lag):
    """corr(x[t], y[t+k]) for k in [-max_lag, max_lag] (k in GRID steps).
    k>0 => y later correlates with x now => x LEADS y by k. k<0 => y leads x.
    Returns (dict k->corr, peak_k, peak_corr)."""
    out = {}
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            a, b = x[:len(x) - k], y[k:]
        else:
            a, b = x[-k:], y[:len(y) + k]
        mask = ~(np.isnan(a) | np.isnan(b))
        a, b = a[mask], b[mask]
        out[k] = float(np.corrcoef(a, b)[0, 1]) if len(a) > 5 and a.std() > 0 and b.std() > 0 else float("nan")
    valid = {k: v for k, v in out.items() if not math.isnan(v)}
    peak_k = max(valid, key=lambda k: abs(valid[k])) if valid else 0
    return out, peak_k, out.get(peak_k, float("nan"))


def build_day(date: str, root: Path = Path("."), grid_s: int = 1):
    """Load all banks + future on a common grid; return basket + future return series."""
    banks = {}
    for name, sid in BANK_SID.items():
        d = _load(root / "data" / date / f"{name}_{sid}.parquet")
        if d is not None:
            banks[name] = d
    fut = _load(root / "data" / date / f"{FUT[0]}_{FUT[1]}.parquet")
    if fut is None or len(banks) < 3:
        return None
    # common window = overlap of all series
    t0 = max([b[0][0] for b in banks.values()] + [fut[0][0]])
    t1 = min([b[0][-1] for b in banks.values()] + [fut[0][-1]])
    if t1 <= t0:
        return None
    w = {k: RAW_WEIGHTS[k] / RECORDED_WEIGHT for k in banks}     # renormalize over recorded
    edges, fut_px = gridded_price(fut[0], fut[1], grid_s, t0, t1)
    basket_ret = np.zeros(len(edges))
    cnt = np.zeros(len(edges))
    for name, d in banks.items():
        _, px = gridded_price(d[0], d[1], grid_s, t0, t1)
        r = _log_returns(px)
        good = ~np.isnan(r)
        basket_ret[good] += w[name] * r[good]
        cnt += good
    basket_ret[cnt == 0] = np.nan
    fut_ret = _log_returns(fut_px)
    return {"edges": edges, "basket_ret": basket_ret, "fut_ret": fut_ret,
            "fut_raw": fut, "banks": banks, "weights": w, "t0": t0, "t1": t1, "grid_s": grid_s}


def _asymmetry(cc: dict):
    """From corr(basket[t], future[t+k]): best correlation at positive lags (cash LEADS
    future) vs negative lags (future LEADS cash). Symmetric magnitudes => co-movement /
    arbitrage; a dominant side => information flow in that direction. This is the real
    tautology control — the reversed cross-correlation is only the trivial mirror."""
    pos = {k: v for k, v in cc.items() if k > 0 and not math.isnan(v)}
    neg = {k: v for k, v in cc.items() if k < 0 and not math.isnan(v)}
    cash_lead = max(pos.values(), key=abs) if pos else float("nan")   # basket leads
    fut_lead = max(neg.values(), key=abs) if neg else float("nan")    # future leads
    return cash_lead, fut_lead


def leadlag_report(day: dict, ret_x=None, ret_y=None, max_lag_s: int = 30) -> dict:
    """Cross-correlation basket(=x) vs future(=y). k>0 => cash LEADS future."""
    b = day["basket_ret"] if ret_x is None else ret_x
    f = day["fut_ret"] if ret_y is None else ret_y
    g = day["grid_s"]
    cc, pk, pv = crosscorr(b, f, max_lag_s // g)
    cash_lead, fut_lead = _asymmetry(cc)
    if pk > 0:
        lead = "cash_leads_future"
    elif pk < 0:
        lead = "future_leads_cash"
    else:
        lead = "co-movement (k=0, no lead)"
    return {"cc": cc, "peak_lag_s": pk * g, "peak_corr": pv, "corr_at_0": cc.get(0),
            "cash_lead_best": cash_lead, "fut_lead_best": fut_lead, "lead": lead}


def regime_leadlag(day: dict, max_lag_s: int = 30, hi_pctile: float = 90.0) -> dict:
    """THE KEY TEST: lead-lag split by regime. Does cash-leads-future appear specifically
    when the index is being driven? Windows are classified by the FUTURE's rolling
    absolute return (no basket look-ahead): HIGH-velocity (top ``hi_pctile``) vs NORMAL.
    A NaN in either series at a grid point drops that point from both regimes."""
    f = day["fut_ret"]
    absf = np.abs(np.nan_to_num(f))
    win = max(5, len(f) // 200)
    # TRAILING (causal) velocity — no look-ahead: a point's regime uses only past |ret|.
    roll = np.convolve(absf, np.ones(win) / win)[:len(absf)]
    valid = roll[~np.isnan(f)]
    thr = np.percentile(valid, hi_pctile) if len(valid) else np.inf
    hi_mask = (roll >= thr)
    out = {}
    for label, mask in (("normal", ~hi_mask), ("high_velocity", hi_mask)):
        bx = np.where(mask, day["basket_ret"], np.nan)
        fy = np.where(mask, f, np.nan)
        r = leadlag_report(day, bx, fy, max_lag_s)
        out[label] = {"peak_lag_s": r["peak_lag_s"], "peak_corr": r["peak_corr"],
                      "cash_lead_best": r["cash_lead_best"], "fut_lead_best": r["fut_lead_best"],
                      "lead": r["lead"], "n_points": int(mask.sum())}
    return out


def bigprint_event_study(day: dict, root: Path, date: str,
                         windows_s=(5, 15, 30, 60), pctile: float = 99.0) -> dict:
    """When a large print hits ONE bank's cash tape, what does the future do at +Ns?
    Big print = per-bank volume-delta above its ``pctile`` percentile."""
    out = {}
    fts, fltp, _ = day["fut_raw"]
    for name, (ts, ltp, vol) in day["banks"].items():
        dvol = np.diff(vol, prepend=vol[0])
        thr = np.percentile(dvol[dvol > 0], pctile) if (dvol > 0).any() else np.inf
        events = ts[dvol >= thr]
        rows = {}
        for W in windows_s:
            rets = []
            for et in events:
                i0 = np.searchsorted(fts, et, "right") - 1
                i1 = np.searchsorted(fts, et + W * NS, "right") - 1   # NO look-ahead
                if i0 >= 0 and i1 > i0:
                    rets.append(math.log(fltp[i1] / fltp[i0]))
            rows[W] = {"n": len(rets), "mean_bps": round(1e4 * float(np.mean(rets)), 2) if rets else None,
                       "median_bps": round(1e4 * float(np.median(rets)), 2) if rets else None}
        out[name] = {"n_events": len(events), "thr_dvol": round(float(thr), 0), "fwd": rows}
    return out


def universe_gap() -> dict:
    return {"recorded_5_weight_pct": round(100 * RECORDED_WEIGHT, 1),
            "missing_weight_pct": round(100 * (1 - RECORDED_WEIGHT), 1),
            "missing_names": ["IndusInd", "BankOfBaroda", "PNB", "Federal", "IDFCFirst",
                              "AU_SmallFin", "Canara", "..."],
            "note": "cash only — no constituent FUTURES recorded; Jane St pattern used "
                    "constituents AND their futures, so a futures-led push is invisible here."}


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", default="2026-07-13,2026-07-14,2026-07-15")
    ap.add_argument("--grid-s", type=int, default=1)
    ap.add_argument("--max-lag-s", type=int, default=30)
    ap.add_argument("--root", default=".")
    a = ap.parse_args(argv[1:])
    root = Path(a.root)
    ug = universe_gap()
    print(f"UNIVERSE: recorded 5 banks = {ug['recorded_5_weight_pct']}% of BANKNIFTY; "
          f"MISSING {ug['missing_weight_pct']}% ({', '.join(ug['missing_names'][:6])}). "
          f"CASH ONLY (no constituent futures).\n")
    usable = 0
    for date in a.dates.split(","):
        day = build_day(date, root, a.grid_s)
        if day is None:
            print(f"{date}: SKIP (insufficient data)")
            continue
        usable += 1
        ll = leadlag_report(day, max_lag_s=a.max_lag_s)
        print(f"=== {date} (grid {a.grid_s}s) ===")
        print(f"  ALL-DAY basket vs future: peak lag {ll['peak_lag_s']:+d}s corr {ll['peak_corr']:+.3f} "
              f"| corr@0 {ll['corr_at_0']:+.3f} | {ll['lead']}")
        print(f"  ASYMMETRY (tautology control): cash-leads best {ll['cash_lead_best']:+.3f} "
              f"vs future-leads best {ll['fut_lead_best']:+.3f}  "
              f"(similar => co-movement/arbitrage; dominant side => info flow)")
        rg = regime_leadlag(day, a.max_lag_s)
        print("  REGIME SPLIT (the key test — does cash lead when the index is driven?):")
        for lab, r in rg.items():
            print(f"    {lab:14s} n={r['n_points']:5d}  peak {r['peak_lag_s']:+d}s corr {r['peak_corr']:+.3f}  "
                  f"cash-lead {r['cash_lead_best']:+.3f} / fut-lead {r['fut_lead_best']:+.3f}  {r['lead']}")
        es = bigprint_event_study(day, root, date)
        print("  BIG-PRINT event study (bank cash print -> future fwd return, bps):")
        for name, e in es.items():
            f30 = e["fwd"].get(30, {})
            print(f"    {name:10s} n={e['n_events']:4d}  +5s={e['fwd'][5]['median_bps']}  "
                  f"+15s={e['fwd'][15]['median_bps']}  +30s={f30.get('median_bps')}  "
                  f"+60s={e['fwd'][60]['median_bps']}")
        print()
    print(f"usable days: {usable} — FIRST LOOK ONLY, not a conclusion (need 15+ clean days). "
          f"Detection = observation, not participation (I1 'trade the machine's shadow').")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))

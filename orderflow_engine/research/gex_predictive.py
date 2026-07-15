"""GEX predictive-vs-descriptive measurement tool (research, read-only).

Founder's question (2026-07-15): chain.run reports a DAY-AGGREGATE net_GEX computed
from the full session — hindsight. GEX is built from open interest (largely prior-day
frozen), so an EARLY-session read might be predictive of the day's realized behaviour,
or it might only describe it after the fact. Until answered, GEX stays weight-0.

This tool, per recorded day:
  1. EARLY GEX  — net_GEX + gamma-flip recomputed from ONLY the chain snapshots inside
     the first N minutes (default 15 → the 09:15-09:30 read). Strict no-look-ahead:
     any snapshot after the window is ignored.
  2. REALIZED   — NIFTY_FUT outcomes: day range (H-L, and % of open), realized vol
     (std of resampled returns), a pinning proxy (|close-max_pain| + time within X pts
     of max_pain), and a trend proxy (|close-open| / (H-L)).
  3. EOD GEX    — the chain_summary day-aggregate, for early-vs-EOD comparison + SIGN
     agreement (if early and EOD disagree, GEX isn't stable intraday).

NOT a study: 3-5 usable days is a first look + tool, never a conclusion. Verdict
needs 15+ days.  Read-only: consumes analysis/<date>/chain_NIFTY.parquet +
chain_summary.json and data/<date>/NIFTY_FUT_61093.parquet.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import pyarrow.parquet as pq

from chain.gex import gamma_flip, net_gex

NS = 1_000_000_000
NIFTY_FUT = "NIFTY_FUT_61093"
NIFTY_CONTRACT_SIZE = 75


# -- 1. EARLY GEX (no look-ahead) -------------------------------------------
def early_gex(chain_rows: list[dict], n_minutes: int = 15,
              contract_size: int = NIFTY_CONTRACT_SIZE) -> Optional[dict]:
    """net_GEX + gamma-flip from ONLY the snapshots within the first ``n_minutes``.

    ``chain_rows`` is the per-strike-per-snapshot list from chain_NIFTY.parquet. The
    window is [first snapshot, first + n_minutes]; the read is the LAST snapshot inside
    it (the T+N chain state). Snapshots after the window are never touched.
    """
    if not chain_rows:
        return None
    snaps = sorted({int(r["snapshot_ts_ns"]) for r in chain_rows})
    window_end = snaps[0] + n_minutes * 60 * NS
    in_window = [s for s in snaps if s <= window_end]            # NO LOOK-AHEAD
    if not in_window:
        return None
    read_ts = in_window[-1]
    strikes = [r for r in chain_rows if int(r["snapshot_ts_ns"]) == read_ts]
    return {
        "early_net_gex": net_gex(strikes, contract_size),
        "early_flip": gamma_flip(strikes, contract_size),
        "window_snapshots": len(in_window),
        "read_ts_ns": read_ts,
        "window_end_ns": window_end,
        "strikes_in_read": len({int(s["strike"]) for s in strikes}),
    }


# -- 2. REALIZED outcomes on NIFTY_FUT --------------------------------------
def realized_outcomes(fut_rows: dict, max_pain: Optional[float],
                      pin_pts: float = 25.0, resample_s: int = 300) -> Optional[dict]:
    """Day outcomes from the NIFTY_FUT ltp series.

    ``fut_rows`` = {"ts": [...ns...], "ltp": [...]} in receipt order (nulls/0 dropped
    by the caller). resample_s buckets (default 5-min) drive the realized-vol std.
    """
    ts, ltp = fut_rows["ts"], fut_rows["ltp"]
    if len(ltp) < 2:
        return None
    o, c = ltp[0], ltp[-1]
    hi, lo = max(ltp), min(ltp)
    rng = hi - lo
    trend = abs(c - o) / rng if rng > 0 else 0.0
    # realized vol: std of log-returns of resample_s-bucketed closes
    bucket_close: dict[int, float] = {}
    t0 = ts[0]
    for t, p in zip(ts, ltp):
        bucket_close[(t - t0) // (resample_s * NS)] = p         # last price in bucket
    closes = [bucket_close[k] for k in sorted(bucket_close)]
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
            if closes[i - 1] > 0 and closes[i] > 0]
    rvol = _std(rets)
    # pinning: distance of close from max_pain + time-weighted fraction within pin_pts
    pin_dist = abs(c - max_pain) if max_pain else None
    pin_frac = None
    if max_pain:
        within = total = 0.0
        for i in range(1, len(ts)):
            dt = ts[i] - ts[i - 1]
            total += dt
            if abs(ltp[i - 1] - max_pain) <= pin_pts:
                within += dt
        pin_frac = round(within / total, 3) if total > 0 else None
    return {
        "open": o, "close": c, "high": hi, "low": lo,
        "day_range": round(rng, 1), "range_pct": round(100.0 * rng / o, 2) if o else None,
        "realized_vol": round(rvol, 6),
        "pin_dist_pts": round(pin_dist, 1) if pin_dist is not None else None,
        "pin_time_frac": pin_frac,
        "trend_proxy": round(trend, 3),
    }


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# -- 3/4. per-day assembly + sign agreement ---------------------------------
def _load_fut(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    t = pq.read_table(str(path))
    ltp = t.column("ltp").to_pylist()
    ts = t.column("ts_recv_ns").to_pylist()
    pairs = [(int(a), float(b)) for a, b in zip(ts, ltp) if a is not None and b]
    if len(pairs) < 2:
        return None
    pairs.sort()
    return {"ts": [p[0] for p in pairs], "ltp": [p[1] for p in pairs]}


def analyze_day(date: str, root: Path = Path("."), n_minutes: int = 15,
                pin_pts: float = 25.0) -> dict:
    a = root / "analysis" / date
    chain_p = a / "chain_NIFTY.parquet"
    summ_p = a / "chain_summary.json"
    fut_p = root / "data" / date / f"{NIFTY_FUT}.parquet"
    out: dict = {"date": date, "usable": False, "skip_reason": None}
    if not chain_p.exists() or not summ_p.exists():
        out["skip_reason"] = "no chain output"
        return out
    ni = json.loads(summ_p.read_text()).get("per_index", {}).get("NIFTY", {})
    eod_gex = ni.get("net_gex")
    if not eod_gex or ni.get("spot_source") in (None, "none"):
        out["skip_reason"] = f"chain has no spot (spot_source={ni.get('spot_source')}, net_gex={eod_gex})"
        return out
    fut = _load_fut(fut_p)
    if fut is None:
        out["skip_reason"] = "no NIFTY_FUT ticks"
        return out
    rows = pq.read_table(str(chain_p)).to_pylist()
    eg = early_gex(rows, n_minutes)
    ro = realized_outcomes(fut, ni.get("max_pain"), pin_pts)
    out.update(usable=True, early=eg, realized=ro, eod_net_gex=eod_gex,
               eod_max_pain=ni.get("max_pain"), spot_source=ni.get("spot_source"),
               sign_agree=(eg is not None and _sign(eg["early_net_gex"]) == _sign(eod_gex)))
    return out


def _sign(x: Optional[float]) -> int:
    return 0 if not x else (1 if x > 0 else -1)


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", default="2026-07-09,2026-07-10,2026-07-13,2026-07-14,2026-07-15")
    ap.add_argument("--n-minutes", type=int, default=15)
    ap.add_argument("--pin-pts", type=float, default=25.0)
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    root = Path(args.root)
    results = [analyze_day(d, root, args.n_minutes, args.pin_pts)
               for d in args.dates.split(",")]

    print(f"GEX predictive-vs-descriptive — early window N={args.n_minutes}min, "
          f"pin±{args.pin_pts:.0f}pts (NIFTY_FUT)\n")
    hdr = (f"{'date':11s} {'early_GEX':>13s} {'early_flip':>10s} {'EOD_GEX':>13s} "
           f"{'sign':>5s} {'range':>7s} {'rng%':>5s} {'rvol':>8s} {'pin_pts':>7s} "
           f"{'pin_t%':>6s} {'trend':>5s}")
    print(hdr)
    print("-" * len(hdr))
    usable = 0
    for r in results:
        if not r["usable"]:
            print(f"{r['date']:11s}  SKIP — {r['skip_reason']}")
            continue
        usable += 1
        e, o = r["early"], r["realized"]
        fl = f"{e['early_flip']:.0f}" if e and e["early_flip"] is not None else "-"
        print(f"{r['date']:11s} {e['early_net_gex']:13.0f} {fl:>10s} {r['eod_net_gex']:13.0f} "
              f"{('SAME' if r['sign_agree'] else 'FLIP'):>5s} {o['day_range']:7.0f} "
              f"{o['range_pct']:5.2f} {o['realized_vol']:8.5f} "
              f"{(o['pin_dist_pts'] if o['pin_dist_pts'] is not None else 0):7.0f} "
              f"{(o['pin_time_frac'] or 0)*100:6.1f} {o['trend_proxy']:5.2f}")
    print(f"\nusable days: {usable} — NOT a conclusion (need 15+ days). Tool + first look only.")
    # sign-stability summary
    ag = [r for r in results if r["usable"]]
    same = sum(1 for r in ag if r["sign_agree"])
    if ag:
        print(f"early-vs-EOD GEX sign agreement: {same}/{len(ag)} days "
              f"({'stable' if same == len(ag) else 'UNSTABLE intraday on ' + str(len(ag)-same) + ' day(s)'})")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))

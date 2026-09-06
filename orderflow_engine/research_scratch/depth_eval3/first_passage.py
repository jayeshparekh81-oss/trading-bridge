"""first_passage.py — RUN 3: the first-passage / excursion engine. NEW module; research/depth_proxies.py is imported
UNMODIFIED only to compute the shallow (levels 1-5) refill events (run 1's F1). No trade tape, no aggressor tag.

Per session (one guarded S3 read):
  * snapshot-level mid series: at every snapshot timestamp, mid = (last bid1 <= ts, last ask1 <= ts)/2, each side no
    older than 2 s -> path resolution = the depth cadence (~200 ms).
  * 5-second bars (09:15:05 .. 15:30:00 IST): mid at bar end; refill counts per side from the unmodified
    DepthProxyEngine (levels=5, trade tape never fed); sigma_1m = std of the 5-s mid changes over the trailing 360 bars
    ENDING AT THE PREVIOUS BAR (changes with bar index <= i-1; never the event bar's own change, never forward),
    x sqrt(12) -> a 1-minute-equivalent realised volatility; undefined with < 120 valid changes.
  * THE JOINT OBJECT, computed ONCE for EVERY bar (orientation +1; a -1 orientation swaps up/down):
      t_up[k], t_down[k]  : first-passage time (s) to +k*sigma / -k*sigma for k in K, NaN if never reached before the
                            last snapshot of the session (right-censored; censor_s = time to the last snapshot)
      mfe_H, mae_H, tmfe_H, tmae_H, mid_H : max / min excursion (points) within horizon H, their times, and the mid at H
    From t_up/t_down the hit-first outcome of ANY (stop=a*sigma, target=b*sigma) pair follows without recomputation.
  * F2 location flags per bar: |mid - level| <= TOL * sigma_1m for level in {prev-clean-session high/low/close of the
    bar mid, opening-range (09:15-09:30) high/low}; eligible after 09:30.
"""
from __future__ import annotations
import sys, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
D3 = Path(__file__).resolve().parent; OE = D3.parents[1]; sys.path.insert(0, str(OE)); sys.path.insert(0, str(D3))
from research.depth_proxies import DepthProxyEngine, snapshot_to_book       # unmodified, levels 1-5
import qguard
IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); BAR_S = 5; MID_MAX_AGE_NS = 2_000_000_000
K = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]; HORIZONS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "60m": 3600, "120m": 7200, "close": None}
SIGMA_WIN = 360; SIGMA_MIN = 120; SIGMA_SCALE = np.sqrt(12.0); TOL = 1.0; OR_BARS = 180          # opening range = first 15 min (180 bars)
LEVELS = 5; COLS = ["ts_recv_ns", "seq_local", "side"] + [f"price_{i}" for i in range(1, LEVELS + 1)] + [f"qty_{i}" for i in range(1, LEVELS + 1)]
SIDE_BID, SIDE_ASK = 0, 1

def grid_ns(date):
    d = dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST); o = d.replace(hour=9, minute=15); c = d.replace(hour=15, minute=30)
    return np.array([int((o + dt.timedelta(seconds=BAR_S * (i + 1))).timestamp() * 1e9) for i in range(int((c - o).total_seconds() // BAR_S))], dtype=np.int64)

def mid_series(ts, side, p1):
    """mid at every snapshot timestamp from the last bid1/ask1 <= ts (age <= 2 s). Returns (ts_unique_ns, mid) with NaN where undefined."""
    isb, isa = side == SIDE_BID, side == SIDE_ASK; bts, bp = ts[isb], p1[isb]; ats, ap = ts[isa], p1[isa]
    u = np.unique(ts); bi = np.searchsorted(bts, u, side="right") - 1; ai = np.searchsorted(ats, u, side="right") - 1
    bok = (bi >= 0) & (u - bts[np.clip(bi, 0, None)] <= MID_MAX_AGE_NS) & (bp[np.clip(bi, 0, None)] > 0); aok = (ai >= 0) & (u - ats[np.clip(ai, 0, None)] <= MID_MAX_AGE_NS) & (ap[np.clip(ai, 0, None)] > 0)
    mid = np.where(bok & aok, (bp[np.clip(bi, 0, None)] + ap[np.clip(ai, 0, None)]) / 2.0, np.nan)
    return u, mid

def refill_counts(df, ends):
    """Shallow refill events from the UNMODIFIED run-1 engine (levels 1-5, on_trade never called), binned per 5-s bar (start < ts <= end)."""
    ts = df.ts_recv_ns.to_numpy(np.int64); side = df.side.to_numpy(); P = [df[f"price_{i}"].to_numpy(float) for i in range(1, LEVELS + 1)]; Q = [df[f"qty_{i}"].to_numpy(float) for i in range(1, LEVELS + 1)]
    eng = DepthProxyEngine()
    for k in range(len(df)):
        parsed = {}
        for i in range(LEVELS): parsed[f"price_{i+1}"] = P[i][k]; parsed[f"qty_{i+1}"] = Q[i][k]
        eng.on_snapshot(int(ts[k]), "bid" if side[k] == SIDE_BID else "ask", snapshot_to_book(parsed))
    starts = ends - BAR_S * 1_000_000_000; out = {}
    for sd in ("bid", "ask"):
        ets = np.array([e.ts_ns for e in eng.events if e.kind == "refill" and e.side == sd], dtype=np.int64)
        idx = np.searchsorted(ends, ets, side="left"); ok = (ets > starts[0]) & (ets <= ends[-1]); out[f"{sd}_refills"] = np.bincount(idx[ok], minlength=len(ends)).astype(np.int32)
    return out

def trailing_sigma(bar_mid):
    """sigma_1m[i] from changes d[j] = mid[j]-mid[j-1] for j in [i-SIGMA_WIN, i-1] (ends at the PREVIOUS bar), x sqrt(12)."""
    d = np.diff(bar_mid, prepend=np.nan); n = len(bar_mid); s = np.full(n, np.nan)
    for i in range(n):
        w = d[max(1, i - SIGMA_WIN): i]; w = w[~np.isnan(w)]
        if len(w) >= SIGMA_MIN: s[i] = float(np.std(w, ddof=1)) * SIGMA_SCALE
    return s

def joint_object(ts_s, mid, bar_end_s, bar_mid, sigma):
    """For every bar with a defined mid and sigma: first-passage times (orientation +1), censor time, MFE/MAE per horizon."""
    n = len(bar_end_s); nk = len(K); H = list(HORIZONS.items())
    t_up = np.full((n, nk), np.nan, np.float32); t_dn = np.full((n, nk), np.nan, np.float32); censor = np.full(n, np.nan, np.float32)
    mfe = np.full((n, len(H)), np.nan, np.float32); mae = np.full((n, len(H)), np.nan, np.float32); tmfe = np.full((n, len(H)), np.nan, np.float32); tmae = np.full((n, len(H)), np.nan, np.float32); midH = np.full((n, len(H)), np.nan, np.float32)
    valid = ~np.isnan(mid); ts_v, mid_v = ts_s[valid], mid[valid]; t_end = ts_v[-1]
    for i in range(n):
        if np.isnan(bar_mid[i]) or np.isnan(sigma[i]) or sigma[i] <= 0: continue
        j0 = np.searchsorted(ts_v, bar_end_s[i], side="right")
        if j0 >= len(ts_v): continue
        path = mid_v[j0:] - bar_mid[i]; rel_t = ts_v[j0:] - bar_end_s[i]; cm = np.maximum.accumulate(path); cn = np.minimum.accumulate(path)
        censor[i] = t_end - bar_end_s[i]
        for ki, k in enumerate(K):
            iu = np.searchsorted(cm, k * sigma[i], side="left"); idn = np.searchsorted(-cn, k * sigma[i], side="left")
            if iu < len(cm): t_up[i, ki] = rel_t[iu]
            if idn < len(cn): t_dn[i, ki] = rel_t[idn]
        for hi, (hn, hs) in enumerate(H):
            m = len(path) if hs is None else np.searchsorted(rel_t, hs, side="right")
            if m == 0: continue
            mfe[i, hi] = max(cm[m - 1], 0.0); mae[i, hi] = min(cn[m - 1], 0.0); a = int(np.argmax(path[:m])); b = int(np.argmin(path[:m]))
            tmfe[i, hi] = rel_t[a] if path[a] > 0 else 0.0; tmae[i, hi] = rel_t[b] if path[b] < 0 else 0.0; midH[i, hi] = mid_v[j0 + m - 1]
    return t_up, t_dn, censor, mfe, mae, tmfe, tmae, midH

def session_levels(bar_mid):
    """Reference levels a LATER session will use: high/low/close of this session's bar-mid series."""
    v = bar_mid[~np.isnan(bar_mid)]; return {"pdh": float(v.max()), "pdl": float(v.min()), "pdc": float(v[-1])} if len(v) else None

def compute_session(date: str, inst: str, stage: str, prev_levels: dict | None, out_path: Path | None = None):
    df = qguard.load_session(date, inst, stage, COLS); ts = df.ts_recv_ns.to_numpy(np.int64); side = df.side.to_numpy(); p1 = df.price_1.to_numpy(float)
    u, mid = mid_series(ts, side, p1); ends = grid_ns(date); ts_s = (u - ends[0]) / 1e9; bar_end_s = (ends - ends[0]) / 1e9
    vi = np.searchsorted(u, ends, side="right") - 1; ok = (vi >= 0) & (ends - u[np.clip(vi, 0, None)] <= MID_MAX_AGE_NS); bar_mid = np.where(ok, mid[np.clip(vi, 0, None)], np.nan)
    sigma = trailing_sigma(bar_mid); rc = refill_counts(df, ends)
    t_up, t_dn, censor, mfe, mae, tmfe, tmae, midH = joint_object(ts_s, mid, bar_end_s, bar_mid, sigma)
    n = len(ends); slot = ((ends - ends[0]) // (15 * 60 * 1_000_000_000)).astype(np.int16)
    orh = np.nanmax(bar_mid[:OR_BARS]) if np.any(~np.isnan(bar_mid[:OR_BARS])) else np.nan; orl = np.nanmin(bar_mid[:OR_BARS]) if np.any(~np.isnan(bar_mid[:OR_BARS])) else np.nan
    levels = {"orh": orh, "orl": orl, **(prev_levels or {"pdh": np.nan, "pdl": np.nan, "pdc": np.nan})}
    feat = {"bar_end_ns": ends, "bar_end_s": bar_end_s.astype(np.float32), "slot": slot, "mid": bar_mid, "sigma_1m": sigma, "bid_refills": rc["bid_refills"], "ask_refills": rc["ask_refills"], "censor_s": censor}
    after_or = np.arange(n) >= OR_BARS
    for name, lv in levels.items(): feat[f"near_{name}"] = after_or & (np.abs(bar_mid - lv) <= TOL * sigma)
    feat["near_any"] = np.any(np.stack([feat[f"near_{x}"] for x in levels]), axis=0); feat["prev_levels_defined"] = np.full(n, prev_levels is not None)
    for ki, k in enumerate(K): feat[f"t_up_{k}"] = t_up[:, ki]; feat[f"t_dn_{k}"] = t_dn[:, ki]
    for hi, hn in enumerate(HORIZONS): feat[f"mfe_{hn}"] = mfe[:, hi]; feat[f"mae_{hn}"] = mae[:, hi]; feat[f"tmfe_{hn}"] = tmfe[:, hi]; feat[f"tmae_{hn}"] = tmae[:, hi]; feat[f"mid_{hn}"] = midH[:, hi]
    out = pd.DataFrame(feat)
    if out_path is not None: out.to_parquet(out_path, index=False)
    summ = {"date": date, "inst": inst, "rows_in": int(len(df)), "snapshots": int(len(u)), "bars": n, "bars_with_mid": int(np.sum(~np.isnan(bar_mid))), "bars_with_sigma": int(np.sum(~np.isnan(sigma))),
            "median_sigma_1m": float(np.nanmedian(sigma)) if np.any(~np.isnan(sigma)) else None, "refill_events": {"bid": int(rc["bid_refills"].sum()), "ask": int(rc["ask_refills"].sum())}, "levels": {k: (None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)) for k, v in levels.items()}, "this_session_levels": session_levels(bar_mid)}
    return out, summ

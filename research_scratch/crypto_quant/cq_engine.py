"""cq_engine.py — A6 first passage / MAE-MFE, A10 independence, A8 funding.

A6: one object per event, from which the hit-first outcome of ANY (stop, target)
pair is derivable without re-running. Right-censoring is carried, never dropped.

A10 [v3-1]: events whose forward windows overlap are not independent. Spacing
suppression plus an effective-N count and a variance ratio.

A8 [v3-5]: funding is a SCHEDULE. Charged as the discrete stamps a holding path
actually crosses, at the realised rate, with sign. Sub-stamp holds pay zero.
Paid and received are reported separately, never netted.
"""
from __future__ import annotations

import bisect
import math

import numpy as np

FUNDING_INTERVAL_MS = 8 * 3600 * 1000


# ────────────────────────────────────────────────────────── A6 first passage
def first_passage(times, prices, t0_idx, sigma, k_grid, horizon_ms):
    """One event's path object.

    Returns dict with, per k: t_up (ms after t0, None if never), t_dn likewise;
    plus mfe/mae in sigma units, the horizon actually available, and whether the
    path was cut short by the end of data (distinct from resolving neither way).
    """
    t0 = int(times[t0_idx])
    p0 = float(prices[t0_idx])
    end_t = t0 + horizon_ms
    hi = bisect.bisect_right(times, end_t)
    seg_t = times[t0_idx + 1:hi]
    seg_p = prices[t0_idx + 1:hi]
    out = {"t0": t0, "p0": p0, "sigma": float(sigma), "n_path": len(seg_p),
           "t_up": {}, "t_dn": {}, "truncated_by_data": hi >= len(times)}
    if len(seg_p) == 0 or sigma <= 0:
        for k in k_grid:
            out["t_up"][k] = None
            out["t_dn"][k] = None
        out["mfe_sigma"] = None
        out["mae_sigma"] = None
        out["horizon_ms"] = 0
        return out
    seg_p = np.asarray(seg_p, dtype=float)
    seg_t = np.asarray(seg_t, dtype=np.int64)
    run_max = np.maximum.accumulate(seg_p)
    run_min = np.minimum.accumulate(seg_p)
    for k in k_grid:
        up_lvl = p0 + k * sigma
        dn_lvl = p0 - k * sigma
        iu = int(np.searchsorted(run_max, up_lvl, side="left"))
        out["t_up"][k] = int(seg_t[iu] - t0) if iu < len(seg_t) else None
        i_dn = int(np.argmax(run_min <= dn_lvl)) if (run_min <= dn_lvl).any() else None
        out["t_dn"][k] = int(seg_t[i_dn] - t0) if i_dn is not None else None
    out["mfe_sigma"] = float((run_max[-1] - p0) / sigma)
    out["mae_sigma"] = float((run_min[-1] - p0) / sigma)
    out["horizon_ms"] = int(seg_t[-1] - t0)
    return out


def hit_first(obj, target_k, stop_k, side=1):
    """Derive the (stop, target) outcome from a stored path object.

    side=+1 long: target is up, stop is down. side=-1 short: mirrored.
    Returns 'target', 'stop', or 'censored'. Censoring is NEVER silently a loss.
    """
    if side == 1:
        tt, ts = obj["t_up"].get(target_k), obj["t_dn"].get(stop_k)
    else:
        tt, ts = obj["t_dn"].get(target_k), obj["t_up"].get(stop_k)
    if tt is None and ts is None:
        return "censored"
    if ts is None:
        return "target"
    if tt is None:
        return "stop"
    return "target" if tt < ts else "stop"


def resolution_time_ms(obj, target_k, stop_k, side=1):
    if side == 1:
        tt, ts = obj["t_up"].get(target_k), obj["t_dn"].get(stop_k)
    else:
        tt, ts = obj["t_dn"].get(target_k), obj["t_up"].get(stop_k)
    cands = [x for x in (tt, ts) if x is not None]
    return min(cands) if cands else None


# ─────────────────────────────────────────────── A10 independence, effective N
def suppress_overlapping(events, objs, target_k, stop_k, side=1):
    """Drop any event that opens inside a prior surviving event's unresolved window.

    Returns (kept_indices, raw_n, effective_n). This is the pre-registered
    default spacing rule of BLUEPRINT_v3 A10.
    """
    kept, busy_until = [], -1
    for i, (ev, obj) in enumerate(zip(events, objs)):
        t0 = obj["t0"]
        if t0 <= busy_until:
            continue
        kept.append(i)
        res = resolution_time_ms(obj, target_k, stop_k, side)
        busy_until = t0 + (res if res is not None else obj["horizon_ms"])
    return kept, len(events), len(kept)


def variance_ratio(raw_n, eff_n):
    return (eff_n / raw_n) if raw_n else None


def block_bootstrap_ci(outcomes, block_len, n_boot=2000, seed=7, alpha=0.05):
    """CI for a mean over autocorrelated outcomes. Blocks preserve local structure."""
    x = np.asarray(outcomes, dtype=float)
    n = len(x)
    if n == 0:
        return None, None
    block_len = max(1, min(int(block_len), n))
    n_blocks = int(math.ceil(n / block_len))
    rng = np.random.default_rng(seed)
    starts_pool = np.arange(0, max(1, n - block_len + 1))
    means = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.choice(starts_pool, size=n_blocks, replace=True)
        idx = np.concatenate([np.arange(s, min(s + block_len, n)) for s in starts])[:n]
        means[b] = x[idx].mean()
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


# ────────────────────────────────────────────────────── A8 [v3-5] funding
def funding_stamps(t_start_ms, t_end_ms, interval_ms=FUNDING_INTERVAL_MS, epoch=0):
    """The discrete stamps strictly inside (t_start, t_end]."""
    if t_end_ms <= t_start_ms:
        return []
    first = ((t_start_ms - epoch) // interval_ms + 1) * interval_ms + epoch
    return [t for t in range(first, t_end_ms + 1, interval_ms)]


def charge_funding(t_entry_ms, t_exit_ms, side, notional, rate_lookup,
                   interval_ms=FUNDING_INTERVAL_MS):
    """Charge the ACTUAL stamps this path crossed. Paid and received kept apart.

    side=+1 long pays when the rate is positive. side=-1 short receives it.
    A path that opens and closes between two stamps pays exactly zero, which is
    a real asymmetry between fast and slow rules and is reported, not smoothed.
    """
    stamps = funding_stamps(t_entry_ms, t_exit_ms, interval_ms)
    paid = recv = 0.0
    detail = []
    for ts in stamps:
        rate = rate_lookup(ts)
        if rate is None:
            detail.append({"stamp": ts, "rate": None, "amount": None,
                           "note": "NOT MEASURED - no rate at this stamp"})
            continue
        amt = -side * float(rate) * float(notional)
        if amt < 0:
            paid += -amt
        else:
            recv += amt
        detail.append({"stamp": ts, "rate": float(rate), "amount": amt})
    return {"stamps_crossed": len(stamps), "funding_paid": paid,
            "funding_received": recv, "net": recv - paid, "detail": detail}


# ──────────────────────────────────── A6, bar-aware (high/low) first passage
def first_passage_bars(ts, high, low, close, i0, sigma, k_grid, horizon_bars):
    """First passage using bar EXTREMES, not closes.

    Same-bar ambiguity (both barriers touched inside one bar) is NOT guessed.
    It is recorded per k as ambiguous_up_dn and surfaces as 'ambiguous' from
    hit_first_bars, so it can be counted and reported rather than silently
    resolved in whichever direction flatters the result.
    """
    t0 = int(ts[i0])
    p0 = float(close[i0])
    a, b = i0 + 1, min(i0 + 1 + horizon_bars, len(close))
    h = high[a:b]
    l = low[a:b]
    t = ts[a:b]
    out = {"t0": t0, "p0": p0, "sigma": float(sigma), "n_path": int(b - a),
           "t_up": {}, "t_dn": {}, "ambig": {},
           "truncated_by_data": b >= len(close)}
    if b - a <= 0 or sigma <= 0 or not np.isfinite(sigma):
        for k in k_grid:
            out["t_up"][k] = out["t_dn"][k] = None
            out["ambig"][k] = False
        out["mfe_sigma"] = out["mae_sigma"] = None
        out["horizon_ms"] = 0
        return out
    for k in k_grid:
        up_lvl, dn_lvl = p0 + k * sigma, p0 - k * sigma
        up_hit = h >= up_lvl
        dn_hit = l <= dn_lvl
        iu = int(np.argmax(up_hit)) if up_hit.any() else None
        idn = int(np.argmax(dn_hit)) if dn_hit.any() else None
        out["t_up"][k] = int(t[iu] - t0) if iu is not None else None
        out["t_dn"][k] = int(t[idn] - t0) if idn is not None else None
        out["ambig"][k] = bool(iu is not None and idn is not None and iu == idn)
    out["mfe_sigma"] = float((h.max() - p0) / sigma)
    out["mae_sigma"] = float((l.min() - p0) / sigma)
    out["horizon_ms"] = int(t[-1] - t0)
    return out


def hit_first_bars(obj, target_k, stop_k, side=1):
    if side == 1:
        tt, ts_, amb = obj["t_up"].get(target_k), obj["t_dn"].get(stop_k), None
    else:
        tt, ts_ = obj["t_dn"].get(target_k), obj["t_up"].get(stop_k)
    if tt is None and ts_ is None:
        return "censored"
    if ts_ is None:
        return "target"
    if tt is None:
        return "stop"
    if tt == ts_:
        return "ambiguous"
    return "target" if tt < ts_ else "stop"

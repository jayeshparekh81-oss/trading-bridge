"""cq_stats.py — A4 null models and A5 [v3-2] minimum detectable effect.

A4 baseline 1, random-walk theoretical: for absorbing barriers at +target and
-stop on a driftless walk, P(target first) = stop/(stop+target) = 1/(1+ratio).
A 1:3 setup breaks even at 25 pct, not 50 pct.

A4 baseline 2, volatility-matched control: non-event timestamps matched on BOTH
hour-of-day and trailing-volatility bucket, drawn WITHOUT replacement and
subject to the same A10 spacing rule as events.

A5 [v3-2]: the MDE is computed at EFFECTIVE N and compared against the effect
size worth having net of cost. If MDE > worth_having the test does not run.
"""
from __future__ import annotations

from statistics import NormalDist

import numpy as np

ND = NormalDist()


# ─────────────────────────────────────────────────── A4 baseline 1
def rw_hit_first_rate(target_k, stop_k):
    """Driftless random walk: P(target before stop) = stop/(stop+target)."""
    return stop_k / (stop_k + target_k)


def breakeven_rate(target_k, stop_k, cost_R=0.0):
    """Hit rate at which expectancy is zero, in R, net of cost."""
    r = target_k / stop_k
    return (1.0 + cost_R) / (1.0 + r)


def worth_having(target_k, stop_k, cost_R):
    """The smallest edge over the random walk that is worth anything after cost.

    breakeven - random_walk = cost / (1 + ratio), in probability points.
    """
    r = target_k / stop_k
    return cost_R / (1.0 + r)


def expectancy_R(p, target_k, stop_k, cost_R=0.0):
    r = target_k / stop_k
    return p * r - (1.0 - p) * 1.0 - cost_R


# ─────────────────────────────────────────────────── A5 [v3-2] MDE
def mde_binomial(p0, n, alpha=0.05, power=0.80, tol=1e-9):
    """Smallest |p1 - p0| detectable at n independent trials, two-sided.

    Solved numerically against the exact normal-approximation sample-size
    formula rather than the sqrt(p0(1-p0)) shortcut, so the answer is honest
    when p0 is far from 0.5.
    """
    if n is None or n <= 0:
        return None
    za = ND.inv_cdf(1 - alpha / 2)
    zb = ND.inv_cdf(power)

    def needed(delta):
        p1 = min(max(p0 + delta, 1e-9), 1 - 1e-9)
        return ((za * np.sqrt(p0 * (1 - p0)) + zb * np.sqrt(p1 * (1 - p1))) ** 2
                / (delta ** 2))

    lo, hi = 1e-6, min(0.5, 1 - p0 - 1e-9)
    if needed(hi) > n:
        return None                      # even the largest effect is undetectable
    for _ in range(200):
        mid = (lo + hi) / 2
        if needed(mid) > n:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return hi


def power_verdict(p0, n_eff, target_k, stop_k, cost_R, alpha=0.05, power=0.80):
    """The A5 [v3-2] gate. Returns a dict; 'run' is False when underpowered."""
    mde = mde_binomial(p0, n_eff, alpha, power)
    wh = worth_having(target_k, stop_k, cost_R)
    if mde is None:
        return {"mde": None, "worth_having": wh, "run": False,
                "verdict": "NOT RUN - UNDERPOWERED",
                "reason": f"no effect is detectable at effective N={n_eff}"}
    ok = mde <= wh
    return {"mde": mde, "worth_having": wh, "effective_n": n_eff,
            "alpha": alpha, "power": power, "run": bool(ok),
            "verdict": ("POWERED" if ok else "NOT RUN - UNDERPOWERED"),
            "reason": (f"MDE {mde:.5f} <= worth_having {wh:.5f}" if ok else
                       f"MDE {mde:.5f} EXCEEDS worth_having {wh:.5f}; "
                       "the test cannot see an effect big enough to matter")}


# ─────────────────────────────────────────────────── A4 baseline 2
def vol_bucket(values, n_buckets=5):
    """Quantile buckets of trailing volatility. Causal input assumed."""
    v = np.asarray(values, dtype=float)
    finite = v[np.isfinite(v)]
    if len(finite) == 0:
        return np.zeros(len(v), dtype=int)
    edges = np.quantile(finite, np.linspace(0, 1, n_buckets + 1)[1:-1])
    return np.digitize(v, edges)


def matched_controls(event_idx, hours, volb, n_per_event=1, seed=11,
                     exclude_idx=None, min_spacing_idx=0):
    """Draw non-event controls matched on (hour-of-day, vol bucket).

    Without replacement (A4), and honouring a minimum index spacing so the
    baseline is not built from a handful of repeatedly-sampled quiet windows.
    Returns (controls, unmatched_events) - unmatched are REPORTED, not dropped
    silently.
    """
    rng = np.random.default_rng(seed)
    n = len(hours)
    banned = set(exclude_idx or [])
    banned |= set(event_idx)
    pools = {}
    for i in range(n):
        pools.setdefault((int(hours[i]), int(volb[i])), []).append(i)
    used, controls, unmatched = [], [], []
    used_sorted = []
    for e in event_idx:
        key = (int(hours[e]), int(volb[e]))
        cand = [i for i in pools.get(key, []) if i not in banned]
        rng.shuffle(cand)
        got = 0
        for i in cand:
            if min_spacing_idx > 0 and used_sorted:
                import bisect as _b
                j = _b.bisect_left(used_sorted, i)
                near = False
                for jj in (j - 1, j):
                    if 0 <= jj < len(used_sorted) and abs(used_sorted[jj] - i) < min_spacing_idx:
                        near = True
                        break
                if near:
                    continue
            controls.append(i)
            banned.add(i)
            import bisect as _b2
            _b2.insort(used_sorted, i)
            got += 1
            if got >= n_per_event:
                break
        if got == 0:
            unmatched.append(e)
    return controls, unmatched

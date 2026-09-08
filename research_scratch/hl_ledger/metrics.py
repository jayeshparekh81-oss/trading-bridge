"""metrics.py — the eight sealed metrics and the sealed classifier.

Thresholds are frozen by PREREG.md at commit d62a46cc and are NOT arguments.
All monetary/size fields arrive as STRINGS (CP1.2) and are parsed with float().
"""
from __future__ import annotations

import statistics
from collections import defaultdict

EPS = 1e-9
HOUR_MS = 3_600_000

MM_MAKER = 0.80
MM_FPD = 200
MM_HOLD = 600
CARRY_FUND = 0.50
CARRY_NET = 0.20
DIR_MAKER = 0.50
DIR_HOLD = 3600


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _signed_delta(fill) -> float:
    sz = abs(_f(fill.get("sz")))
    return sz if fill.get("side") == "B" else -sz


def episodes(fills):
    """Flat-to-flat episodes per coin. Returns (closed_durations_s, n_never_closed)."""
    by_coin = defaultdict(list)
    for f in fills:
        by_coin[f.get("coin")].append(f)
    durations, never = [], 0
    for coin, fs in by_coin.items():
        fs = sorted(fs, key=lambda x: int(x["time"]))
        pos = _f(fs[0].get("startPosition"))
        open_at = int(fs[0]["time"]) if abs(pos) > EPS else None
        for f in fs:
            before = pos
            pos = pos + _signed_delta(f)
            t = int(f["time"])
            if abs(before) <= EPS and abs(pos) > EPS:
                open_at = t
            elif abs(before) > EPS and abs(pos) <= EPS:
                if open_at is not None:
                    durations.append((t - open_at) / 1000.0)
                open_at = None
        if open_at is not None and abs(pos) > EPS:
            never += 1
    return durations, never


def net_exposure(fills):
    """mean over hourly sample points of |sum signed ntl| / sum |ntl|.

    Per coin we precompute a time-ordered array of (time, position, px) and use
    bisect to find the state at each hourly sample, so cost is
    O(coins * samples * log n) rather than a linear rescan per sample.
    """
    import bisect
    if not fills:
        return None, 0
    fs = sorted(fills, key=lambda x: int(x["time"]))
    t0, t1 = int(fs[0]["time"]), int(fs[-1]["time"])
    if t1 <= t0:
        return None, 0
    by_coin = defaultdict(list)
    for f in fs:
        by_coin[f.get("coin")].append(f)
    tracks = {}
    for coin, cf in by_coin.items():
        pos = _f(cf[0].get("startPosition"))
        times, states = [], []
        for f in cf:
            pos = pos + _signed_delta(f)
            times.append(int(f["time"]))
            states.append((pos, _f(f.get("px"))))
        tracks[coin] = (times, states)
    ratios = []
    t = t0
    while t <= t1:
        net = gross = 0.0
        for coin, (times, states) in tracks.items():
            i = bisect.bisect_right(times, t) - 1
            if i < 0:
                continue
            pos, px = states[i]
            ntl = pos * px
            net += ntl
            gross += abs(ntl)
        if gross > EPS:
            ratios.append(abs(net) / gross)
        t += HOUR_MS
    if not ratios:
        return None, 0
    return sum(ratios) / len(ratios), len(ratios)


def compute(addr, fills, funding):
    gross = sum(abs(_f(f.get("sz"))) * _f(f.get("px")) for f in fills)
    maker = sum(abs(_f(f.get("sz"))) * _f(f.get("px"))
                for f in fills if f.get("crossed") is False)
    days = {int(f["time"]) // 86_400_000 for f in fills}
    durs, never = episodes(fills)
    n_ep = len(durs) + never
    netx, npts = net_exposure(fills)
    recv = sum(_f(r.get("delta", {}).get("usdc"))
               for r in funding if _f(r.get("delta", {}).get("usdc")) > 0)
    pos_pnl = sum(_f(f.get("closedPnl")) for f in fills if _f(f.get("closedPnl")) > 0)
    pnls = [_f(f.get("closedPnl")) for f in fills if abs(_f(f.get("closedPnl"))) > EPS]
    total_profit = sum(p for p in pnls if p > 0)
    return {
        "wallet": addr,
        "maker_share_ntl": (maker / gross) if gross > EPS else None,
        "fills_per_active_day": (len(fills) / len(days)) if days else None,
        "median_flat_to_flat_holding_seconds": statistics.median(durs) if durs else None,
        "never_closed_fraction": (never / n_ep) if n_ep else None,
        "episodes_closed": len(durs), "episodes_never_closed": never,
        "mean_abs_net_exposure_over_gross": netx,
        "net_exposure_sample_points": npts,
        "funding_share_of_pnl": (recv / (recv + pos_pnl)) if (recv + pos_pnl) > EPS else None,
        "funding_received_usdc": recv,
        "n_distinct_coins": len({f.get("coin") for f in fills}),
        "fee_paid_over_gross_notional": (sum(_f(f.get("fee")) for f in fills) / gross)
                                         if gross > EPS else None,
        "closedPnl_count": len(pnls),
        "closedPnl_median": statistics.median(pnls) if pnls else None,
        "closedPnl_mean": (sum(pnls) / len(pnls)) if pnls else None,
        "best_episode_share_of_profit": (max(pnls) / total_profit)
                                         if pnls and total_profit > EPS else None,
        "gross_notional": gross,
        "n_fills": len(fills),
    }


def classify(m):
    """The SEALED rules. First match wins. Missing metric never satisfies a rule."""
    ms = m.get("maker_share_ntl")
    fpd = m.get("fills_per_active_day")
    hold = m.get("median_flat_to_flat_holding_seconds")
    fund = m.get("funding_share_of_pnl")
    netx = m.get("mean_abs_net_exposure_over_gross")
    if (ms is not None and fpd is not None and hold is not None
            and ms >= MM_MAKER and fpd >= MM_FPD and hold <= MM_HOLD):
        return "MARKET-MAKER"
    if ((fund is not None and fund >= CARRY_FUND)
            or (netx is not None and netx <= CARRY_NET)):
        return "NEUTRAL/CARRY"
    if (ms is not None and hold is not None
            and ms <= DIR_MAKER and hold >= DIR_HOLD):
        return "DIRECTIONAL"
    return "UNCLASSIFIED"

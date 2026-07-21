"""STRESS GATES (P4, 2026-07-21) — three teeth for the walk-forward harness.

  (a) remove_best_days — is the edge FAT-TAIL-CONCENTRATED? Drop the n best days from
      the stitched daily net-R series and recompute expectancy. An edge that dies with
      its best 5 days is two lucky trades, not a system.
  (b) slippage_stress — does the edge survive WORSE EXECUTION? Recompute net R at
      slippage_multiplier=1.5 via the EXISTING cost knob (signals/costs.py:55; scales
      friction spread+slippage only, statutory charges untouched). REUSES trade_net_r —
      zero duplicate cost math.
  (c) paired_block_bootstrap — is system A REALLY better than B? Contiguous-block
      (default 5-day) bootstrap of the PAIRED daily difference (resampling the same
      blocks for both systems == resampling the difference series), stored seed,
      mean delta + 95% CI; verdict "no clear superiority" when the CI includes 0.

All three are PURE and additive: nothing existing changes; CLI exposure is DEFAULT OFF.
Every gate REFUSES loudly on insufficient data rather than emitting a degenerate number.
"""

from __future__ import annotations

import random
from typing import Optional, Sequence

from signals.costs import CostConfig, trade_net_r

REFUSAL_BEST = "INSUFFICIENT DATA — best-day removal degenerate"
REFUSAL_PAIRED = "INSUFFICIENT DATA — paired bootstrap degenerate"


# ---------------------------------------------------------------- (a) best-day removal
def daily_net_series(trades) -> list[tuple[str, float]]:
    """Stitch per-trade outcomes into a sorted per-day net series. ``trades`` = any
    iterable with .day and .r (research.walkforward.Trade)."""
    acc: dict[str, float] = {}
    for t in trades:
        acc[t.day] = acc.get(t.day, 0.0) + t.r
    return sorted(acc.items())


def remove_best_days(series: Sequence[tuple[str, float]], n: int = 5) -> dict:
    """Drop the ``n`` best days; recompute expectancy. GUARDRAIL: usable < 3n refuses —
    with fewer than 3n days the 'ex-best' remainder is too short to mean anything."""
    days = list(series)
    if len(days) < 3 * n:
        return {"refused": True, "reason": f"{REFUSAL_BEST} (days={len(days)} < {3 * n})",
                "n_days": len(days), "n_removed": 0}
    ranked = sorted(days, key=lambda kv: kv[1], reverse=True)
    removed = ranked[:n]
    kept = ranked[n:]
    tot_b = sum(v for _, v in days)
    tot_a = sum(v for _, v in kept)
    return {"refused": False, "n_days": len(days), "n_removed": n,
            "removed_days": [d for d, _ in removed],
            "removed_r": round(sum(v for _, v in removed), 4),
            "total_before": round(tot_b, 4), "mean_before": round(tot_b / len(days), 4),
            "total_after": round(tot_a, 4), "mean_after": round(tot_a / len(kept), 4),
            "survives": tot_a > 0}


# ---------------------------------------------------------------- (b) slippage stress
def slippage_stress(cost_inputs: Sequence[dict], *, stress: float = 1.5) -> dict:
    """Net totals at multiplier 1.0 vs ``stress``, via the EXISTING knob — each entry
    needs {gross, r_unit, premium, delta, delta_source, lot}. Entries missing an input
    are counted UNCOSTED (never estimated); coverage is reported."""
    base_cfg = CostConfig()                                    # multiplier 1.0
    stress_cfg = CostConfig.from_dict({"slippage_multiplier": stress})
    gross_t = 0.0
    net1 = net_s = 0.0
    costed = 0
    uncosted = 0
    for ci in cost_inputs:
        g = ci.get("gross")
        if g is None:
            uncosted += 1
            continue
        gross_t += g
        if not ci.get("premium") or not ci.get("lot") or not ci.get("r_unit"):
            uncosted += 1
            continue
        kw = dict(realized_r=g, r_unit_pts=ci["r_unit"], entry_premium=ci["premium"],
                  delta=ci.get("delta", 0.5), delta_source=ci.get("delta_source", "fallback"),
                  lot_size=ci["lot"])
        n1, _, _ = trade_net_r(cfg=base_cfg, **kw)
        ns, _, _ = trade_net_r(cfg=stress_cfg, **kw)
        net1 += n1
        net_s += ns
        costed += 1
    return {"stress_multiplier": stress, "n_costed": costed, "n_uncosted": uncosted,
            "gross_total": round(gross_t, 4),
            "net_1p0x": round(net1, 4), "net_stress": round(net_s, 4),
            "survives_1p0x": net1 > 0, "survives_stress": net_s > 0}


# ---------------------------------------------------------------- (c) paired bootstrap
def paired_block_bootstrap(a_daily: Sequence[float], b_daily: Sequence[float], *,
                           block: int = 5, n_boot: int = 10000, seed: int = 20260721,
                           ci: float = 0.95) -> dict:
    """Contiguous-block bootstrap of the PAIRED daily difference A−B (moving blocks of
    ``block`` days; identical block picks for both systems ⇔ resampling the difference
    series). STORED SEED → bit-reproducible. Verdict 'no clear superiority' when the
    ``ci`` interval includes 0. GUARDRAIL: needs len(A)==len(B) ≥ 2·block."""
    if len(a_daily) != len(b_daily):
        return {"refused": True, "reason": f"{REFUSAL_PAIRED} (len A {len(a_daily)} != len B {len(b_daily)})"}
    n = len(a_daily)
    if n < 2 * block:
        return {"refused": True, "reason": f"{REFUSAL_PAIRED} (days={n} < {2 * block})"}
    diff = [a - b for a, b in zip(a_daily, b_daily)]
    observed = sum(diff) / n
    rng = random.Random(seed)
    n_starts = n - block + 1                                   # moving-block starts
    k = -(-n // block)                                         # blocks per replicate (ceil)
    boots: list[float] = []
    for _ in range(n_boot):
        sample: list[float] = []
        for _ in range(k):
            s = rng.randrange(n_starts)
            sample.extend(diff[s:s + block])
        sample = sample[:n]
        boots.append(sum(sample) / n)
    boots.sort()
    lo = boots[int((1 - ci) / 2 * (n_boot - 1))]
    hi = boots[int((1 - (1 - ci) / 2) * (n_boot - 1))]
    includes0 = lo <= 0.0 <= hi
    return {"refused": False, "n_days": n, "block": block, "n_boot": n_boot, "seed": seed,
            "mean_delta": round(observed, 4), "ci_pct": ci,
            "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "verdict": "no clear superiority" if includes0 else
                       ("A superior" if lo > 0 else "B superior")}

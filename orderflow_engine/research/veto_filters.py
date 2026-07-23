"""VETO FILTERS (2026-07-22) — two OFFLINE, IN-SAMPLE veto hypotheses layered on top of the
delta+VWAP-side evaluator's fired set. Pure post-filters: they only REMOVE fires, never add
or reprice one. No scorer change, no build_exit_plan/SimPosition change, no live/config touch.

FROZEN PARAMETERS (result-blind, do not alter):
  * BAND veto (K=1.0): veto LONG if bar-close price > VWAP+1*SD (== ctx.vwap_bands["upper_1"]);
    veto SHORT if price < VWAP-1*SD (== lower_1). STRICT inequalities (exactly at the band =
    NO veto). Inactive while SD==0 OR fewer than 20 prior same-session bars exist.
  * ABSORPTION veto: heavy := bar volume >= 3 * mean(volume of the prior 20 same-session bars)
    (inactive until 20 prior bars exist; >= at exactly 3x counts). doji := body/range <= 0.2
    with a range>0 guard (<= at exactly 0.2 counts). veto LONG if heavy AND (close<open OR doji);
    veto SHORT if heavy AND (close>open OR doji).

Both are computed ONLY from already-captured DayCapture state (ctx + bars) and are strictly
CAUSAL — the rolling average and the prior-bar count use bars STRICTLY BEFORE the candidate
bar, never the candidate bar or anything later. IN-SAMPLE exploration on burned days only.
"""

from __future__ import annotations

from typing import Optional, Sequence

from research.delta_vwap_evaluator import (
    DayCapture, R_FIELDS, Trade, price_candidate, rule_decisions,
)

BAND_K = 1.0
WARMUP_BARS = 20
HEAVY_MULT = 3.0
AVG_WINDOW = 20
DOJI_MAX = 0.2


def _signal_bar_and_priors(cap: DayCapture, cand: dict):
    """(candidate's own bar, list of bars STRICTLY BEFORE it). The prior list is what every
    causal statistic uses — never the candidate bar, never a later bar."""
    bars = cap.bars.get(cand["sid"], [])
    for i, b in enumerate(bars):                      # bars are end_ts_ns-ascending
        if b["end_ts_ns"] == cand["ts_ns"]:
            return b, bars[:i]
    return None, []


def veto_band(cand: dict, cap: DayCapture) -> bool:
    """K=1 VWAP-SD band veto (frozen). Inactive during warm-up (<20 prior bars) or SD==0."""
    ctx = cap.ctx.get((cand["sid"], cand["ts_ns"]))
    if ctx is None or ctx.vwap is None:
        return False
    _, priors = _signal_bar_and_priors(cap, cand)
    if len(priors) < WARMUP_BARS:                     # warm-up: not enough session history
        return False
    upper = ctx.vwap_bands.get(f"upper_{int(BAND_K)}")
    lower = ctx.vwap_bands.get(f"lower_{int(BAND_K)}")
    if upper is None or lower is None:
        return False
    sd = upper - ctx.vwap                             # bands are vwap +/- K*sd; K=1 -> sd
    if sd == 0:                                        # degenerate band -> inactive (frozen)
        return False
    p = ctx.price                                     # candidate bar close
    if cand["side"] == "long":
        return p > upper                              # STRICT: exactly at upper_1 -> no veto
    return p < lower                                  # STRICT: exactly at lower_1 -> no veto


def veto_absorption(cand: dict, cap: DayCapture) -> bool:
    """Heavy-volume rejection veto (frozen). Inactive until 20 prior bars exist."""
    bar, priors = _signal_bar_and_priors(cap, cand)
    if bar is None or len(priors) < AVG_WINDOW:
        return False
    last = priors[-AVG_WINDOW:]                        # prior 20 ONLY — strictly causal
    avg = sum(float(b["volume"]) for b in last) / AVG_WINDOW
    if avg <= 0:                                       # degenerate denominator -> no veto
        return False
    if float(bar["volume"]) < HEAVY_MULT * avg:        # >= at exactly 3x counts as heavy
        return False
    rng = float(bar["high"]) - float(bar["low"])
    body = abs(float(bar["close"]) - float(bar["open"]))
    doji = rng > 0 and (body / rng) <= DOJI_MAX        # <= at exactly 0.2 counts as doji
    if cand["side"] == "long":
        return (float(bar["close"]) < float(bar["open"])) or doji
    return (float(bar["close"]) > float(bar["open"])) or doji


def day_trades_filtered(cap: DayCapture, instrument: str, dmed: Optional[float],
                        r_field: str = "realized_r", *,
                        apply_band: bool = False, apply_absorption: bool = False):
    """Mirror of delta_vwap_evaluator.day_trades with veto POST-FILTERING. With both
    apply_* False the returned Trade list is byte-identical to day_trades (same rule_decisions,
    same price_candidate, same skip accounting; the only additions are the veto TALLIES).
    ``removed_*`` count every rule-fired candidate a veto would flag (regardless of apply
    flags), so the report can show band-only / absorption-only / either removals in one pass."""
    if r_field not in R_FIELDS:
        raise ValueError(f"r_field must be one of {R_FIELDS}")
    trades: list[Trade] = []
    audit = {"day": cap.day, "candidates": 0, "rule_fires": 0, "priced": 0,
             "skipped_unpriceable": 0, "skipped_no_net": 0,
             "removed_band": 0, "removed_absorption": 0, "removed_either": 0, "vetoed": 0}
    for cand, fires in rule_decisions(cap, instrument, dmed):
        audit["candidates"] += 1
        if not fires:
            continue
        audit["rule_fires"] += 1
        vb = veto_band(cand, cap)
        va = veto_absorption(cand, cap)
        if vb:
            audit["removed_band"] += 1
        if va:
            audit["removed_absorption"] += 1
        if vb or va:
            audit["removed_either"] += 1
        if (apply_band and vb) or (apply_absorption and va):
            audit["vetoed"] += 1
            continue
        rec = price_candidate(cap, cand)
        if rec is None:
            audit["skipped_unpriceable"] += 1
            continue
        r = rec.get(r_field)
        if r is None:
            audit["skipped_no_net"] += 1
            continue
        audit["priced"] += 1
        trades.append(Trade(day=cap.day, entry_ns=rec["entry_ns"],
                            exit_ns=rec["exit_ns"], r=r))
    return trades, audit

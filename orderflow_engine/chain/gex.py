"""Gamma Exposure (GEX) proxy (Module R5).

Per strike: gamma × OI × contract_size, signed by the standard SqueezeMetrics-style
dealer convention — CALL gamma POSITIVE, PUT gamma NEGATIVE (net dealer gamma).
Summed across strikes => net GEX; the gamma-flip level is the spot at which net
GEX crosses zero (linear interpolation between adjacent strikes' cumulative GEX).

The convention (sign AND scale) is itself a CALIBRATION SUBJECT — validated against
observed pin/acceleration behaviour on replay. Net GEX is computed + logged, but
the regime FLAG is INERT (threshold 0) until calibrated.
"""

from __future__ import annotations

from typing import Optional

CALL = "CE"
PUT = "PE"


def strike_gex(gamma: float, oi: int, contract_size: int, right: str) -> float:
    """Signed dealer gamma for one strike (call +, put -)."""
    if gamma is None:
        return 0.0
    mag = gamma * int(oi or 0) * int(contract_size)
    return mag if right == CALL else -mag


def net_gex(strikes: list[dict], contract_size: int) -> float:
    """Sum signed per-strike GEX. Each strike dict needs gamma, oi, right."""
    return sum(strike_gex(s.get("gamma"), s.get("oi") or 0, contract_size, s.get("right"))
               for s in strikes)


def gamma_flip(strikes: list[dict], contract_size: int) -> Optional[float]:
    """Strike level where cumulative signed GEX (ordered by strike) crosses zero.

    Cumulative GEX is built low->high strike; the flip is where it changes sign,
    linearly interpolated between the bracketing strikes. None if it never crosses.
    """
    by_strike: dict[int, float] = {}
    for s in strikes:
        k = int(s["strike"])
        by_strike[k] = by_strike.get(k, 0.0) + strike_gex(
            s.get("gamma"), s.get("oi") or 0, contract_size, s.get("right"))
    ks = sorted(by_strike)
    if len(ks) < 2:
        return None
    cum = 0.0
    prev_k, prev_cum = None, None
    for k in ks:
        cum += by_strike[k]
        if prev_cum is not None and (prev_cum <= 0 <= cum or prev_cum >= 0 >= cum) \
                and prev_cum != cum:
            frac = (0.0 - prev_cum) / (cum - prev_cum)
            return prev_k + frac * (k - prev_k)
        prev_k, prev_cum = k, cum
    return None


def regime_flag(net: float, threshold: float) -> Optional[str]:
    """Positive/negative gamma regime — INERT (None) while threshold==0."""
    if threshold <= 0:
        return None
    if net >= threshold:
        return "positive_gamma"
    if net <= -threshold:
        return "negative_gamma"
    return "neutral"

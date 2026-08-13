"""Black-Scholes pricing, implied-vol inversion, and Greeks (Module R5).

Stdlib only (math.erf for the normal CDF — no scipy/numpy). Rate is passed in
(config constant). All functions are pure and defensive at the boundaries:

  * T <= 0 (expired)                  -> price = intrinsic; IV/Greeks = None
  * price <= 0 or <= forward intrinsic-> IV None (deep ITM / stale / arb)
  * price >= underlying (call)        -> IV None (no BSM solution)

IV is found by bisection on sigma in [1e-6, 5.0] (BSM price is monotincreasing in
sigma, so bisection always converges within the no-arb band). Vega is per 1.0 of
vol and theta is per YEAR (callers scale to per-1% / per-day as needed).
"""

from __future__ import annotations

import math
from typing import Optional

CALL = "CE"
PUT = "PE"

_SQRT2 = math.sqrt(2.0)
_SQRT2PI = math.sqrt(2.0 * math.pi)


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT2PI


def _d1_d2(S, K, T, r, sigma):
    v = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / v
    return d1, d1 - v


def bs_price(S: float, K: float, T: float, r: float, sigma: float, right: str) -> float:
    if T <= 0 or sigma <= 0:
        # expired / zero-vol -> discounted intrinsic
        disc_k = K * math.exp(-r * max(T, 0.0))
        return max(0.0, S - disc_k) if right == CALL else max(0.0, disc_k - S)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    if right == CALL:
        return S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)
    return K * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)


def implied_vol(price: float, S: float, K: float, T: float, r: float,
                right: str) -> Optional[float]:
    if price is None or price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None
    intrinsic = bs_price(S, K, T, r, 1e-9, right)   # ~ discounted intrinsic
    upper = S if right == CALL else K * math.exp(-r * T)
    if price < intrinsic - 1e-9 or price >= upper:
        return None                                  # outside the no-arb band
    lo, hi = 1e-6, 5.0
    plo = bs_price(S, K, T, r, lo, right)
    phi = bs_price(S, K, T, r, hi, right)
    if not (plo <= price <= phi):
        return None
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        pm = bs_price(S, K, T, r, mid, right)
        if abs(pm - price) < 1e-7:
            return mid
        if pm < price:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def greeks(S: float, K: float, T: float, r: float, sigma: float,
           right: str) -> Optional[dict]:
    """delta, gamma (per 1pt), vega (per 1.0 vol), theta (per year). None if degenerate."""
    if sigma is None or sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    pdf = _npdf(d1)
    gamma = pdf / (S * sigma * math.sqrt(T))
    vega = S * pdf * math.sqrt(T)
    if right == CALL:
        delta = _ncdf(d1)
        theta = (-(S * pdf * sigma) / (2 * math.sqrt(T))
                 - r * K * math.exp(-r * T) * _ncdf(d2))
    else:
        delta = _ncdf(d1) - 1.0
        theta = (-(S * pdf * sigma) / (2 * math.sqrt(T))
                 + r * K * math.exp(-r * T) * _ncdf(-d2))
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

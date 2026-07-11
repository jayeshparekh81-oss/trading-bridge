"""Descriptive chain analytics (Module R5) — pure functions on a chain snapshot.

A "snapshot" is a list of per-strike dicts with keys: right (CE/PE), strike, oi,
volume, ltp, iv (may be None). All functions are functional (descriptive context),
not signal-firing.
"""

from __future__ import annotations

from typing import Optional

CALL = "CE"
PUT = "PE"


def _sum(strikes, right, field) -> int:
    return sum(int(s.get(field) or 0) for s in strikes if s.get("right") == right)


def pcr_oi(strikes: list[dict]) -> Optional[float]:
    ce = _sum(strikes, CALL, "oi")
    pe = _sum(strikes, PUT, "oi")
    return (pe / ce) if ce > 0 else None


def pcr_volume(strikes: list[dict]) -> Optional[float]:
    ce = _sum(strikes, CALL, "volume")
    pe = _sum(strikes, PUT, "volume")
    return (pe / ce) if ce > 0 else None


def max_pain(strikes: list[dict]) -> Optional[int]:
    """Strike minimizing total option-writer payout at expiry (classic max pain)."""
    ce_oi: dict[int, int] = {}
    pe_oi: dict[int, int] = {}
    for s in strikes:
        k = int(s["strike"])
        if s.get("right") == CALL:
            ce_oi[k] = ce_oi.get(k, 0) + int(s.get("oi") or 0)
        elif s.get("right") == PUT:
            pe_oi[k] = pe_oi.get(k, 0) + int(s.get("oi") or 0)
    candidates = sorted(set(ce_oi) | set(pe_oi))
    if not candidates:
        return None
    best_k, best_pay = None, None
    for expiry_price in candidates:
        pay = 0
        for k, oi in ce_oi.items():
            pay += oi * max(0, expiry_price - k)
        for k, oi in pe_oi.items():
            pay += oi * max(0, k - expiry_price)
        if best_pay is None or pay < best_pay:
            best_pay, best_k = pay, expiry_price
    return best_k


def basis(fut: Optional[float], spot: Optional[float]) -> Optional[float]:
    if fut is None or spot is None:
        return None
    return fut - spot


def annualized_basis(fut, spot, days_to_expiry: float, day_count: int = 365) -> Optional[float]:
    b = basis(fut, spot)
    if b is None or spot in (None, 0) or days_to_expiry <= 0:
        return None
    return (b / spot) * (day_count / days_to_expiry)


def atm_strike(strikes: list[dict], spot: float) -> Optional[int]:
    ks = sorted({int(s["strike"]) for s in strikes})
    if not ks:
        return None
    return min(ks, key=lambda k: abs(k - spot))


def atm_iv(strikes: list[dict], spot: Optional[float]) -> Optional[float]:
    """Average of CE and PE IV at the ATM strike (whichever are available)."""
    if spot is None:
        return None
    atm = atm_strike(strikes, spot)
    if atm is None:
        return None
    ivs = [s["iv"] for s in strikes
           if int(s["strike"]) == atm and s.get("iv") is not None]
    return sum(ivs) / len(ivs) if ivs else None

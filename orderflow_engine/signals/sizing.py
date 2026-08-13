"""R8 position sizing (I4) — hold RISK constant by varying SIZE against stop distance.

The missing layer: fixed-lot = uncontrolled risk (a 7pt stop and a 40pt stop at the same
lots are ~5.7× different risk). Instead:

    lots = min( floor(risk_budget / (stop_pts × delta × lot_size)), customer_max_lots )

then rounded DOWN to an EVEN lot count (the 1R 50% partial needs a whole half — an odd lot
can't be halved), and REJECTED below ``min_lots`` (2). The 2-lot minimum is STRUCTURAL, not
optional: the Gear-2 free-trade (move stop to breakeven after the 1R partial) is what makes
a trade survivable against ~55%-of-1R costs; a sub-2-lot trade can't take the partial and is
naked — so it is rejected, with the reason logged.

``delta`` comes from the RECORDED greeks and ``lot_size`` from the SCRIP MASTER — the same
authoritative sources as the cost model, never hardcoded. risk_budget = risk_pct × equity ×
size_factor (the D1 post-win size-down multiplies size_factor). All knobs HYPOTHESIS.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Optional


@dataclass(frozen=True)
class SizingConfig:
    risk_pct: float = 0.01
    customer_max_lots: int = 8
    even_lots_only: bool = True
    min_lots: int = 2

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "SizingConfig":
        d = d or {}
        return cls(risk_pct=float(d.get("risk_pct", 0.01)),
                   customer_max_lots=int(d.get("customer_max_lots", 8)),
                   even_lots_only=bool(d.get("even_lots_only", True)),
                   min_lots=int(d.get("min_lots", 2)))


@dataclass(frozen=True)
class SizingResult:
    lots: int
    raw_lots: float
    risk_budget_inr: float
    risk_per_lot_inr: float          # stop_pts × delta × lot_size
    size_factor: float               # D1 multiplier applied (1.0 or the sizedown)
    capped_by: str                   # "" | "customer_max_lots" | "risk"
    rejected: bool
    reason: str                      # "" if sized, else the rejection reason


def _even_down(n: int) -> int:
    return n - (n % 2)


def size_position(*, equity_inr: float, stop_pts: float, delta: float, lot_size: int,
                  cfg: SizingConfig, size_factor: float = 1.0) -> SizingResult:
    """Compute the sized lot count (or a REJECT). Pure; no I/O."""
    if stop_pts <= 0 or delta <= 0 or lot_size <= 0 or equity_inr <= 0:
        return SizingResult(0, 0.0, 0.0, 0.0, size_factor, "", True, "invalid_inputs")
    risk_budget = equity_inr * cfg.risk_pct * size_factor
    risk_per_lot = stop_pts * delta * lot_size
    raw = risk_budget / risk_per_lot
    lots = floor(raw)
    if cfg.even_lots_only:
        lots = _even_down(lots)
    capped_by = ""
    if lots > cfg.customer_max_lots:
        lots = cfg.customer_max_lots
        if cfg.even_lots_only:
            lots = _even_down(lots)
        capped_by = "customer_max_lots"
    if lots < cfg.min_lots:
        return SizingResult(0, raw, risk_budget, risk_per_lot, size_factor, capped_by,
                            True, f"sub_{cfg.min_lots}lot_reject")
    return SizingResult(lots, raw, risk_budget, risk_per_lot, size_factor,
                        capped_by, False, "")

"""LinReg channel lower band — companion to :mod:`linear_regression_upper`."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.linear_regression_upper import (
    _linreg_band,
)


def linear_regression_lower(
    values: Sequence[float],
    period: int = 20,
    std_mult: float = 2.0,
) -> list[float | None]:
    """LinReg channel — lower band."""
    return _linreg_band(values, period, std_mult, side=-1)


__all__ = ["linear_regression_lower"]

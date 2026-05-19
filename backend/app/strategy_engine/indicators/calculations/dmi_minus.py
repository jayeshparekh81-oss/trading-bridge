"""DMI -DI (dmi_minus) — wrapper around adx() returning just the -DI line.

The existing ``adx()`` calc returns ``(adx, plus_di, minus_di)``. This
wrapper exposes ``minus_di`` under the library-canonical slug.

No duplicate math — pure wrapper.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.adx import adx


def dmi_minus(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Return only the -DI series from the DMI/ADX pipeline."""
    _, _, minus_di = adx(highs, lows, closes, period=period)
    return minus_di


__all__ = ["dmi_minus"]

"""DMI +DI (dmi_plus) — wrapper around adx() returning just the +DI line.

The existing ``adx()`` calc returns ``(adx, plus_di, minus_di)``. This
wrapper exposes ``plus_di`` under the library-canonical slug.

No duplicate math — pure wrapper.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.adx import adx


def dmi_plus(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Return only the +DI series from the DMI/ADX pipeline."""
    _, plus_di, _ = adx(highs, lows, closes, period=period)
    return plus_di


__all__ = ["dmi_plus"]

"""Volume SMA — simple moving average applied to the volume series.

Thin wrapper over :func:`app.strategy_engine.indicators.calculations.sma.sma`
exposed under its own registry id so the indicator-library UI can
present "Volume SMA" without overloading "SMA" with a source flag.

Edge cases inherit from :func:`sma` — empty input or
``period > len(volumes)`` returns ``[]``; otherwise output length equals
input length with ``None`` warm-up positions.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.sma import sma


def volume_sma(volumes: Sequence[float], period: int = 20) -> list[float | None]:
    """SMA of the volume series."""
    return sma(volumes, period)


__all__ = ["volume_sma"]

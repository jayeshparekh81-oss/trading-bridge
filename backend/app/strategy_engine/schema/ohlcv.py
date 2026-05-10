"""OHLCV typing — bar / candle and price-source enum.

Indicator calculation functions accept plain ``Sequence[float]`` for
performance (Pydantic per-bar validation would be wasteful inside a
backtest hot loop). :class:`Candle` is the validated typed shape used at
boundaries — fixture loaders, JSON parsers, the backtest engine input.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PriceSource(StrEnum):
    """Indicator input source — which price series to read from a candle."""

    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    VOLUME = "volume"
    HL2 = "hl2"  # (high + low) / 2
    HLC3 = "hlc3"  # (high + low + close) / 3 — typical price
    OHLC4 = "ohlc4"  # (open + high + low + close) / 4


class Candle(BaseModel):
    """One OHLCV bar. Frozen so it's hashable and safe to share across loops.

    Validation enforces the basic OHLC invariant
    ``low <= min(open, close) <= max(open, close) <= high`` and
    ``volume >= 0``. Bars that violate the invariant are rejected at the
    boundary; calculations downstream may assume the invariant holds.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: float = Field(..., ge=0)

    @model_validator(mode="after")
    def _check_ohlc_invariant(self) -> Candle:
        if self.low > self.high:
            raise ValueError(f"Candle invariant violated: low ({self.low}) > high ({self.high}).")
        for label, value in (("open", self.open), ("close", self.close)):
            if value < self.low or value > self.high:
                raise ValueError(
                    f"Candle invariant violated: {label} ({value}) outside "
                    f"[low={self.low}, high={self.high}]."
                )
        return self

    def price(self, source: PriceSource) -> float:
        """Return the requested price series for this candle."""
        if source is PriceSource.OPEN:
            return self.open
        if source is PriceSource.HIGH:
            return self.high
        if source is PriceSource.LOW:
            return self.low
        if source is PriceSource.CLOSE:
            return self.close
        if source is PriceSource.VOLUME:
            return self.volume
        if source is PriceSource.HL2:
            return (self.high + self.low) / 2
        if source is PriceSource.HLC3:
            return (self.high + self.low + self.close) / 3
        if source is PriceSource.OHLC4:
            return (self.open + self.high + self.low + self.close) / 4
        raise ValueError(f"Unknown price source: {source!r}")  # pragma: no cover


__all__ = ["Candle", "PriceSource"]

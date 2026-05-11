"""Pydantic v2 schemas for the indicator service.

Request shape uses a **discriminated union** on the ``params.indicator``
field — clients send a flat object whose discriminator value picks the
correct per-indicator params schema. OpenAPI renders this as a clean
``oneOf`` so frontend codegen stays narrow.

Response shape is a uniform ``series: dict[str, list[float | None]]``
indexed by output name. Single-output indicators (SMA, EMA, RSI) use
``{"value": [...]}``; multi-output indicators use named keys:

    * MACD → ``macd``, ``signal``, ``histogram``
    * BB   → ``upper``, ``middle``, ``lower``

NaN values in the underlying TA-Lib output are converted to ``None`` at
the service boundary — Pydantic v2 strict mode rejects ``float('nan')``
in JSON output, and ``None`` round-trips cleanly through every JSON
deserialiser the frontend may use.

All datetimes are timezone-aware (UTC). All schemas are frozen + strict
+ ``extra="forbid"`` per chart-module convention.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.broker import Exchange
from app.schemas.candle import Timeframe


# ═══════════════════════════════════════════════════════════════════════
# IndicatorName enum — the discriminator value
# ═══════════════════════════════════════════════════════════════════════


class IndicatorName(StrEnum):
    """Day-6-scoped indicators. Phase 2 will extend this enum."""

    SMA = "sma"
    EMA = "ema"
    RSI = "rsi"
    MACD = "macd"
    BB = "bb"


# ═══════════════════════════════════════════════════════════════════════
# Per-indicator parameter schemas
# ═══════════════════════════════════════════════════════════════════════
#
# Each declares ``indicator: Literal[...]`` as its first field so the
# discriminated union can route by it. ``ge`` / ``le`` bounds catch
# pathological inputs (length 0, length 10_000) at the API boundary
# before any TA-Lib call.


_LENGTH_MIN = 1
_LENGTH_MAX = 500


class _ParamsBase(BaseModel):
    """Shared config for every per-indicator params schema."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")


class SmaParams(_ParamsBase):
    """Simple Moving Average parameters."""

    indicator: Literal[IndicatorName.SMA] = IndicatorName.SMA
    length: int = Field(
        default=20, ge=_LENGTH_MIN, le=_LENGTH_MAX,
        description="Window size in bars (e.g. 20 for 20-period SMA).",
    )


class EmaParams(_ParamsBase):
    """Exponential Moving Average parameters."""

    indicator: Literal[IndicatorName.EMA] = IndicatorName.EMA
    length: int = Field(
        default=20, ge=_LENGTH_MIN, le=_LENGTH_MAX,
        description="Window size in bars.",
    )


class RsiParams(_ParamsBase):
    """Relative Strength Index parameters.

    TA-Lib's RSI uses Wilder's smoothing, which matches TradingView's
    default ``ta.rsi(close, length)`` Pine Script behaviour.
    """

    indicator: Literal[IndicatorName.RSI] = IndicatorName.RSI
    length: int = Field(default=14, ge=2, le=_LENGTH_MAX)


class MacdParams(_ParamsBase):
    """Moving Average Convergence Divergence parameters.

    Three EMAs: ``fast`` and ``slow`` build the MACD line, then
    ``signal`` smooths the MACD line itself.
    """

    indicator: Literal[IndicatorName.MACD] = IndicatorName.MACD
    fast_length: int = Field(default=12, ge=_LENGTH_MIN, le=_LENGTH_MAX)
    slow_length: int = Field(default=26, ge=_LENGTH_MIN, le=_LENGTH_MAX)
    signal_length: int = Field(default=9, ge=_LENGTH_MIN, le=_LENGTH_MAX)

    @model_validator(mode="after")
    def _fast_lt_slow(self) -> MacdParams:
        if self.fast_length >= self.slow_length:
            raise ValueError(
                f"fast_length ({self.fast_length}) must be < "
                f"slow_length ({self.slow_length})."
            )
        return self


class BbParams(_ParamsBase):
    """Bollinger Bands parameters.

    .. note::
        TA-Lib computes the band's standard deviation using the
        **biased** (population) formula — divides by N. TradingView's
        Pine ``ta.stdev(src, length)`` uses **sample** stddev — divides
        by N-1. For length=20 the bands differ by a factor of
        ``sqrt(20/19) ≈ 1.026``. This deviation is **flagged**, not
        fixed, per the locked architecture (TA-Lib defaults are
        industry-standard; deviations are documented).
    """

    indicator: Literal[IndicatorName.BB] = IndicatorName.BB
    length: int = Field(default=20, ge=_LENGTH_MIN, le=_LENGTH_MAX)
    stddev_multiplier: float = Field(
        default=2.0, gt=0.0, le=10.0,
        description="Number of standard deviations for the upper/lower bands.",
    )


#: Discriminated-union alias for OpenAPI clarity. Pydantic resolves the
#: concrete subclass via the ``indicator`` literal.
IndicatorParams = Annotated[
    SmaParams | EmaParams | RsiParams | MacdParams | BbParams,
    Discriminator("indicator"),
]


# ═══════════════════════════════════════════════════════════════════════
# Request
# ═══════════════════════════════════════════════════════════════════════


class IndicatorRequest(BaseModel):
    """Body of ``POST /api/chart/indicator``.

    ``strict=True`` is intentionally OFF on this schema — FastAPI's
    body parsing receives the request as a dict-decoded-from-JSON,
    and strict mode would reject the string→Enum and ISO-string→
    datetime coercions that happen at the wire boundary. Validation
    is still tight (``extra="forbid"``, frozen, all field bounds
    enforced, custom validators run).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=64)
    exchange: Exchange = Field(...)
    timeframe: Timeframe = Field(...)
    params: IndicatorParams = Field(...)
    from_ts: datetime = Field(..., description="Window start (UTC).")
    to_ts: datetime = Field(..., description="Window end (UTC).")

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("from_ts", "to_ts")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("from_ts and to_ts must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def _window_ordered(self) -> IndicatorRequest:
        if self.from_ts > self.to_ts:
            raise ValueError(
                f"from_ts ({self.from_ts.isoformat()}) must be ≤ "
                f"to_ts ({self.to_ts.isoformat()})."
            )
        return self


# ═══════════════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════════════


class IndicatorResponse(BaseModel):
    """Body of ``POST /api/chart/indicator`` response.

    Layout:
        * ``candle_timestamps`` — list of UTC datetimes, one per CLOSED
          candle in the requested range. The in-progress bar is
          deliberately excluded per the closed-candle-only rule (R1).
        * ``series`` — dict keyed by output name (``value`` for
          single-output indicators, ``macd``/``signal``/``histogram``
          for MACD, ``upper``/``middle``/``lower`` for BB) → list of
          float-or-None values, **parallel** to ``candle_timestamps``.
        * ``last_closed_candle_ts`` — the timestamp of the most recent
          closed bar; also the cache-key suffix.
        * ``cached`` — True when the response came from the 5-min
          Redis cache (set by the service on hit; serialised back as
          False on miss).
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=64)
    timeframe: Timeframe = Field(...)
    indicator: IndicatorName = Field(...)
    from_ts: datetime = Field(...)
    to_ts: datetime = Field(...)
    last_closed_candle_ts: datetime | None = Field(
        default=None,
        description=(
            "Timestamp of the most recent closed bar in the window. "
            "``None`` if no closed bars exist in range (empty response)."
        ),
    )
    candle_timestamps: list[datetime] = Field(default_factory=list)
    series: dict[str, list[float | None]] = Field(default_factory=dict)
    cached: bool = Field(default=False)

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "from_ts", "to_ts", "last_closed_candle_ts"
    )
    @classmethod
    def _tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def _series_aligned(self) -> IndicatorResponse:
        """Every series array must have the same length as
        ``candle_timestamps`` — alignment is the entire promise of
        this response shape."""
        n = len(self.candle_timestamps)
        for name, values in self.series.items():
            if len(values) != n:
                raise ValueError(
                    f"series[{name!r}] length {len(values)} != "
                    f"candle_timestamps length {n}."
                )
        return self


__all__ = [
    "BbParams",
    "EmaParams",
    "IndicatorName",
    "IndicatorParams",
    "IndicatorRequest",
    "IndicatorResponse",
    "MacdParams",
    "RsiParams",
    "SmaParams",
]

"""Boundary models for the Dhan historical-data adapter.

Both models are frozen + ``extra="forbid"`` so a fetched response,
once returned, flows through the rest of the engine (backtest
endpoint, future caching layer, audit) as an immutable snapshot.

``HistoricalDataRequest`` runs the public symbol/timeframe/date
validation. The fetcher consumes the validated request directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.strategy_engine.data_provider.constants import (
    DAILY_TIMEFRAME,
    INTRADAY_MAX_DAYS_PER_REQUEST,
)
from app.strategy_engine.schema.ohlcv import Candle

Timeframe = Literal["1m", "5m", "15m", "1h", "1d"]


class HistoricalDataRequest(BaseModel):
    """Public request shape for :func:`fetch_historical_candles`.

    ``symbol`` is the user-friendly handle (e.g. ``"NIFTY"``,
    ``"RELIANCE"``). The fetcher resolves it through the bundled
    :data:`constants.KNOWN_SYMBOLS` map. Callers with their own scrip-
    master access can bypass the map by passing ``security_id``,
    ``exchange_segment``, and ``instrument`` directly.

    ``from_date`` and ``to_date`` are UTC-aware datetimes. The fetcher
    enforces ``from_date < to_date`` and the Dhan-imposed 90-day
    intraday window.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=64)
    timeframe: Timeframe
    from_date: datetime
    to_date: datetime

    # Optional overrides for callers that already know the Dhan
    # security id (e.g. the broker's scrip master).
    security_id: str | None = Field(default=None, min_length=1, max_length=32)
    exchange_segment: str | None = Field(default=None, min_length=1, max_length=32)
    instrument: str | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def _check_dates(self) -> HistoricalDataRequest:
        if self.from_date >= self.to_date:
            raise ValueError(
                f"from_date ({self.from_date.isoformat()}) must be strictly "
                f"earlier than to_date ({self.to_date.isoformat()})."
            )
        if self.timeframe != DAILY_TIMEFRAME:
            span_days = (self.to_date - self.from_date).total_seconds() / 86400.0
            if span_days > INTRADAY_MAX_DAYS_PER_REQUEST:
                raise ValueError(
                    f"Intraday requests can span at most "
                    f"{INTRADAY_MAX_DAYS_PER_REQUEST} days; got "
                    f"{span_days:.1f} days."
                )
        return self


class HistoricalDataResponse(BaseModel):
    """Result envelope for :func:`fetch_historical_candles`.

    ``cache_hit`` is ``True`` when the response was served from the
    on-disk cache without a live HTTP call. ``quality_warnings``
    aggregates short Phase 11 issue messages so the caller can
    surface them to the UI without re-running validation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    candles: list[Candle]
    request: HistoricalDataRequest
    fetched_at: datetime
    cache_hit: bool
    quality_warnings: list[str] = Field(default_factory=list)


class DhanFetchError(RuntimeError):
    """Raised when the Dhan API call exhausts retries or returns a
    non-recoverable error. Carries the HTTP status code (when
    available) and the parsed ``errorMessage`` so the caller can
    surface it directly."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        original_error: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.original_error = original_error


__all__ = [
    "DhanFetchError",
    "HistoricalDataRequest",
    "HistoricalDataResponse",
    "Timeframe",
]

"""Dhan historical-data adapter — Phase A+B foundation.

Replaces the synthetic 120-bar candle stream the backtest endpoint
falls back to with real OHLCV pulled from Dhan's historical-data
API. Phase A is the discovery write-up
(``DHAN_API_NOTES.md``) — read it before extending. Phase B is this
adapter: a self-contained module with file-based caching, mockable
HTTP, and Phase 11 quality validation on every response.

Phase C / D / E (endpoint integration, frontend wiring, integration
tests) ride on top of this surface in later sessions.

Public boundary::

    fetch_historical_candles / clear_cache /
    HistoricalDataRequest / HistoricalDataResponse / DhanFetchError
"""

from __future__ import annotations

from app.strategy_engine.data_provider.fetcher import (
    clear_cache,
    fetch_historical_candles,
    normalise_symbol,
)
from app.strategy_engine.data_provider.models import (
    DhanFetchError,
    HistoricalDataRequest,
    HistoricalDataResponse,
    Timeframe,
)

__all__ = [
    "DhanFetchError",
    "HistoricalDataRequest",
    "HistoricalDataResponse",
    "Timeframe",
    "clear_cache",
    "fetch_historical_candles",
    "normalise_symbol",
]

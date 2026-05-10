"""Locked constants for the Dhan historical-data adapter.

Single tunable knobs for endpoint URLs, rate-limit handling, cache
behaviour, and the bundled symbol resolution map. Keep this module
dependency-free.
"""

from __future__ import annotations

from typing import Final

# ─── Endpoints ─────────────────────────────────────────────────────────

DHAN_API_BASE_URL: Final[str] = "https://api.dhan.co/v2"
"""Base URL for Dhan API v2 (matches ``settings.dhan_api_base_url``
default in :mod:`app.core.config`). Tests override via dependency
injection rather than mutating this constant."""

DHAN_HISTORICAL_DAILY_PATH: Final[str] = "/charts/historical"
DHAN_HISTORICAL_INTRADAY_PATH: Final[str] = "/charts/intraday"

# ─── Rate-limit + retry ────────────────────────────────────────────────

DHAN_RATE_LIMIT_PER_SECOND: Final[int] = 5
"""Per the Dhan support article — data APIs allow 5 requests/sec.
Hitting it produces a 429 response, optionally with a ``Retry-After``
header."""

DHAN_RATE_LIMIT_PER_DAY: Final[int] = 100_000
"""Headline daily cap. Documented for context; the adapter does not
enforce a daily quota."""

MAX_RETRY_ATTEMPTS: Final[int] = 3
INITIAL_BACKOFF_SECONDS: Final[float] = 2.0
"""On 429 / 5xx the fetcher waits ``INITIAL_BACKOFF_SECONDS *
(2 ** attempt)`` before retrying, capped at :data:`MAX_RETRY_ATTEMPTS`
total attempts. When Dhan returns a ``Retry-After`` header it is used
directly instead of the exponential schedule."""

# ─── Cache ─────────────────────────────────────────────────────────────

CACHE_DIR_NAME: Final[str] = "tradetri_dhan_cache"
"""Cache directory name — created under ``/tmp`` when writable,
otherwise under ``~/.cache``. Phase B only cares about pickle-safe
JSON, so the cache is a flat directory of ``*.json`` files."""

CACHE_TTL_RECENT_HOURS: Final[int] = 1
"""TTL for data whose ``to_date`` is within the last 7 days. Recent
bars are still in flux (last bar of an active session can change), so
a short TTL prevents stale reads."""

CACHE_TTL_HISTORICAL_HOURS: Final[int] = 24
"""TTL for data whose ``to_date`` is older than 7 days. Older bars are
immutable, so a 24-hour TTL keeps cache pressure low while letting a
data fix on the Dhan side propagate within a day."""

RECENT_DATA_THRESHOLD_DAYS: Final[int] = 7
"""Cut-off used to pick between :data:`CACHE_TTL_RECENT_HOURS` and
:data:`CACHE_TTL_HISTORICAL_HOURS`."""

# ─── Constraint floors ────────────────────────────────────────────────

INTRADAY_MAX_DAYS_PER_REQUEST: Final[int] = 90
"""Dhan refuses intraday requests spanning more than 90 days. Phase B
rejects them client-side rather than waiting for the server's 4xx."""

QUALITY_SCORE_WARN_THRESHOLD: Final[float] = 40.0
"""Below this Phase 11 quality score the fetcher logs a warning. The
data is still returned — the caller decides whether to proceed."""

# ─── Timeframe map (public string → endpoint + interval) ──────────────

# Phase B exposes ``Literal["1m","5m","15m","1h","1d"]``. Dhan's
# intraday endpoint accepts the integer minute counts ``1, 5, 15, 25,
# 60``; we omit ``25m`` from the public surface.
TIMEFRAME_TO_INTERVAL_MINUTES: Final[dict[str, int]] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
}

DAILY_TIMEFRAME: Final[str] = "1d"

# ─── Symbol resolution ────────────────────────────────────────────────

# Alias map applied *before* :data:`KNOWN_SYMBOLS` lookup. Whitespace
# is collapsed and the result upper-cased before matching.
SYMBOL_ALIASES: Final[dict[str, str]] = {
    "NIFTY 50": "NIFTY",
    "NIFTY50": "NIFTY",
    "BANK NIFTY": "BANKNIFTY",
    "BANKNIFTY 50": "BANKNIFTY",
    "FIN NIFTY": "FINNIFTY",
}


class _SymbolMeta:
    """Internal record. Bundled so a future edit can extend the map
    without drifting the surface schema."""

    __slots__ = ("exchange_segment", "instrument", "security_id")

    def __init__(self, security_id: str, exchange_segment: str, instrument: str) -> None:
        self.security_id = security_id
        self.exchange_segment = exchange_segment
        self.instrument = instrument


KNOWN_SYMBOLS: Final[dict[str, _SymbolMeta]] = {
    # Index spot — Dhan's IDX_I segment with INDEX instrument type.
    # Security ids are the canonical NSE numeric ids (NIFTY=13,
    # BANKNIFTY=25, FINNIFTY=27 per the broker scrip master).
    "NIFTY": _SymbolMeta("13", "IDX_I", "INDEX"),
    "BANKNIFTY": _SymbolMeta("25", "IDX_I", "INDEX"),
    "FINNIFTY": _SymbolMeta("27", "IDX_I", "INDEX"),
    # Cash equity — security ids match NSE's listing.
    "RELIANCE": _SymbolMeta("2885", "NSE_EQ", "EQUITY"),
    "TCS": _SymbolMeta("11536", "NSE_EQ", "EQUITY"),
    "INFY": _SymbolMeta("1594", "NSE_EQ", "EQUITY"),
}


__all__ = [
    "CACHE_DIR_NAME",
    "CACHE_TTL_HISTORICAL_HOURS",
    "CACHE_TTL_RECENT_HOURS",
    "DAILY_TIMEFRAME",
    "DHAN_API_BASE_URL",
    "DHAN_HISTORICAL_DAILY_PATH",
    "DHAN_HISTORICAL_INTRADAY_PATH",
    "DHAN_RATE_LIMIT_PER_DAY",
    "DHAN_RATE_LIMIT_PER_SECOND",
    "INITIAL_BACKOFF_SECONDS",
    "INTRADAY_MAX_DAYS_PER_REQUEST",
    "KNOWN_SYMBOLS",
    "MAX_RETRY_ATTEMPTS",
    "QUALITY_SCORE_WARN_THRESHOLD",
    "RECENT_DATA_THRESHOLD_DAYS",
    "SYMBOL_ALIASES",
    "TIMEFRAME_TO_INTERVAL_MINUTES",
]

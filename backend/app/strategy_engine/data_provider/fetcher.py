"""Public orchestrator for the Dhan historical-data adapter.

Sequence:

    request → symbol resolution → cache check → HTTP fetch (mockable)
                                              → Dhan column parse
                                              → Phase 11 quality check
                                              → cache write
                                              → frozen response

The HTTP layer lives in :mod:`dhan_client`; the disk cache lives in
:mod:`cache`. This module only orchestrates and applies symbol-
resolution / quality-check business rules.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.strategy_engine.data_provider import cache as cache_mod
from app.strategy_engine.data_provider.constants import (
    DHAN_API_BASE_URL,
    KNOWN_SYMBOLS,
    QUALITY_SCORE_WARN_THRESHOLD,
    SYMBOL_ALIASES,
    TIMEFRAME_TO_INTERVAL_MINUTES,
)
from app.strategy_engine.data_provider.dhan_client import (
    HttpPost,
    SleepFn,
    fetch_from_dhan,
    parse_candles,
)
from app.strategy_engine.data_provider.models import (
    DhanFetchError,
    HistoricalDataRequest,
    HistoricalDataResponse,
)

logger = get_logger("app.strategy_engine.data_provider")

AccessTokenProvider = Callable[[], str]


def fetch_historical_candles(
    request: HistoricalDataRequest,
    use_cache: bool = True,
    *,
    access_token: str | None = None,
    base_url: str = DHAN_API_BASE_URL,
    http_post: HttpPost = httpx.post,
    sleep_fn: SleepFn = time.sleep,
    now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> HistoricalDataResponse:
    """Fetch candles for ``request`` from Dhan (with caching).

    Args:
        request: Validated :class:`HistoricalDataRequest`.
        use_cache: When ``True`` (default), consult the file cache
            first and write the response back on a fresh fetch.
        access_token: Override for the Dhan access token. Defaults to
            ``settings.dhan_access_token`` if defined; tests should
            always pass an explicit value.
        base_url / http_post / sleep_fn / now_fn: Test injection
            seams. Production code uses the defaults.

    Returns:
        :class:`HistoricalDataResponse` with the parsed candle list,
        the original request, the fetch timestamp, the cache-hit
        flag, and any Phase 11 quality warnings.
    """
    security_id, exchange_segment, instrument = _resolve_symbol(request)

    if use_cache:
        cached = cache_mod.cache_get(
            symbol=request.symbol,
            timeframe=request.timeframe,
            from_date=request.from_date,
            to_date=request.to_date,
        )
        if cached is not None:
            try:
                candles = parse_candles(cached)
            except DhanFetchError:
                # Corrupt cache entry — fall through to a live fetch.
                cached = None
            else:
                quality_warnings = _quality_warnings(candles, request.timeframe)
                return HistoricalDataResponse(
                    candles=candles,
                    request=request,
                    fetched_at=now_fn(),
                    cache_hit=True,
                    quality_warnings=quality_warnings,
                )

    token = access_token if access_token is not None else _resolve_access_token()
    raw = fetch_from_dhan(
        request,
        access_token=token,
        security_id=security_id,
        exchange_segment=exchange_segment,
        instrument=instrument,
        base_url=base_url,
        http_post=http_post,
        sleep_fn=sleep_fn,
    )
    candles = parse_candles(raw)
    quality_warnings = _quality_warnings(candles, request.timeframe)

    if use_cache:
        cache_mod.cache_put(
            symbol=request.symbol,
            timeframe=request.timeframe,
            from_date=request.from_date,
            to_date=request.to_date,
            payload=raw,
        )

    return HistoricalDataResponse(
        candles=candles,
        request=request,
        fetched_at=now_fn(),
        cache_hit=False,
        quality_warnings=quality_warnings,
    )


def clear_cache() -> None:
    """Empty the on-disk cache. Intended for tests only."""
    cache_mod.clear()


# ─── Symbol resolution ────────────────────────────────────────────────


def normalise_symbol(symbol: str) -> str:
    """Trim, collapse whitespace, upper-case, then apply alias map.

    Public for tests so they can pin the normalisation contract
    without round-tripping through the full fetcher.

    Whitespace policy (changed in Step 1/5 v2):
        * Outer whitespace is always trimmed.
        * Internal whitespace is collapsed to a single space.
        * Internal whitespace is *preserved* on alias miss — the
          previous policy of stripping it (e.g. ``"NIFTY NEXT 50"`` →
          ``"NIFTYNEXT50"``) broke resolution for the new canonical
          spaced keys Dhan ships in its scrip master (``NIFTY NEXT
          50``, etc.). Symbols that need the joined form continue to
          work because the alias map covers the common cases
          (``"BANK NIFTY"`` → ``"BANKNIFTY"`` etc.).
    """
    collapsed = re.sub(r"\s+", " ", symbol.strip()).upper()
    return SYMBOL_ALIASES.get(collapsed, collapsed)


def _resolve_symbol(request: HistoricalDataRequest) -> tuple[str, str, str]:
    """Return ``(security_id, exchange_segment, instrument)``.

    Priority:
        1. Explicit overrides on the request.
        2. Bundled :data:`KNOWN_SYMBOLS` lookup (after normalisation).

    Raises:
        ValueError: when the symbol is not in the bundled map and the
            caller did not pass overrides.
    """
    if (
        request.security_id is not None
        and request.exchange_segment is not None
        and request.instrument is not None
    ):
        return (
            request.security_id,
            request.exchange_segment,
            request.instrument,
        )

    canonical = normalise_symbol(request.symbol)
    meta = KNOWN_SYMBOLS.get(canonical)
    if meta is None:
        raise ValueError(
            f"Symbol {request.symbol!r} (normalised to {canonical!r}) is not in "
            "the bundled KNOWN_SYMBOLS map. Pass security_id, "
            "exchange_segment, and instrument explicitly to bypass."
        )
    return meta.security_id, meta.exchange_segment, meta.instrument


def _resolve_access_token() -> str:
    """Default access-token source: ``settings.dhan_access_token``.

    Falls back to an empty string when the field doesn't exist on
    the settings object — tests should always pass ``access_token``
    explicitly so this branch never fires in production-equivalent
    code paths.
    """
    settings = get_settings()
    token: Any = getattr(settings, "dhan_access_token", None)
    return str(token) if token else ""


# ─── Quality-check integration ────────────────────────────────────────


def _quality_warnings(candles: list[Any], timeframe: str) -> list[str]:
    """Run Phase 11 :func:`validate_candles` and return short messages.

    Logs a warning when ``quality_score`` falls below
    :data:`QUALITY_SCORE_WARN_THRESHOLD`. Always returns the list of
    issue messages (empty when the stream is clean) so the caller
    can render them in the UI without re-running validation.
    """
    if not candles:
        return ["Empty candle stream returned by Dhan."]

    # Local import so the data-quality module is only loaded when
    # the fetcher is actually used (cheap to import, but keeps the
    # constants module dependency-light).
    from app.strategy_engine.data_quality import validate_candles

    minutes = TIMEFRAME_TO_INTERVAL_MINUTES.get(
        timeframe,
        # Daily — pass a large interval so the gap check tolerates
        # weekend gaps without flagging them as missing.
        24 * 60,
    )
    report = validate_candles(candles, expected_timeframe_minutes=minutes)
    if report.quality_score < QUALITY_SCORE_WARN_THRESHOLD:
        logger.warning(
            "data_provider.quality_below_threshold",
            quality_score=report.quality_score,
            issue_count=len(report.issues),
            threshold=QUALITY_SCORE_WARN_THRESHOLD,
        )
    return [issue.message for issue in report.issues]


__all__ = [
    "clear_cache",
    "fetch_historical_candles",
    "normalise_symbol",
]

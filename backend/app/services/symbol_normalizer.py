"""Symbol normalizer — stable underlying + expiry preference → Dhan contract.

Pine alerts now send a STABLE underlying (``"BSE"``) plus ``instrument_type``
and ``expiry_preference`` instead of a hard-coded monthly contract symbol
(``"BSE-MAY2026-FUT"``) that breaks at every expiry rollover. This module
resolves the underlying to the current (or next) month's Dhan futures trading
symbol via the **public** scrip master — no broker credential is required, the
CSV is a public download.

Caching: a process-wide :class:`app.brokers.dhan._ScripMaster` instance with a
24 h TTL (in-memory). A Redis-shared cache across workers is a future
optimization; in-memory is the documented fallback and is correct — each
worker downloads the CSV at most once per day.

Rollover: contracts are filtered to ``expiry_date >= today`` and sorted
ascending, so ``current_month`` resolves to the nearest *non-expired*
contract (if this calendar month's contract already expired, that is the next
month — the rollover is automatic) and ``next_month`` to the second-nearest.

Options resolution is Phase 3 — ``instrument_type="options"`` raises
``NotImplementedError`` for now.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.brokers.dhan import _EXCHANGE_TO_DHAN_SEGMENT, _ScripMaster
from app.core.exceptions import BrokerInvalidSymbolError
from app.core.logging import get_logger
from app.schemas.broker import Exchange

logger = get_logger("services.symbol_normalizer")

#: Public Dhan scrip-master CSV (no auth). Mirrors the URL the Dhan adapter
#: downloads from; kept local so the normalizer needs no broker instance.
_SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"

ExpiryPreference = Literal["current_month", "next_month"]

#: Process-wide scrip-master cache (in-memory, 24h TTL inside _ScripMaster).
_scrip = _ScripMaster()


async def _ensure_scrip_loaded() -> None:
    """Lazily download + parse the public scrip master (cached 24h)."""
    if _scrip.is_loaded():
        return
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as http:
        await _scrip.ensure_loaded(http, _SCRIP_MASTER_URL)


def _segment_for(exchange: str | Exchange) -> str:
    """Map an Exchange (or its string) to the Dhan exchange_segment."""
    if isinstance(exchange, Exchange):
        seg = _EXCHANGE_TO_DHAN_SEGMENT.get(exchange)
    else:
        try:
            seg = _EXCHANGE_TO_DHAN_SEGMENT.get(Exchange(exchange.upper()))
        except ValueError:
            seg = None
    if seg is None:
        raise BrokerInvalidSymbolError(
            f"Unsupported exchange {exchange!r} for symbol normalization.",
            broker_name="dhan",
        )
    return seg


async def resolve_futures_symbol(
    underlying: str,
    expiry_preference: ExpiryPreference = "current_month",
    exchange: str | Exchange = Exchange.NFO,
) -> dict[str, Any]:
    """Resolve ``underlying`` → the Dhan futures contract for the requested
    month.

    Returns ``{dhan_symbol, security_id, lot_size, expiry_date}``.

    Raises:
        BrokerInvalidSymbolError: unknown underlying / no live contract /
            unsupported exchange.
    """
    await _ensure_scrip_loaded()
    segment = _segment_for(exchange)
    contracts = _scrip.futures_for_underlying(underlying, segment)
    today = datetime.now(UTC).date()
    live = [c for c in contracts if c.expiry_date and c.expiry_date >= today]
    if not live:
        raise BrokerInvalidSymbolError(
            f"No live futures contract for underlying {underlying!r} in "
            f"{segment} (matched {len(contracts)} total, 0 non-expired). "
            "Check the underlying ticker and that the scrip master is current.",
            broker_name="dhan",
        )
    idx = 0 if expiry_preference == "current_month" else 1
    if idx >= len(live):
        # next_month requested but only the front month is listed → fall back
        # to the furthest available contract rather than failing.
        idx = len(live) - 1
    chosen = live[idx]
    logger.info(
        "symbol_normalizer.resolved",
        underlying=underlying,
        expiry_preference=expiry_preference,
        dhan_symbol=chosen.symbol,
        security_id=chosen.security_id,
        expiry_date=str(chosen.expiry_date),
    )
    return {
        "dhan_symbol": chosen.symbol,
        "security_id": chosen.security_id,
        "lot_size": chosen.lot_size,
        "expiry_date": chosen.expiry_date,
    }


async def resolve_symbol(
    underlying: str,
    instrument_type: str,
    expiry_preference: ExpiryPreference = "current_month",
    exchange: str | Exchange = Exchange.NFO,
) -> dict[str, Any]:
    """Dispatch on ``instrument_type``. Futures resolve now; options later."""
    kind = (instrument_type or "").lower()
    if kind == "futures":
        return await resolve_futures_symbol(underlying, expiry_preference, exchange)
    if kind == "options":
        raise NotImplementedError(
            "Options symbol resolution is Phase 3 work — not yet implemented."
        )
    raise BrokerInvalidSymbolError(
        f"Unknown instrument_type {instrument_type!r} (expected 'futures' or 'options').",
        broker_name="dhan",
    )


__all__ = ["resolve_futures_symbol", "resolve_symbol"]

"""The protective stops that live at the BROKER, not in our database.

WHY THIS EXISTS (2026-09-09)
────────────────────────────
``/positions`` printed "—" in the SL column for a live short 200 while Dhan
was holding a real resting stop on it (Forever order ``23132609081456``,
trigger 3354.85, ``STOP_LOSS_LEG``, status PENDING). The founder's words:
**an invisible stop reads as no stop.** A trader looking at that screen sees
an unprotected position and may act on it — the most dangerous kind of wrong.

The column was honest about the DATABASE and silent about reality.
``strategy_positions.stop_loss_price`` is NULL for these rows because
``pine_replica`` owns the trailing stop: it places and re-places a Forever
(GTT) order directly at Dhan on every trail step and never tells the platform.
So the fact exists — it is simply held in a system this one never asked.

WHAT THIS DOES
──────────────
Reads the broker's resting stop orders and caches them in Redis. The
reconciliation loop already builds a broker client and polls every 60s, so it
does the read (best-effort, never allowed to affect reconciliation) and the
positions API serves whatever the cache holds. No broker call is made on a
page request.

DELIBERATELY NOT DONE — ``app/brokers/dhan.py`` IS NOT TOUCHED. It is a sacred
file (CLAUDE.md: broker adapters are not modified without an explicit
live-money authorisation), and a display feature is nowhere near a good enough
reason. We reach the endpoint through the adapter's own authenticated
``_call``, so no credential handling, retry or logging is duplicated here. The
underscore is deliberate and the trade is conscious: reusing one private
read-only method beats either copying the auth path or editing the adapter.

READ-ONLY, ALWAYS. Nothing in this module places, modifies or cancels an
order. The only endpoint it knows is a GET.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.core import redis_client
from app.core.logging import get_logger

_logger = get_logger("services.broker_resting_stops")

#: Slightly longer than the 60s reconciliation tick, so a single failed poll
#: does not blank the column. Long enough to survive a blip, short enough that
#: a cancelled stop stops being advertised quickly.
_TTL_SECONDS = 300

#: Dhan's GTT/"Forever" order book. GET only.
_FOREVER_PATH = "/forever/orders"

#: The leg that is actually a stop. A Forever order can also carry a target
#: leg; advertising that as protection would be worse than showing nothing.
_STOP_LEG = "STOP_LOSS_LEG"

#: Statuses that mean the order is still WAITING at the exchange. A TRADED or
#: CANCELLED stop protects nothing and must never be shown as if it did.
_RESTING_STATUSES = frozenset({"PENDING", "ACTIVE", "TRIGGERED", "CONFIRMED"})


def _key(user_id: UUID | str) -> str:
    return f"broker:resting_stops:{user_id}"


def _decimal(value: Any) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d > 0 else None


def parse_resting_stops(rows: Any) -> dict[str, dict[str, Any]]:
    """Broker rows → ``{NORMALISED SYMBOL: {price, order_id, quantity}}``.

    Symbols are upper-cased for the same reason the reconciliation diff
    normalises them: we store ``BSE-SEP2026-FUT`` and Dhan answers
    ``BSE-Sep2026-FUT``, and a lookup that misses is indistinguishable from
    a position with no stop.

    A row is kept only when it is a resting STOP leg with a usable trigger
    price. Everything else is dropped rather than guessed at.
    """
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("legName") or "").upper() != _STOP_LEG:
            continue
        if str(row.get("orderStatus") or "").upper() not in _RESTING_STATUSES:
            continue
        symbol = str(row.get("tradingSymbol") or "").strip().upper()
        price = _decimal(row.get("triggerPrice"))
        if not symbol or price is None:
            continue
        try:
            quantity = int(row.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0
        out[symbol] = {
            "price": str(price),
            "order_id": str(row.get("orderId") or ""),
            "quantity": quantity,
        }
    return out


async def refresh_for_user(broker: Any, user_id: UUID | str) -> int:
    """Poll the broker's resting stops and cache them. Returns how many.

    BEST EFFORT BY CONTRACT. Every failure is swallowed and logged: this runs
    inside the reconciliation loop, and a display feature must never be able
    to interfere with drift detection. On failure the previous cache entry is
    left alone to age out rather than being cleared — a stale-but-recent stop
    is better than falsely showing none.
    """
    if not hasattr(broker, "_call"):
        return 0
    try:
        result = await broker._call("resting_stops", "GET", _FOREVER_PATH)
    except Exception as exc:  # noqa: BLE001 — never break the caller.
        _logger.warning(
            "resting_stops.fetch_failed", user_id=str(user_id), error=str(exc)
        )
        return 0

    rows = result if isinstance(result, list) else (result or {}).get("data", [])
    stops = parse_resting_stops(rows)
    try:
        await redis_client.cache_set_json(_key(user_id), stops, _TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "resting_stops.cache_failed", user_id=str(user_id), error=str(exc)
        )
        return 0
    _logger.info(
        "resting_stops.cached", user_id=str(user_id), count=len(stops)
    )
    return len(stops)


async def get_for_user(user_id: UUID | str) -> dict[str, dict[str, Any]]:
    """Cached resting stops for this user, or ``{}`` when we have not read.

    ``{}`` means UNKNOWN, not "no stop". Callers must render the difference:
    a position with no cached entry gets the same "—" it has today, never a
    claim that it is unprotected.
    """
    try:
        cached = await redis_client.cache_get_json(_key(user_id))
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "resting_stops.read_failed", user_id=str(user_id), error=str(exc)
        )
        return {}
    return cached if isinstance(cached, dict) else {}


__all__ = ["get_for_user", "parse_resting_stops", "refresh_for_user"]

"""Reverse-phantom guard for orders that don't reach a terminal state.

When ``DhanBroker.confirm_fill`` times out (order still PENDING/TRANSIT after the
poll window), the order MAY fill *after* we've given up — producing a real
broker position with no local state (the *reverse* of the phantom we already
guard against on the create side). The entry/exit paths still raise / leave the
position open (so no half-state row is written), but that alone is silent: the
late fill would only surface as a ``broker_only`` drift in the 60-second
reconciliation loop, whose Telegram is gated OFF by default.

This module makes the timeout LOUD and reconcilable:

  * :func:`flag_ambiguous_fill` — write a short-TTL redis marker keyed by symbol
    and fire a distinct CRITICAL alert (NOT a generic "rejected").
  * :func:`is_flagged` / :func:`clear_flag` — let the reconciliation loop detect
    a ``broker_only`` position that corresponds to a flagged ambiguous order and
    alert ALWAYS (bypassing the manual-position spam gate), then clear it.
"""

from __future__ import annotations

import contextlib

from app.core import redis_client
from app.core.logging import get_logger

_logger = get_logger("services.ambiguous_fill")

#: How long a flagged order is watched. A Dhan order that hasn't gone terminal
#: within ~15 min is settled/expired; the reconcile loop runs every 60 s so it
#: gets many chances to catch a late fill inside this window.
_TTL_S = 900


def _key(symbol: str) -> str:
    return f"ambiguous_fill:{symbol.upper()}"


async def flag_ambiguous_fill(
    *,
    broker_order_id: str,
    symbol: str,
    side: str,
    qty: int,
    context: str = "entry",
) -> None:
    """Record an ambiguous (non-terminal-at-timeout) order + alert loudly."""
    try:
        await redis_client.get_redis().set(_key(symbol), str(broker_order_id), ex=_TTL_S)
    except Exception:
        _logger.exception("ambiguous_fill.redis_write_failed", order_id=str(broker_order_id))
    try:
        from app.services import telegram_alerts as _alerts

        await _alerts.send_alert(
            _alerts.AlertLevel.CRITICAL,
            (
                "⚠️ *AMBIGUOUS FILL — reverse-phantom risk*\n"
                f"`{symbol}` {side} {qty} ({context})\n"
                f"order `{broker_order_id}` did NOT reach a terminal state in "
                "the confirm window.\n"
                "It MAY fill late → a REAL broker position with no local state.\n"
                "Reconciliation will re-check each tick; verify the Dhan "
                "orderbook/positions now."
            ),
        )
    except Exception:
        _logger.exception("ambiguous_fill.alert_failed", order_id=str(broker_order_id))


async def is_flagged(symbol: str) -> str | None:
    """Return the flagged order id for ``symbol`` (case-insensitive), else None."""
    try:
        return await redis_client.get_redis().get(_key(symbol))
    except Exception:
        return None


async def clear_flag(symbol: str) -> None:
    """Clear the watch once reconciliation has handled / confirmed it."""
    with contextlib.suppress(Exception):
        await redis_client.get_redis().delete(_key(symbol))


__all__ = ["clear_flag", "flag_ambiguous_fill", "is_flagged"]

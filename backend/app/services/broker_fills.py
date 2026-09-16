"""The fills that happened at the BROKER but never came through this platform.

WHY THIS EXISTS (2026-09-16)
────────────────────────────
The orders page (``/trades``) lists ``strategy_executions``, and a row lands in
that table only at the end of one chain: TradingView → our webhook →
``strategy_signals`` → broker order → execution rows. ``signal_id`` is
``NOT NULL`` with an FK, so an order born anywhere else **cannot** have a row.

Two real order sources on the founder's account are born elsewhere:

* **pine_replica's resting stops.** The engine places Forever/GTT orders
  straight at Dhan and re-places them on every trail step. When one fires it
  closes a real position — e.g. order ``312260908126806``, SELL 800 @3394.025
  on 2026-09-08 09:42 IST, which closed the 07-Sep BUY 800. It is the whole
  exit of a round trip and the orders page has never shown it.
* **the Dhan app.** Manual fills the founder takes by hand.

Six such fills exist on BSE-SEP2026-FUT in 2026-09-01…16 alone. The page was
not wrong about its own table — it was silent about the account, which on a
money surface reads the same way.

WHAT THIS DOES
──────────────
Reads Dhan's TRADE BOOK (history, not the day order book — the whole point is
fills from previous days) and caches it in Redis. The reconciliation loop
already builds a broker client and polls, so it does the read, best-effort,
and the orders API serves whatever the cache holds. **No broker call is made on
a page request.**

RATE LIMIT IS A FIRST-CLASS CONCERN. The live account's Dhan quota is shared
with the trading engine, so this is deliberately not a per-tick read: the
refresh is throttled to :data:`_REFRESH_EVERY_SECONDS` and skipped otherwise.
The reconciliation loop ticks every 60s; this adds roughly one paged trade-book
read every 15 minutes, not one per tick.

DELIBERATELY NOT DONE
─────────────────────
* ``app/brokers/dhan.py`` is NOT touched — a sacred file, and a display feature
  is nowhere near a good enough reason. We reach the endpoint through the
  adapter's own authenticated ``_call``, exactly as
  :mod:`app.services.broker_resting_stops` already does.
* Nothing is written to ``strategy_executions``. Inserting a synthesised row
  there would fabricate a platform order in the very log that gets reconciled
  against Dhan, and would need a ``signal_id`` that does not exist. These fills
  are served alongside that table, labelled, never merged into it.
* READ-ONLY, ALWAYS. The only endpoint this module knows is a GET.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from app.core import redis_client
from app.core.logging import get_logger

_logger = get_logger("services.broker_fills")

#: Long enough to survive a failed poll, short enough that a fill taken minutes
#: ago still reaches the page within one refresh cycle.
_TTL_SECONDS = 3600

#: How often the trade book is actually pulled, regardless of how often the
#: reconciliation loop ticks. See the rate-limit note in the module docstring.
_REFRESH_EVERY_SECONDS = 900

#: How far back the trade book is pulled. The record begins 2026-09-01 and a
#: customer looking at the orders page cares about the recent past, not the
#: archive; a wider window costs more pages on a shared quota.
_WINDOW_DAYS = 30

#: Dhan's historical trade book. GET only. ``/trades/{from}/{to}/{page}``.
_TRADES_PATH = "/trades/{start}/{end}/{page}"

#: Stop paging defensively — a runaway loop here burns the shared quota.
_MAX_PAGES = 20


def _key(user_id: UUID | str) -> str:
    return f"broker:fills:{user_id}"


def _stamp_key(user_id: UUID | str) -> str:
    return f"broker:fills:refreshed_at:{user_id}"


def classify_source(row: dict[str, Any]) -> str:
    """Who placed this order, from the broker's own metadata.

    The discriminator was verified against the raw order-update tape rather
    than assumed (three clean clusters, no cross-contamination):

    ====================  =========  ===================  ==================
    ``orderPlatform``     ``algoId`` ``correlationId``    meaning
    ====================  =========  ===================  ==================
    ``API``               ``99999``  ``strategy-engine*`` this platform
    ``FOVR``              ``0``      ``NR``               engine resting stop
    ``FAST``              ``0``      ``NA``               manual, Dhan app
    ====================  =========  ===================  ==================

    Anything that matches none of them is ``unknown`` — never forced into the
    nearest bucket, because mislabelling a manual fill as the bot's would put a
    human's trade into the bot's record.
    """
    platform = str(row.get("orderPlatform") or "").strip().upper()
    correlation = str(row.get("correlationId") or "").strip().upper()
    if platform == "API" or correlation.startswith("STRATEGY-ENGINE"):
        return "tradetri"
    if platform == "FOVR" or correlation == "NR":
        return "engine_stop"
    if platform == "FAST" or correlation == "NA":
        return "manual"
    return "unknown"


def parse_fills(rows: Any) -> list[dict[str, Any]]:
    """Trade-book rows → the minimal shape the orders page renders.

    Deliberately a small explicit projection, not the broker envelope: the
    trade book carries ``dhanClientId``, ``exchangeOrderId``, ``securityId``
    and the rest, and none of it belongs in a browser. Same discipline as
    ``owner_executions.broker_status_of``.

    A row with no usable order id, side or quantity is dropped rather than
    half-rendered.
    """
    out: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        order_id = str(row.get("orderId") or "").strip()
        side = str(row.get("transactionType") or "").strip().upper()
        if not order_id or side not in ("BUY", "SELL"):
            continue
        try:
            quantity = int(row.get("tradedQuantity") or 0)
        except (TypeError, ValueError):
            continue
        if quantity <= 0:
            continue
        price = row.get("tradedPrice")
        if price is None:
            price = row.get("averageTradedPrice")
        out.append(
            {
                "broker_order_id": order_id,
                "symbol": str(row.get("tradingSymbol") or "").strip().upper(),
                "side": side.lower(),
                "quantity": quantity,
                "price": None if price is None else str(price),
                "filled_at": str(row.get("exchangeTime") or "").strip() or None,
                "source": classify_source(row),
            }
        )
    return out


def _window(today: date | None = None) -> tuple[str, str]:
    end = today or datetime.now(UTC).date()
    start = end - timedelta(days=_WINDOW_DAYS)
    return start.isoformat(), end.isoformat()


async def _due_for_refresh(user_id: UUID | str) -> bool:
    """True when the throttle window has elapsed (or we have never read)."""
    try:
        stamp = await redis_client.cache_get_json(_stamp_key(user_id))
    except Exception:  # a cache miss must not block the read.
        return True
    if not isinstance(stamp, dict):
        return True
    raw = stamp.get("at")
    if not isinstance(raw, str):
        return True
    try:
        last = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return (datetime.now(UTC) - last).total_seconds() >= _REFRESH_EVERY_SECONDS


async def refresh_for_user(broker: Any, user_id: UUID | str, *, today: date | None = None) -> int:
    """Poll the broker's trade book and cache the fills. Returns how many.

    BEST EFFORT BY CONTRACT. Every failure is swallowed and logged: this runs
    inside the reconciliation loop, and a display feature must never be able to
    interfere with drift detection. On failure the previous cache entry is left
    alone to age out rather than being cleared — showing the fills we read ten
    minutes ago beats showing none.
    """
    if not hasattr(broker, "_call"):
        return 0
    if not await _due_for_refresh(user_id):
        return 0

    start, end = _window(today)
    fills: list[dict[str, Any]] = []
    for page in range(_MAX_PAGES):
        path = _TRADES_PATH.format(start=start, end=end, page=page)
        try:
            result = await broker._call("broker_fills", "GET", path)
        except Exception as exc:  # never break the caller.
            _logger.warning(
                "broker_fills.fetch_failed",
                user_id=str(user_id),
                page=page,
                error=str(exc),
            )
            if page == 0:
                return 0
            break
        rows = result if isinstance(result, list) else (result or {}).get("data", [])
        parsed = parse_fills(rows)
        if not parsed:
            break
        fills.extend(parsed)
    else:
        # Ran the whole range without an empty page. Say so — silently
        # truncating a customer's order history is the failure mode this
        # branch exists to make visible.
        _logger.warning("broker_fills.page_cap_hit", user_id=str(user_id), pages=_MAX_PAGES)

    try:
        await redis_client.cache_set_json(_key(user_id), fills, _TTL_SECONDS)
        await redis_client.cache_set_json(
            _stamp_key(user_id),
            {"at": datetime.now(UTC).isoformat()},
            _TTL_SECONDS,
        )
    except Exception as exc:  # never break the caller.
        _logger.warning("broker_fills.cache_failed", user_id=str(user_id), error=str(exc))
        return 0
    _logger.info("broker_fills.cached", user_id=str(user_id), count=len(fills))
    return len(fills)


async def get_for_user(user_id: UUID | str) -> list[dict[str, Any]]:
    """Cached broker fills, or ``[]`` when we have not read any.

    ``[]`` means UNKNOWN, not "no fills happened". Every caller must render it
    as an absence of information, never as an assertion that the account was
    quiet — that distinction is the whole reason this module exists.
    """
    try:
        cached = await redis_client.cache_get_json(_key(user_id))
    except Exception:  # a display read never raises.
        return []
    return cached if isinstance(cached, list) else []


def fills_without_platform_row(
    fills: list[dict[str, Any]], known_order_ids: set[str]
) -> list[dict[str, Any]]:
    """The fills this platform has no ``strategy_executions`` row for.

    Matching is by broker order id and nothing else. A looser join — symbol +
    side + quantity + timestamp — would occasionally fuse a manual fill onto a
    bot order that happened to look like it, which is exactly the kind of quiet
    mis-attribution the founder's exit rule exists to prevent.
    """
    return [f for f in fills if f.get("broker_order_id") not in known_order_ids]


__all__ = [
    "classify_source",
    "fills_without_platform_row",
    "get_for_user",
    "parse_fills",
    "refresh_for_user",
]

"""Circuit-breaker safety net — volatility + fat-finger guards.

Fat-finger protection and flash-crash blocking. The checks are cheap
enough (Redis + arithmetic) to run inline on every webhook; the cost of
a missed halt is orders of magnitude larger than the cost of the guard.

State model
-----------
Per-symbol state lives in Redis under ``cb_state:{EXCHANGE}:{SYMBOL}``
as JSON::

    {"level": "PAUSE_SHORT", "until": "2026-01-01T10:00:05+00:00",
     "last_price": "2501.1", "last_ts": "2026-01-01T09:59:59+00:00"}

Levels are hierarchical — once HALT is set, nothing short of an admin
``ALLOW`` override resumes trading. Lower levels auto-expire via the
``until`` timestamp, so no scheduled job is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.core import redis_client
from app.core.logging import get_logger
from app.schemas.broker import Exchange, OrderRequest, OrderType

logger = get_logger("app.services.circuit_breaker")


# ═══════════════════════════════════════════════════════════════════════
# Levels
# ═══════════════════════════════════════════════════════════════════════


class CircuitBreakerLevel(StrEnum):
    """Ordered severity — higher index = stricter gate."""

    ALLOW = "ALLOW"
    PAUSE_SHORT = "PAUSE_SHORT"
    PAUSE_LONG = "PAUSE_LONG"
    HALT = "HALT"


#: Durations per level. HALT has no expiry — admin override required.
_PAUSE_SHORT_SECONDS = 30
_PAUSE_LONG_SECONDS = 300


# ═══════════════════════════════════════════════════════════════════════
# Thresholds
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class VolatilityThreshold:
    """A (move%, window_seconds, level) triple. Evaluated in severity order."""

    move_pct: Decimal
    max_window_seconds: int
    level: CircuitBreakerLevel


_THRESHOLDS: tuple[VolatilityThreshold, ...] = (
    # Most severe first — fall through to less severe.
    VolatilityThreshold(Decimal("10"), 300, CircuitBreakerLevel.HALT),
    VolatilityThreshold(Decimal("5"), 60, CircuitBreakerLevel.PAUSE_LONG),
    VolatilityThreshold(Decimal("2"), 5, CircuitBreakerLevel.PAUSE_SHORT),
)


# ═══════════════════════════════════════════════════════════════════════
# Order-sanity thresholds
# ═══════════════════════════════════════════════════════════════════════

#: Block an order if quantity is this multiple of the user's rolling avg.
DEFAULT_QTY_MULTIPLIER_CAP = Decimal("10")
#: Warn when LIMIT price deviates this far from the last traded price.
DEFAULT_PRICE_BAND_PCT = Decimal("5")
#: During PAUSE we convert MARKET → LIMIT with this much buffer above LTP.
PAUSE_LIMIT_BUFFER_PCT = Decimal("0.5")


# ═══════════════════════════════════════════════════════════════════════
# Redis keys
# ═══════════════════════════════════════════════════════════════════════


def _state_key(symbol: str, exchange: Exchange) -> str:
    return f"cb_state:{exchange.value}:{symbol}"


def _last_price_key(symbol: str, exchange: Exchange) -> str:
    return f"cb_last:{exchange.value}:{symbol}"


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class VolatilityDecision:
    """Return value of :func:`check_volatility`."""

    level: CircuitBreakerLevel
    move_pct: Decimal
    until: datetime | None
    reason: str


@dataclass
class SanityDecision:
    """Return value of :func:`check_order_sanity`."""

    allow: bool
    warnings: list[str]
    reasons: list[str]


class CircuitBreakerService:
    """Namespace for the circuit-breaker checks.

    Instance-less so the webhook hot path can call the module singleton
    ``circuit_breaker_service`` without constructing anything per-request.
    """

    # ── Volatility ───────────────────────────────────────────────────

    async def get_state(
        self, symbol: str, exchange: Exchange
    ) -> CircuitBreakerLevel:
        """Current effective level — auto-expires PAUSE_* when ``until`` passes."""
        stored = await redis_client.cache_get_json(_state_key(symbol, exchange))
        if not stored:
            return CircuitBreakerLevel.ALLOW
        until = _parse_iso(stored.get("until"))
        if until and until <= datetime.now(UTC):
            await self._clear_state(symbol, exchange)
            return CircuitBreakerLevel.ALLOW
        try:
            return CircuitBreakerLevel(stored.get("level", "ALLOW"))
        except ValueError:
            return CircuitBreakerLevel.ALLOW

    async def check_volatility(
        self,
        symbol: str,
        exchange: Exchange,
        current_price: Decimal,
        *,
        now: datetime | None = None,
    ) -> VolatilityDecision:
        """Compare against the last cached price/time; set level if breached.

        ``now`` is an injectable clock — real callers leave it ``None`` so
        we read ``datetime.now(UTC)``; tests pass a fixed datetime.
        """
        if current_price <= Decimal("0"):
            return VolatilityDecision(
                level=CircuitBreakerLevel.ALLOW,
                move_pct=Decimal("0"),
                until=None,
                reason="invalid price — ignored",
            )
        now = now or datetime.now(UTC)

        existing_state = await self.get_state(symbol, exchange)
        if existing_state is CircuitBreakerLevel.HALT:
            return VolatilityDecision(
                level=CircuitBreakerLevel.HALT,
                move_pct=Decimal("0"),
                until=None,
                reason="halt in effect",
            )

        prev = await redis_client.cache_get_json(_last_price_key(symbol, exchange))
        await redis_client.cache_set_json(
            _last_price_key(symbol, exchange),
            {"price": str(current_price), "ts": now.isoformat()},
            ttl_seconds=3600,
        )

        if not prev:
            return VolatilityDecision(
                level=existing_state,
                move_pct=Decimal("0"),
                until=None,
                reason="first sample",
            )

        prev_price = Decimal(str(prev.get("price", "0")))
        prev_ts = _parse_iso(prev.get("ts"))
        if prev_price <= 0 or prev_ts is None:
            return VolatilityDecision(
                level=existing_state,
                move_pct=Decimal("0"),
                until=None,
                reason="stale baseline",
            )

        window_seconds = max((now - prev_ts).total_seconds(), 0.0)
        move_pct = abs(current_price - prev_price) / prev_price * Decimal("100")

        breach = _match_threshold(move_pct, window_seconds)
        if breach is None:
            return VolatilityDecision(
                level=existing_state,
                move_pct=move_pct,
                until=None,
                reason="within tolerance",
            )

        until = _compute_expiry(now, breach)
        await self._persist_state(
            symbol,
            exchange,
            level=breach,
            until=until,
            current_price=current_price,
            now=now,
        )
        logger.warning(
            "circuit_breaker.tripped",
            symbol=symbol,
            exchange=exchange.value,
            level=breach.value,
            move_pct=str(move_pct),
            window_s=window_seconds,
        )
        return VolatilityDecision(
            level=breach,
            move_pct=move_pct,
            until=until,
            reason=f"move {move_pct:.2f}% in {window_seconds:.1f}s",
        )

    async def admin_override(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        action: CircuitBreakerLevel,
        admin_user_id: UUID | None = None,
    ) -> None:
        """Operator override — force ALLOW (resume) or HALT."""
        if action not in (CircuitBreakerLevel.ALLOW, CircuitBreakerLevel.HALT):
            raise ValueError("admin_override supports ALLOW or HALT only")
        if action is CircuitBreakerLevel.ALLOW:
            await self._clear_state(symbol, exchange)
        else:
            await self._persist_state(
                symbol,
                exchange,
                level=CircuitBreakerLevel.HALT,
                until=None,
                current_price=None,
                now=datetime.now(UTC),
            )
        logger.warning(
            "circuit_breaker.admin_override",
            symbol=symbol,
            exchange=exchange.value,
            action=action.value,
            admin_user_id=str(admin_user_id) if admin_user_id else None,
        )

    # ── Order sanity ──────────────────────────────────────────────────

    def check_order_sanity(
        self,
        order: OrderRequest,
        *,
        user_avg_order_size: Decimal | None = None,
        user_daily_budget: Decimal | None = None,
        ltp: Decimal | None = None,
    ) -> SanityDecision:
        """Synchronous fat-finger guard — no I/O."""
        reasons: list[str] = []
        warnings: list[str] = []

        if (
            user_avg_order_size is not None
            and user_avg_order_size > Decimal("0")
            and Decimal(order.quantity)
            > user_avg_order_size * DEFAULT_QTY_MULTIPLIER_CAP
        ):
            reasons.append(
                f"quantity {order.quantity} exceeds {DEFAULT_QTY_MULTIPLIER_CAP}× user average"
            )

        if user_daily_budget is not None and order.price is not None:
            value = order.price * Decimal(order.quantity)
            if value > user_daily_budget:
                reasons.append(
                    f"order value {value} exceeds daily budget {user_daily_budget}"
                )

        if ltp is not None and order.price is not None and ltp > Decimal("0"):
            band = abs(order.price - ltp) / ltp * Decimal("100")
            if band > DEFAULT_PRICE_BAND_PCT:
                warnings.append(
                    f"price {order.price} is {band:.2f}% from LTP {ltp}"
                )

        return SanityDecision(
            allow=not reasons,
            warnings=warnings,
            reasons=reasons,
        )

    def convert_order_in_volatile_market(
        self,
        order: OrderRequest,
        *,
        level: CircuitBreakerLevel,
        ltp: Decimal | None,
    ) -> OrderRequest | None:
        """Adjust or block an order based on the circuit-breaker level.

        Returns a new :class:`OrderRequest` when conversion is possible,
        ``None`` when the order should be blocked (HALT, or a PAUSE with
        no LTP to anchor the LIMIT buffer to).
        """
        if level is CircuitBreakerLevel.HALT:
            return None
        if level is CircuitBreakerLevel.ALLOW:
            return order
        # PAUSE_SHORT / PAUSE_LONG — convert MARKET → LIMIT with buffer.
        if order.order_type is not OrderType.MARKET:
            return order
        if ltp is None or ltp <= Decimal("0"):
            return None

        buffer = ltp * PAUSE_LIMIT_BUFFER_PCT / Decimal("100")
        limit_price = (ltp + buffer) if order.side.value == "buy" else (ltp - buffer)
        # Round to 2 dp — tick size handling is broker-specific; this is
        # safe for cash equities and our test surface. The broker layer
        # will reject or snap if needed.
        limit_price = limit_price.quantize(Decimal("0.01"))
        return order.model_copy(
            update={"order_type": OrderType.LIMIT, "price": limit_price}
        )

    # ── Internals ─────────────────────────────────────────────────────

    async def _persist_state(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        level: CircuitBreakerLevel,
        until: datetime | None,
        current_price: Decimal | None,
        now: datetime,
    ) -> None:
        payload: dict[str, Any] = {
            "level": level.value,
            "until": until.isoformat() if until else None,
            "set_at": now.isoformat(),
        }
        if current_price is not None:
            payload["last_price"] = str(current_price)
        ttl = _state_ttl(level, until, now)
        await redis_client.cache_set_json(
            _state_key(symbol, exchange), payload, ttl_seconds=ttl
        )

    async def _clear_state(self, symbol: str, exchange: Exchange) -> None:
        await redis_client.cache_delete(_state_key(symbol, exchange))


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _match_threshold(
    move_pct: Decimal, window_seconds: float
) -> CircuitBreakerLevel | None:
    """Return the most-severe level triggered, or None."""
    for t in _THRESHOLDS:
        if move_pct >= t.move_pct and window_seconds <= t.max_window_seconds:
            return t.level
    return None


def _compute_expiry(
    now: datetime, level: CircuitBreakerLevel
) -> datetime | None:
    match level:
        case CircuitBreakerLevel.PAUSE_SHORT:
            return now + timedelta(seconds=_PAUSE_SHORT_SECONDS)
        case CircuitBreakerLevel.PAUSE_LONG:
            return now + timedelta(seconds=_PAUSE_LONG_SECONDS)
        case CircuitBreakerLevel.HALT:
            return None
        case _:
            return None


def _state_ttl(
    level: CircuitBreakerLevel,
    until: datetime | None,
    now: datetime,
) -> int:
    """Bound the Redis TTL so a stale HALT key still eventually expires."""
    if until is None:
        return 24 * 3600  # HALT — manual reset expected within a day
    delta = (until - now).total_seconds()
    return max(int(delta) + 5, 10)


def _parse_iso(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


# Module-level singleton.
circuit_breaker_service = CircuitBreakerService()


__all__ = [
    "CircuitBreakerLevel",
    "CircuitBreakerService",
    "SanityDecision",
    "VolatilityDecision",
    "VolatilityThreshold",
    "circuit_breaker_service",
]

"""Kill-switch orchestration.

This is the safety pylon. Every path that mutates a user's exposure —
every webhook, every Celery task, every admin action — ultimately passes
through one of these methods. The service takes care of:

* Evaluating threshold breaches (realized + unrealized P&L against the
  user's configured daily-loss cap).
* Firing all brokers in parallel to cancel pending orders and square off
  open positions.
* Persisting the kill-switch event + audit row.
* Flipping the Redis state so downstream webhooks reject new orders.
* Surfacing a structured :class:`KillSwitchResult` for the caller to log
  and report.

Partial-failure policy
----------------------
If broker A's ``square_off_all`` raises while broker B's succeeds, we
record both results, continue (B must not be penalised for A), and let
the caller (Celery task) schedule a retry for A. The Redis TRIPPED flag
is set *before* any broker call so a second webhook landing mid-firing
is rejected instead of racing us.
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import delete, select

from app.brokers.registry import get_broker_class
from app.core import redis_client
from app.core.logging import get_logger
from app.core.security import decrypt_credential
from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.broker_credential import BrokerCredential
from app.db.models.kill_switch import KillSwitchConfig, KillSwitchEvent
from app.schemas.broker import BrokerCredentials
from app.schemas.kill_switch import (
    KillSwitchActionLog,
    KillSwitchConfigCreate,
    KillSwitchDailySummary,
    KillSwitchResult,
    KillSwitchState,
    KillSwitchStatus,
    KillSwitchTestResult,
    TripReason,
)
from app.services import pnl_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.brokers.base import BrokerInterface


logger = get_logger("app.services.kill_switch")


# ═══════════════════════════════════════════════════════════════════════
# Redis keys (service-level — distinct namespace from redis_client)
# ═══════════════════════════════════════════════════════════════════════

_TRADES_KEY_PREFIX = "daily_trades"
_TRIP_META_PREFIX = "kill_meta"
_RESET_TOKEN_PREFIX = "kill_reset_token"
_CONFIG_CACHE_PREFIX = "kill_config"

_CONFIG_CACHE_TTL = 300           # 5 min
_RESET_TOKEN_TTL = 300            # 5 min
_TRIP_META_TTL = 86400            # 24 h
_DAILY_TRADES_TTL = 86400         # 24 h


def _trades_key(user_id: UUID | str) -> str:
    return f"{_TRADES_KEY_PREFIX}:{user_id}"


def _trip_meta_key(user_id: UUID | str) -> str:
    return f"{_TRIP_META_PREFIX}:{user_id}"


def _reset_token_key(user_id: UUID | str) -> str:
    return f"{_RESET_TOKEN_PREFIX}:{user_id}"


def _config_cache_key(user_id: UUID | str) -> str:
    return f"{_CONFIG_CACHE_PREFIX}:{user_id}"


# ═══════════════════════════════════════════════════════════════════════
# Service
# ═══════════════════════════════════════════════════════════════════════


class KillSwitchService:
    """Stateless orchestration — Redis + DB are the real state stores."""

    # ── Config lookup ─────────────────────────────────────────────────

    async def get_config(
        self, user_id: UUID, session: AsyncSession
    ) -> KillSwitchConfig | None:
        """Redis → DB fallback read of a user's config row."""
        cached = await redis_client.cache_get_json(_config_cache_key(user_id))
        if cached:
            return _config_from_dict(cached)

        row = await session.get(KillSwitchConfig, user_id)
        if row is None:
            return None
        await redis_client.cache_set_json(
            _config_cache_key(user_id),
            _config_to_dict(row),
            ttl_seconds=_CONFIG_CACHE_TTL,
        )
        return row

    async def update_config(
        self,
        user_id: UUID,
        config: KillSwitchConfigCreate,
        session: AsyncSession,
    ) -> KillSwitchConfig:
        """Upsert and return the persisted config."""
        row = await session.get(KillSwitchConfig, user_id)
        if row is None:
            row = KillSwitchConfig(user_id=user_id)
            session.add(row)
        row.max_daily_loss_inr = config.max_daily_loss_inr
        row.max_daily_trades = config.max_daily_trades
        row.enabled = config.enabled
        row.auto_square_off = config.auto_square_off
        # SQLite doesn't honour ``onupdate=func.now()`` on async refresh — set
        # ``updated_at`` explicitly so the response serialiser has a value.
        row.updated_at = datetime.now(UTC)
        await session.flush()

        await redis_client.cache_delete(_config_cache_key(user_id))
        await self._audit(
            session,
            user_id=user_id,
            action="kill_switch.config_updated",
            metadata={
                "max_daily_loss_inr": str(config.max_daily_loss_inr),
                "max_daily_trades": config.max_daily_trades,
                "enabled": config.enabled,
                "auto_square_off": config.auto_square_off,
            },
        )
        return row

    # ── Read paths ────────────────────────────────────────────────────

    async def get_status(
        self, user_id: UUID, session: AsyncSession
    ) -> KillSwitchStatus:
        """Build a full live status snapshot from Redis + cached config."""
        config = await self.get_config(user_id, session)
        max_loss = config.max_daily_loss_inr if config else Decimal("0")
        max_trades = config.max_daily_trades if config else 0
        enabled = config.enabled if config else False

        daily_pnl = await pnl_service.calculate_daily_pnl(user_id)
        trades_today = await self._get_daily_trades(user_id)
        state_raw = await redis_client.get_kill_switch_status(user_id)
        state = (
            KillSwitchState.TRIPPED
            if state_raw == redis_client.KILL_SWITCH_TRIPPED
            else KillSwitchState.ACTIVE
        )
        meta = await redis_client.cache_get_json(_trip_meta_key(user_id)) or {}

        remaining_budget = max_loss + daily_pnl  # pnl is negative when losing
        return KillSwitchStatus(
            user_id=user_id,
            state=state,
            daily_pnl=daily_pnl,
            max_daily_loss_inr=max_loss,
            remaining_loss_budget=max(remaining_budget, Decimal("0")),
            trades_today=trades_today,
            max_daily_trades=max_trades,
            remaining_trades=max(max_trades - trades_today, 0),
            enabled=enabled,
            tripped_at=_parse_dt(meta.get("tripped_at")),
            trip_reason=(
                TripReason(meta["reason"]) if meta.get("reason") else None
            ),
        )

    async def get_daily_summary(
        self, user_id: UUID, session: AsyncSession
    ) -> KillSwitchDailySummary:
        config = await self.get_config(user_id, session)
        max_loss = config.max_daily_loss_inr if config else Decimal("0")
        max_trades = config.max_daily_trades if config else 0

        realized = await pnl_service.get_realized_pnl(user_id)
        unrealized = await pnl_service.calculate_unrealized_pnl(user_id)
        total = realized + unrealized
        trades = await self._get_daily_trades(user_id)

        return KillSwitchDailySummary(
            user_id=user_id,
            trades_today=trades,
            daily_pnl=total,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            remaining_loss_budget=max(max_loss + total, Decimal("0")),
            remaining_trades=max(max_trades - trades, 0),
        )

    async def get_trip_history(
        self, user_id: UUID, session: AsyncSession, *, limit: int = 50
    ) -> list[KillSwitchEvent]:
        stmt = (
            select(KillSwitchEvent)
            .where(KillSwitchEvent.user_id == user_id)
            .order_by(KillSwitchEvent.triggered_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ── Daily-trades counter ──────────────────────────────────────────

    async def increment_daily_trades(self, user_id: UUID) -> int:
        """Atomic counter — called after every successful webhook dispatch."""
        client = redis_client.get_redis()
        pipe = client.pipeline(transaction=False)
        pipe.incr(_trades_key(user_id))
        pipe.expire(_trades_key(user_id), _DAILY_TRADES_TTL)
        count, _ = await pipe.execute()
        return int(count)

    async def check_max_daily_trades(
        self, user_id: UUID, session: AsyncSession
    ) -> tuple[bool, int, int]:
        """Returns (within_cap, trades_today, max_allowed)."""
        config = await self.get_config(user_id, session)
        if config is None or not config.enabled:
            return True, 0, 0
        trades = await self._get_daily_trades(user_id)
        return trades < config.max_daily_trades, trades, config.max_daily_trades

    async def _get_daily_trades(self, user_id: UUID) -> int:
        client = redis_client.get_redis()
        raw = await client.get(_trades_key(user_id))
        return int(raw) if raw else 0

    # ── The big one — check & trigger ─────────────────────────────────

    async def check_and_trigger(
        self,
        user_id: UUID,
        session: AsyncSession,
        *,
        force_reason: TripReason | None = None,
        broker_factory: Any = None,
    ) -> KillSwitchResult:
        """Evaluate thresholds and fire if breached.

        Safe to call after every trade: the function is a no-op unless
        the kill-switch is enabled AND a limit is exceeded (or
        ``force_reason`` is passed by a caller that already knows the
        trigger condition, e.g. the circuit-breaker HALT path).
        """
        config = await self.get_config(user_id, session)
        daily_pnl = await pnl_service.calculate_daily_pnl(user_id)

        if force_reason is None:
            if config is None or not config.enabled:
                return KillSwitchResult(triggered=False, daily_pnl=daily_pnl)
            reason = _evaluate_breach(
                daily_pnl=daily_pnl,
                max_loss=config.max_daily_loss_inr,
                trades_today=await self._get_daily_trades(user_id),
                max_trades=config.max_daily_trades,
            )
            if reason is None:
                return KillSwitchResult(triggered=False, daily_pnl=daily_pnl)
        else:
            reason = force_reason

        # Flip the gate BEFORE firing brokers — any concurrent webhook now rejects.
        await redis_client.set_kill_switch_status(
            user_id, redis_client.KILL_SWITCH_TRIPPED
        )

        actions, errors = await self._execute_emergency_square_off(
            user_id, session, broker_factory=broker_factory
        )

        event = KillSwitchEvent(
            user_id=user_id,
            reason=reason.value,
            daily_pnl_at_trigger=daily_pnl,
            positions_squared_off=[a.model_dump(mode="json") for a in actions],
        )
        session.add(event)
        await session.flush()

        await redis_client.cache_set_json(
            _trip_meta_key(user_id),
            {
                "tripped_at": datetime.now(UTC).isoformat(),
                "reason": reason.value,
                "event_id": str(event.id),
            },
            ttl_seconds=_TRIP_META_TTL,
        )

        await self._audit(
            session,
            user_id=user_id,
            action="kill_switch.triggered",
            metadata={
                "reason": reason.value,
                "daily_pnl": str(daily_pnl),
                "actions": [a.model_dump(mode="json") for a in actions],
            },
        )
        logger.warning(
            "kill_switch.triggered",
            user_id=str(user_id),
            reason=reason.value,
            daily_pnl=str(daily_pnl),
        )

        return KillSwitchResult(
            triggered=True,
            reason=reason,
            daily_pnl=daily_pnl,
            event_id=event.id,
            actions=actions,
            errors=errors,
        )

    # ── Manual reset ──────────────────────────────────────────────────

    async def create_reset_token(self, user_id: UUID) -> str:
        """Issue a short-lived token that ``manual_reset`` will consume."""
        token = secrets.token_urlsafe(24)
        client = redis_client.get_redis()
        await client.set(
            _reset_token_key(user_id), token, ex=_RESET_TOKEN_TTL
        )
        return token

    async def manual_reset(
        self,
        user_id: UUID,
        *,
        reset_by: UUID,
        confirmation_token: str,
        session: AsyncSession,
    ) -> KillSwitchEvent | None:
        """Clear the tripped flag and zero the day's counters.

        Requires a matching reset token issued by :meth:`create_reset_token`.
        """
        client = redis_client.get_redis()
        expected = await client.get(_reset_token_key(user_id))
        if not expected:
            raise PermissionError("No active reset token; request one first.")
        import hmac

        if not hmac.compare_digest(expected, confirmation_token):
            raise PermissionError("Confirmation token mismatch.")

        await client.delete(_reset_token_key(user_id))
        await redis_client.clear_kill_switch(user_id)
        await redis_client.set_daily_pnl(user_id, Decimal("0"))
        await client.delete(_trades_key(user_id))
        await redis_client.cache_delete(_trip_meta_key(user_id).split(":", 1)[1])
        # The trip-meta key wasn't written through cache_set so use raw delete.
        await client.delete(_trip_meta_key(user_id))

        stmt = (
            select(KillSwitchEvent)
            .where(
                KillSwitchEvent.user_id == user_id,
                KillSwitchEvent.reset_at.is_(None),
            )
            .order_by(KillSwitchEvent.triggered_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            row.reset_at = datetime.now(UTC)
            row.reset_by = reset_by
            await session.flush()

        await self._audit(
            session,
            user_id=user_id,
            action="kill_switch.reset",
            metadata={"reset_by": str(reset_by)},
            actor=ActorType.ADMIN if reset_by != user_id else ActorType.USER,
        )
        logger.info("kill_switch.reset", user_id=str(user_id))
        return row

    # ── Simulation (dry run) ──────────────────────────────────────────

    async def test_trip(
        self, user_id: UUID, session: AsyncSession
    ) -> KillSwitchTestResult:
        config = await self.get_config(user_id, session)
        daily_pnl = await pnl_service.calculate_daily_pnl(user_id)
        max_loss = config.max_daily_loss_inr if config else Decimal("0")
        max_trades = config.max_daily_trades if config else 0
        trades = await self._get_daily_trades(user_id)
        reason = _evaluate_breach(
            daily_pnl=daily_pnl,
            max_loss=max_loss,
            trades_today=trades,
            max_trades=max_trades,
        )
        return KillSwitchTestResult(
            would_trigger=reason is not None and bool(config and config.enabled),
            reason=reason,
            daily_pnl=daily_pnl,
            max_daily_loss_inr=max_loss,
        )

    # ── Daily / scheduled jobs ────────────────────────────────────────

    async def daily_reset_all(self, session: AsyncSession) -> int:
        """Wipe per-user day-state at 9:00 IST.

        Iterates Redis SCAN rather than FLUSHDB because other namespaces
        (idempotency, auth lockouts) must survive the reset. Returns the
        count of user-scoped keys removed.
        """
        client = redis_client.get_redis()
        patterns = (
            f"{redis_client._NS_PNL}:*",
            f"{_TRADES_KEY_PREFIX}:*",
            f"{redis_client._NS_KILL}:*",
            f"{_TRIP_META_PREFIX}:*",
        )
        total = 0
        for pattern in patterns:
            async for key in client.scan_iter(match=pattern, count=200):
                await client.delete(key)
                total += 1

        await self._audit(
            session,
            user_id=None,
            action="kill_switch.daily_reset",
            metadata={"keys_removed": total},
            actor=ActorType.SYSTEM,
        )
        logger.info("kill_switch.daily_reset", keys_removed=total)
        return total

    async def auto_square_off_intraday(
        self, session: AsyncSession, *, broker_factory: Any = None
    ) -> list[UUID]:
        """Close every INTRADAY position for users with auto_square_off=True.

        Used at 15:15 IST as a net for users who forgot to exit.
        Returns the user_ids whose emergency-close ran.
        """
        stmt = select(KillSwitchConfig).where(
            KillSwitchConfig.auto_square_off.is_(True),
            KillSwitchConfig.enabled.is_(True),
        )
        rows = list((await session.execute(stmt)).scalars().all())
        touched: list[UUID] = []
        for row in rows:
            try:
                await self.check_and_trigger(
                    row.user_id,
                    session,
                    force_reason=TripReason.AUTO_SQUARE_OFF,
                    broker_factory=broker_factory,
                )
                touched.append(row.user_id)
            except Exception as exc:  # noqa: BLE001 — one user's failure must not halt the job
                logger.warning(
                    "auto_square_off.user_failed",
                    user_id=str(row.user_id),
                    error=str(exc),
                )
        return touched

    # ── Internals ─────────────────────────────────────────────────────

    async def _execute_emergency_square_off(
        self,
        user_id: UUID,
        session: AsyncSession,
        *,
        broker_factory: Any = None,
    ) -> tuple[list[KillSwitchActionLog], list[str]]:
        stmt = select(BrokerCredential).where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.is_active.is_(True),
        )
        creds = list((await session.execute(stmt)).scalars().all())
        if not creds:
            return [], []

        async def _run_one(row: BrokerCredential) -> KillSwitchActionLog:
            try:
                broker = _build_broker(row, user_id, broker_factory=broker_factory)
                if not await broker.is_session_valid():
                    await broker.login()
                cancelled = await broker.cancel_all_pending()
                squared = await broker.square_off_all()
                return KillSwitchActionLog(
                    broker_credential_id=row.id,
                    broker_name=row.broker_name.value,
                    pending_cancelled=int(cancelled),
                    positions_squared_off=len(squared),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "kill_switch.broker_failed",
                    broker_credential_id=str(row.id),
                    error=str(exc),
                )
                return KillSwitchActionLog(
                    broker_credential_id=row.id,
                    broker_name=row.broker_name.value,
                    error=f"{type(exc).__name__}: {exc}",
                )

        results = await asyncio.gather(
            *(_run_one(c) for c in creds), return_exceptions=False
        )
        errors = [r.error for r in results if r.error]
        return list(results), errors

    async def _audit(
        self,
        session: AsyncSession,
        *,
        user_id: UUID | None,
        action: str,
        metadata: dict[str, Any],
        actor: ActorType = ActorType.SYSTEM,
    ) -> None:
        row = AuditLog(
            user_id=user_id,
            actor=actor,
            action=action,
            resource_type="kill_switch",
            resource_id=str(user_id) if user_id else None,
            audit_metadata=metadata,
        )
        session.add(row)
        await session.flush()


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _evaluate_breach(
    *,
    daily_pnl: Decimal,
    max_loss: Decimal,
    trades_today: int,
    max_trades: int,
) -> TripReason | None:
    """Return the first breached reason, or None.

    Loss comparison: ``daily_pnl`` is signed (negative = losing). The
    kill switch fires when the *loss magnitude* exceeds ``max_loss`` —
    i.e. ``daily_pnl < -max_loss``. Equal-to-limit does NOT fire (the
    blueprint states "only when exceeded").
    """
    if max_loss > 0 and daily_pnl < -max_loss:
        return TripReason.DAILY_LOSS_BREACHED
    if max_trades > 0 and trades_today > max_trades:
        return TripReason.MAX_TRADES_BREACHED
    return None


def _config_to_dict(row: KillSwitchConfig) -> dict[str, Any]:
    return {
        "user_id": str(row.user_id),
        "max_daily_loss_inr": str(row.max_daily_loss_inr),
        "max_daily_trades": row.max_daily_trades,
        "enabled": row.enabled,
        "auto_square_off": row.auto_square_off,
        "updated_at": (
            row.updated_at.isoformat() if row.updated_at else None
        ),
    }


def _config_from_dict(data: dict[str, Any]) -> KillSwitchConfig:
    row = KillSwitchConfig(
        user_id=UUID(data["user_id"]),
        max_daily_loss_inr=Decimal(data["max_daily_loss_inr"]),
        max_daily_trades=int(data["max_daily_trades"]),
        enabled=bool(data["enabled"]),
        auto_square_off=bool(data["auto_square_off"]),
    )
    if data.get("updated_at"):
        row.updated_at = datetime.fromisoformat(data["updated_at"])
    return row


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _build_broker(
    row: BrokerCredential,
    user_id: UUID,
    *,
    broker_factory: Any = None,
) -> BrokerInterface:
    """Construct a :class:`BrokerInterface` for one credential row."""
    creds = BrokerCredentials(
        broker=row.broker_name,
        user_id=str(user_id),
        client_id=decrypt_credential(row.client_id_enc),
        api_key=decrypt_credential(row.api_key_enc),
        api_secret=decrypt_credential(row.api_secret_enc),
        access_token=(
            decrypt_credential(row.access_token_enc) if row.access_token_enc else None
        ),
        refresh_token=(
            decrypt_credential(row.refresh_token_enc) if row.refresh_token_enc else None
        ),
        token_expires_at=row.token_expires_at,
    )
    if broker_factory is not None:
        return broker_factory(creds)  # type: ignore[no-any-return]
    return get_broker_class(creds.broker)(creds)


# Module-level singleton — every caller uses the same instance.
kill_switch_service = KillSwitchService()


__all__ = ["KillSwitchService", "kill_switch_service"]


# ── Cleanup helper the daily job uses to purge expired idempotency rows.
async def delete_expired_idempotency(session: AsyncSession) -> int:
    """Remove expired rows from ``idempotency_keys``.

    Lives here (not in ``redis_client``) because it's a DB-level cleanup
    that the scheduled-task layer calls; the Redis TTLs age the fast-path
    keys automatically, so this only covers the persisted ones.
    """
    from app.db.models.idempotency import IdempotencyKey

    stmt = delete(IdempotencyKey).where(
        IdempotencyKey.expires_at < datetime.now(UTC)
    )
    result = await session.execute(stmt)
    await session.flush()
    return int(result.rowcount or 0)

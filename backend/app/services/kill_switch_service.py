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
from sqlalchemy.orm.attributes import flag_modified

from app.brokers.registry import get_broker_class
from app.core import redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import decrypt_credential
from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.broker_credential import BrokerCredential
from app.db.models.kill_switch import KillSwitchConfig, KillSwitchEvent
from app.db.models.strategy_position import StrategyPosition
from app.schemas.broker import (
    BrokerCredentials,
    Exchange,
    OrderRequest,
    OrderType,
    ProductType,
)
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
from app.services.direct_exit import opposite_side

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

        # Layer 1 gate (2026-05-10): if the user has explicitly opted out
        # of automatic position close, flip the trip flag and audit but
        # do NOT touch the broker. The user is responsible for manual
        # close. Prevents the 2026-05-08 incident where a manual trip
        # wiped personal Dhan positions alongside system positions.
        if config is not None and not config.auto_square_off:
            actions: list[KillSwitchActionLog] = []
            errors: list[str] = []
            logger.info(
                "kill_switch.square_off_skipped",
                user_id=str(user_id),
                reason="auto_square_off_disabled_in_config",
            )
        else:
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

        # Operator alert. Fire-and-forget — a Telegram outage MUST NOT
        # block a kill-switch trip from completing. ``send_alert`` itself
        # swallows exceptions, but we wrap the import too in case the
        # alerts module fails to load (env-misconfig).
        try:
            from app.services import telegram_alerts as _alerts

            await _alerts.send_alert(
                _alerts.AlertLevel.CRITICAL,
                f"Kill switch TRIPPED\nuser=`{user_id}` "
                f"reason=`{reason.value}` daily_pnl=`{daily_pnl}` "
                f"squared_off=`{len(actions)}` errors=`{len(errors)}`",
            )
        except Exception:
            logger.exception(
                "kill_switch.alert_failed", user_id=str(user_id)
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
        """Close ONLY strategy-tracked positions for this user.

        Layer 2 (2026-05-10) — replaces the prior broker-wide square-off
        that closed personal Dhan positions alongside system positions
        (root cause of the 2026-05-08 ₹50K incident). Now we:

        1. Read open ``strategy_positions`` rows for the user — the DB
           is the source of truth for what TRADETRI placed.
        2. Group by ``broker_credential_id`` and place an opposing
           market order per position via the broker associated with that
           credential.
        3. Per-position failures are collected, never raised — a failed
           close on one symbol must not block the rest.

        Positions held in the broker account but absent from
        ``strategy_positions`` (i.e. user's personal manual trades) are
        intentionally untouched. Pending order cancellation is also
        removed from the emergency path — same scope problem applies
        and we have no DB-side record of which open orders are
        TRADETRI's.
        """
        stmt = select(StrategyPosition).where(
            StrategyPosition.user_id == user_id,
            StrategyPosition.status.in_(("open", "partial")),
            StrategyPosition.remaining_quantity > 0,
        )
        positions = list((await session.execute(stmt)).scalars().all())
        if not positions:
            return [], []

        # Fix #8 (incident 2026-05-20): bucket positions into paper/live
        # by per-strategy paper_mode_resolver, NOT by global settings flag.
        # Pre-fix: a single global-flag check at this point silenced the
        # broker close path for ALL positions in mixed-mode deployments
        # (global paper=True, BSE LTD live=False per migration 027) —
        # which would mean a kill-switch trip on the live strategy marked
        # the DB row closed while leaving the real Dhan position OPEN.
        from app.db.models.strategy import Strategy as _Strategy
        from app.services.paper_mode_resolver import resolve_paper_mode

        strategy_ids = {p.strategy_id for p in positions if p.strategy_id}
        strat_rows = list(
            (
                await session.execute(
                    select(_Strategy).where(_Strategy.id.in_(strategy_ids))
                )
            )
            .scalars()
            .all()
        )
        strat_by_id = {s.id: s for s in strat_rows}

        paper_positions: list[StrategyPosition] = []
        live_positions: list[StrategyPosition] = []
        for p in positions:
            strat = strat_by_id.get(p.strategy_id)
            if resolve_paper_mode(strat):
                paper_positions.append(p)
            else:
                live_positions.append(p)

        # Bucket BY credential within each mode for the close loops.
        by_cred_paper: dict[UUID, list[StrategyPosition]] = {}
        for p in paper_positions:
            by_cred_paper.setdefault(p.broker_credential_id, []).append(p)
        by_cred_live: dict[UUID, list[StrategyPosition]] = {}
        for p in live_positions:
            by_cred_live.setdefault(p.broker_credential_id, []).append(p)

        all_cred_ids = list(set(by_cred_paper.keys()) | set(by_cred_live.keys()))
        cred_stmt = select(BrokerCredential).where(
            BrokerCredential.id.in_(all_cred_ids)
        )
        cred_by_id = {
            c.id: c
            for c in (await session.execute(cred_stmt)).scalars().all()
        }

        paper_results: list[KillSwitchActionLog] = []
        if by_cred_paper:
            logger.info(
                "kill_switch.paper_positions_synthetic_close",
                user_id=str(user_id),
                positions=len(paper_positions),
                credentials=len(by_cred_paper),
            )
            for cred_id, group in by_cred_paper.items():
                cred_row = cred_by_id.get(cred_id)
                broker_name_str = (
                    cred_row.broker_name.value if cred_row else "unknown"
                )
                closed_count = 0
                for pos in group:
                    self._close_position_in_paper(pos)
                    closed_count += 1
                paper_results.append(
                    KillSwitchActionLog(
                        broker_credential_id=cred_id,
                        broker_name=broker_name_str,
                        positions_squared_off=closed_count,
                        error=None,
                    )
                )
            await session.flush()

        # If there are no live positions, we're done — return just the
        # paper-side actions.
        if not by_cred_live:
            return paper_results, []

        async def _run_one(
            cred_id: UUID, group: list[StrategyPosition]
        ) -> KillSwitchActionLog:
            cred_row = cred_by_id.get(cred_id)
            if cred_row is None:
                return KillSwitchActionLog(
                    broker_credential_id=cred_id,
                    broker_name="unknown",
                    positions_squared_off=0,
                    error="broker_credential row missing",
                )
            try:
                broker = _build_broker(
                    cred_row, user_id, broker_factory=broker_factory
                )
                if not await broker.is_session_valid():
                    await broker.login()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "kill_switch.broker_login_failed",
                    broker_credential_id=str(cred_id),
                    error=str(exc),
                )
                return KillSwitchActionLog(
                    broker_credential_id=cred_id,
                    broker_name=cred_row.broker_name.value,
                    positions_squared_off=0,
                    error=f"{type(exc).__name__}: {exc}",
                )

            closed = 0
            per_pos_errors: list[str] = []
            for pos in group:
                try:
                    await self._close_position_via_broker(
                        position=pos, broker=broker, session=session
                    )
                    closed += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "kill_switch.position_close_failed",
                        position_id=str(pos.id),
                        symbol=pos.symbol,
                        error=str(exc),
                    )
                    per_pos_errors.append(f"{pos.symbol}: {exc}")

            return KillSwitchActionLog(
                broker_credential_id=cred_id,
                broker_name=cred_row.broker_name.value,
                positions_squared_off=closed,
                error="; ".join(per_pos_errors) if per_pos_errors else None,
            )

        results = await asyncio.gather(
            *(_run_one(cid, group) for cid, group in by_cred_live.items())
        )
        errors = [r.error for r in results if r.error]
        # Paper + live action logs both surfaced in the KillSwitchResult.
        return paper_results + list(results), errors

    def _close_position_in_paper(self, position: StrategyPosition) -> None:
        """Mark a ``strategy_position`` closed without any broker call.

        Mirror of :meth:`_close_position_via_broker`'s state mutation
        but with a synthetic ``PAPER-KILL-SWITCH-…`` order id in the
        ``action_history`` entry. Sync because there is no I/O — the
        caller drives a single ``session.flush()`` after every position
        in the group has been mutated.
        """
        import uuid as _uuid

        now = datetime.now(UTC)
        closed_qty = position.remaining_quantity
        exit_side = opposite_side(position.side)
        position.remaining_quantity = 0
        position.status = "closed"
        position.closed_at = now
        position.exit_reason = "kill_switch"
        position.last_action = "kill_switch"
        position.last_action_at = now
        history = list(position.action_history or [])
        history.append(
            {
                "action": "kill_switch",
                "qty": closed_qty,
                "side": exit_side.value,
                "ts": now.isoformat(),
                "broker_order_id": f"PAPER-KILL-SWITCH-{_uuid.uuid4()}",
                "broker_status": "complete",
                "broker_message": "paper-mode kill switch — no broker call",
                "paper_mode": True,
            }
        )
        position.action_history = history
        flag_modified(position, "action_history")

    async def _close_position_via_broker(
        self,
        *,
        position: StrategyPosition,
        broker: BrokerInterface,
        session: AsyncSession,
    ) -> None:
        """Place an opposing market order to close one strategy_position.

        On success: mutate position state — status='closed', closed_at,
        exit_reason='kill_switch', broker_exit_response, last_action,
        action_history. Caller commits.

        Raises on broker rejection — caller catches and continues with
        the next position so one bad symbol does not block the trip.
        """
        exit_side = opposite_side(position.side)
        # Fix #8 (incident 2026-05-20): F&O close legs must use MARGIN
        # per permanent rule 1 (/tmp/PERMANENT_RULES.md). Pre-fix this
        # was hardcoded INTRADAY — a position opened MARGIN would be
        # closed as if opening a NEW intraday position, leaving the
        # carry-forward leg open. Current TRADETRI is F&O-only
        # (Exchange.NFO hardcode); equity support would need to look up
        # the position's original product_type — file a follow-up if/
        # when added.
        order = OrderRequest(
            symbol=position.symbol,
            exchange=Exchange.NFO,
            side=exit_side,
            quantity=position.remaining_quantity,
            order_type=OrderType.MARKET,
            product_type=ProductType.MARGIN,
            tag="kill-switch",
        )
        response = await broker.place_order(order)

        now = datetime.now(UTC)
        closed_qty = position.remaining_quantity
        position.remaining_quantity = 0
        position.status = "closed"
        position.closed_at = now
        position.exit_reason = "kill_switch"
        position.last_action = "kill_switch"
        position.last_action_at = now
        # NOTE: ``StrategyPosition.broker_exit_response`` exists as a DB
        # column but is NOT mapped on the ORM class today — writing to it
        # via ``flag_modified`` would KeyError. The action_history entry
        # below carries the broker_order_id + status, which is enough for
        # audit until a future model-update migration maps the column.
        history = list(position.action_history or [])
        history.append(
            {
                "action": "kill_switch",
                "qty": closed_qty,
                "side": exit_side.value,
                "ts": now.isoformat(),
                "broker_order_id": response.broker_order_id,
                "broker_status": response.status.value,
                "broker_message": response.message,
            }
        )
        position.action_history = history
        flag_modified(position, "action_history")
        await session.flush()

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

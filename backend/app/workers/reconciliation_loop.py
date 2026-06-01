"""Order-reconciliation loop — DB-vs-broker drift detection.

Runs as an asyncio task spawned from FastAPI's lifespan. Every tick:

1. List active :class:`BrokerCredential` rows.
2. For each: list open :class:`StrategyPosition` rows, fetch the
   broker's live ``get_positions()``, build comparable sets, diff.
3. On any non-empty diff: log + fire a CRITICAL Telegram alert
   describing both sides (DB-only and broker-only positions).

The loop is a **no-op in paper mode** — paper trades have no broker
side to reconcile against, and we want to avoid hitting real broker
APIs from dev / staging / Monday paper-observation environments.

Per-credential errors (broker outage, decryption failure, expired
session) are caught, logged, and SKIPPED — one bad credential does
not kill the tick. The next tick retries.

Lifecycle mirrors :mod:`app.workers.position_loop`:
    * ``start_reconciliation_loop(app)`` — spawned in lifespan startup.
    * ``stop_reconciliation_loop(app)`` — cancelled cleanly on shutdown.
    * ``reconcile_once(session)`` — public test seam for one tick.
    * ``_sleep`` — module-level alias so tests can patch the inter-tick
      sleep without affecting global ``asyncio.sleep``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition

if TYPE_CHECKING:
    from fastapi import FastAPI

_logger = get_logger("workers.reconciliation_loop")

#: See :mod:`app.workers.position_loop` for why this indirection exists.
_sleep = asyncio.sleep


async def reconcile_once(session: AsyncSession) -> int:
    """One reconciliation pass — returns total mismatch count.

    Fix #7 (incident 2026-05-20): scans only broker_credentials backing
    at least one LIVE strategy (``Strategy.is_paper=False``).  Pre-fix
    behaviour was a global ``settings.strategy_paper_mode`` short-circuit,
    which silenced drift detection for live strategies in a mixed-mode
    deployment (today's prod: global paper=True, BSE LTD live=False)
    — the very scenario migration 027 enabled.  The May 20 phantom
    position would have been caught on the next 60-second tick if this
    loop had been allowed to run.

    Per-credential errors are caught and skipped so a single broker
    outage does not kill the tick — the next tick retries.
    """
    creds = await _list_credentials_backing_live_strategies(session)
    if not creds:
        _logger.debug("reconciliation.no_live_strategies")
        return 0

    total_mismatches = 0
    for cred in creds:
        try:
            total_mismatches += await _reconcile_credential(session, cred)
        except Exception as exc:  # noqa: BLE001 — never let one bad cred kill the tick.
            _logger.warning(
                "reconciliation.cred_failed",
                cred_id=str(cred.id),
                broker=cred.broker_name.value
                if hasattr(cred.broker_name, "value")
                else str(cred.broker_name),
                error=str(exc),
            )
    return total_mismatches


async def _list_active_credentials(
    session: AsyncSession,
) -> list[BrokerCredential]:
    """Legacy helper — retained so external callers that imported the
    private name don't break.  Internal reconciliation now goes through
    ``_list_credentials_backing_live_strategies`` for per-strategy
    awareness (Fix #7)."""
    stmt = select(BrokerCredential).where(BrokerCredential.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def _list_credentials_backing_live_strategies(
    session: AsyncSession,
) -> list[BrokerCredential]:
    """Active BrokerCredentials referenced by ≥1 strategy with
    ``is_paper=False``.  Replaces the global-paper-mode short-circuit
    that pre-Fix #7 silenced reconciliation for live strategies in
    mixed-mode deployments (incident 2026-05-20)."""
    stmt = (
        select(BrokerCredential)
        .where(BrokerCredential.is_active.is_(True))
        .where(
            BrokerCredential.id.in_(
                select(Strategy.broker_credential_id)
                .where(Strategy.is_active.is_(True))
                .where(Strategy.is_paper.is_(False))
                .where(Strategy.broker_credential_id.is_not(None))
            )
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def _reconcile_credential(
    session: AsyncSession, cred: BrokerCredential
) -> int:
    """Diff DB open positions vs live broker positions for ONE credential.

    Returns the number of mismatched position records (sum of DB-only
    and broker-only entries). On non-zero mismatches, fires a CRITICAL
    Telegram alert with both sides of the diff.
    """
    # ── DB side — LIVE strategies only (Fix #7) ─────────────────────────
    # A credential may back both paper and live strategies after
    # migration 027.  Including paper positions would surface them as
    # false `db_only` drift (the paper position has no broker leg).
    db_stmt = (
        select(StrategyPosition)
        .join(Strategy, Strategy.id == StrategyPosition.strategy_id)
        .where(
            StrategyPosition.broker_credential_id == cred.id,
            StrategyPosition.status == "open",
            Strategy.is_paper.is_(False),
        )
    )
    db_positions = list((await session.execute(db_stmt)).scalars().all())
    db_set: set[tuple[str, str, int]] = {
        (p.symbol, p.side, p.remaining_quantity) for p in db_positions
    }

    # ── Broker side ────────────────────────────────────────────────────
    broker = await _build_broker(cred)
    if not await broker.is_session_valid():
        await broker.login()
    broker_positions = await broker.get_positions()
    broker_set: set[tuple[str, str, int]] = set()
    for bp in broker_positions:
        if bp.quantity == 0:
            continue  # closed leg, ignore
        side = "buy" if bp.quantity > 0 else "sell"
        broker_set.add((bp.symbol, side, abs(bp.quantity)))

    db_only = db_set - broker_set
    broker_only = broker_set - db_set
    mismatches = len(db_only) + len(broker_only)

    if mismatches == 0:
        return 0

    _logger.warning(
        "reconciliation.drift",
        cred_id=str(cred.id),
        db_only=sorted(db_only),
        broker_only=sorted(broker_only),
    )

    # Reverse-phantom catch: a ``broker_only`` position that matches a
    # previously-flagged ambiguous (timed-out) order is a CONFIRMED late fill
    # with no local state. Alert ALWAYS — bypassing the manual-position spam
    # gate below — because a flagged-then-appeared position is NOT a manual
    # trade; then clear the watch so it doesn't re-alert every tick.
    from app.services.ambiguous_fill import clear_flag, is_flagged

    for sym, side, qty in sorted(broker_only):
        flagged_order = await is_flagged(sym)
        if flagged_order is None:
            continue
        _logger.error(
            "reconciliation.reverse_phantom_confirmed",
            cred_id=str(cred.id),
            symbol=sym,
            side=side,
            qty=qty,
            order_id=flagged_order,
        )
        try:
            from app.services import telegram_alerts as _alerts

            await _alerts.send_alert(
                _alerts.AlertLevel.CRITICAL,
                (
                    "🚨 *REVERSE-PHANTOM CONFIRMED*\n"
                    f"`{sym}` {side} {qty} filled LATE "
                    f"(order `{flagged_order}`) — a REAL broker position with "
                    "NO local state.\n"
                    f"cred=`{cred.id}`. Square off / reconcile in Dhan NOW."
                ),
            )
        except Exception:  # noqa: BLE001
            _logger.exception("reconciliation.reverse_phantom_alert_failed")
        await clear_flag(sym)

    # Operator Telegram alert is gated behind a feature flag (default OFF).
    # Manual broker-side positions placed directly on the broker UI cause
    # continuous drift every tick — without the gate, that's 60 msg/hour
    # of Telegram spam. Drift is still logged at warning level above so
    # ops can grep for it; the flag only controls whether Telegram fires.
    settings = get_settings()
    if settings.reconciliation_telegram_enabled:
        try:
            from app.services import telegram_alerts as _alerts

            await _alerts.send_alert(
                _alerts.AlertLevel.CRITICAL,
                (
                    f"DB-broker drift detected\n"
                    f"cred=`{cred.id}` user=`{cred.user_id}`\n"
                    f"db_only=`{sorted(db_only)}`\n"
                    f"broker_only=`{sorted(broker_only)}`"
                ),
            )
        except Exception:
            _logger.exception(
                "reconciliation.alert_failed", cred_id=str(cred.id)
            )

    return mismatches


async def _build_broker(cred: BrokerCredential):  # type: ignore[no-untyped-def]
    """Construct a broker instance from a credential row.

    Lazy imports keep this module loadable even if the strategy executor
    is monkeypatched in tests.
    """
    from app.brokers.registry import get_broker_class
    from app.core.security import decrypt_credential
    from app.schemas.broker import BrokerCredentials

    creds = BrokerCredentials(
        broker=cred.broker_name,
        user_id=str(cred.user_id),
        client_id=decrypt_credential(cred.client_id_enc),
        api_key=decrypt_credential(cred.api_key_enc),
        api_secret=decrypt_credential(cred.api_secret_enc),
        access_token=(
            decrypt_credential(cred.access_token_enc)
            if cred.access_token_enc
            else None
        ),
        refresh_token=(
            decrypt_credential(cred.refresh_token_enc)
            if cred.refresh_token_enc
            else None
        ),
        token_expires_at=cred.token_expires_at,
    )
    return get_broker_class(creds.broker)(creds)


async def _run_loop() -> None:
    """Forever-loop driver — opens one session per tick, calls
    :func:`reconcile_once`. Per-tick errors are swallowed; only
    ``CancelledError`` exits."""
    settings = get_settings()
    interval = settings.reconciliation_poll_seconds

    from app.db.session import get_sessionmaker

    maker = get_sessionmaker()
    _logger.info(
        "reconciliation_loop.started",
        interval=interval,
        paper_mode=settings.strategy_paper_mode,
    )
    try:
        while True:
            try:
                async with maker() as session:
                    mismatches = await reconcile_once(session)
                    if mismatches:
                        _logger.warning(
                            "reconciliation_loop.tick", mismatches=mismatches
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — keep the loop alive.
                _logger.warning(
                    "reconciliation_loop.tick_failed", error=str(exc)
                )
            await _sleep(interval)
    except asyncio.CancelledError:
        _logger.info("reconciliation_loop.cancelled")
        raise


def start_reconciliation_loop(app: FastAPI) -> asyncio.Task[None]:
    """Spawn the loop on FastAPI startup. Returns the task so lifespan can cancel it."""
    task = asyncio.create_task(_run_loop(), name="reconciliation_loop")
    app.state.reconciliation_loop_task = task
    return task


async def stop_reconciliation_loop(app: FastAPI) -> None:
    """Cancel and await the loop. Idempotent."""
    task: asyncio.Task[None] | None = getattr(
        app.state, "reconciliation_loop_task", None
    )
    if task is None or task.done():
        return
    import contextlib

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


__all__ = [
    "reconcile_once",
    "start_reconciliation_loop",
    "stop_reconciliation_loop",
]

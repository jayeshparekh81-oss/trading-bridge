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
from app.db.models.strategy_position import StrategyPosition

if TYPE_CHECKING:
    from fastapi import FastAPI

_logger = get_logger("workers.reconciliation_loop")

#: See :mod:`app.workers.position_loop` for why this indirection exists.
_sleep = asyncio.sleep


async def reconcile_once(session: AsyncSession) -> int:
    """One reconciliation pass — returns total mismatch count.

    No-op when ``settings.strategy_paper_mode`` is True. Per-credential
    errors are caught and skipped so a single broker outage does not
    kill the tick — the next tick retries.
    """
    settings = get_settings()
    if settings.strategy_paper_mode:
        _logger.debug("reconciliation.skipped_paper_mode")
        return 0

    creds = await _list_active_credentials(session)
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
    stmt = select(BrokerCredential).where(BrokerCredential.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def _reconcile_credential(
    session: AsyncSession, cred: BrokerCredential
) -> int:
    """Diff DB open positions vs live broker positions for ONE credential.

    Returns the number of mismatched position records (sum of DB-only
    and broker-only entries). On non-zero mismatches, fires a CRITICAL
    Telegram alert with both sides of the diff.
    """
    # ── DB side ────────────────────────────────────────────────────────
    db_stmt = select(StrategyPosition).where(
        StrategyPosition.broker_credential_id == cred.id,
        StrategyPosition.status == "open",
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

    # Operator alert — fire-and-forget. Lazy import keeps cold-start cost
    # off this module and lets tests monkeypatch the alert sender.
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

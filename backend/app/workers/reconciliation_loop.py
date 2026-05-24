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
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal

if TYPE_CHECKING:
    from fastapi import FastAPI

_logger = get_logger("workers.reconciliation_loop")

#: See :mod:`app.workers.position_loop` for why this indirection exists.
_sleep = asyncio.sleep

#: Broker order statuses we treat as terminal — once an execution reaches
#: one of these it no longer needs polling. Compared case-insensitively
#: against ``OrderStatus.value``.
_TERMINAL_BROKER_STATUS: frozenset[str] = frozenset(
    {"complete", "traded", "executed", "filled", "cancelled", "rejected", "expired"}
)

#: Don't poll executions older than this. At EOD they are handled by
#: square-off and broker order ids expire next session; the bound also keeps
#: long-stuck historical rows (e.g. the 2026-05-20 phantom) out of scope —
#: those need audited manual remediation, not a silent mutation here.
_MAX_EXECUTION_AGE_HOURS = 24


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
            total_mismatches += await _reconcile_order_status(session, cred)
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


async def _reconcile_order_status(
    session: AsyncSession, cred: BrokerCredential
) -> int:
    """Poll the broker for non-terminal live executions and persist the
    confirmed outcome (incident 2026-05-20, order ``222260520454106``).

    :func:`_reconcile_credential` only diffs open-position *sets* and never
    reads ``strategy_executions``; an entry left in TRANSIT/pending had no
    path to ever flip to COMPLETE/REJECTED. This pass closes that gap: for
    every non-terminal entry leg under ``cred`` placed within the last
    ``_MAX_EXECUTION_AGE_HOURS`` hours, ask the broker for the order's
    current status (plus fill qty / avg price when the adapter exposes them)
    and write it back, committing the change.

    The age bound deliberately excludes long-stuck historical rows — those
    need audited manual remediation, not a silent mutation here. Returns the
    count of executions that resolved to REJECTED/CANCELLED (a drift the
    operator should see); COMPLETE resolutions are normal progress and are
    not counted.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=_MAX_EXECUTION_AGE_HOURS)
    stmt = (
        select(StrategyExecution)
        .join(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
        .join(Strategy, Strategy.id == StrategySignal.strategy_id)
        .where(
            StrategyExecution.broker_credential_id == cred.id,
            StrategyExecution.broker_order_id.is_not(None),
            StrategyExecution.completed_at.is_(None),
            StrategyExecution.placed_at >= cutoff,
            Strategy.is_paper.is_(False),
        )
    )
    rows = list((await session.execute(stmt)).scalars().all())
    pending = [
        ex
        for ex in rows
        if (ex.broker_status or "").lower() not in _TERMINAL_BROKER_STATUS
    ]
    if not pending:
        return 0

    broker = await _build_broker(cred)
    if not await broker.is_session_valid():
        await broker.login()

    detail_cache: dict[str, dict[str, Any]] = {}
    drift = 0
    wrote = False
    for ex in pending:
        oid = ex.broker_order_id
        if oid is None:
            continue
        if oid not in detail_cache:
            try:
                detail_cache[oid] = await _fetch_order_detail(broker, oid)
            except Exception as exc:  # skip this leg, retry next tick.
                _logger.warning(
                    "reconciliation.order_status_failed",
                    cred_id=str(cred.id),
                    broker_order_id=oid,
                    error=str(exc),
                )
                continue
        detail = detail_cache[oid]
        status_val = detail["status"].value
        status_lc = status_val.lower()
        if status_lc not in _TERMINAL_BROKER_STATUS:
            continue  # still in flight — leave NULL, retry next tick.

        ex.broker_status = status_val
        ex.completed_at = datetime.now(UTC)
        if detail.get("avg_price") is not None:
            ex.price = detail["avg_price"]
        merged = dict(ex.broker_response or {})
        merged["reconciled"] = detail.get("raw")
        if detail.get("filled_qty") is not None:
            merged["filled_qty"] = detail["filled_qty"]
        ex.broker_response = merged
        if status_lc in ("rejected", "cancelled", "expired"):
            ex.error_code = ex.error_code or "BROKER_NOT_FILLED"
            ex.error_message = ex.error_message or f"reconciled: {status_val}"
            drift += 1
        wrote = True
        _logger.warning(
            "reconciliation.order_status_resolved",
            cred_id=str(cred.id),
            execution_id=str(ex.id),
            broker_order_id=oid,
            resolved_status=status_val,
            filled_qty=detail.get("filled_qty"),
        )

    if wrote:
        await session.commit()
    return drift


async def _fetch_order_detail(broker: Any, broker_order_id: str) -> dict[str, Any]:
    """Return ``{status, filled_qty, avg_price, raw}`` for an order.

    Prefers the adapter's richer ``get_order_detail`` (Dhan) and falls back
    to the interface-standard ``get_order_status`` (status only) for
    adapters that don't expose fills (e.g. Fyers).
    """
    getter = getattr(broker, "get_order_detail", None)
    if getter is not None:
        detail: dict[str, Any] = await getter(broker_order_id)
        return detail
    status = await broker.get_order_status(broker_order_id)
    return {"status": status, "filled_qty": None, "avg_price": None, "raw": None}


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

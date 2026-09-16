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
import time
import uuid
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

#: A position with lots still in the market. ``partial`` belongs here:
#: it means SOME lots were booked and the REST are still open at the
#: broker. Filtering on ``open`` alone (the behaviour until 2026-09-09)
#: made a row vanish from reconciliation the moment it took its first
#: partial — exactly when its remaining quantity stops matching the
#: original and drift matters most.
_LIVE_STATUSES = ("open", "partial")

#: Re-alert cadence for a drift signature that has not changed. A stale
#: row is a standing condition, not an event: without this the loop would
#: send the same CRITICAL every 60 seconds (60/hour), which is why the
#: alert was switched off entirely and then nobody was told anything.
_ALERT_REPEAT_SECONDS = 6 * 60 * 60

#: (user_id, broker) -> (signature, monotonic timestamp of last alert).
#: In-process; a restart re-alerts once, which is the safe direction.
_last_alert: dict[tuple[str, str], tuple[frozenset[tuple[str, str, int]], float]] = {}


def _norm_symbol(symbol: str) -> str:
    """Normalise a contract symbol for comparison ACROSS systems.

    We store ``BSE-SEP2026-FUT``; Dhan returns ``BSE-Sep2026-FUT``. The
    diff was a case-SENSITIVE set difference, so a row could never match
    its own broker leg — the same live position was reported in `db_only`
    AND `broker_only` on the same tick (observed 2026-09-07T05:01:17Z).
    Every mismatch it has ever printed for a correctly-tracked position
    was noise, which is its own reason nobody trusted the output.
    """
    return symbol.strip().upper()


def _broker_of(cred: BrokerCredential) -> str:
    """The broker name as a plain string, Enum or not."""
    return getattr(cred.broker_name, "value", str(cred.broker_name))


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
    """Active BrokerCredentials backing ≥1 strategy with ``is_paper=False``.

    Replaces the global-paper-mode short-circuit that pre-Fix #7 silenced
    reconciliation for live strategies in mixed-mode deployments (incident
    2026-05-20).

    ROTATION FALLBACK (2026-08-30) — mirrors
    ``strategy_executor._load_credential`` exactly.

    ``auto_login.py`` rotates the Dhan token nightly by DEACTIVATING the old
    credential row and INSERTING a new one, and it does NOT update
    ``strategies.broker_credential_id``. The executor has handled that since
    2026-05-03 by falling back to the active credential for the same
    ``(user_id, broker_name)``. This function did not, so its ``is_active``
    filter matched nothing the morning after any rotation: the loop woke every
    60s, found zero credentials, logged at DEBUG and returned — silently.

    That asymmetry is the bug. Trading kept working (the executor falls back)
    while reconciliation stopped (this did not), so nothing looked wrong from
    the outside and DB-vs-broker drift went unwatched. Found 2026-08-30 with the
    FK pointing at a deactivated row and the loop inert.

    The FK is deliberately NOT repointed here: that is a data change good for
    exactly one night, until the next rotation breaks it again.
    """
    # 1. The direct path — an FK that still points at an active credential.
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
    creds: dict[uuid.UUID, BrokerCredential] = {
        c.id: c for c in (await session.execute(stmt)).scalars().all()
    }

    # 2. FALLBACK — for every live strategy whose FK target is NOT active,
    #    resolve the newest active credential for the same
    #    (user_id, broker_name), exactly as the executor does.
    stale_stmt = (
        select(Strategy.user_id, Strategy.broker_credential_id)
        .where(Strategy.is_active.is_(True))
        .where(Strategy.is_paper.is_(False))
        .where(Strategy.broker_credential_id.is_not(None))
    )
    for user_id, cred_id in (await session.execute(stale_stmt)).all():
        if cred_id in creds:
            continue  # direct path already covered it
        pointed = await session.get(BrokerCredential, cred_id)
        if pointed is None:
            _logger.warning(
                "reconciliation.credential_missing",
                strategy_credential_id=str(cred_id),
                user_id=str(user_id),
            )
            continue
        fallback = (
            await session.execute(
                select(BrokerCredential)
                .where(
                    BrokerCredential.user_id == user_id,
                    BrokerCredential.broker_name == pointed.broker_name,
                    BrokerCredential.is_active.is_(True),
                )
                .order_by(BrokerCredential.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if fallback is None:
            # Genuinely no active credential — auto-login may have failed.
            # Loud, because it means reconciliation cannot run at all.
            _logger.warning(
                "reconciliation.no_active_credential",
                strategy_credential_id=str(cred_id),
                broker_name=getattr(pointed.broker_name, "value", str(pointed.broker_name)),
                user_id=str(user_id),
            )
            continue
        # Same event name + fields the executor logs, so one grep finds both.
        _logger.warning(
            "reconciliation.credential_rotated",
            strategy_credential_id=str(cred_id),
            active_credential_id=str(fallback.id),
            broker_name=getattr(pointed.broker_name, "value", str(pointed.broker_name)),
            user_id=str(user_id),
        )
        creds[fallback.id] = fallback

    return list(creds.values())


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
    #
    # SCOPE IS (user_id, broker_name), NOT the credential FK (2026-09-09).
    # ``auto_login`` mints a NEW credential row every weekday ~03:00 and
    # deactivates the old one; a position row keeps the id it was opened
    # with. Matching ``broker_credential_id == cred.id`` therefore made
    # every position invisible at the next rotation — the loop iterates
    # ACTIVE credentials, and no active credential is the one the row
    # points at. ``_list_credentials_backing_live_strategies`` already
    # resolves rotation this way for the CREDENTIAL; this query did not,
    # so the two halves disagreed and `db_only` was silently `[]`.
    # Observed on the phantom BUY 800: the row went invisible at the
    # 2026-09-08 03:00 rotation while still `open`, and stayed invisible.
    db_stmt = (
        select(StrategyPosition)
        .join(Strategy, Strategy.id == StrategyPosition.strategy_id)
        .join(
            BrokerCredential,
            BrokerCredential.id == StrategyPosition.broker_credential_id,
        )
        .where(
            StrategyPosition.user_id == cred.user_id,
            BrokerCredential.broker_name == cred.broker_name,
            StrategyPosition.status.in_(_LIVE_STATUSES),
            Strategy.is_paper.is_(False),
            # OWNER scope only (migration 034). A subscriber's PAPER position
            # reuses the owner strategy's credential as a placeholder, so on a
            # LIVE strategy it would otherwise show here as false `db_only`
            # drift (no broker leg) and fire a CRITICAL alert. Owner rows are
            # subscription_id NULL → byte-identical to today.
            StrategyPosition.subscription_id.is_(None),
        )
    )
    db_positions = list((await session.execute(db_stmt)).scalars().all())
    db_set: set[tuple[str, str, int]] = {
        (_norm_symbol(p.symbol), p.side.lower(), p.remaining_quantity)
        for p in db_positions
    }

    # ── Broker side ────────────────────────────────────────────────────
    broker = await _build_broker(cred)
    if not await broker.is_session_valid():
        await broker.login()
    broker_positions = await broker.get_positions()

    # Piggy-back the protective-stop read on the poll that is already here,
    # so /positions can show a stop that lives ONLY at the broker (an
    # invisible stop reads as no stop). Best effort by contract: this is a
    # display feature and is never allowed to disturb drift detection.
    try:
        from app.services import broker_fills, broker_resting_stops

        await broker_resting_stops.refresh_for_user(broker, cred.user_id)
        # The account's own fills, for orders placed OUTSIDE this platform
        # (pine_replica's resting stops, the founder's manual Dhan-app trades).
        # Internally throttled to ~15 minutes: the live account's Dhan quota is
        # shared with the trading engine, so this must not become a per-tick
        # read. Same best-effort contract as the stops above.
        await broker_fills.refresh_for_user(broker, cred.user_id)
    except Exception:  # noqa: BLE001 — display must never break safety.
        _logger.warning(
            "reconciliation.broker_display_reads_skipped", cred_id=str(cred.id)
        )
    broker_set: set[tuple[str, str, int]] = set()
    for bp in broker_positions:
        if bp.quantity == 0:
            continue  # closed leg, ignore
        side = "buy" if bp.quantity > 0 else "sell"
        broker_set.add((_norm_symbol(bp.symbol), side, abs(bp.quantity)))

    db_only = db_set - broker_set
    broker_only = broker_set - db_set
    mismatches = len(db_only) + len(broker_only)

    if mismatches == 0:
        return 0

    # Two different facts, deliberately no longer averaged into one
    # "drift" line:
    #   db_only     — WE think a position is open and the broker does NOT
    #                 have it. A STALE ROW. Actionable, and the exact
    #                 condition that hid the phantom BUY 800 for two days.
    #   broker_only — a position at the broker with no row of ours,
    #                 usually a manual trade placed in the broker's app.
    #                 Informational, and the source of the original spam.
    _logger.error(
        "reconciliation.drift",
        cred_id=str(cred.id),
        user_id=str(cred.user_id),
        broker=_broker_of(cred),
        db_only=sorted(db_only),
        broker_only=sorted(broker_only),
        stale_rows=len(db_only),
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
        except Exception:
            _logger.exception("reconciliation.reverse_phantom_alert_failed")
        await clear_flag(sym)

    settings = get_settings()

    # ── STALE ROWS — ON BY DEFAULT ───────────────────────────────────
    # This alert used to sit behind ``reconciliation_telegram_enabled``,
    # default OFF, because it fired EVERY tick. The real problem was not
    # the alert, it was the cadence and the conflation: a manual broker
    # position drifts forever, so an unconditional per-tick message is
    # 60/hour and the flag was the only way to stop it. Alerting on a
    # CHANGED signature (or once per 6h for a standing condition) makes
    # on-by-default safe, so a position we believe in that the broker
    # does not have can never again go two days without a word.
    if db_only:
        key = (str(cred.user_id), _broker_of(cred))
        signature = frozenset(db_only)
        now = time.monotonic()
        previous = _last_alert.get(key)
        should_speak = (
            previous is None
            or previous[0] != signature
            or (now - previous[1]) >= _ALERT_REPEAT_SECONDS
        )
        if should_speak:
            _last_alert[key] = (signature, now)
            try:
                from app.services import telegram_alerts as _alerts

                lines = "\n".join(
                    f"• `{sym}` {side} {qty}" for sym, side, qty in sorted(db_only)
                )
                await _alerts.send_alert(
                    _alerts.AlertLevel.CRITICAL,
                    (
                        "*STALE POSITION ROW* — TRADETRI shows these as OPEN, "
                        "the broker does NOT hold them:\n"
                        f"{lines}\n"
                        "Nothing closes these automatically. Check the broker, "
                        "then correct the row."
                    ),
                )
            except Exception:
                _logger.exception(
                    "reconciliation.stale_alert_failed", cred_id=str(cred.id)
                )

    # ── BROKER-ONLY ON A CONTRACT WE TRADE — ON BY DEFAULT ───────────
    #
    # 🔴 THE 2026-09-11 HOLE. Closing a stale position row by hand moved a
    # LIVE, unprotected short 200 BSE-SEP2026-FUT out of ``db_only`` (CRITICAL,
    # on by default) and into ``broker_only`` (WARNING, flag-gated OFF). The
    # divergence did not go away — it went quiet. The loop logged it every 60
    # seconds and told nobody, which is the same two-day silence the phantom
    # BUY 800 got, just through the other door.
    #
    # The original gate was right about ONE thing: the founder's own manual
    # option legs sit in this account permanently and would spam forever. So
    # the split is not "alert or don't", it is WHICH CONTRACT:
    #
    #   * a contract this platform has traded for this user  → OUR problem.
    #     An unmatched leg there means our record and the account disagree
    #     about a position the bot could act on. CRITICAL, on by default,
    #     deduped on a CHANGED signature exactly like the stale-row alert.
    #   * any other instrument → genuinely the founder's own manual book.
    #     Stays behind the flag, exactly as before.
    traded_symbols = {
        _norm_symbol(s)
        for s in (
            await session.execute(
                select(StrategyPosition.symbol)
                .join(Strategy, Strategy.id == StrategyPosition.strategy_id)
                .where(
                    StrategyPosition.user_id == cred.user_id,
                    Strategy.is_paper.is_(False),
                    StrategyPosition.subscription_id.is_(None),
                )
                .distinct()
            )
        ).scalars()
    }
    ours = {leg for leg in broker_only if leg[0] in traded_symbols}
    theirs = broker_only - ours

    if ours:
        key = (str(cred.user_id), f"{_broker_of(cred)}:broker_only")
        signature = frozenset(ours)
        now = time.monotonic()
        previous = _last_alert.get(key)
        should_speak = (
            previous is None
            or previous[0] != signature
            or (now - previous[1]) >= _ALERT_REPEAT_SECONDS
        )
        if should_speak:
            _last_alert[key] = (signature, now)
            try:
                from app.services import telegram_alerts as _alerts

                lines = "\n".join(f"• `{sym}` {side} {qty}" for sym, side, qty in sorted(ours))
                await _alerts.send_alert(
                    _alerts.AlertLevel.CRITICAL,
                    (
                        "🚨 *UNTRACKED POSITION ON A CONTRACT WE TRADE* — the "
                        "broker holds these, TRADETRI has NO open row for "
                        "them:\n"
                        f"{lines}\n"
                        "Nothing of ours is protecting or watching these. "
                        "Check the broker, then correct the record."
                    ),
                )
            except Exception:
                _logger.exception(
                    "reconciliation.broker_only_alert_failed", cred_id=str(cred.id)
                )

    # ── BROKER-ONLY ELSEWHERE — still flag-gated ─────────────────────
    # Manual positions placed in the broker's own app are a normal fact of
    # this account, not a fault, and they drift on every tick forever.
    # They stay behind the flag; the ERROR log above always records them.
    if theirs and settings.reconciliation_telegram_enabled:
        try:
            from app.services import telegram_alerts as _alerts

            await _alerts.send_alert(
                _alerts.AlertLevel.WARNING,
                (
                    f"Broker-only positions (no TRADETRI row)\n"
                    f"user=`{cred.user_id}`\n"
                    f"broker_only=`{sorted(theirs)}`"
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

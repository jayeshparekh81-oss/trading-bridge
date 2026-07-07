"""Celery task for async strategy-signal execution.

Bug #2 fix (incident 2026-05-20): TradingView marks webhook delivery
"failed — timed out" at ~5 s. The old strategy webhook ran the full
pipeline (AI validation → broker HTTP call → Telegram → DB writes)
inside the request handler, regularly exceeding TV's timeout and
triggering retries (which surface as duplicate signals).

Architecture after the refactor:

    POST /api/webhook/strategy/{token}
        ├─ FAST path (webhook):
        │     validate + idempotency + persist StrategySignal
        │     → execute_signal_async.delay(signal_id, action_kind)
        │     → return 202 in <200 ms
        │
        └─ WORKER path (Celery, this module):
              execute_signal_async picks up from the Redis-backed queue
              → AI validator → strategy_executor → broker → Telegram
              → final StrategySignal.status update

Idempotency is unaffected: the webhook still claims the Redis SET NX
slot BEFORE persisting the signal row, so TradingView retries that
arrive while the worker is still busy are silently absorbed.

The two ``_process_*`` coroutines below were lifted verbatim from
``app.api.strategy_webhook`` so the behaviour preserved by Bug #3/4/5/6/7/8
fixes is identical — only the dispatch trampoline changed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.async_bridge import run_async as _run
from app.core.exceptions import BrokerError, DuplicateOrderSuppressedError
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.strategy_signal import StrategySignal
from app.strategy_engine.instrument_router import (
    CASH,
    OPTIONS,
    resolve_instrument_type,
)
from app.tasks.celery_app import celery_app

logger = get_logger("app.tasks.signal_execution")


# ═══════════════════════════════════════════════════════════════════════
# Sync ↔ async bridge
# ═══════════════════════════════════════════════════════════════════════
#
# ``_run`` is the shared :func:`app.core.async_bridge.run_async` (imported
# above). It reuses ONE persistent event loop per worker process so the cached
# Redis / DB connections stay bound to a live loop across tasks. The previous
# per-task ``asyncio.run`` created a fresh loop every call, which left the
# process-wide ``@lru_cache`` clients bound to a closed loop and raised
# "Event loop is closed" on ~every other task. See async_bridge for the full
# write-up (incident 2026-05-24).


# ═══════════════════════════════════════════════════════════════════════
# Public Celery task — entry point dispatched from the webhook
# ═══════════════════════════════════════════════════════════════════════


#: Lowercase action tags accepted by :func:`execute_signal_async`. The
#: webhook normalises the canonical Pydantic action to one of these
#: before dispatching, so the worker never has to re-translate.
ACTION_ENTRY = "entry"
ACTION_PARTIAL = "partial"
ACTION_EXIT = "exit"
ACTION_SL_HIT = "sl_hit"

_VALID_ACTION_KINDS: frozenset[str] = frozenset(
    {ACTION_ENTRY, ACTION_PARTIAL, ACTION_EXIT, ACTION_SL_HIT}
)


@celery_app.task(
    bind=True,
    name="app.tasks.signal_execution.execute_signal_async",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def execute_signal_async(
    self: Any, signal_id: str, action_kind: str = ACTION_ENTRY
) -> dict[str, str]:
    """Run the heavy strategy-execution chain for a persisted signal.

    ``signal_id`` is the StrategySignal UUID (string-encoded so Celery's
    JSON serialiser stays happy). ``action_kind`` decides which branch
    of the pipeline runs:

    * ``entry`` — AI validation + strategy_executor + broker order +
      post-trade kill-switch hooks (Black-Swan Shield, Trade DNA, and
      Probability Engine all run in the same order as before).
    * ``partial`` / ``exit`` / ``sl_hit`` — direct-exit handler;
      AI validation skipped (Pine already decided).

    Retries up to 3× with a 5 s delay for transient errors (DB
    connection drops, broker network blips). Permanent failures are
    logged and the StrategySignal.status is left in ``failed``.
    """
    if action_kind not in _VALID_ACTION_KINDS:
        logger.error(
            "signal_execution.invalid_action_kind",
            signal_id=signal_id,
            action_kind=action_kind,
        )
        return {"status": "error", "reason": f"invalid action_kind={action_kind}"}

    try:
        if action_kind == ACTION_ENTRY:
            _run(_process_entry(signal_id))
        else:
            _run(_process_direct_exit(signal_id, action_kind))
        return {"status": "ok", "signal_id": signal_id, "action_kind": action_kind}
    except Exception as exc:  # noqa: BLE001 — surface every error to Celery retry
        logger.exception(
            "signal_execution.task_failed",
            signal_id=signal_id,
            action_kind=action_kind,
        )
        # Retry only for transient-looking errors. DB/network blips =
        # try again; ValueError / TypeError = permanent, no retry.
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return {"status": "error", "reason": str(exc)}
        raise self.retry(exc=exc) from exc


# ═══════════════════════════════════════════════════════════════════════
# Worker-side pipeline — lifted from app.api.strategy_webhook
# (Bug #3 / #4 / #5 / #6 / #7 / #8 fixes preserved verbatim)
# ═══════════════════════════════════════════════════════════════════════


async def _process_entry(signal_id: str) -> None:
    """Run AI validator → executor for an ENTRY signal.

    Owns its own DB session — the webhook's request session is long
    closed by the time this worker fires. Errors are logged + surfaced
    via Telegram CRITICAL alerts, never re-raised here (the Celery task
    wrapper decides whether to retry based on the exception type).
    """
    from app.db.session import get_sessionmaker
    from app.schemas.ai_decision import AIDecisionStatus
    from app.services.ai_validator import validate_signal
    from app.services.kill_switch_service import kill_switch_service
    from app.services.strategy_executor import (
        StrategyExecutorError,
        place_strategy_orders,
    )

    maker = get_sessionmaker()
    sid = UUID(signal_id)
    try:
        async with maker() as session:
            sig = await session.get(StrategySignal, sid)
            if sig is None:
                logger.warning("signal_execution.signal_missing", signal_id=signal_id)
                return
            strategy = await session.get(Strategy, sig.strategy_id)
            if strategy is None or not strategy.is_active:
                sig.status = "failed"
                sig.notes = "strategy missing or inactive"
                await session.commit()
                return

            sig.status = "validating"
            await session.commit()

            # Black-Swan Anomaly Shield (W3.1) — ENTRY-block only.
            from app.services import anomaly_shield_service

            shield_indicators = (sig.raw_payload or {}).get("indicators") or {}
            shield_result = None
            dna_result = None

            if anomaly_shield_service.is_enabled():
                await anomaly_shield_service.record_indicator_bar(
                    strategy.id, shield_indicators
                )

                if await anomaly_shield_service.check_and_consume_release(strategy.id):
                    from app.services import telegram_alerts as _alerts

                    await _alerts.send_alert(
                        _alerts.AlertLevel.INFO,
                        "✅ Black-Swan Shield released — entries resumed.",
                    )

                if await anomaly_shield_service.is_block_active(strategy.id):
                    sig.status = "rejected"
                    sig.ai_decision = AIDecisionStatus.REJECTED.value
                    sig.ai_reasoning = (
                        "Black-Swan Shield active: anomaly cooldown in effect"
                    )
                    sig.ai_confidence = Decimal("0")
                    sig.validated_at = datetime.now(UTC)
                    sig.processed_at = datetime.now(UTC)
                    await session.commit()
                    logger.info(
                        "anomaly_shield.entry_blocked_cooldown",
                        signal_id=signal_id,
                        strategy_id=str(strategy.id),
                    )
                    return

                shield_result = await anomaly_shield_service.evaluate(
                    strategy.id, shield_indicators
                )
                if shield_result.tripped:
                    cooldown_secs = await anomaly_shield_service.activate_block(
                        strategy.id
                    )
                    sig.status = "rejected"
                    sig.ai_decision = AIDecisionStatus.REJECTED.value
                    sig.ai_reasoning = (
                        f"Black-Swan Shield TRIPPED — composite "
                        f"{shield_result.composite_score:.1f}/100, "
                        f"{len(shield_result.extreme_indicators)} extreme "
                        f"indicators (cooldown {cooldown_secs // 60}m)"
                    )
                    sig.ai_confidence = Decimal("0")
                    sig.validated_at = datetime.now(UTC)
                    sig.processed_at = datetime.now(UTC)
                    await session.commit()
                    logger.warning(
                        "anomaly_shield.tripped",
                        signal_id=signal_id,
                        strategy_id=str(strategy.id),
                        composite=shield_result.composite_score,
                        extreme_count=len(shield_result.extreme_indicators),
                        bars=shield_result.bars_collected,
                    )
                    from app.services import telegram_alerts as _alerts

                    top_extreme = ", ".join(
                        f"{e['indicator']}(z={e['z']:.1f})"
                        for e in shield_result.extreme_indicators[:5]
                    )
                    await _alerts.send_alert(
                        _alerts.AlertLevel.WARNING,
                        f"🦢 *Black-Swan Shield TRIPPED*\n"
                        f"Strategy: `{strategy.id}`\n"
                        f"Composite: `{shield_result.composite_score:.1f}/100`\n"
                        f"Extreme: {top_extreme}\n"
                        f"Cooldown: `{cooldown_secs // 60}m`",
                    )
                    return

            # Trade DNA Sequencing (W3.2) — advisory only.
            from app.services import trade_dna_service

            if trade_dna_service.is_enabled() and sig.action == "ENTRY":
                dna_side = str((sig.raw_payload or {}).get("side") or "").lower()
                if dna_side in ("long", "short"):
                    try:
                        dna_result = await trade_dna_service.evaluate(
                            session, strategy.id, dna_side, shield_indicators,
                        )
                        payload = dict(sig.raw_payload or {})
                        payload["_dna"] = dna_result.to_payload_dict()
                        sig.raw_payload = payload
                        logger.info(
                            "trade_dna.evaluated",
                            signal_id=signal_id,
                            strategy_id=str(strategy.id),
                            side=dna_side,
                            score=dna_result.score,
                            win_prob=dna_result.win_prob,
                            confidence=dna_result.confidence,
                            winners=dna_result.winners,
                            losers=dna_result.losers,
                            sample_size=dna_result.sample_size,
                            note=dna_result.note,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "trade_dna.evaluation_failed",
                            signal_id=signal_id,
                            strategy_id=str(strategy.id),
                            error=str(exc),
                        )

            # Predictive Probability Engine (W3.3) — advisory only.
            from app.services import probability_engine

            if probability_engine.is_enabled() and sig.action == "ENTRY":
                prob_result = probability_engine.compute(dna_result, shield_result)
                payload = dict(sig.raw_payload or {})
                payload["_probability"] = prob_result.to_payload_dict()
                sig.raw_payload = payload
                logger.info(
                    "probability_engine.evaluated",
                    signal_id=signal_id,
                    strategy_id=str(strategy.id),
                    win_probability=prob_result.win_probability,
                    confidence_pct=prob_result.confidence_pct,
                    confidence_band=prob_result.confidence_band,
                    expected_rr=prob_result.expected_rr,
                    recommendation=prob_result.recommendation,
                    note=prob_result.note,
                )

            decision = await validate_signal(sig, strategy)
            sig.ai_decision = decision.decision.value
            sig.ai_reasoning = decision.reasoning
            sig.ai_confidence = decision.confidence
            sig.validated_at = datetime.now(UTC)

            if decision.decision is AIDecisionStatus.REJECTED:
                sig.status = "rejected"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                return

            sig.status = "executing"
            await session.commit()

            # ── Instrument-router (Module #2) ───────────────────────────────
            # Branch on instrument type. FUTURES (the live BSE/CDSL/ANGELONE
            # case — strategy_json IS NULL) takes the existing executor path
            # below, VERBATIM. OPTIONS/CASH are recognised but their executors
            # don't exist yet → inert skip+log, no execution. Any unexpected
            # value defensively falls through to the FUTURES path.
            instrument = resolve_instrument_type(strategy)
            if instrument in (OPTIONS, CASH):
                logger.warning(
                    "signal_execution.instrument_not_implemented",
                    signal_id=signal_id,
                    strategy_id=str(strategy.id),
                    instrument=instrument,
                    seam="entry",
                )
                sig.status = "skipped"
                sig.notes = (
                    f"{instrument} execution not yet implemented — skipped"
                )
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                return

            from app.services import telegram_alerts as _alerts

            try:
                result = await place_strategy_orders(
                    session,
                    signal=sig,
                    strategy=strategy,
                    recommended_lots=decision.recommended_lots,
                )
                sig.status = "executed"
                sig.notes = (
                    f"position_id={result.position_id} "
                    f"broker_order_id={result.broker_order_id}"
                )
                sig.processed_at = datetime.now(UTC)
                await session.commit()

                # Fix #6 — status-driven single Telegram alert.
                broker_status_lc = (result.broker_status or "unknown").lower()
                _alert_body = (
                    f"`{sig.symbol}` {sig.action} qty=`{sig.quantity or '?'}` "
                    f"order=`{result.broker_order_id}` "
                    f"position=`{result.position_id}` "
                    f"broker_status=`{broker_status_lc}` "
                    f"paper=`{result.paper_mode}`"
                )
                if result.paper_mode:
                    await _alerts.send_alert(
                        _alerts.AlertLevel.INFO,
                        "📝 *PAPER MODE* — Order simulated\n" + _alert_body,
                    )
                elif broker_status_lc in ("complete", "traded", "executed"):
                    await _alerts.send_alert(
                        _alerts.AlertLevel.SUCCESS,
                        "✅ Order filled (broker confirmed)\n" + _alert_body,
                    )
                elif broker_status_lc in ("pending", "transit", "open"):
                    await _alerts.send_alert(
                        _alerts.AlertLevel.INFO,
                        "⏳ Order placed (awaiting fill)\n" + _alert_body,
                    )
                else:
                    await _alerts.send_alert(
                        _alerts.AlertLevel.WARNING,
                        f"⚠️ Order placed but broker_status=`{broker_status_lc}` "
                        "— verify manually\n" + _alert_body,
                    )

                # Post-trade hooks — Gate C + Gate E auto-trip.
                # CRITICAL: failures here MUST NOT undo a successful order.
                try:
                    await kill_switch_service.increment_daily_trades(sig.user_id)
                    await kill_switch_service.check_and_trigger(
                        sig.user_id, session
                    )
                    await session.commit()
                except Exception:
                    logger.exception(
                        "signal_execution.post_trade_hook_failed",
                        signal_id=signal_id,
                        user_id=str(sig.user_id),
                    )
                    await session.rollback()
            except DuplicateOrderSuppressedError:
                # A prior attempt already placed (or attempted) this order;
                # the idempotency slot is held. Do NOT re-place, mark failed,
                # or retry — the original attempt owns the outcome and the
                # reconciliation loop resolves the true broker status. Benign.
                logger.warning(
                    "signal_execution.duplicate_suppressed",
                    signal_id=signal_id,
                    action_kind="entry",
                )
                sig.notes = "duplicate_suppressed: order already attempted"
                await session.commit()
                return
            except StrategyExecutorError as exc:
                sig.status = "failed"
                sig.notes = f"executor_error: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                await _alerts.send_alert(
                    _alerts.AlertLevel.WARNING,
                    f"Order rejected\n`{sig.symbol}` {sig.action}: {exc}",
                )
            except BrokerError as exc:
                from app.core.exceptions import BrokerOrderRejectedError

                sig.status = "failed"
                sig.notes = f"{type(exc).__name__}: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                if isinstance(exc, BrokerOrderRejectedError):
                    await _alerts.send_alert(
                        _alerts.AlertLevel.CRITICAL,
                        f"🚨 *BROKER REJECTED*\n"
                        f"`{sig.symbol}` {sig.action}: {exc.reason}\n"
                        f"signal=`{signal_id}`",
                    )
                else:
                    await _alerts.send_alert(
                        _alerts.AlertLevel.CRITICAL,
                        f"🚨 *Broker error*\n"
                        f"`{sig.symbol}` {sig.action}: {exc}\n"
                        f"signal=`{signal_id}`",
                    )
            except Exception as exc:
                logger.exception(
                    "signal_execution.executor_unexpected", signal_id=signal_id
                )
                sig.status = "failed"
                sig.notes = f"unexpected: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                await _alerts.send_alert(
                    _alerts.AlertLevel.CRITICAL,
                    f"Backend error in executor\nsignal=`{signal_id}` "
                    f"user=`{sig.user_id}` error=`{type(exc).__name__}: {exc}`",
                )
    except Exception:
        logger.exception(
            "signal_execution.entry_outer_failed", signal_id=signal_id
        )
        try:
            from app.services import telegram_alerts as _alerts2

            await _alerts2.send_alert(
                _alerts2.AlertLevel.CRITICAL,
                f"Backend error in signal_execution worker\n"
                f"signal=`{signal_id}` (DB/session-level — see logs)",
            )
        except Exception:
            pass
        raise


async def _process_direct_exit(signal_id: str, action_kind: str) -> None:
    """Run the direct-exit handler for a PARTIAL / EXIT / SL_HIT signal.

    ``action_kind`` is one of ``partial``, ``exit``, ``sl_hit``. SL_HIT
    and EXIT both call :func:`app.services.direct_exit.execute_exit`
    with distinct ``leg_role`` values for audit clarity. AI validation
    is intentionally skipped — Pine already decided.
    """
    from app.db.session import get_sessionmaker
    from app.services import direct_exit
    from app.services import telegram_alerts as _alerts
    from app.services.strategy_executor import StrategyExecutorError

    maker = get_sessionmaker()
    sid = UUID(signal_id)
    try:
        async with maker() as session:
            sig = await session.get(StrategySignal, sid)
            if sig is None:
                logger.warning(
                    "signal_execution.direct_exit_signal_missing",
                    signal_id=signal_id,
                )
                return
            strategy = await session.get(Strategy, sig.strategy_id)
            if strategy is None or not strategy.is_active:
                sig.status = "failed"
                sig.notes = "strategy missing or inactive"
                await session.commit()
                return

            sig.status = "executing"
            await session.commit()

            # ── Instrument-router (Module #2) ───────────────────────────────
            # FUTURES takes the existing direct-exit dispatch below, VERBATIM.
            # OPTIONS/CASH are recognised but unimplemented → inert skip+log,
            # uniform for ALL exit actions (PARTIAL/EXIT/SL_HIT) so no exit
            # leaks to direct_exit. Any unexpected value defensively falls
            # through to the FUTURES path.
            instrument = resolve_instrument_type(strategy)
            if instrument in (OPTIONS, CASH):
                logger.warning(
                    "signal_execution.instrument_not_implemented",
                    signal_id=signal_id,
                    strategy_id=str(strategy.id),
                    instrument=instrument,
                    seam="exit",
                    action_kind=action_kind,
                )
                sig.status = "skipped"
                sig.notes = f"{instrument} exit not yet implemented — skipped"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                return

            try:
                if action_kind == ACTION_PARTIAL:
                    result = await direct_exit.execute_partial(
                        session, signal=sig, strategy=strategy
                    )
                elif action_kind == ACTION_EXIT:
                    result = await direct_exit.execute_exit(
                        session,
                        signal=sig,
                        strategy=strategy,
                        leg_role="direct_exit",
                    )
                elif action_kind == ACTION_SL_HIT:
                    result = await direct_exit.execute_exit(
                        session,
                        signal=sig,
                        strategy=strategy,
                        leg_role="direct_sl",
                    )
                else:
                    raise StrategyExecutorError(
                        f"Unknown direct-exit action_kind {action_kind!r}"
                    )

                if result["status"] == "ignored":
                    sig.status = "ignored"
                    sig.notes = f"direct_exit ignored: {result['reason']}"
                else:
                    sig.status = "executed"
                    sig.notes = (
                        f"close_qty={result['close_qty']} "
                        f"remaining={result['remaining']} "
                        f"position_status={result['position_status']} "
                        f"broker_order_id={result['broker_order_id']}"
                    )
                sig.processed_at = datetime.now(UTC)
                await session.commit()
            except DuplicateOrderSuppressedError:
                # Prior attempt already placed (or attempted) this close;
                # slot held. No re-place, no retry — reconciliation resolves
                # the true broker status. Benign no-op.
                logger.warning(
                    "signal_execution.duplicate_suppressed",
                    signal_id=signal_id,
                    action_kind=action_kind,
                )
                sig.notes = "duplicate_suppressed: close already attempted"
                await session.commit()
                return
            except StrategyExecutorError as exc:
                sig.status = "failed"
                sig.notes = f"direct_exit_error: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                await _alerts.send_alert(
                    _alerts.AlertLevel.WARNING,
                    f"Direct-exit rejected\n"
                    f"`{sig.symbol}` {sig.action} (kind={action_kind}): {exc}",
                )
            except Exception as exc:
                logger.exception(
                    "signal_execution.direct_exit_unexpected",
                    signal_id=signal_id,
                    action_kind=action_kind,
                )
                sig.status = "failed"
                sig.notes = f"unexpected: {exc}"
                sig.processed_at = datetime.now(UTC)
                await session.commit()
                await _alerts.send_alert(
                    _alerts.AlertLevel.CRITICAL,
                    f"Backend error in direct-exit handler\n"
                    f"signal=`{signal_id}` user=`{sig.user_id}` "
                    f"kind=`{action_kind}` "
                    f"error=`{type(exc).__name__}: {exc}`",
                )
    except Exception:
        logger.exception(
            "signal_execution.direct_exit_outer_failed",
            signal_id=signal_id,
            action_kind=action_kind,
        )
        raise


# ═══════════════════════════════════════════════════════════════════════
# Dispatch helper — single import surface for the webhook
# ═══════════════════════════════════════════════════════════════════════


def dispatch_signal(signal_id: str, action_kind: str) -> None:
    """Push a persisted signal onto the Celery queue for async execution.

    Single indirection so the webhook never imports ``execute_signal_async``
    directly — keeps the import graph shallow and gives tests a single
    monkeypatch target. With ``task_always_eager=True`` (test setting)
    ``.delay()`` runs synchronously in-process, which is exactly the
    behaviour the existing integration tests rely on.
    """
    if action_kind not in _VALID_ACTION_KINDS:
        raise ValueError(
            f"action_kind must be one of {sorted(_VALID_ACTION_KINDS)}, got {action_kind!r}"
        )
    execute_signal_async.delay(signal_id, action_kind)


__all__ = [
    "ACTION_ENTRY",
    "ACTION_EXIT",
    "ACTION_PARTIAL",
    "ACTION_SL_HIT",
    "dispatch_signal",
    "execute_signal_async",
]

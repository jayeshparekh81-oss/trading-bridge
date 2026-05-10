"""Live-orders SafetyChain — fail-fast orchestrator.

Runs the seven safety checks in :mod:`safety_checks` in the locked
order below. Stops at the first failure and reports it as
``blocking_check``; the ``checks`` tuple records every check that
*executed*, so a fail-fast block produces a shorter list than an
all-pass run.

Locked order (highest priority first):

    1. auto_kill_switch     — platform safety overrides everything else.
    2. paper_sessions       — strategy maturity gate.
    3. trust_score          — backtest reliability.
    4. truth_score          — fake-backtest detection.
    5. live_trading_enabled — global + per-user opt-in (defence in depth).
    6. broker_connection    — at least one real broker linked.
    7. risk_engine_precheck — DEFERRED (fail-open, see safety_checks).

Re-ordering is a load-bearing change: kill-switch first means an
incident in progress never hits a downstream gate that might leak
information about the user's strategy state. ``Phase 8B-1 DESIGN``
Section 2.2 pinned this order; tests pin it again so a refactor that
shuffles the list trips a regression.

The orchestrator is intentionally narrow:

    * No network I/O of its own — every check owns its read.
    * No mutation — read-only over Redis + DB. Audit emission is
      the live-orders router's job (Phase 8B-2 Part 2).
    * Pure stdlib + Pydantic + SQLAlchemy on direct imports;
      ``test_safety_chain_does_not_import_forbidden_modules`` AST-
      inspects the package to keep that property honest.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.strategy_engine.live_orders import safety_checks
from app.strategy_engine.live_orders.models import (
    SafetyChainResult,
    SafetyCheckResult,
)


async def run_safety_chain(
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    db_session: AsyncSession,
) -> SafetyChainResult:
    """Execute the SafetyChain for one (user, strategy) pair.

    Returns a :class:`SafetyChainResult` populated with every check
    that ran; on the first failure later checks are skipped (their
    entries are absent from the ``checks`` tuple). ``checked_at`` is
    stamped with ``datetime.now(UTC)`` once at the start so callers
    can correlate parallel chain runs.

    Args:
        user_id: Platform user placing the would-be order.
        strategy_id: Strategy the order would execute against.
        db_session: Open :class:`AsyncSession`. The chain reads only —
            it never commits and never mutates a row.

    Returns:
        :class:`SafetyChainResult`. Inspect ``all_passed`` for the
        single boolean the router uses; iterate ``checks`` for the
        UI's pre-flight panel; read ``blocking_check`` for the modal's
        primary message.
    """
    checked_at = datetime.now(UTC)
    results: list[SafetyCheckResult] = []
    blocking: SafetyCheckResult | None = None

    # 1. Auto Kill Switch — Redis read.
    result = await safety_checks.check_auto_kill_switch(user_id=user_id)
    results.append(result)
    if not result.passed:
        return _build_result(
            user_id=user_id,
            strategy_id=strategy_id,
            checked_at=checked_at,
            results=results,
            blocking=result,
        )

    # 2. Paper sessions — DB read.
    result = await safety_checks.check_paper_sessions(
        db=db_session, user_id=user_id, strategy_id=strategy_id
    )
    results.append(result)
    if not result.passed:
        return _build_result(
            user_id=user_id,
            strategy_id=strategy_id,
            checked_at=checked_at,
            results=results,
            blocking=result,
        )

    # 3. Trust score — DB read (cached scores).
    result = await safety_checks.check_trust_score(
        db=db_session, strategy_id=strategy_id
    )
    results.append(result)
    if not result.passed:
        return _build_result(
            user_id=user_id,
            strategy_id=strategy_id,
            checked_at=checked_at,
            results=results,
            blocking=result,
        )

    # 4. Truth score — DB read (cached scores; same row as trust).
    result = await safety_checks.check_truth_score(
        db=db_session, strategy_id=strategy_id
    )
    results.append(result)
    if not result.passed:
        return _build_result(
            user_id=user_id,
            strategy_id=strategy_id,
            checked_at=checked_at,
            results=results,
            blocking=result,
        )

    # 5. Live trading enabled — feature flag + DB column.
    result = await safety_checks.check_live_trading_enabled(
        db=db_session, user_id=user_id
    )
    results.append(result)
    if not result.passed:
        return _build_result(
            user_id=user_id,
            strategy_id=strategy_id,
            checked_at=checked_at,
            results=results,
            blocking=result,
        )

    # 6. Broker connection — DB count of active credentials.
    result = await safety_checks.check_broker_connection(
        db=db_session, user_id=user_id
    )
    results.append(result)
    if not result.passed:
        return _build_result(
            user_id=user_id,
            strategy_id=strategy_id,
            checked_at=checked_at,
            results=results,
            blocking=result,
        )

    # 7. Risk Engine pre-check — DEFERRED, fail-open.
    result = await safety_checks.check_risk_engine_precheck(
        db=db_session, user_id=user_id, strategy_id=strategy_id
    )
    results.append(result)
    if not result.passed:
        blocking = result

    return _build_result(
        user_id=user_id,
        strategy_id=strategy_id,
        checked_at=checked_at,
        results=results,
        blocking=blocking,
    )


def _build_result(
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    checked_at: datetime,
    results: list[SafetyCheckResult],
    blocking: SafetyCheckResult | None,
) -> SafetyChainResult:
    """Wrap the per-check list in the immutable aggregate."""
    return SafetyChainResult(
        all_passed=blocking is None,
        checks=tuple(results),
        blocking_check=blocking,
        user_id=user_id,
        strategy_id=strategy_id,
        checked_at=checked_at,
    )


__all__ = ["run_safety_chain"]

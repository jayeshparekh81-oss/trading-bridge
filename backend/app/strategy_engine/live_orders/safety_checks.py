"""Individual SafetyChain checks for live order placement.

Each function is a tiny, focused gate over a single existing module's
state. The pattern:

    async def check_<name>(db, user_id, strategy_id) -> SafetyCheckResult

All checks follow the same contract:

    * Read-only — they never mutate any table or Redis key.
    * Cheap — at most one DB query or one Redis read.
    * Hinglish reason — populates ``reason_hinglish`` with the
      user-facing message. ``details`` carries engineer-facing debug
      context (counts, scores, etc.).
    * Defensive — when an underlying module is absent or unimplemented,
      the check fails OPEN (returns ``passed=True``) with a clear
      ``reason_hinglish`` noting the deferral, so the chain doesn't
      block live trading on infrastructure that isn't built yet. The
      :mod:`safety_chain` orchestrator runs them in order and short-
      circuits on the first hard failure.

Discovery sources (verified by reading existing modules):

    1. auto_kill_switch  → ``redis_client.get_kill_switch_status``
    2. paper_sessions    → ``paper_trading.store.get_completed_sessions_count``
    3. trust_score       → ``strategy_scores.inspect_cached_scores``
    4. truth_score       → same as 3 (single read shared between checks)
    5. live_trading      → ``user_flags.is_live_trading_enabled_for_user``
    6. broker_connection → DB row check on ``broker_credentials``
    7. risk_engine       → DEFERRED (no module yet — fail-open with note)
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis_client
from app.db.models.broker_credential import BrokerCredential
from app.schemas.broker import BrokerName
from app.strategy_engine.broker_guard.constants import (
    MIN_TRUST_SCORE_FOR_LIVE,
    MIN_TRUTH_SCORE_FOR_LIVE,
)
from app.strategy_engine.live_orders.models import SafetyCheckResult
from app.strategy_engine.live_orders.strategy_scores import (
    CachedScoresInspection,
    CachedScoresState,
    inspect_cached_scores,
)
from app.strategy_engine.live_orders.user_flags import (
    is_live_trading_enabled_for_user,
)
from app.strategy_engine.paper_trading import store as paper_store
from app.strategy_engine.paper_trading.engine import MIN_COMPLETED_SESSIONS

#: Brokers whose adapter is fully implemented (not a stub). Mirrors
#: ``app.brokers.registry.FULLY_IMPLEMENTED`` but without importing it
#: — registry transitively pulls ``httpx`` via the concrete broker
#: classes, which would violate the SafetyChain's no-network rule.
_FULLY_IMPLEMENTED_BROKERS: frozenset[BrokerName] = frozenset(
    {BrokerName.FYERS, BrokerName.DHAN}
)


# ─── 1. Auto Kill Switch ──────────────────────────────────────────────


async def check_auto_kill_switch(
    *, user_id: uuid.UUID
) -> SafetyCheckResult:
    """Fail when the user's Auto Kill Switch is currently TRIPPED.

    State is held in Redis at ``kill_switch:{user_id}`` — written by
    :class:`KillSwitchService.check_and_trigger` *before* it fires
    brokers, so any live order arriving mid-trip is correctly rejected.
    """
    status = await redis_client.get_kill_switch_status(user_id)
    tripped = status == redis_client.KILL_SWITCH_TRIPPED
    if tripped:
        return SafetyCheckResult(
            check_name="auto_kill_switch",
            passed=False,
            reason_hinglish=(
                "Auto Kill Switch active hai. Aaj ka loss budget exhaust "
                "ho gaya, kal try karo."
            ),
            details={"redis_status": status},
        )
    return SafetyCheckResult(
        check_name="auto_kill_switch",
        passed=True,
        reason_hinglish="Auto Kill Switch inactive hai.",
        details={"redis_status": status},
    )


# ─── 2. Paper sessions ────────────────────────────────────────────────


async def check_paper_sessions(
    *, db: AsyncSession, user_id: uuid.UUID, strategy_id: uuid.UUID
) -> SafetyCheckResult:
    """Fail when fewer than 7 paper sessions have been completed.

    The launch plan locks the count at ``MIN_COMPLETED_SESSIONS = 7``
    distinct trading days per strategy. Migration 010 made the count
    survive engine restarts; this check reads it from the DB.
    """
    count = await paper_store.get_completed_sessions_count(
        db, user_id=user_id, strategy_id=strategy_id
    )
    if count >= MIN_COMPLETED_SESSIONS:
        return SafetyCheckResult(
            check_name="paper_sessions",
            passed=True,
            reason_hinglish=(
                f"{count} paper sessions complete — live ke liye kaafi hai."
            ),
            details={
                "completed": count,
                "required": MIN_COMPLETED_SESSIONS,
            },
        )
    remaining = MIN_COMPLETED_SESSIONS - count
    return SafetyCheckResult(
        check_name="paper_sessions",
        passed=False,
        reason_hinglish=(
            f"Sirf {count}/{MIN_COMPLETED_SESSIONS} paper sessions complete. "
            f"{remaining} aur karo before going live."
        ),
        details={
            "completed": count,
            "required": MIN_COMPLETED_SESSIONS,
            "remaining": remaining,
        },
    )


# ─── 3. Trust score ───────────────────────────────────────────────────


async def check_trust_score(
    *, db: AsyncSession, strategy_id: uuid.UUID
) -> SafetyCheckResult:
    """Fail when cached Trust score is missing, stale, or below 70.

    Reuses the inspection result so :func:`check_truth_score` can
    accept the same snapshot and avoid a duplicate read; see
    :func:`check_trust_and_truth` for the combined entry point.
    """
    inspection = await inspect_cached_scores(db, strategy_id)
    return _trust_result_from_inspection(inspection)


# ─── 4. Truth score ───────────────────────────────────────────────────


async def check_truth_score(
    *, db: AsyncSession, strategy_id: uuid.UUID
) -> SafetyCheckResult:
    """Fail when cached Truth score is missing, stale, or below 55."""
    inspection = await inspect_cached_scores(db, strategy_id)
    return _truth_result_from_inspection(inspection)


# ─── 5. Live trading enabled ──────────────────────────────────────────


async def check_live_trading_enabled(
    *, db: AsyncSession, user_id: uuid.UUID
) -> SafetyCheckResult:
    """Fail when either the global flag OR the per-user column is off.

    The combinator function (:func:`is_live_trading_enabled_for_user`)
    returns the AND of both — we don't surface which one failed, only
    that the gate is closed; the user-facing message is the same
    either way ("contact support").
    """
    enabled = await is_live_trading_enabled_for_user(db, user_id)
    if enabled:
        return SafetyCheckResult(
            check_name="live_trading_enabled",
            passed=True,
            reason_hinglish="Live trading enabled hai tumhare account ke liye.",
            details={"enabled": True},
        )
    return SafetyCheckResult(
        check_name="live_trading_enabled",
        passed=False,
        reason_hinglish=(
            "Live trading abhi enabled nahi hai tumhare account ke liye. "
            "Customer support se contact karo."
        ),
        details={"enabled": False},
    )


# ─── 6. Broker connection ─────────────────────────────────────────────


async def check_broker_connection(
    *, db: AsyncSession, user_id: uuid.UUID
) -> SafetyCheckResult:
    """Fail when the user has no active credential for a real broker.

    The cheap, no-network version: count active rows in
    ``broker_credentials`` for ``user_id`` whose ``broker_name`` is
    in :data:`_FULLY_IMPLEMENTED_BROKERS`. Going further (calling
    ``broker.is_session_valid()``) would import the httpx-backed
    broker classes and violate the SafetyChain's no-HTTP rule. The
    "session healthy" check happens on the order placement path
    itself — it can react to ``BrokerSessionExpiredError`` with a
    relogin retry, which is the same one-shot recovery
    ``order_service.process_webhook_signal`` uses today.
    """
    stmt = (
        select(func.count())
        .select_from(BrokerCredential)
        .where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.is_active.is_(True),
            BrokerCredential.broker_name.in_(_FULLY_IMPLEMENTED_BROKERS),
        )
    )
    active_count = int((await db.execute(stmt)).scalar_one())
    if active_count > 0:
        return SafetyCheckResult(
            check_name="broker_connection",
            passed=True,
            reason_hinglish=(
                f"{active_count} broker connection active — order place ho sakta hai."
            ),
            details={"active_count": active_count},
        )
    return SafetyCheckResult(
        check_name="broker_connection",
        passed=False,
        reason_hinglish=(
            "Broker connection offline. Refresh login karo Brokers page se."
        ),
        details={"active_count": 0},
    )


# ─── 7. Risk engine pre-check (DEFERRED) ──────────────────────────────


async def check_risk_engine_precheck(
    *, db: AsyncSession, user_id: uuid.UUID, strategy_id: uuid.UUID
) -> SafetyCheckResult:
    """Placeholder for the strategy-level risk pre-check.

    Discovery confirmed there is no "risk engine pre-check" module
    today — :mod:`app.services.circuit_breaker_service` exposes
    ``check_volatility`` and ``check_order_sanity`` but both require
    runtime context (live price, full :class:`OrderRequest`) the
    SafetyChain doesn't have at place-decision time.

    Following the spec's "fail-open for missing modules" rule, this
    check passes by default and surfaces the deferral in
    ``reason_hinglish`` so the audit log records what was *not*
    enforced. Phase 8B-3 wires this to whatever the real risk module
    becomes.
    """
    _ = (db, user_id, strategy_id)  # parameters reserved for the real check.
    return SafetyCheckResult(
        check_name="risk_engine_precheck",
        passed=True,
        reason_hinglish=(
            "Risk Engine pre-check abhi implement nahi hua — Phase 8B-3 "
            "tak skip ho raha hai. Kill Switch + Trust/Truth gates active hain."
        ),
        details={"deferred": True, "phase": "8B-3"},
    )


# ─── Shared helpers ───────────────────────────────────────────────────


def _trust_result_from_inspection(
    inspection: CachedScoresInspection,
) -> SafetyCheckResult:
    """Translate a :class:`CachedScoresInspection` into the trust verdict."""
    if inspection.state is CachedScoresState.MISSING:
        return SafetyCheckResult(
            check_name="trust_score",
            passed=False,
            reason_hinglish="Pehle backtest run karo - Trust Score chahiye.",
            details={"state": inspection.state.value},
        )
    if inspection.state is CachedScoresState.STALE:
        return SafetyCheckResult(
            check_name="trust_score",
            passed=False,
            reason_hinglish="Backtest 24h purana hai - dobara run karo.",
            details={"state": inspection.state.value},
        )
    snap = inspection.snapshot
    assert snap is not None  # FRESH always carries a snapshot.
    if snap.trust_score < MIN_TRUST_SCORE_FOR_LIVE:
        return SafetyCheckResult(
            check_name="trust_score",
            passed=False,
            reason_hinglish=(
                f"Trust Score {int(snap.trust_score)}/100 hai, "
                f"{MIN_TRUST_SCORE_FOR_LIVE}+ chahiye live ke liye."
            ),
            details={
                "state": inspection.state.value,
                "trust_score": snap.trust_score,
                "required": MIN_TRUST_SCORE_FOR_LIVE,
                "age_hours": snap.age_hours,
            },
        )
    return SafetyCheckResult(
        check_name="trust_score",
        passed=True,
        reason_hinglish=(
            f"Trust Score {int(snap.trust_score)}/100 — passed."
        ),
        details={
            "state": inspection.state.value,
            "trust_score": snap.trust_score,
            "age_hours": snap.age_hours,
        },
    )


def _truth_result_from_inspection(
    inspection: CachedScoresInspection,
) -> SafetyCheckResult:
    """Translate a :class:`CachedScoresInspection` into the truth verdict."""
    if inspection.state is CachedScoresState.MISSING:
        return SafetyCheckResult(
            check_name="truth_score",
            passed=False,
            reason_hinglish="Pehle backtest run karo - Truth Score chahiye.",
            details={"state": inspection.state.value},
        )
    if inspection.state is CachedScoresState.STALE:
        return SafetyCheckResult(
            check_name="truth_score",
            passed=False,
            reason_hinglish="Backtest 24h purana hai - dobara run karo.",
            details={"state": inspection.state.value},
        )
    snap = inspection.snapshot
    assert snap is not None
    if snap.truth_score < MIN_TRUTH_SCORE_FOR_LIVE:
        return SafetyCheckResult(
            check_name="truth_score",
            passed=False,
            reason_hinglish=(
                f"Truth Score {int(snap.truth_score)}/100 hai, "
                f"{MIN_TRUTH_SCORE_FOR_LIVE}+ chahiye. Strategy mein fake "
                "patterns dikh rahe hain - AI Doctor se theek karo."
            ),
            details={
                "state": inspection.state.value,
                "truth_score": snap.truth_score,
                "required": MIN_TRUTH_SCORE_FOR_LIVE,
                "age_hours": snap.age_hours,
            },
        )
    return SafetyCheckResult(
        check_name="truth_score",
        passed=True,
        reason_hinglish=(
            f"Truth Score {int(snap.truth_score)}/100 — passed."
        ),
        details={
            "state": inspection.state.value,
            "truth_score": snap.truth_score,
            "age_hours": snap.age_hours,
        },
    )


__all__ = [
    "check_auto_kill_switch",
    "check_broker_connection",
    "check_live_trading_enabled",
    "check_paper_sessions",
    "check_risk_engine_precheck",
    "check_trust_score",
    "check_truth_score",
]

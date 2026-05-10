"""Broker Execution Guard — orchestrator.

Pure decision function that composes the individual checks in
:mod:`broker_guard.checks` and returns a :class:`GuardDecision` the
caller can act on.

Wiring this verdict into actual order placement is a *separate* future
phase. The guard intentionally:

    * Imports nothing from any broker adapter.
    * Imports nothing from the kill-switch implementation.
    * Performs no I/O (no HTTP, no DB, no clock reads).
    * Mutates none of its inputs (frozen Pydantic models).

These properties are tested via AST inspection and a determinism check
in ``tests/strategy_engine/broker_guard/``.
"""

from __future__ import annotations

from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.broker_guard.checks import (
    check_broker_connected,
    check_high_drawdown,
    check_kill_switch_inactive,
    check_low_trade_count,
    check_paper_override_used,
    check_paper_readiness,
    check_paper_sessions_recommended,
    check_stop_loss_present,
    check_trust_score,
    check_truth_risk_level,
    check_truth_score,
)
from app.strategy_engine.broker_guard.models import GuardCheckResult, GuardDecision
from app.strategy_engine.paper_trading.models import PaperReadinessReport
from app.strategy_engine.reliability.reliability_report import ReliabilityReport
from app.strategy_engine.schema.strategy import StrategyJSON
from app.strategy_engine.truth import TruthReport


def evaluate_broker_guard(
    *,
    strategy: StrategyJSON,
    backtest: BacktestResult | None,
    reliability: ReliabilityReport | None,
    truth: TruthReport | None,
    paper_readiness: PaperReadinessReport | None,
    broker_connected: bool,
    auto_kill_switch_active: bool,
    user_override_paper: bool = False,
) -> GuardDecision:
    """Run every check, then aggregate into a single pre-trade verdict.

    Args:
        strategy: The Phase 1 user-built DSL. Consulted for the
            stop-loss gate; never mutated.
        backtest: Phase 3 backtest output. ``None`` skips the warning
            checks that depend on it (low sample size, high drawdown).
        reliability: Phase 4 reliability report. ``None`` blocks live
            trading via the trust-score gate.
        truth: Phase 6 truth report. ``None`` blocks live trading via
            the truth-score gate.
        paper_readiness: Phase 8 readiness report. ``None`` blocks live
            trading unless ``user_override_paper`` is set.
        broker_connected: External flag — is the broker session live?
        auto_kill_switch_active: External flag — is the platform-level
            kill switch currently engaged?
        user_override_paper: When ``True`` the paper-readiness gate is
            bypassed, but the bypass itself raises a warning so the
            decision log makes the override explicit.

    Returns:
        :class:`GuardDecision` carrying ``allowed`` plus the bucketed
        check results. Determinism is guaranteed by the underlying
        checks being pure and the orchestrator doing no I/O.
    """
    raw_results: list[GuardCheckResult | None] = [
        # Blocking — must all pass.
        check_stop_loss_present(strategy),
        check_broker_connected(broker_connected),
        check_kill_switch_inactive(auto_kill_switch_active),
        check_truth_score(truth),
        check_trust_score(reliability),
        check_paper_readiness(paper_readiness, user_override_paper),
        # Warnings — flag but do not block.
        check_truth_risk_level(truth),
        check_low_trade_count(backtest),
        check_high_drawdown(backtest),
        check_paper_override_used(paper_readiness, user_override_paper),
        # Info — purely advisory.
        check_paper_sessions_recommended(paper_readiness),
    ]

    results: list[GuardCheckResult] = [r for r in raw_results if r is not None]

    blocking_failures = tuple(r for r in results if r.severity == "blocking" and not r.passed)
    warnings = tuple(r for r in results if r.severity == "warning" and not r.passed)
    info = tuple(r for r in results if r.severity == "info" and not r.passed)

    allowed = len(blocking_failures) == 0
    reason = _summarise_decision(allowed, blocking_failures, warnings)

    return GuardDecision(
        allowed=allowed,
        reason=reason,
        blocking_failures=blocking_failures,
        warnings=warnings,
        info=info,
        checks_run=tuple(r.check_name for r in results),
    )


def _summarise_decision(
    allowed: bool,
    blocking_failures: tuple[GuardCheckResult, ...],
    warnings: tuple[GuardCheckResult, ...],
) -> str:
    """Build a single human-readable reason string.

    Operators see this in the order log; the structured lists carry the
    exhaustive detail for the UI / audit trail.
    """
    if not allowed:
        # First blocking failure leads — it's typically the most actionable.
        # Additional failures are still surfaced via ``blocking_failures``.
        primary = blocking_failures[0].message
        if len(blocking_failures) > 1:
            return f"{primary} (+{len(blocking_failures) - 1} more blocking issue(s))"
        return primary
    if warnings:
        return (
            f"Live trading allowed with {len(warnings)} warning(s); review "
            "decision.warnings before sizing the position."
        )
    return "All blocking checks passed. Live trading allowed."


__all__ = ["evaluate_broker_guard"]

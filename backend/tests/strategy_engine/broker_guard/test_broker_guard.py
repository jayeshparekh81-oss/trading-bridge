"""Broker Execution Guard — locked behaviour pinned by 11 cases.

The fixtures in :mod:`conftest` build the upstream reports directly so
each test pins one axis of the guard's decision matrix. The default
fixture state is "all gates pass" — each test then degrades exactly
one input to assert the corresponding check fires.

The 11 cases mirror the spec one-for-one (see prompts/master-plan-final.md
"Broker Execution Guard") so anyone reading the test list immediately
knows what behaviour is locked.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.broker_guard import (
    GuardCheckResult,
    GuardDecision,
    evaluate_broker_guard,
)
from app.strategy_engine.paper_trading.models import PaperReadinessReport
from app.strategy_engine.reliability.reliability_report import ReliabilityReport
from app.strategy_engine.schema.strategy import StrategyJSON
from app.strategy_engine.truth import TruthReport
from tests.strategy_engine.broker_guard.conftest import (
    make_backtest,
    make_paper_readiness,
    make_reliability,
    make_strategy_with_stop,
    make_strategy_without_stop,
    make_truth,
)

# ─── Shared "all gates pass" call helper ───────────────────────────────


def _evaluate(
    *,
    strategy: StrategyJSON | None = None,
    backtest: BacktestResult | None = None,
    reliability: ReliabilityReport | None = None,
    truth: TruthReport | None = None,
    paper_readiness: PaperReadinessReport | None = None,
    broker_connected: bool = True,
    auto_kill_switch_active: bool = False,
    user_override_paper: bool = False,
) -> GuardDecision:
    """Call ``evaluate_broker_guard`` with healthy defaults.

    Each test passes only the inputs it cares about; everything else
    falls through to a state that clears the corresponding gate.
    """
    return evaluate_broker_guard(
        strategy=strategy if strategy is not None else make_strategy_with_stop(),
        backtest=backtest if backtest is not None else make_backtest(),
        reliability=(reliability if reliability is not None else make_reliability(trust_score=85)),
        truth=truth if truth is not None else make_truth(truth_score=80),
        paper_readiness=(
            paper_readiness
            if paper_readiness is not None
            else make_paper_readiness(live_ready=True, completed_sessions=14)
        ),
        broker_connected=broker_connected,
        auto_kill_switch_active=auto_kill_switch_active,
        user_override_paper=user_override_paper,
    )


def _named_failures(decision: GuardDecision) -> list[str]:
    return [r.check_name for r in decision.blocking_failures]


# ─── 1. Missing stop loss → BLOCKED ────────────────────────────────────


def test_missing_stop_loss_blocks_live() -> None:
    decision = _evaluate(strategy=make_strategy_without_stop())
    assert decision.allowed is False
    assert "stop_loss_present" in _named_failures(decision)
    assert "no stop loss" in decision.reason.lower()


# ─── 2. Broker disconnected → BLOCKED ──────────────────────────────────


def test_broker_disconnected_blocks_live() -> None:
    decision = _evaluate(broker_connected=False)
    assert decision.allowed is False
    assert "broker_connected" in _named_failures(decision)


# ─── 3. Auto Kill Switch active → BLOCKED ──────────────────────────────


def test_kill_switch_active_blocks_live() -> None:
    decision = _evaluate(auto_kill_switch_active=True)
    assert decision.allowed is False
    assert "kill_switch_inactive" in _named_failures(decision)


# ─── 4. Truth score below threshold → BLOCKED ──────────────────────────


def test_low_truth_score_blocks_live() -> None:
    decision = _evaluate(truth=make_truth(truth_score=50))
    assert decision.allowed is False
    failures = _named_failures(decision)
    assert "truth_score" in failures
    blocking_messages = " ".join(r.message for r in decision.blocking_failures)
    assert "Truth Score 50" in blocking_messages


# ─── 5. Trust score below threshold → BLOCKED ──────────────────────────


def test_low_trust_score_blocks_live() -> None:
    decision = _evaluate(reliability=make_reliability(trust_score=65))
    assert decision.allowed is False
    failures = _named_failures(decision)
    assert "trust_score" in failures


# ─── 6. Paper not ready, no override → BLOCKED ─────────────────────────


def test_paper_not_ready_without_override_blocks_live() -> None:
    paper = make_paper_readiness(
        live_ready=False,
        completed_sessions=5,
        blocked_reasons=("paper_pnl negative", "completed_sessions < 7"),
    )
    decision = _evaluate(paper_readiness=paper, user_override_paper=False)
    assert decision.allowed is False
    failures = _named_failures(decision)
    assert "paper_readiness" in failures
    blocking_msgs = " ".join(r.message for r in decision.blocking_failures)
    assert "paper_pnl negative" in blocking_msgs


# ─── 7. Paper not ready, override=True → ALLOWED + warning ─────────────


def test_paper_not_ready_with_override_allows_with_warning() -> None:
    paper = make_paper_readiness(
        live_ready=False,
        completed_sessions=5,
        blocked_reasons=("paper_pnl negative",),
    )
    decision = _evaluate(paper_readiness=paper, user_override_paper=True)
    assert decision.allowed is True
    assert _named_failures(decision) == []
    warning_names = [r.check_name for r in decision.warnings]
    assert "paper_override_used" in warning_names


# ─── 8. All checks pass → ALLOWED, no blocking_failures ────────────────


def test_all_checks_pass_allows_live() -> None:
    decision = _evaluate()
    assert decision.allowed is True
    assert decision.blocking_failures == ()
    assert decision.warnings == ()
    # Every blocking check must have run, plus the warning + info ones
    # whose inputs were available (they were, in this happy path).
    assert "stop_loss_present" in decision.checks_run
    assert "truth_score" in decision.checks_run
    assert "trust_score" in decision.checks_run
    assert "paper_readiness" in decision.checks_run
    assert decision.reason.startswith("All blocking checks passed")


# ─── 9. High risk level → ALLOWED + warning ────────────────────────────


def test_high_risk_level_allows_with_warning() -> None:
    decision = _evaluate(truth=make_truth(truth_score=80, risk_level="high"))
    assert decision.allowed is True
    warning_names = [r.check_name for r in decision.warnings]
    assert "truth_risk_level" in warning_names
    high_warning = next(r for r in decision.warnings if r.check_name == "truth_risk_level")
    assert "high risk level" in high_warning.message.lower()


# ─── 10. Determinism — running twice gives an equal decision ───────────


def test_decision_is_deterministic_across_runs() -> None:
    """Two identical calls must produce equal :class:`GuardDecision` objects.

    The guard is pure and frozen-in/frozen-out, so equality is structural.
    Catches accidental ``set`` ordering, ``dict`` traversal, or hidden
    randomness sneaking into the orchestrator.
    """
    first = _evaluate()
    second = _evaluate()
    assert first == second
    assert first.checks_run == second.checks_run
    assert first.allowed == second.allowed
    assert first.reason == second.reason


# ─── 11. AST inspection — no broker / kill-switch imports ──────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "app.services.fyers",
    "app.services.dhan",
    "app.services.broker",
    "app.brokers",
    "app.kill_switch",
)
_FORBIDDEN_SUFFIX_HINTS: tuple[str, ...] = (
    "kill_switch",
    "fyers_",
    "dhan_",
    "broker_",
)


def _broker_guard_python_files() -> list[Path]:
    pkg_root = Path(__file__).resolve().parents[3] / "app" / "strategy_engine" / "broker_guard"
    return sorted(p for p in pkg_root.glob("*.py"))


@pytest.mark.parametrize("source_file", _broker_guard_python_files())
def test_broker_guard_module_does_not_import_broker_or_killswitch(
    source_file: Path,
) -> None:
    """Walk every import in every broker_guard *.py file and assert it
    does not pull in broker adapters or kill-switch internals.

    The guard is, by design, isolated from execution-side modules — it
    consumes only the structured outputs of upstream phases. This test
    pins that isolation so a future contributor can't quietly couple
    the guard to a broker adapter or kill-switch helper.
    """
    tree = ast.parse(source_file.read_text(), filename=str(source_file))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                offenders.append(f"from {module} import …")
    assert not offenders, f"{source_file.name} pulls in forbidden modules: {offenders}"


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    if any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES):
        return True
    last_segment = name.rsplit(".", 1)[-1]
    return any(hint in last_segment for hint in _FORBIDDEN_SUFFIX_HINTS)


# ─── Output-model integrity safeguards ─────────────────────────────────


def test_guard_decision_is_frozen() -> None:
    """The decision is the audit-trail anchor — mutating it would
    invalidate that promise. Pin the frozen config explicitly."""
    decision = _evaluate()
    # Pydantic v2 with ``frozen=True`` raises ValidationError on assignment.
    with pytest.raises(ValidationError):
        decision.allowed = False  # type: ignore[misc]


def test_guard_check_result_severity_literal() -> None:
    """Severity must be one of the documented bands."""
    decision = _evaluate(broker_connected=False)
    severities = {
        r.severity
        for r in (
            *decision.blocking_failures,
            *decision.warnings,
            *decision.info,
        )
    }
    assert severities.issubset({"info", "warning", "blocking"})
    assert isinstance(decision.blocking_failures[0], GuardCheckResult)

"""Fixtures for the Broker Execution Guard tests.

The guard is pure and consumes Phase 3/4/6/8 outputs, so the tests
fabricate fully-formed reports directly rather than running real
pipelines. That keeps each test under 100 ms and lets us pin specific
boundary conditions (truth score = 54 vs 55) without engineering a
backtest that produces them.

Helpers stay self-contained on purpose — they import only the public
boundary types of each upstream phase, not internal helpers.
"""

from __future__ import annotations

from typing import Any, Literal

from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.paper_trading.models import PaperReadinessReport
from app.strategy_engine.reliability.reliability_report import ReliabilityReport
from app.strategy_engine.reliability.trust_score import TrustScore
from app.strategy_engine.schema.strategy import StrategyJSON
from app.strategy_engine.truth import TruthReport

GradeLetter = Literal["A", "B", "C", "D", "F"]
RiskLevelLiteral = Literal["low", "medium", "high", "extreme"]


# ─── Strategy ──────────────────────────────────────────────────────────


_BASE_STRATEGY: dict[str, Any] = {
    "id": "broker_guard_test",
    "name": "Broker Guard Test",
    "mode": "expert",
    "indicators": [
        {"id": "ema_20", "type": "ema", "params": {"period": 20}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [{"type": "indicator", "left": "ema_20", "op": ">", "value": 100.0}],
    },
    "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
    "risk": {},
    "execution": {
        "mode": "backtest",
        "orderType": "MARKET",
        "productType": "INTRADAY",
    },
}


def make_strategy_with_stop() -> StrategyJSON:
    """Strategy whose ExitRules has a ``stop_loss_percent``."""
    return StrategyJSON.model_validate(_BASE_STRATEGY)


def make_strategy_without_stop() -> StrategyJSON:
    """Strategy with no stop loss and no trailing stop — only a target.

    ExitRules requires *some* exit primitive, so we keep the target so
    the schema remains valid. The guard's stop-loss check still fails.
    """
    payload = {
        **_BASE_STRATEGY,
        "exit": {"targetPercent": 2.0},
    }
    return StrategyJSON.model_validate(payload)


def make_strategy_with_trailing_only() -> StrategyJSON:
    """Trailing stop only (no fixed stop_loss) — guard should treat the
    stop-loss gate as satisfied.
    """
    payload = {
        **_BASE_STRATEGY,
        "exit": {"targetPercent": 2.0, "trailingStopPercent": 1.0},
    }
    return StrategyJSON.model_validate(payload)


# ─── Backtest ──────────────────────────────────────────────────────────


def make_backtest(
    *,
    total_pnl: float = 1500.0,
    total_return_percent: float = 15.0,
    win_rate: float = 0.6,
    total_trades: int = 50,
    average_win: float = 200.0,
    average_loss: float = 100.0,
    max_drawdown: float = 0.10,
    profit_factor: float = 2.0,
    expectancy: float = 30.0,
) -> BacktestResult:
    """Synthesise a healthy :class:`BacktestResult`.

    Defaults are deliberately above every warning threshold so the
    tests can dial *one* axis down without tripping unrelated checks.
    """
    return BacktestResult(
        total_pnl=total_pnl,
        total_return_percent=total_return_percent,
        win_rate=win_rate,
        loss_rate=max(0.0, min(1.0, 1.0 - win_rate)),
        total_trades=total_trades,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=average_win * 2,
        largest_loss=average_loss * 2,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        expectancy=expectancy,
        equity_curve=[],
        trades=[],
        warnings=[],
    )


# ─── Trust score (manual, not via calculate_trust_score) ───────────────


def make_trust_score(score: int) -> TrustScore:
    """Build a :class:`TrustScore` with an exact integer ``score``.

    The verdict + grade letters do not affect the broker guard, so we
    use stable placeholders and let the score itself drive the
    behaviour we're testing.
    """
    return TrustScore(
        score=score,
        grade=_grade_for(score),
        verdict=f"Synthetic trust score {score}.",
        warnings=(),
        passed_checks=(),
        failed_checks=(),
        suggestions=(),
    )


def _grade_for(score: int) -> GradeLetter:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def make_reliability(
    *,
    backtest: BacktestResult | None = None,
    trust_score: int = 80,
) -> ReliabilityReport:
    """Build a :class:`ReliabilityReport` carrying the requested trust score."""
    return ReliabilityReport(
        backtest=backtest if backtest is not None else make_backtest(),
        trust_score=make_trust_score(trust_score),
        out_of_sample=None,
        walk_forward=None,
        sensitivity=None,
    )


# ─── Truth report (manual) ─────────────────────────────────────────────


def make_truth(
    *,
    truth_score: int = 80,
    risk_level: RiskLevelLiteral = "low",
    verdict: str = "Synthetic truth verdict.",
) -> TruthReport:
    """Build a :class:`TruthReport` with the score / risk we need."""
    return TruthReport(
        truth_score=truth_score,
        grade=_grade_for(truth_score),
        verdict=verdict,
        risk_level=risk_level,
        fake_backtest_warnings=(),
        overfitting_warnings=(),
        execution_warnings=(),
        cost_warnings=(),
        strengths=(),
        weaknesses=(),
        recommended_next_actions=(),
    )


# ─── Paper readiness ───────────────────────────────────────────────────


def make_paper_readiness(
    *,
    completed_sessions: int = 14,
    paper_pnl: float = 500.0,
    paper_win_rate: float = 0.55,
    rule_adherence_percent: float = 90.0,
    live_ready: bool = True,
    blocked_reasons: tuple[str, ...] = (),
) -> PaperReadinessReport:
    """Build a :class:`PaperReadinessReport`."""
    return PaperReadinessReport(
        completed_sessions=completed_sessions,
        paper_pnl=paper_pnl,
        paper_win_rate=paper_win_rate,
        rule_adherence_percent=rule_adherence_percent,
        live_ready=live_ready,
        blocked_reasons=blocked_reasons,
    )

"""Coach tests reuse the truth tests' BacktestResult fabricator + add a
helper for fabricating ``ReliabilityReport`` directly with a chosen
trust score (the truth-helper computes one via Phase 4, which means
giving it a "low" trust score requires careful BacktestResult shaping;
a direct builder is simpler for the coach's reliability-aware tip)."""

from __future__ import annotations

from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.reliability.constants import Grade
from app.strategy_engine.reliability.reliability_report import ReliabilityReport
from app.strategy_engine.reliability.trust_score import TrustScore
from tests.strategy_engine.truth.conftest import make_backtest_result

__all__ = [
    "make_backtest_result",
    "make_reliability_with_trust",
]


def make_reliability_with_trust(
    backtest: BacktestResult,
    *,
    trust_score: int,
    grade: Grade = "B",
) -> ReliabilityReport:
    """Bundle ``backtest`` with a hand-built TrustScore at the chosen number."""
    trust = TrustScore(
        score=trust_score,
        grade=grade,
        verdict="custom test trust score",
        warnings=(),
        passed_checks=(),
        failed_checks=(),
        suggestions=(),
    )
    return ReliabilityReport(
        backtest=backtest,
        trust_score=trust,
        out_of_sample=None,
        walk_forward=None,
        sensitivity=None,
    )

"""Strategy Truth Engine — fake-backtest detection on top of reliability.

Phase 6 of the AI trading system. Sits **above** the Phase 4 reliability
engine: it consumes a pre-computed
:class:`~app.strategy_engine.reliability.ReliabilityReport` (the
backtest, the trust score, the optional OOS / sensitivity results) plus
the cost / ambiguity settings the operator picked, and answers a single
question:

    "Is this backtest actually reliable, or is it giving false confidence?"

The output is a structured :class:`TruthReport` partitioned into four
warning buckets — fake-backtest, overfitting, execution, cost — plus
strengths, weaknesses, and a recommended-next-action list.

The engine is **pure** and **AI-free**:

    * No LLM, no network, no clock reads, no backtest invocations.
    * Same inputs always produce the same :class:`TruthReport`.
    * Phase 3 ``BacktestResult`` and Phase 4 sub-results are frozen
      Pydantic models, so the engine cannot mutate them even by
      accident — a regression test pins the round-trip equality.

Public boundary::

    TruthReport / RiskLevel / evaluate_strategy_truth
"""

from __future__ import annotations

from app.strategy_engine.truth.truth_score import (
    RiskLevel,
    TruthReport,
    evaluate_strategy_truth,
)

__all__ = [
    "RiskLevel",
    "TruthReport",
    "evaluate_strategy_truth",
]

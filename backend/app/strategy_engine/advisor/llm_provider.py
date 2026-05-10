"""Pluggable LLM provider interface.

The advisor and doctor are deterministic and produce useful output on
their own. When a caller wants natural-language elaboration on top
(e.g. a beginner-friendly walk-through of the truth report), they can
inject an :class:`LLMProvider` adapter that wraps an external API.

The interface is **opt-in** and **best-effort**: every method may
return ``None`` to indicate "no enrichment available". The default
:class:`NullLLMProvider` does exactly that for every call so the base
app needs no API key.

This module is **disjoint** from :mod:`app.services.algomitra_ai` (the
chat companion) and :mod:`app.services.ai_validator` (the signal
scorer). Both of those run on their own model and prompt; the advisor
LLM provider is a different surface used during strategy authoring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.strategy_engine.advisor.advisor import Advice
    from app.strategy_engine.advisor.doctor import Problem
    from app.strategy_engine.backtest.runner import BacktestResult
    from app.strategy_engine.reliability.reliability_report import (
        ReliabilityReport,
    )
    from app.strategy_engine.schema.strategy import StrategyJSON
    from app.strategy_engine.truth.truth_score import TruthReport


@runtime_checkable
class LLMProvider(Protocol):
    """Optional adapter that an external LLM client implements.

    Every method may return ``None`` — callers must treat the LLM
    layer as best-effort and gracefully fall back to the deterministic
    advisor / doctor output.
    """

    def explain_strategy(self, strategy: StrategyJSON) -> str | None:
        """Plain-language summary of what the strategy does."""

    def improve_strategy(
        self,
        strategy: StrategyJSON,
        problems: list[Problem],
    ) -> dict[str, object] | None:
        """Suggested improved StrategyJSON (raw dict; not validated here)."""

    def explain_backtest(self, backtest: BacktestResult) -> str | None:
        """Walk-through of the backtest result for a non-quant audience."""

    def generate_learning_tip(self, advice: list[Advice]) -> str | None:
        """One-liner teaching moment derived from the advisor's findings."""

    def explain_reliability(self, reliability: ReliabilityReport) -> str | None:
        """Why the reliability checks did or did not pass."""

    def explain_truth_score(self, truth: TruthReport) -> str | None:
        """Why the strategy got the truth score it got."""


class NullLLMProvider:
    """Default provider — every method returns ``None``.

    Lets the rest of the app code unconditionally call into an
    :class:`LLMProvider` without branching on whether one is configured.
    """

    def explain_strategy(self, strategy: StrategyJSON) -> str | None:
        return None

    def improve_strategy(
        self,
        strategy: StrategyJSON,
        problems: list[Problem],
    ) -> dict[str, object] | None:
        return None

    def explain_backtest(self, backtest: BacktestResult) -> str | None:
        return None

    def generate_learning_tip(self, advice: list[Advice]) -> str | None:
        return None

    def explain_reliability(self, reliability: ReliabilityReport) -> str | None:
        return None

    def explain_truth_score(self, truth: TruthReport) -> str | None:
        return None


__all__ = ["LLMProvider", "NullLLMProvider"]

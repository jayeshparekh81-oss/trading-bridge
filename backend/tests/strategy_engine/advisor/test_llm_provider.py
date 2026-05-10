"""LLM provider interface — base app must work without an API key.

The :class:`NullLLMProvider` returns ``None`` from every method; the
runtime-checkable :class:`LLMProvider` Protocol therefore accepts it
even though no inheritance is in play.
"""

from __future__ import annotations

from app.strategy_engine.advisor import (
    AdvisorReport,
    LLMProvider,
    NullLLMProvider,
    diagnose_strategy,
    generate_advice,
)
from tests.strategy_engine.advisor.conftest import (
    make_backtest_result,
    make_reliability,
    make_strategy,
    make_truth_report,
)


def test_null_provider_satisfies_protocol() -> None:
    """Structural typing — NullLLMProvider IS-A LLMProvider."""
    provider = NullLLMProvider()
    assert isinstance(provider, LLMProvider)


def test_null_provider_returns_none_for_every_method() -> None:
    """Every advice / explanation method returns ``None`` — no enrichment."""
    provider = NullLLMProvider()
    strategy = make_strategy()
    backtest = make_backtest_result()
    reliability = make_reliability(backtest)
    truth = make_truth_report()

    advice_report = generate_advice(strategy=strategy)
    diagnosis = diagnose_strategy(strategy=strategy)

    assert provider.explain_strategy(strategy) is None
    assert provider.improve_strategy(strategy, list(diagnosis.problems)) is None
    assert provider.explain_backtest(backtest) is None
    assert provider.generate_learning_tip(list(advice_report.advice)) is None
    assert provider.explain_reliability(reliability) is None
    assert provider.explain_truth_score(truth) is None


def test_advisor_does_not_require_an_llm_provider() -> None:
    """The base app produces a useful AdvisorReport without any LLM."""
    report = generate_advice(strategy=make_strategy())
    assert isinstance(report, AdvisorReport)
    # At minimum, the paper-trading recommendation always lands.
    assert any(a.category.value == "paper_trading" for a in report.advice)

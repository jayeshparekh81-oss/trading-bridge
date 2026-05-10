"""Phase 7 — Base AI Advisor + AI Strategy Doctor (deterministic).

Two cooperating, AI-free engines plus a pluggable LLM hook:

    * :func:`generate_advice` — the rule-based **Base Advisor**. Walks
      a ten-rule book (indicator coverage, missing stop loss / exit,
      high win-rate caution, low trust score, overfitting, drawdown,
      paper / live recommendations, regime mismatch, live deviation)
      and emits a list of typed :class:`Advice` objects.

    * :func:`diagnose_strategy` — the **Strategy Doctor**. Inspects
      the same inputs, classifies problems by ``ProblemType`` and
      ``Severity``, and produces a draft of a fixable strategy when
      one trivial repair is possible (e.g. inserting a stop loss).
      Never mutates the input strategy; the draft is a fresh
      ``model_dump`` so the caller decides whether to apply it.

    * :class:`LLMProvider` — Protocol that an external LLM adapter
      can implement to enrich either engine. The default
      :class:`NullLLMProvider` returns ``None`` from every method so
      the base app works without an API key.

This package is deliberately **separate** from
:mod:`app.services.algomitra_ai` (the chat companion) and
:mod:`app.services.ai_validator` (the 17-indicator signal scorer).
Those run live; this advises during strategy authoring.
"""

from __future__ import annotations

from app.strategy_engine.advisor.advisor import (
    Advice,
    AdviceCategory,
    AdviceSeverity,
    AdvisorReport,
    generate_advice,
)
from app.strategy_engine.advisor.doctor import (
    Diagnosis,
    Problem,
    ProblemType,
    diagnose_strategy,
)
from app.strategy_engine.advisor.llm_provider import (
    LLMProvider,
    NullLLMProvider,
)
from app.strategy_engine.advisor.trade_quality import (
    TradeQualityComponent,
    TradeQualityReport,
    compute_trade_quality,
)

__all__ = [
    "Advice",
    "AdviceCategory",
    "AdviceSeverity",
    "AdvisorReport",
    "Diagnosis",
    "LLMProvider",
    "NullLLMProvider",
    "Problem",
    "ProblemType",
    "TradeQualityComponent",
    "TradeQualityReport",
    "compute_trade_quality",
    "diagnose_strategy",
    "generate_advice",
]

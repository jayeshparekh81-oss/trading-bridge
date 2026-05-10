"""Phase 5 REST surface for user-built strategies.

Lives inside ``strategy_engine`` (alongside ``schema``, ``backtest``,
``reliability``) because the entities it persists — the user-built
StrategyJSON DSL — belong to the strategy engine's bounded context. The
generic platform endpoints (``/api/strategies/positions``,
``/api/strategies/signals``) live in :mod:`app.api`; this module owns
strategy-definition CRUD only.
"""

from __future__ import annotations

from app.strategy_engine.api.strategies import router

__all__ = ["router"]

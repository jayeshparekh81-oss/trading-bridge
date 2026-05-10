"""Indicator registry + pure-Python calculation functions.

Two layers:
    * :mod:`app.strategy_engine.indicators.registry` — metadata-only
      registry. The single source of truth for "what indicators exist".
    * :mod:`app.strategy_engine.indicators.calculations` — pure functions
      that compute each indicator's series from OHLCV inputs.

The two layers are decoupled by design. The registry stores only the
*name* of the calculation function (a string) so the metadata can be
serialised to JSON and shipped to the frontend without pulling the
calculation code along. Resolution from name → callable is the caller's
job (e.g. via :func:`registry.get_calculation_function`).
"""

from __future__ import annotations

from app.strategy_engine.indicators.registry import (
    INDICATOR_REGISTRY,
    IndicatorParamError,
    get_active_indicators,
    get_beginner_recommended_indicators,
    get_calculation_function,
    get_indicator_by_id,
    get_indicators_by_category,
    list_categories,
    validate_indicator_params,
)

__all__ = [
    "INDICATOR_REGISTRY",
    "IndicatorParamError",
    "get_active_indicators",
    "get_beginner_recommended_indicators",
    "get_calculation_function",
    "get_indicator_by_id",
    "get_indicators_by_category",
    "list_categories",
    "validate_indicator_params",
]

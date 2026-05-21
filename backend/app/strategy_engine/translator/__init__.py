"""Template → StrategyJSON translator (Queue BB prototype).

Public entry point: :func:`translate_template`. See
``docs/TRANSLATOR_ARCHITECTURE_PROPOSAL.md`` (Option Z, hybrid) for
the design and ``docs/TRANSLATOR_PROTOTYPE/PROGRESS.md`` for per-template
translation status.
"""

from __future__ import annotations

from app.strategy_engine.translator.errors import (
    AmbiguousFieldError,
    MissingFieldError,
    TranslationError,
    UnknownIndicatorError,
    UnparseableConditionError,
)
from app.strategy_engine.translator.field_mappers import (
    parse_condition,
    parse_conditions,
    parse_indicator_id,
)
from app.strategy_engine.translator.override_registry import (
    clear_overrides,
    get_override,
    list_overrides,
    register_override,
)
from app.strategy_engine.translator.parser import translate_template

__all__ = [
    "AmbiguousFieldError",
    "MissingFieldError",
    "TranslationError",
    "UnknownIndicatorError",
    "UnparseableConditionError",
    "clear_overrides",
    "get_override",
    "list_overrides",
    "parse_condition",
    "parse_conditions",
    "parse_indicator_id",
    "register_override",
    "translate_template",
]

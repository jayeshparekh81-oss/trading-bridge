"""Feature-flag store — public boundary.

In-memory feature-flag toggles with environment-variable override.
The store is intentionally in-memory for now — a future phase will
swap a DB-backed implementation in behind the same public API.

Resolution order: env (``TRADETRI_FF_{FLAG_NAME}``) > runtime
override > hardcoded default. Mutations to critical flags
(``LIVE_TRADING_ENABLED``, ``LLM_ADVISOR_ENABLED``,
``BROKER_GUARD_ENABLED``) are audit-logged.

Public surface::

    is_enabled / set_flag / get_flag / reset_flag /
    get_all_flags / reset_all_flags /
    FeatureFlag / FlagsSnapshot / UnknownFlagError
"""

from __future__ import annotations

from app.strategy_engine.feature_flags.manager import (
    get_all_flags,
    get_flag,
    is_enabled,
    reset_all_flags,
    reset_flag,
    set_flag,
)
from app.strategy_engine.feature_flags.models import (
    FeatureFlag,
    FlagSource,
    FlagsSnapshot,
)
from app.strategy_engine.feature_flags.registry import UnknownFlagError

__all__ = [
    "FeatureFlag",
    "FlagSource",
    "FlagsSnapshot",
    "UnknownFlagError",
    "get_all_flags",
    "get_flag",
    "is_enabled",
    "reset_all_flags",
    "reset_flag",
    "set_flag",
]

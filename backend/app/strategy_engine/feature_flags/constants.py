"""Locked constants for the feature-flag store.

Single tunable knobs for env-prefix, truthy/falsy parsing, and the
critical-flag set whose runtime mutations get audit-logged. Keep this
module dependency-free.
"""

from __future__ import annotations

from typing import Final

ENV_PREFIX: Final[str] = "TRADETRI_FF_"
"""Environment variables of the form ``TRADETRI_FF_{FLAG_NAME}`` (e.g.
``TRADETRI_FF_LIVE_TRADING_ENABLED``) override both the hardcoded
default and any in-process runtime override. Re-read on every
:func:`is_enabled` call so a process-env change takes effect without
a restart."""

TRUTHY_VALUES: Final[frozenset[str]] = frozenset({"true", "1", "yes"})
"""Case-insensitive env values that resolve to ``True``."""

FALSY_VALUES: Final[frozenset[str]] = frozenset({"false", "0", "no"})
"""Case-insensitive env values that resolve to ``False``. Anything
that is neither truthy nor falsy is *ignored* and falls through to
the next layer (runtime override → default)."""

CRITICAL_FLAGS: Final[frozenset[str]] = frozenset(
    {
        "LIVE_TRADING_ENABLED",
        "LLM_ADVISOR_ENABLED",
        "BROKER_GUARD_ENABLED",
    }
)
"""Flags whose runtime mutation is audit-logged at ``critical``
severity. Disabling ``BROKER_GUARD_ENABLED`` is additionally recorded
as a ``risk_block`` event because it's the safety net for live order
flow — losing it without a paper trail would be a security incident."""


__all__ = [
    "CRITICAL_FLAGS",
    "ENV_PREFIX",
    "FALSY_VALUES",
    "TRUTHY_VALUES",
]

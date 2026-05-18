"""ALMA — alias for :func:`arnaud_legoux_ma`.

The Phase 9 coming-soon registry shipped ``alma`` as a stub while the
working calculation lived under the longer ``arnaud_legoux_ma`` id in
Pack 9. Templates reference the short ``alma`` name, so this module
re-exports the existing implementation under the canonical id.

Why a re-export instead of a duplicate copy:
    * Single source of truth — only one place to fix a bug
    * No subtle math drift between the two names
    * Registry maps both ``alma`` AND ``arnaud_legoux_ma`` to the
      SAME calculation function so customer-facing template configs
      keep working without rewrites
"""

from __future__ import annotations

from app.strategy_engine.indicators.calculations.arnaud_legoux_ma import (
    arnaud_legoux_ma as _alma_impl,
)


def alma(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Gaussian-weighted MA. Thin wrapper over :func:`arnaud_legoux_ma`."""
    return _alma_impl(*args, **kwargs)


__all__ = ["alma"]

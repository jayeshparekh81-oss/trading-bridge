"""Pure-Python indicator calculations.

Conventions (Phase 1, locked-in):
    * Output length always equals input length when ``period <= len(values)``.
      Warm-up positions are filled with ``None`` so callers can align the
      series with the original price series by index.
    * Empty input ``[]`` returns ``[]``.
    * ``period > len(values)`` returns ``[]`` (truly insufficient data).
    * Functions are pure: no I/O, no module-level mutable state, no side
      effects. Inputs are sequences of ``float``; outputs are ``list[float | None]``
      (or ``tuple`` of such lists for multi-output indicators).
    * No external dependencies (NumPy etc.) — Phase 1 stays stdlib-only so
      these calculations can be reused in any deployment context.
"""

from __future__ import annotations

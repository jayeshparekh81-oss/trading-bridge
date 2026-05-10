"""NIFTY correlation — STUB pending market-context integration.

⚠️  This indicator is intentionally a no-op in Pack 8.

The real implementation needs to fetch a parallel NIFTY series at
the same bar frequency + alignment as the input, then compute a
rolling Pearson correlation against close. The data-provider
layer doesn't yet expose a "fetch comparison series for the same
window" helper at the calc-layer abstraction; wiring that
crossing is a Phase 2 item.

For now the function returns an all-``None`` series of the right
length. Strategies that reference it get a defined-shape placeholder
they can branch on (``is None`` → "data not yet available"). The
registry entry's docstring + this module's header are the
operator-visible explanations.

Phase 2 plan: add a ``comparison_close: Sequence[float]`` parameter
sourced from a higher-level data-provider call. The signature
will gain that argument; current call sites that pass only
``period`` will continue to receive an all-``None`` series until
the dispatcher is updated to thread the comparison series in.
"""

from __future__ import annotations

from collections.abc import Sequence

#: Operator-visible flag. The dashboard / registry UI can render a
#: "needs market context" badge by importing this constant rather
#: than hardcoding the indicator id.
HAS_MARKET_CONTEXT = False


def nifty_correlation(
    closes: Sequence[float],
    period: int = 30,
) -> list[float | None]:
    """Phase 1 stub — returns an all-``None`` series of length
    ``len(closes)``.

    Validates ``period`` so a typo at the config layer still
    surfaces a useful ``ValueError`` instead of being silently
    accepted."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 1:
        raise ValueError(f"period must be an int > 1; got {period!r}.")
    return [None] * len(closes)


__all__ = ["HAS_MARKET_CONTEXT", "nifty_correlation"]

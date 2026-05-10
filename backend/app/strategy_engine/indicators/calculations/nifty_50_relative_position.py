"""NIFTY 50 relative position - Phase-1 STUB.

Real implementation requires:
    * NIFTY 50 candles parallel to the symbol candles.
    * A symbol-to-NIFTY-component mapping (only the 50 constituents
      have meaningful "relative position").

Both are below the calc-layer abstraction in Phase 1, so this
indicator ships as an honest no-op returning all-None.

When Phase-2 wiring lands, the indicator will compute::

    symbol_pct[i] = symbol_close[i] / symbol_close[i - lookback] - 1
    nifty_pct[i]  = nifty_close[i]  / nifty_close[i - lookback]  - 1
    output[i]     = (symbol_pct[i] - nifty_pct[i]) * 100

Same honest-stub pattern as Pack 8 ``nifty_correlation``, Pack 13
``relative_strength_vs_benchmark``, Pack 16 ``vix_correlation``,
Pack 18 ``nse_bse_arbitrage_proxy``.

The ``HAS_SYMBOL_CONTEXT = False`` flag is exported so callers /
tests can assert the contract.
"""

from __future__ import annotations

from collections.abc import Sequence

HAS_SYMBOL_CONTEXT: bool = False


def nifty_50_relative_position(
    closes: Sequence[float],
    lookback: int = 30,
) -> list[float | None]:
    """Phase-1 stub - returns all-None until symbol/NIFTY mapping lands."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 2:
        raise ValueError(f"lookback must be int >= 2; got {lookback!r}.")
    return [None] * len(closes)


__all__ = ["HAS_SYMBOL_CONTEXT", "nifty_50_relative_position"]

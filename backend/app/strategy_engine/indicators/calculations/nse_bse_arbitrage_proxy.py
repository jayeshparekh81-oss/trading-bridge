"""NSE/BSE arbitrage proxy - Phase-1 STUB.

Real arbitrage detection requires parallel candle feeds from BOTH
NSE and BSE for the same symbol. The data-provider layer currently
exposes only one exchange per request, so this calc ships as an
honest no-op returning all-None.

When Phase-2 wiring exposes a parallel-feed fetch, the indicator
will compute::

    spread_pct[i] = (nse_close[i] - bse_close[i]) / nse_close[i] * 100
    output[i]     = 1.0 if |spread_pct[i]| > spread_threshold_pct else 0.0

Same honest-stub pattern as Pack 8 ``nifty_correlation``, Pack 13
``relative_strength_vs_benchmark``, Pack 16 ``vix_correlation``.

The ``HAS_DUAL_EXCHANGE = False`` flag is exported so callers /
tests can assert the contract.
"""

from __future__ import annotations

from collections.abc import Sequence

HAS_DUAL_EXCHANGE: bool = False


def nse_bse_arbitrage_proxy(
    closes: Sequence[float],
    spread_threshold_pct: float = 0.1,
) -> list[float | None]:
    """Phase-1 stub - returns all-None until dual-exchange feed lands."""
    if spread_threshold_pct <= 0:
        raise ValueError(
            f"spread_threshold_pct must be > 0; got {spread_threshold_pct!r}."
        )
    return [None] * len(closes)


__all__ = ["HAS_DUAL_EXCHANGE", "nse_bse_arbitrage_proxy"]

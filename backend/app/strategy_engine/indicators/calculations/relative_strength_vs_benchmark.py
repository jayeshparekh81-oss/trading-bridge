"""Relative Strength vs Benchmark — Phase-1 STUB.

⚠️  This indicator is intentionally a no-op in Pack 13.

The real implementation needs to fetch a parallel benchmark
candle series (e.g. NIFTY for stock RS) at the same bar
frequency + alignment as the input, then compute a rolling
ratio of the symbol's return vs the benchmark's. The data-
provider layer doesn't yet expose a "fetch benchmark series for
the same window" helper at the calc-layer abstraction; that
crossing is a Phase 2 item — same shape as the Pack 8
``nifty_correlation`` stub.

For now the function returns an all-``None`` series of the right
length. Strategies that reference it get a defined-shape
placeholder they can branch on (``is None`` -> "data not yet
available"). The :data:`HAS_BENCHMARK_CONTEXT` flag is the
operator-visible signal for the dashboard.

Phase 2 plan: add a ``benchmark_close: Sequence[float]``
parameter sourced from a higher-level data-provider call. The
signature will gain that argument; current call sites that pass
only ``period`` will continue to receive an all-``None`` series
until the dispatcher is updated to thread the benchmark series
in.
"""

from __future__ import annotations

from collections.abc import Sequence

#: Operator-visible flag. The dashboard / registry UI can render a
#: "needs benchmark context" badge by importing this constant
#: rather than hardcoding the indicator id.
HAS_BENCHMARK_CONTEXT = False


def relative_strength_vs_benchmark(
    closes: Sequence[float],
    period: int = 30,
) -> list[float | None]:
    """Phase 1 stub - returns an all-``None`` series of length
    ``len(closes)``.

    Validates ``period`` so a typo at the config layer still
    surfaces a useful ``ValueError`` instead of being silently
    accepted."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 1:
        raise ValueError(f"period must be an int > 1; got {period!r}.")
    return [None] * len(closes)


__all__ = ["HAS_BENCHMARK_CONTEXT", "relative_strength_vs_benchmark"]

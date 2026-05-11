"""Indicator dispatch interface + shared helpers.

Every concrete indicator subclasses :class:`IndicatorImpl` (well — it
implements the Protocol; we use a Protocol rather than ABC so each
concrete impl can be a plain class without inheritance noise).

The orchestrator (:mod:`app.services.indicator_service`) holds a
``REGISTRY: dict[IndicatorName, IndicatorImpl]`` populated by the
package ``__init__``; on every request it does

    impl = REGISTRY[request.params.indicator]
    series = impl.compute(candles, request.params)

and serialises the result into :class:`IndicatorResponse`.

Design rules every concrete indicator must follow:

    * **Pure**: no I/O, no global state, no logging from
      ``compute()``. Inputs are immutable; outputs are deterministic
      for given inputs.
    * **NaN-propagate**: pass NaN inputs through TA-Lib unchanged.
      Output contains ``float('nan')`` at warm-up positions and
      wherever the input had NaN; the service converts these to
      ``None`` at the JSON boundary.
    * **Float ouput, not Decimal**: TA-Lib returns float64. Chart
      consumers display price-precision (2-4 decimals); the latency
      cost of Decimal conversion is not worth it for a read-only
      visualisation surface.
    * **Output keys come from ``output_names``** — a class attribute
      so the orchestrator builds the response ``series`` dict without
      having to introspect the impl.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from app.schemas.candle import Candle
from app.schemas.indicator import (
    BbParams,
    EmaParams,
    IndicatorName,
    MacdParams,
    RsiParams,
    SmaParams,
)


#: Type alias for "any of the discriminated params shapes".
IndicatorParamsLike = (
    SmaParams | EmaParams | RsiParams | MacdParams | BbParams
)


class IndicatorImpl(Protocol):
    """Protocol every concrete indicator implements.

    Concrete impls are *registered* via the package ``__init__``
    rather than via metaclass-magic so the registration step is
    explicit and grep-able.
    """

    #: The :class:`IndicatorName` this impl handles. Used as the
    #: registry key.
    name: IndicatorName

    #: Tuple of output series names this indicator produces, in a
    #: stable order. Single-output indicators yield ``("value",)``;
    #: multi-output yield e.g. ``("macd", "signal", "histogram")``.
    output_names: tuple[str, ...]

    def compute(
        self, candles: list[Candle], params: IndicatorParamsLike
    ) -> dict[str, np.ndarray]:
        """Return one ``np.ndarray`` per output series, aligned 1:1
        with ``candles``.

        Pre-warmup positions and NaN-input positions return
        ``np.nan``; the orchestrator translates these to ``None`` in
        the JSON response.

        Implementations may assume ``candles`` is closed-only and
        chronologically sorted ascending — the candle-source helper
        enforces this before dispatch.
        """
        ...


#: Process-wide dispatch table, populated by
#: :mod:`app.services.indicators.__init__`.
REGISTRY: dict[IndicatorName, IndicatorImpl] = {}


# ═══════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════


def closes_as_array(candles: list[Candle]) -> np.ndarray:
    """Extract the ``close`` field of ``candles`` into a contiguous
    float64 numpy array — the canonical input shape for every TA-Lib
    call we make.

    Uses ``float(...)`` on each :class:`~decimal.Decimal` value rather
    than ``np.array([c.close for c in candles])`` directly, because
    numpy doesn't know how to convert ``Decimal`` to float64 in
    bulk — it raises ``TypeError``. The per-row ``float()`` cast is
    safe because ``Candle.close`` is bounded (``gt=0`` validator) and
    we lose no precision a chart can display.
    """
    if not candles:
        return np.empty(0, dtype=np.float64)
    return np.array(
        [float(c.close) for c in candles], dtype=np.float64
    )


def nan_array(length: int, count: int = 1) -> dict[str, np.ndarray]:
    """Return ``count`` numpy arrays of NaN, each length ``length``.

    Used by indicators when ``candles`` is empty or below the warmup
    threshold so the response shape stays consistent regardless of
    how much data the caller asked for.
    """
    return {
        f"_{i}": np.full(length, np.nan, dtype=np.float64)
        for i in range(count)
    }


__all__ = [
    "IndicatorImpl",
    "IndicatorParamsLike",
    "REGISTRY",
    "closes_as_array",
    "nan_array",
]

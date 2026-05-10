"""Shared 22-key indicator vector helpers — used by Black-Swan Anomaly
Shield (z-score detector) and Trade DNA Sequencing (cosine k-NN).

Both services consume the same indicator payload from the TradingView
webhook (Pine emits these 22 fields on every bar close) and need the
same fixed-order vectorization. Centralising the key list here prevents
the two services from drifting apart silently.
"""

from __future__ import annotations

from typing import Any

#: 22-key fixed-order indicator basis. Matches the legacy AWS bot's
#: ``trade_brain._DNA_KEYS`` (``/tmp/cowork_legacy/trade_brain.py:147``)
#: byte-for-byte. **Order matters** — both services store vectors
#: positionally and z-score per index, so reordering breaks every cached
#: history entry.
DNA_KEYS: tuple[str, ...] = (
    "PriceSpd", "RSI", "ATR", "RVOL", "DeltaPwr", "OFInten", "VWAPDist",
    "FastMA", "SlowMA", "LongMA", "GaussL", "GaussS", "BodyPct", "Squeeze",
    "BearGap", "BullGap", "Vol", "ADX", "MFI", "STDir", "OIBuild", "MACDH",
)


def coerce_float(value: Any) -> float:
    """Best-effort float coercion. Missing / unparseable → 0.0.

    Matches the ai_validator contract: a missing indicator scores as 0
    rather than raising, so a mid-payload schema drift never poisons a
    live signal.
    """
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def indicators_to_vector(indicators: dict[str, Any]) -> list[float]:
    """Project an indicator dict into the fixed-order DNA vector."""
    return [coerce_float(indicators.get(k)) for k in DNA_KEYS]


__all__ = ["DNA_KEYS", "coerce_float", "indicators_to_vector"]

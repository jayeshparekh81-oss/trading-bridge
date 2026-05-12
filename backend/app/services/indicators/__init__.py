"""Indicator implementations + central dispatch registry.

Importing this package eagerly imports every concrete indicator module
so the :data:`REGISTRY` dict is populated by the time the orchestrator
asks for a dispatch entry.

Phase 2 additions:
    1. Drop a new file `services/indicators/{name}.py` with a class
       implementing :class:`IndicatorImpl` (see ``base.py``).
    2. Add ``from .{name} import {Name}Indicator`` below + register it.
    3. Done — the orchestrator picks it up via the registry.
"""

from __future__ import annotations

from app.services.indicators.base import REGISTRY, IndicatorImpl
from app.services.indicators.bb import BollingerBandsIndicator
from app.services.indicators.ema import EmaIndicator
from app.services.indicators.macd import MacdIndicator
from app.services.indicators.rsi import RsiIndicator
from app.services.indicators.sma import SmaIndicator

# Register each implementation by its IndicatorName enum value. The
# orchestrator does ``REGISTRY[params.indicator]`` at request time.
for _impl in (
    SmaIndicator(),
    EmaIndicator(),
    RsiIndicator(),
    MacdIndicator(),
    BollingerBandsIndicator(),
):
    REGISTRY[_impl.name] = _impl


__all__ = [
    "BollingerBandsIndicator",
    "EmaIndicator",
    "IndicatorImpl",
    "MacdIndicator",
    "REGISTRY",
    "RsiIndicator",
    "SmaIndicator",
]

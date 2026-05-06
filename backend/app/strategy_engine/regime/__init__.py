"""Market Regime detector — public boundary.

Pure deterministic pipeline that consumes a candle stream and returns
a structured :class:`RegimeReport`. No LLM calls, no network, no
clock reads — the same inputs always produce the same report.

Public surface::

    detect_regime / RegimeReport / RegimeMetrics / RegimeName /
    StrategySuitability / StrategyType / SuitabilityRiskLevel
"""

from __future__ import annotations

from app.strategy_engine.regime.detector import detect_regime
from app.strategy_engine.regime.models import (
    RegimeMetrics,
    RegimeName,
    RegimeReport,
    StrategySuitability,
    StrategyType,
    SuitabilityRiskLevel,
)

__all__ = [
    "RegimeMetrics",
    "RegimeName",
    "RegimeReport",
    "StrategySuitability",
    "StrategyType",
    "SuitabilityRiskLevel",
    "detect_regime",
]

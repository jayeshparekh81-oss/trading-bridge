"""Compliance dashboard — license / lifecycle visibility.

Pure read-only layer over the indicator registry + strategies
table. Never mutates registry state, never re-classifies indicators
behind the registry's back. The registry's
:class:`IndicatorStatus` enum is the source of truth; this module
maps those statuses to user-facing risk + scoring.
"""

from app.strategy_engine.compliance.aggregate import (
    LicenseUsageStats,
    compute_indicator_usage_stats,
)
from app.strategy_engine.compliance.evaluator import (
    BLOCKED_RISK,
    SAFE_RISK,
    WARNING_RISK,
    IndicatorComplianceInfo,
    StrategyComplianceReport,
    StrategyComplianceSummary,
    evaluate_indicator,
    evaluate_strategy_compliance,
    summarise_strategy,
)

__all__ = [
    "BLOCKED_RISK",
    "SAFE_RISK",
    "WARNING_RISK",
    "IndicatorComplianceInfo",
    "LicenseUsageStats",
    "StrategyComplianceReport",
    "StrategyComplianceSummary",
    "compute_indicator_usage_stats",
    "evaluate_indicator",
    "evaluate_strategy_compliance",
    "summarise_strategy",
]

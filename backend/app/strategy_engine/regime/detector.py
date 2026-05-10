"""Market Regime detector — orchestrator.

Pure deterministic pipeline:

    candles ─► metrics ─► classifier ─► (optional) suitability ─► report

No LLM calls, no network, no clock reads. Inputs are immutable
sequences of :class:`Candle`; outputs are frozen Pydantic models.
"""

from __future__ import annotations

from app.strategy_engine.regime.classifier import classify_regime
from app.strategy_engine.regime.metrics import compute_metrics
from app.strategy_engine.regime.models import (
    RegimeMetrics,
    RegimeName,
    RegimeReport,
)
from app.strategy_engine.regime.suitability import (
    assess_suitability,
    detect_strategy_type,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

# ─── Hinglish summaries (locked templates) ─────────────────────────────


_HINGLISH_SUMMARIES: dict[RegimeName, str] = {
    "trending": "Market trend mein hai. Trend-following strategies achhi chalengi.",
    "sideways": ("Market range mein hai. Trend-following strategies false signals de sakti hain."),
    "high_volatility": ("Volatility zyada hai. Position size kam karo ya stop loss wider."),
    "low_volatility": "Volatility kam hai. Breakout setups intezaar karo.",
    "gap_day": ("Gap day detected. Backtest assumptions live mein match nahi karenge."),
    "choppy": ("Market choppy hai. Whipsaws zyada honge — paper trade pehle."),
    "breakout": "Range expansion ho rahi hai. Breakout setups active.",
    "abnormal": ("Market mein abnormal movement. Trade na karna recommended."),
}


# ─── Public API ────────────────────────────────────────────────────────


def detect_regime(
    candles: list[Candle],
    strategy: StrategyJSON | None = None,
    timeframe: str = "5m",
) -> RegimeReport:
    """Classify the current market regime from ``candles``.

    Args:
        candles: OHLCV bars in chronological order. Behaviour degrades
            gracefully on short series — a sub-30-bar input still
            produces a report (typically ``abnormal`` or ``sideways``)
            so the caller can still make decisions.
        strategy: Optional Phase 1 DSL. When supplied the report
            includes a :class:`StrategySuitability` verdict matching
            the strategy's archetype against the detected regime.
        timeframe: Carried for future use (the metrics + classifier
            are timeframe-agnostic right now). Stored unused so the
            public signature stays stable when timeframe-specific
            tuning lands later.

    Returns:
        :class:`RegimeReport` with regime, confidence, the metric
        snapshot, locked Hinglish summary, and (when ``strategy`` is
        supplied) a strategy suitability verdict.
    """
    # ``timeframe`` is reserved for future tuning (different ADX /
    # range windows per timeframe). Reference it explicitly so static
    # analysis doesn't flag the parameter as unused.
    _ = timeframe

    metrics = compute_metrics(candles)
    regime, confidence = classify_regime(metrics, list(candles))

    warnings = _build_warnings(regime, metrics)

    suitability = None
    if strategy is not None:
        strategy_type = detect_strategy_type(strategy)
        suitability = assess_suitability(strategy_type, regime)

    return RegimeReport(
        regime=regime,
        confidence=confidence,
        metrics=metrics,
        warnings=tuple(warnings),
        strategy_suitability=suitability,
        hinglish_summary=_HINGLISH_SUMMARIES[regime],
    )


def _build_warnings(regime: RegimeName, metrics: RegimeMetrics) -> list[str]:
    """Surface metric-level concerns the operator should see alongside
    the regime verdict — short factual lines, never a wall of text."""
    out: list[str] = []
    if metrics.gap_percent is not None and abs(metrics.gap_percent) > 0.005:
        out.append(
            f"Gap of {metrics.gap_percent * 100:.2f}% from previous close — "
            "live fills will diverge from backtest opens."
        )
    if metrics.volatility_percentile >= 0.95:
        out.append("Volatility is in the top 5% of recent history — size positions down.")
    if metrics.direction_changes_count >= 15:
        out.append(
            f"{metrics.direction_changes_count} direction flips in the last "
            "30 bars — whipsaw risk is elevated."
        )
    if regime == "abnormal":
        out.append("Abnormal market state — discretion advised over automation.")
    return out


__all__ = ["detect_regime"]

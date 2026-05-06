"""Strategy-regime suitability matching.

Two responsibilities:

    1. Heuristically detect the *type* of a user-built strategy from
       its indicators + entry conditions
       (:func:`detect_strategy_type`).
    2. Map ``(strategy_type, regime)`` to a :class:`StrategySuitability`
       verdict (:func:`assess_suitability`).

The matrix is intentionally narrow — only the locked combinations from
the spec produce a strong verdict. Unlisted combinations default to
``suitable=True, risk="medium"`` with a generic note so the broker
guard / advisor can still surface a reasonable recommendation without
inventing rules that aren't documented.

The detection is best-effort: a strategy whose indicators don't match
any known archetype gets ``StrategyType.unknown`` and a neutral
suitability verdict.
"""

from __future__ import annotations

from app.strategy_engine.regime.models import (
    RegimeName,
    StrategySuitability,
    StrategyType,
)
from app.strategy_engine.schema.strategy import (
    IndicatorCondition,
    PriceCondition,
    PriceConditionOp,
    StrategyJSON,
)

# ─── Strategy-type detection ───────────────────────────────────────────


_TREND_INDICATOR_TYPES: frozenset[str] = frozenset(
    {"ema", "sma", "wma", "macd", "ichimoku", "linear_regression"}
)
_MEAN_REVERSION_INDICATOR_TYPES: frozenset[str] = frozenset(
    {"rsi", "bollinger_bands", "stochastic", "ultimate_oscillator", "williams_r"}
)
_BREAKOUT_PRICE_OPS: frozenset[PriceConditionOp] = frozenset(
    {PriceConditionOp.PREVIOUS_HIGH_BREAKOUT, PriceConditionOp.PREVIOUS_LOW_BREAKDOWN}
)
_VOLATILITY_INDICATOR_TYPES: frozenset[str] = frozenset({"atr"})


def detect_strategy_type(strategy: StrategyJSON) -> StrategyType:
    """Pick the most likely archetype from the strategy's shape.

    Detection priority (locked):

        1. ``breakout`` — entry uses a price-breakout primitive (the
           clearest signature; never overridden).
        2. ``mean_reversion`` — strategy declares an oscillator
           indicator AND the entry compares it against a constant
           value (e.g. ``RSI < 30``).
        3. ``trend_following`` — strategy declares two trend-family
           indicators AND the entry crosses them (`>`, `<`,
           `crossover`, `crossunder` between two indicator series).
        4. ``volatility`` — strategy declares an ATR-family indicator.
        5. ``unknown`` — nothing else matches.
    """
    # 1. Breakout via price-breakout primitives.
    for cond in strategy.entry.conditions:
        if isinstance(cond, PriceCondition) and cond.op in _BREAKOUT_PRICE_OPS:
            return "breakout"
    for cond in strategy.exit.indicator_exits:
        if isinstance(cond, PriceCondition) and cond.op in _BREAKOUT_PRICE_OPS:
            return "breakout"

    indicator_types = {ind.type for ind in strategy.indicators}

    # 2. Mean-reversion: oscillator + value-based comparison.
    has_oscillator = bool(indicator_types & _MEAN_REVERSION_INDICATOR_TYPES)
    has_value_compare = any(
        isinstance(c, IndicatorCondition) and c.value is not None for c in strategy.entry.conditions
    )
    if has_oscillator and has_value_compare:
        return "mean_reversion"

    # 3. Trend-following: two trend indicators + an indicator-vs-indicator
    #    comparison (the user is testing one trend line against another).
    trend_types = indicator_types & _TREND_INDICATOR_TYPES
    has_indicator_vs_indicator = any(
        isinstance(c, IndicatorCondition) and c.right is not None for c in strategy.entry.conditions
    )
    if len(trend_types) >= 2 and has_indicator_vs_indicator:
        return "trend_following"

    # 4. Volatility-based.
    if indicator_types & _VOLATILITY_INDICATOR_TYPES:
        return "volatility"

    # 5. Single trend indicator with simple value comparison — close
    # enough to trend-following for the matrix to land somewhere useful.
    if trend_types:
        return "trend_following"

    return "unknown"


# ─── Suitability matrix ────────────────────────────────────────────────


def assess_suitability(strategy_type: StrategyType, regime: RegimeName) -> StrategySuitability:
    """Map (strategy_type, regime) → :class:`StrategySuitability`.

    Hard rules from the spec:

        * trend_following + sideways → not suitable, risk=high
        * trend_following + trending → suitable, risk=low
        * mean_reversion + trending → not suitable, risk=high
        * mean_reversion + sideways → suitable, risk=low
        * any + abnormal → not suitable, risk=high
        * any + gap_day → suitable, risk=high (warning)

    Additional sensible defaults the spec implies but doesn't list:

        * trend_following + choppy → not suitable (whipsaws), risk=high
        * mean_reversion + choppy → marginal, risk=medium
        * breakout + breakout regime → suitable, risk=low
        * breakout + sideways → not yet suitable, risk=medium
        * any + high_volatility → suitable, risk=high
        * any + low_volatility → marginal, risk=medium

    Anything else → ``suitable=True, risk="medium"`` with a generic note.
    """
    # ── Universal regime overrides ────────────────────────────────
    if regime == "abnormal":
        return StrategySuitability(
            suitable=False,
            reason=("Market mein abnormal movement detected — koi bhi strategy live trade na ho."),
            risk_level="high",
            strategy_type=strategy_type,
        )
    if regime == "gap_day":
        return StrategySuitability(
            suitable=True,
            reason=(
                "Gap day — strategy chal sakti hai par live fills backtest se "
                "alag honge. Position size kam karo."
            ),
            risk_level="high",
            strategy_type=strategy_type,
        )

    # ── Strategy-specific rules ───────────────────────────────────
    if strategy_type == "trend_following":
        if regime == "trending":
            return StrategySuitability(
                suitable=True,
                reason="Trend market mein trend-following strategies achhi chalti hain.",
                risk_level="low",
                strategy_type=strategy_type,
            )
        if regime in ("sideways", "choppy"):
            return StrategySuitability(
                suitable=False,
                reason=(
                    "Sideways/choppy market mein trend-following strategy false "
                    "signals degi — losses zyada honge."
                ),
                risk_level="high",
                strategy_type=strategy_type,
            )

    if strategy_type == "mean_reversion":
        if regime == "sideways":
            return StrategySuitability(
                suitable=True,
                reason="Range-bound market mean-reversion ke liye ideal hai.",
                risk_level="low",
                strategy_type=strategy_type,
            )
        if regime == "trending":
            return StrategySuitability(
                suitable=False,
                reason=(
                    "Trending market mein RSI/oscillator-based entries jaldi "
                    "trigger hote hain par price aur badh/gir sakti hai — "
                    "mean-reversion not suitable."
                ),
                risk_level="high",
                strategy_type=strategy_type,
            )
        if regime == "choppy":
            return StrategySuitability(
                suitable=True,
                reason=(
                    "Choppy market mean-reversion ke liye OK hai par whipsaws "
                    "kaafi honge — position size dheere rakho."
                ),
                risk_level="medium",
                strategy_type=strategy_type,
            )

    if strategy_type == "breakout":
        if regime == "breakout":
            return StrategySuitability(
                suitable=True,
                reason="Active range expansion — breakout strategy ke liye sahi waqt.",
                risk_level="low",
                strategy_type=strategy_type,
            )
        if regime == "sideways":
            return StrategySuitability(
                suitable=False,
                reason=(
                    "Sideways market mein breakouts ka false signal aata hai — "
                    "compression ke baad expansion ka intezaar karo."
                ),
                risk_level="medium",
                strategy_type=strategy_type,
            )

    # ── Volatility regime overlay (applies regardless of strategy) ─
    if regime == "high_volatility":
        return StrategySuitability(
            suitable=True,
            reason=(
                "High volatility regime — strategy chal sakti hai par stop loss "
                "wider aur position size kam rakho."
            ),
            risk_level="high",
            strategy_type=strategy_type,
        )
    if regime == "low_volatility":
        return StrategySuitability(
            suitable=True,
            reason=(
                "Low volatility — moves chhote rahenge; targets thoda agressive "
                "rakhne pe trade kam fire honge."
            ),
            risk_level="medium",
            strategy_type=strategy_type,
        )

    # Default fallback for unlisted combinations.
    return StrategySuitability(
        suitable=True,
        reason=(
            f"Strategy type {strategy_type} ke liye {regime} regime mein no hard "
            "warning — paper trade pe verify karo."
        ),
        risk_level="medium",
        strategy_type=strategy_type,
    )


__all__ = ["assess_suitability", "detect_strategy_type"]

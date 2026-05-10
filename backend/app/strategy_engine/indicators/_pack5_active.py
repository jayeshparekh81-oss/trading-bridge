"""Pack 5 — 12 advanced statistical / risk / performance indicators.

All 12 ids are net-new (no coming-soon stubs to override).

Difficulty split:

    INTERMEDIATE (6) — percentile_rank, percentile_nearest,
                       median_value, max_drawdown_pct,
                       underwater_curve, zscore
    EXPERT (6)       — sharpe_ratio, sortino_ratio, calmar_ratio,
                       omega_ratio, recovery_factor,
                       hurst_exponent

Pine importer wires only the 3 ids whose Pine ``ta.*`` equivalents
exist in the standard library (``percentrank``,
``percentile_nearest_rank``, ``median``); the other 9 are
builder-UI only.
"""

from __future__ import annotations

from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
    InputSpec,
    InputType,
)

# ─── Statistical Ranks (3) ─────────────────────────────────────────────


_PERCENTILE_RANK = IndicatorMetadata(
    id="percentile_rank",
    name="Percentile Rank",
    category="Statistical",
    description=(
        "Percentile rank of the current value within the trailing "
        "``period`` bars (matches Pine ``ta.percentrank``). Output "
        "0-100; 90 means the current bar is among the highest 10 % "
        "of the lookback."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=100, min=2, max=2000),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.percentrank"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Percentile Rank dikhata hai ki abhi ka close pichla 100 "
        "bars mein kahan baith raha hai. >90 = nayi peak banne ka "
        "chance, <10 = oversold zone."
    ),
    tags=["statistical", "rank"],
    calculation_function="percentile_rank",
)

_PERCENTILE_NEAREST = IndicatorMetadata(
    id="percentile_nearest",
    name="Percentile (Nearest Rank)",
    category="Statistical",
    description=(
        "Value at percentage ``p`` within the trailing ``period`` "
        "bars using the nearest-rank method (matches Pine "
        "``ta.percentile_nearest_rank``)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=100, min=2, max=2000),
        InputSpec(
            name="percentage", type=InputType.NUMBER, default=50.0, min=0.0, max=100.0
        ),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.percentile_nearest_rank"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Percentile Nearest se aap puch sakte ho 'last 100 bars ka "
        "75th percentile close kya tha?'. Resistance / target levels "
        "set karne ke liye useful."
    ),
    tags=["statistical", "rank"],
    calculation_function="percentile_nearest",
)

_MEDIAN_VALUE = IndicatorMetadata(
    id="median_value",
    name="Median Value",
    category="Statistical",
    description=(
        "Rolling median of the trailing ``period`` bars (matches "
        "Pine ``ta.median``). More robust to outliers than SMA."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.median"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Median outlier-resistant central tendency hai — gap-up / "
        "spike days ke baad SMA distort ho jaata hai but median "
        "stable rehta hai."
    ),
    tags=["statistical", "robust"],
    calculation_function="median_value",
)

# ─── Performance Ratios (4) — all EXPERT ───────────────────────────────


_SHARPE_RATIO = IndicatorMetadata(
    id="sharpe_ratio",
    name="Sharpe Ratio",
    category="Performance",
    description=(
        "Annualised Sharpe Ratio over a trailing window (mean excess "
        "return / annualised stdev). Default ``period=252`` rolls a "
        "1-year Sharpe on daily data."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=252, min=20, max=5000),
        InputSpec(
            name="annualization", type=InputType.NUMBER, default=252, min=1, max=10000
        ),
        InputSpec(
            name="risk_free_rate", type=InputType.NUMBER, default=0.0, min=-1, max=1
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Sharpe risk-adjusted return ka classic measure hai. >1 "
        "decent, >2 strong, >3 outstanding. Lekin tail risk ignore "
        "karta hai — Sortino zyada accurate downside picture deta hai."
    ),
    tags=["performance", "ratio", "risk-adjusted"],
    calculation_function="sharpe_ratio",
)

_SORTINO_RATIO = IndicatorMetadata(
    id="sortino_ratio",
    name="Sortino Ratio",
    category="Performance",
    description=(
        "Annualised Sortino Ratio — like Sharpe but uses *downside* "
        "deviation only. Captures how much pain you're getting paid "
        "for, ignoring beneficial volatility."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=252, min=20, max=5000),
        InputSpec(
            name="annualization", type=InputType.NUMBER, default=252, min=1, max=10000
        ),
        InputSpec(
            name="risk_free_rate", type=InputType.NUMBER, default=0.0, min=-1, max=1
        ),
        InputSpec(
            name="target_return", type=InputType.NUMBER, default=0.0, min=-1, max=1
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Sortino Sharpe se behtar hai jab returns asymmetric ho. "
        "Trend-following systems ke liye jyada relevant — upside "
        "vol punish nahi karta."
    ),
    tags=["performance", "ratio", "downside-risk"],
    calculation_function="sortino_ratio",
)

_CALMAR_RATIO = IndicatorMetadata(
    id="calmar_ratio",
    name="Calmar Ratio",
    category="Performance",
    description=(
        "Annualised return / max drawdown over a trailing window. "
        "Most stable of the drawdown-based ratios — bounded "
        "denominator prevents the explosive behaviour of Sharpe in "
        "low-vol regimes."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=252, min=20, max=5000),
        InputSpec(
            name="annualization", type=InputType.NUMBER, default=252, min=1, max=10000
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Calmar = return / max DD. Trend-following / managed-futures "
        "industry mein primary KPI. >1 acceptable, >3 elite."
    ),
    tags=["performance", "ratio", "drawdown"],
    calculation_function="calmar_ratio",
)

_OMEGA_RATIO = IndicatorMetadata(
    id="omega_ratio",
    name="Omega Ratio",
    category="Performance",
    description=(
        "Probability-weighted gains-to-losses ratio relative to a "
        "threshold (Keating + Shadwick, 2002). Captures the entire "
        "return distribution, not just first two moments."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=252, min=20, max=5000),
        InputSpec(
            name="threshold", type=InputType.NUMBER, default=0.0, min=-1, max=1
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Omega Sharpe ke beyond — full distribution dekhta hai. >1 "
        "matlab gains exceed losses (probability-weighted) at the "
        "threshold."
    ),
    tags=["performance", "ratio", "distribution"],
    calculation_function="omega_ratio",
)

# ─── Risk / Performance (3) ────────────────────────────────────────────


_MAX_DRAWDOWN_PCT = IndicatorMetadata(
    id="max_drawdown_pct",
    name="Max Drawdown %",
    category="Risk",
    description=(
        "Rolling max drawdown over the last ``period`` bars, "
        "expressed as a positive percent. Zero means the window "
        "rose monotonically."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=60, min=2, max=2000),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Max DD % aapke worst-case loss ka measure hai trailing "
        "window mein. Position sizing aur risk-of-ruin ke calc mein "
        "load-bearing."
    ),
    tags=["risk", "drawdown"],
    calculation_function="max_drawdown_pct",
)

_UNDERWATER_CURVE = IndicatorMetadata(
    id="underwater_curve",
    name="Underwater Curve",
    category="Risk",
    description=(
        "Cumulative drawdown from the running all-time peak. Output "
        "is ``<= 0`` percent at every bar; ``0`` means new ATH."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Underwater Curve cumulative — visually dikhata hai kab "
        "strategy / instrument ne new peak banayi aur kab kitna "
        "neeche thi. Equity-curve QA ka standard plot."
    ),
    tags=["risk", "drawdown", "equity-curve"],
    calculation_function="underwater_curve",
)

_RECOVERY_FACTOR = IndicatorMetadata(
    id="recovery_factor",
    name="Recovery Factor",
    category="Risk",
    description=(
        "Net return divided by max drawdown over a trailing "
        "window — robustness measure favoured by trend-following "
        "systems."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=60, min=2, max=2000),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Recovery Factor = return / DD. Higher matlab har rupiya "
        "DD ke liye zyada profit nikala. Trend-system robustness "
        "ka indicator."
    ),
    tags=["risk", "performance", "drawdown"],
    calculation_function="recovery_factor",
)

# ─── Advanced Statistical (2) ──────────────────────────────────────────


_HURST_EXPONENT = IndicatorMetadata(
    id="hurst_exponent",
    name="Hurst Exponent",
    category="Statistical",
    description=(
        "Hurst exponent via Rescaled-Range analysis. ``H < 0.5`` = "
        "mean-reverting tape; ``H ≈ 0.5`` = random walk; ``H > 0.5`` "
        "= trending. Window ``period=100`` is the practical minimum."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=100, min=16, max=2000),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Hurst regime classifier hai — strategy switching ke liye "
        "use karo. Trend-following ko H > 0.55 ke time mein chalao, "
        "mean-reversion ko H < 0.45 mein."
    ),
    tags=["statistical", "regime"],
    calculation_function="hurst_exponent",
)

_ZSCORE = IndicatorMetadata(
    id="zscore",
    name="Z-Score",
    category="Statistical",
    description=(
        "Standardised distance from the rolling mean: ``(value - "
        "mean) / stdev``. Population variance (matches Pine's "
        "``ta.stdev``)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Z-Score mean-reversion entries ka classic trigger. ``|z| > "
        "2`` ka matlab 2 sigma tail — reversion ka chance high."
    ),
    tags=["statistical", "mean-reversion"],
    calculation_function="zscore",
)

# ─── Aggregate ─────────────────────────────────────────────────────────


PACK5_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _PERCENTILE_RANK,
    _PERCENTILE_NEAREST,
    _MEDIAN_VALUE,
    _SHARPE_RATIO,
    _SORTINO_RATIO,
    _CALMAR_RATIO,
    _OMEGA_RATIO,
    _MAX_DRAWDOWN_PCT,
    _UNDERWATER_CURVE,
    _RECOVERY_FACTOR,
    _HURST_EXPONENT,
    _ZSCORE,
)


__all__ = ["PACK5_ACTIVE_INDICATORS"]

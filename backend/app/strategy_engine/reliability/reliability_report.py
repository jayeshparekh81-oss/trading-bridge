"""Reliability report — single-call orchestrator that bundles every check.

Convenience wrapper around :func:`calculate_trust_score`,
:func:`run_out_of_sample`, :func:`run_walk_forward`, and
:func:`run_sensitivity`. The UI builder (Phase 5) and AI advisor
(Phase 6) call ``build_reliability_report`` and consume the structured
:class:`ReliabilityReport` directly.

Each sub-analysis can be opted out of via a flag — useful when the
caller already has a pre-computed result or wants to avoid the
~21-backtest cost of a full sensitivity run during interactive UI work.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.strategy_engine.backtest import (
    BacktestInput,
    BacktestResult,
    CostSettings,
    run_backtest,
)
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.reliability.out_of_sample import (
    OOSResult,
    run_out_of_sample,
)
from app.strategy_engine.reliability.parameter_sensitivity import (
    SensitivityResult,
    run_sensitivity,
)
from app.strategy_engine.reliability.trust_score import (
    TrustScore,
    calculate_trust_score,
)
from app.strategy_engine.reliability.walk_forward import (
    WalkForwardResult,
    run_walk_forward,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON


class ReliabilityReport(BaseModel):
    """Top-level reliability boundary — what the UI / advisor consumes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    backtest: BacktestResult
    trust_score: TrustScore
    out_of_sample: OOSResult | None = None
    walk_forward: WalkForwardResult | None = None
    sensitivity: SensitivityResult | None = None


def build_reliability_report(
    *,
    strategy: StrategyJSON,
    candles: Sequence[Candle],
    initial_capital: float = 100_000.0,
    quantity: float = 1.0,
    cost_settings: CostSettings | None = None,
    ambiguity_mode: AmbiguityMode = AmbiguityMode.CONSERVATIVE,
    include_oos: bool = True,
    include_walk_forward: bool = True,
    include_sensitivity: bool = True,
) -> ReliabilityReport:
    """Compose a full :class:`ReliabilityReport` for ``strategy`` over ``candles``.

    The base backtest runs unconditionally; each optional analysis is
    gated by its corresponding ``include_*`` flag. When the candle list
    is too short for an analysis (e.g. < 4 for OOS, < 20 for walk-
    forward), that analysis is silently skipped — the trust score still
    fires the checks that have inputs supplied.
    """
    cost_settings = cost_settings or CostSettings()
    candles_list = list(candles)

    base_result = run_backtest(
        BacktestInput(
            candles=candles_list,
            strategy=strategy,
            initial_capital=initial_capital,
            quantity=quantity,
            cost_settings=cost_settings,
            ambiguity_mode=ambiguity_mode,
        )
    )

    oos: OOSResult | None = None
    if include_oos and len(candles_list) >= 4:
        oos = run_out_of_sample(
            strategy=strategy,
            candles=candles_list,
            initial_capital=initial_capital,
            quantity=quantity,
            cost_settings=cost_settings,
            ambiguity_mode=ambiguity_mode,
        )

    wf: WalkForwardResult | None = None
    if include_walk_forward and len(candles_list) >= 20:
        wf = run_walk_forward(
            strategy=strategy,
            candles=candles_list,
            initial_capital=initial_capital,
            quantity=quantity,
            cost_settings=cost_settings,
            ambiguity_mode=ambiguity_mode,
        )

    sensitivity: SensitivityResult | None = None
    if include_sensitivity:
        sensitivity = run_sensitivity(
            strategy=strategy,
            candles=candles_list,
            initial_capital=initial_capital,
            quantity=quantity,
            cost_settings=cost_settings,
            ambiguity_mode=ambiguity_mode,
        )

    trust = calculate_trust_score(
        base_result,
        oos_degradation=(oos.degradation_percent if oos else None),
        walk_forward_consistency=(wf.summary.consistency_score if wf else None),
        sensitivity_fragile=(sensitivity.fragile if sensitivity else None),
    )

    return ReliabilityReport(
        backtest=base_result,
        trust_score=trust,
        out_of_sample=oos,
        walk_forward=wf,
        sensitivity=sensitivity,
    )


__all__ = ["ReliabilityReport", "build_reliability_report"]

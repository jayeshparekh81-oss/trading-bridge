"""Out-of-sample test — single 70/30 train/test split.

Splits the candle list into a 70 % training segment and a 30 % testing
segment, runs the Phase 3 backtest on each independently, and returns
the train/test pair plus a single ``degradation_percent`` figure.

Definition (locked Phase 4 contract):

    degradation_percent = (train.total_return_percent - test.total_return_percent)
                          / abs(train.total_return_percent)

with the convention that:
    * ``train.total_return_percent == 0`` -> degradation = 0 (no train P&L
      to "degrade from"; emit an INFO warning so the caller can re-frame).
    * ``test > train`` -> degradation < 0 (testing improved over training);
      no warning fires.
    * ``train > test`` and ``degradation > 0.25`` -> overfit-risk warning.

The function does not call any LLM, network, or DB. It re-uses Phase 3's
:func:`run_backtest` exactly — no parallel simulator implementation.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.backtest import (
    BacktestInput,
    BacktestResult,
    CostSettings,
    run_backtest,
)
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.reliability.constants import (
    OOS_DEGRADATION_WARNING_THRESHOLD,
    OOS_TRAIN_FRACTION,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON


class OOSResult(BaseModel):
    """Out-of-sample comparison — full BacktestResult on each side."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    training: BacktestResult
    testing: BacktestResult
    degradation_percent: float
    warning: str = Field(default="", max_length=512)


def run_out_of_sample(
    *,
    strategy: StrategyJSON,
    candles: Sequence[Candle],
    initial_capital: float = 100_000.0,
    quantity: float = 1.0,
    cost_settings: CostSettings | None = None,
    ambiguity_mode: AmbiguityMode = AmbiguityMode.CONSERVATIVE,
) -> OOSResult:
    """Run the strategy on the first 70 % then the last 30 % of ``candles``.

    Raises:
        ValueError: When the input has fewer than 4 candles (each side
            of the split must have at least the simulator's 2-candle
            minimum).
    """
    n = len(candles)
    if n < 4:
        raise ValueError(f"Need at least 4 candles to run an OOS split; got {n}.")

    split_index = max(2, int(n * OOS_TRAIN_FRACTION))
    # Both sides must have at least 2 candles for the simulator's
    # minimum; clamp split_index away from the boundaries.
    if split_index >= n - 1:
        split_index = n - 2

    train_candles = list(candles[:split_index])
    test_candles = list(candles[split_index:])

    cost_settings = cost_settings or CostSettings()

    train_result = run_backtest(
        BacktestInput(
            candles=train_candles,
            strategy=strategy,
            initial_capital=initial_capital,
            quantity=quantity,
            cost_settings=cost_settings,
            ambiguity_mode=ambiguity_mode,
        )
    )
    test_result = run_backtest(
        BacktestInput(
            candles=test_candles,
            strategy=strategy,
            initial_capital=initial_capital,
            quantity=quantity,
            cost_settings=cost_settings,
            ambiguity_mode=ambiguity_mode,
        )
    )

    degradation = _compute_degradation(
        train_return=train_result.total_return_percent,
        test_return=test_result.total_return_percent,
    )
    warning = _build_warning(degradation, train_result.total_return_percent)

    return OOSResult(
        training=train_result,
        testing=test_result,
        degradation_percent=degradation,
        warning=warning,
    )


# ─── Helpers ────────────────────────────────────────────────────────────


def _compute_degradation(*, train_return: float, test_return: float) -> float:
    """Locked formula. See module docstring for edge-case rules."""
    if train_return == 0:
        return 0.0
    return (train_return - test_return) / abs(train_return)


def _build_warning(degradation: float, train_return: float) -> str:
    """Compose the operator-visible warning string. Empty when no concern."""
    if train_return == 0:
        return (
            "Training segment produced zero return — degradation comparison "
            "is uninformative. Try a longer training window."
        )
    if degradation > OOS_DEGRADATION_WARNING_THRESHOLD:
        return (
            f"Out-of-sample performance degraded {degradation * 100:.1f} % "
            "from training to testing — overfit risk."
        )
    return ""


__all__ = ["OOSResult", "run_out_of_sample"]

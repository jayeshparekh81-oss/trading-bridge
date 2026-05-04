"""Walk-forward analysis — 5 tumbling windows, each with internal 70/30 split.

Locked Phase 4 interpretation (the simpler of the two reasonable readings of
"5 rolling windows, each 70/30"):

    The candle list is divided into :data:`WALK_FORWARD_WINDOWS` (5)
    sequential, non-overlapping segments of equal size. For each segment,
    the first :data:`WALK_FORWARD_TRAIN_FRACTION` (70 %) is the training
    sub-segment and the last 30 % is the testing sub-segment. The
    Phase 3 backtest runs on each sub-segment independently. A window
    "passes" iff its **test** sub-segment produces strictly positive
    total P&L.

    The consistency score = (passing windows) / (total windows).

The alternative — "anchored" walk-forward where training expands and
only the test slides — is a Phase 9 expansion. The choice is documented
here so a future review can switch interpretations cleanly.

Like :mod:`out_of_sample`, this module orchestrates Phase 3's
:func:`run_backtest` and contains zero re-implemented simulation logic.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.backtest import (
    BacktestInput,
    CostSettings,
    run_backtest,
)
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.reliability.constants import (
    WALK_FORWARD_TRAIN_FRACTION,
    WALK_FORWARD_WINDOWS,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON


class WalkForwardWindow(BaseModel):
    """One window's outcome — training + testing P&L plus pass/fail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(..., ge=0)
    train_pnl: float
    test_pnl: float
    passed: bool


class WalkForwardSummary(BaseModel):
    """Aggregate verdict across all windows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed_windows: int = Field(..., ge=0)
    failed_windows: int = Field(..., ge=0)
    consistency_score: float = Field(..., ge=0, le=1)


class WalkForwardResult(BaseModel):
    """Public output of :func:`run_walk_forward`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    windows: tuple[WalkForwardWindow, ...]
    summary: WalkForwardSummary


# ─── Public API ────────────────────────────────────────────────────────


#: Minimum candles per sub-segment (matches the Phase 3 simulator's floor).
_MIN_SUB_SEGMENT = 2

#: 5 windows x (2 train + 2 test) = 20 candles minimum to run a meaningful
#: walk-forward. Below this we raise rather than silently returning empty.
_MIN_TOTAL_CANDLES = WALK_FORWARD_WINDOWS * 2 * _MIN_SUB_SEGMENT


def run_walk_forward(
    *,
    strategy: StrategyJSON,
    candles: Sequence[Candle],
    initial_capital: float = 100_000.0,
    quantity: float = 1.0,
    cost_settings: CostSettings | None = None,
    ambiguity_mode: AmbiguityMode = AmbiguityMode.CONSERVATIVE,
) -> WalkForwardResult:
    """Run a tumbling-window walk-forward over the candle list.

    Raises:
        ValueError: When ``len(candles) < _MIN_TOTAL_CANDLES`` (20).
    """
    n = len(candles)
    if n < _MIN_TOTAL_CANDLES:
        raise ValueError(
            f"Need at least {_MIN_TOTAL_CANDLES} candles to run a "
            f"{WALK_FORWARD_WINDOWS}-window walk-forward; got {n}."
        )

    cost_settings = cost_settings or CostSettings()

    windows: list[WalkForwardWindow] = []
    segment_size = n // WALK_FORWARD_WINDOWS

    for idx in range(WALK_FORWARD_WINDOWS):
        start = idx * segment_size
        # The last window picks up any remainder candles so we never
        # silently drop tail data. Earlier windows are exactly
        # ``segment_size`` long.
        end = n if idx == WALK_FORWARD_WINDOWS - 1 else (idx + 1) * segment_size
        segment = candles[start:end]

        train, test = _split_70_30(segment)
        train_result = run_backtest(
            BacktestInput(
                candles=list(train),
                strategy=strategy,
                initial_capital=initial_capital,
                quantity=quantity,
                cost_settings=cost_settings,
                ambiguity_mode=ambiguity_mode,
            )
        )
        test_result = run_backtest(
            BacktestInput(
                candles=list(test),
                strategy=strategy,
                initial_capital=initial_capital,
                quantity=quantity,
                cost_settings=cost_settings,
                ambiguity_mode=ambiguity_mode,
            )
        )
        windows.append(
            WalkForwardWindow(
                index=idx,
                train_pnl=train_result.total_pnl,
                test_pnl=test_result.total_pnl,
                passed=test_result.total_pnl > 0,
            )
        )

    summary = _summarise(windows)
    return WalkForwardResult(windows=tuple(windows), summary=summary)


# ─── Internal helpers ──────────────────────────────────────────────────


def _split_70_30(
    segment: Sequence[Candle],
) -> tuple[Sequence[Candle], Sequence[Candle]]:
    """70/30 train/test split on a single window's segment.

    Clamps the split so each sub-segment has at least the simulator's
    2-candle floor.
    """
    seg_len = len(segment)
    split = int(seg_len * WALK_FORWARD_TRAIN_FRACTION)
    if split < _MIN_SUB_SEGMENT:
        split = _MIN_SUB_SEGMENT
    if split > seg_len - _MIN_SUB_SEGMENT:
        split = seg_len - _MIN_SUB_SEGMENT
    return segment[:split], segment[split:]


def _summarise(windows: list[WalkForwardWindow]) -> WalkForwardSummary:
    """Aggregate per-window results into the consistency score."""
    if not windows:  # pragma: no cover — caller raises before this point
        return WalkForwardSummary(passed_windows=0, failed_windows=0, consistency_score=0.0)
    passed = sum(1 for w in windows if w.passed)
    total = len(windows)
    return WalkForwardSummary(
        passed_windows=passed,
        failed_windows=total - passed,
        consistency_score=passed / total,
    )


__all__ = [
    "WalkForwardResult",
    "WalkForwardSummary",
    "WalkForwardWindow",
    "run_walk_forward",
]

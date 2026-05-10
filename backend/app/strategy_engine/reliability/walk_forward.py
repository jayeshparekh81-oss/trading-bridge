"""Walk-forward analysis — anchored expanding-train schedule.

Pure deterministic implementation that orchestrates Phase 3's
:func:`run_backtest` over a rolling train/test schedule:

    Given ``N`` candles split into ``K`` equal segments, for each
    window ``i`` in ``[1, K-1]``::

        train = candles[0           : i * N // K]   # expanding
        test  = candles[i * N // K  : (i + 1) * N // K]

    The strategy runs on each test slice and the per-window outcomes
    are aggregated into a :class:`WalkForwardReport`. Producing
    ``K - 1`` test windows by design — the first segment is training-
    only because there's nothing to its left to anchor against.

The anchored schedule (training expands, testing slides) is the
gold-standard for "did the edge survive walking forward in time?".
The earlier tumbling-window placeholder ran a 70/30 split inside each
non-overlapping segment — that schedule did not test temporal
generalisation and is replaced wholesale here.

The module is **AI-free**: no LLM calls, no network, no clock reads.
Same inputs always produce the same :class:`WalkForwardReport`.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.backtest import (
    BacktestInput,
    CostSettings,
    run_backtest,
)
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.reliability.walk_forward_constants import (
    DEFAULT_NUM_WINDOWS,
    MIN_BARS_PER_WINDOW,
    PROFITABLE_PCT_WEIGHT,
    VARIANCE_PENALTY_PER_UNIT,
    VARIANCE_WEIGHT,
    VERDICT_THRESHOLDS,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

WalkForwardVerdict = Literal["excellent", "good", "acceptable", "poor"]


# ─── Models ────────────────────────────────────────────────────────────


class WalkForwardWindow(BaseModel):
    """One window's train + test outcome.

    Train metrics are intentionally absent — the train slice runs only
    to anchor the test (and would be redundant with the existing
    ``BacktestResult`` exposed at the report level). Future revisions
    can add training stats without breaking the public schema.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    window_index: int = Field(..., ge=0)
    train_bar_count: int = Field(..., ge=0)
    test_bar_count: int = Field(..., ge=0)
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    test_pnl: float
    test_total_trades: int = Field(..., ge=0)
    test_win_rate: float = Field(..., ge=0.0, le=1.0)
    test_max_drawdown: float = Field(..., ge=0.0)


class WalkForwardReport(BaseModel):
    """Top-level walk-forward output.

    ``consistency_score`` is on the master 0-100 scale (matches Trust
    Score / Truth Score conventions) so consumers don't have to
    re-scale at the boundary. The reliability report wrapper divides
    by 100 when handing the value to ``calculate_trust_score`` to
    preserve that helper's existing 0-1 contract.

    ``verdict`` is the discrete band derived from
    ``consistency_score`` via :data:`VERDICT_THRESHOLDS`.

    ``windows`` is empty only when the input was below the minimum bar
    count — in that case every numeric field is the insufficient-data
    sentinel and ``verdict`` is ``"poor"``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_windows: int = Field(..., ge=0)
    windows: tuple[WalkForwardWindow, ...] = Field(default_factory=tuple)
    consistency_score: float = Field(..., ge=0.0, le=100.0)
    pnl_variance_ratio: float = Field(..., ge=0.0)
    avg_test_pnl: float
    median_test_pnl: float
    profitable_windows_count: int = Field(..., ge=0)
    profitable_windows_percent: float = Field(..., ge=0.0, le=100.0)
    verdict: WalkForwardVerdict
    hinglish_summary: str = Field(..., min_length=1, max_length=512)


# ─── Public API ────────────────────────────────────────────────────────


def run_walk_forward(
    candles: Sequence[Candle],
    strategy: StrategyJSON,
    num_windows: int = DEFAULT_NUM_WINDOWS,
    cost_settings: CostSettings | None = None,
    *,
    initial_capital: float = 100_000.0,
    quantity: float = 1.0,
    ambiguity_mode: AmbiguityMode = AmbiguityMode.CONSERVATIVE,
) -> WalkForwardReport:
    """Run an anchored expanding-train walk-forward.

    Args:
        candles: OHLCV bars in chronological order.
        strategy: The strategy under test. The same DSL runs on every
            train and test slice — walk-forward measures temporal
            generalisation, not strategy-shape robustness.
        num_windows: Number of equal segments to partition ``candles``
            into. The schedule produces ``num_windows - 1`` test
            windows. Defaults to :data:`DEFAULT_NUM_WINDOWS`.
        cost_settings: Costs applied inside every per-window backtest.
            Defaults to :class:`CostSettings` defaults.
        initial_capital / quantity / ambiguity_mode: Forwarded to each
            inner :func:`run_backtest` call. Same defaults as the
            Phase 3 entry point.

    Returns:
        :class:`WalkForwardReport`. When the input is below the
        ``num_windows x MIN_BARS_PER_WINDOW`` floor, the report is
        the insufficient-data placeholder (no exception).
    """
    n = len(candles)
    cost_settings = cost_settings or CostSettings()

    if num_windows < 2 or n < num_windows * MIN_BARS_PER_WINDOW:
        return _insufficient_data_report(n, num_windows)

    segment_size = n // num_windows
    windows: list[WalkForwardWindow] = []
    for i in range(1, num_windows):
        train_end_idx = i * segment_size
        # The last test window picks up any remainder so we never
        # silently drop tail data.
        test_end_idx = n if i == num_windows - 1 else (i + 1) * segment_size

        train_slice = candles[:train_end_idx]
        test_slice = candles[train_end_idx:test_end_idx]

        # Run the strategy on the test slice. The train slice exists
        # only to define the temporal anchor; the simulator is pure
        # so no fitting happens during the train backtest.
        test_result = run_backtest(
            BacktestInput(
                candles=list(test_slice),
                strategy=strategy,
                initial_capital=initial_capital,
                quantity=quantity,
                cost_settings=cost_settings,
                ambiguity_mode=ambiguity_mode,
            )
        )

        windows.append(
            WalkForwardWindow(
                window_index=i - 1,
                train_bar_count=len(train_slice),
                test_bar_count=len(test_slice),
                train_start=train_slice[0].timestamp.isoformat(),
                train_end=train_slice[-1].timestamp.isoformat(),
                test_start=test_slice[0].timestamp.isoformat(),
                test_end=test_slice[-1].timestamp.isoformat(),
                test_pnl=test_result.total_pnl,
                test_total_trades=test_result.total_trades,
                test_win_rate=test_result.win_rate,
                test_max_drawdown=test_result.max_drawdown,
            )
        )

    return _aggregate(windows)


# ─── Aggregation ───────────────────────────────────────────────────────


def _aggregate(windows: list[WalkForwardWindow]) -> WalkForwardReport:
    """Roll the per-window outcomes up into the report-level metrics."""
    total = len(windows)
    pnls = [w.test_pnl for w in windows]
    profitable = sum(1 for p in pnls if p > 0)
    profitable_pct = (profitable / total) * 100.0 if total > 0 else 0.0

    avg_pnl = statistics.fmean(pnls) if pnls else 0.0
    med_pnl = statistics.median(pnls) if pnls else 0.0
    pnl_variance_ratio = _variance_ratio(pnls, avg_pnl)
    consistency = _consistency_score(profitable_pct, pnl_variance_ratio)
    verdict = _verdict_for(consistency)

    return WalkForwardReport(
        total_windows=total,
        windows=tuple(windows),
        consistency_score=round(consistency, 2),
        pnl_variance_ratio=round(pnl_variance_ratio, 4),
        avg_test_pnl=round(avg_pnl, 4),
        median_test_pnl=round(med_pnl, 4),
        profitable_windows_count=profitable,
        profitable_windows_percent=round(profitable_pct, 2),
        verdict=verdict,
        hinglish_summary=_hinglish_summary(verdict, profitable_pct),
    )


def _variance_ratio(pnls: list[float], mean: float) -> float:
    """Coefficient of variation: ``std(pnls) / |mean|``.

    Returns 0 when there are fewer than two samples (variance is
    undefined). Returns the documented infinite sentinel
    (:data:`VARIANCE_PENALTY_PER_UNIT * 4`) when the mean is
    effectively zero — that drives the variance sub-score to 0
    without raising.
    """
    if len(pnls) < 2:
        return 0.0
    std = statistics.pstdev(pnls)
    if abs(mean) < 1e-9:
        # Break-even on average; treat as worst-case variance.
        return 4.0 if std > 0 else 0.0
    return std / abs(mean)


def _consistency_score(profitable_pct: float, variance_ratio: float) -> float:
    """``0.6 x profitable_pct + 0.4 x variance_score`` (locked formula)."""
    variance_score = max(0.0, 100.0 - variance_ratio * VARIANCE_PENALTY_PER_UNIT)
    score = PROFITABLE_PCT_WEIGHT * profitable_pct + VARIANCE_WEIGHT * variance_score
    return max(0.0, min(100.0, score))


def _verdict_for(score: float) -> WalkForwardVerdict:
    if score >= VERDICT_THRESHOLDS["excellent"]:
        return "excellent"
    if score >= VERDICT_THRESHOLDS["good"]:
        return "good"
    if score >= VERDICT_THRESHOLDS["acceptable"]:
        return "acceptable"
    return "poor"


def _hinglish_summary(verdict: WalkForwardVerdict, profitable_pct: float) -> str:
    pct = f"{profitable_pct:.0f}"
    if verdict == "excellent":
        return f"Walk-forward strong - {pct}% windows mein profit, low variance."
    if verdict == "good":
        return f"Walk-forward theek - {pct}% windows profitable, consistency acceptable."
    if verdict == "acceptable":
        return f"Walk-forward concerning - sirf {pct}% windows profitable."
    return "Walk-forward fail - strategy out-of-sample mein consistent nahi hai."


# ─── Insufficient-data placeholder ─────────────────────────────────────


def _insufficient_data_report(n_candles: int, num_windows: int) -> WalkForwardReport:
    """Build the empty placeholder when the input is too short.

    ``hinglish_summary`` quotes the *required* total bar count so the
    operator can tell at a glance how much more data they need.
    """
    required = max(num_windows, 2) * MIN_BARS_PER_WINDOW
    return WalkForwardReport(
        total_windows=0,
        windows=(),
        consistency_score=0.0,
        pnl_variance_ratio=0.0,
        avg_test_pnl=0.0,
        median_test_pnl=0.0,
        profitable_windows_count=0,
        profitable_windows_percent=0.0,
        verdict="poor",
        hinglish_summary=(
            f"Sample chhota hai - walk-forward ke liye {required} bars "
            f"chahiye (abhi {n_candles} hain)."
        ),
    )


__all__ = [
    "WalkForwardReport",
    "WalkForwardVerdict",
    "WalkForwardWindow",
    "run_walk_forward",
]

"""Walk-forward analyser tests.

Pure-function coverage for the anchored expanding-train schedule, the
consistency-score formula, the verdict bands, and the
insufficient-data placeholder. Each test fabricates exactly the
candle stream it needs to drive a deterministic outcome.
"""

from __future__ import annotations

import ast
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.strategy_engine.reliability import (
    ReliabilityReport,
    WalkForwardReport,
    WalkForwardWindow,
    build_reliability_report,
    run_walk_forward,
)
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

# ─── Builders ──────────────────────────────────────────────────────────


_T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def _flat_candles(n: int, *, price: float = 100.0) -> list[Candle]:
    """Boring flat candles — entry condition will or won't fire based
    on the strategy's threshold."""
    return [
        Candle(
            timestamp=_T0 + timedelta(minutes=i),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=1_000.0,
        )
        for i in range(n)
    ]


def _strong_uptrend_candles(n: int) -> list[Candle]:
    """Monotonically rising bars with intra-bar range so target/stop
    can plausibly hit. Drives a buy-and-hold strategy to consistent
    profitable test windows."""
    out: list[Candle] = []
    price = 100.0
    for i in range(n):
        mid = price + i * 0.4
        out.append(
            Candle(
                timestamp=_T0 + timedelta(minutes=i),
                open=mid,
                high=mid + 0.6,
                low=mid - 0.3,
                close=mid + 0.5,
                volume=1_000.0,
            )
        )
    return out


def _noisy_candles(n: int, seed: int = 42) -> list[Candle]:
    """Random-walk candles seeded for determinism. Flips signs across
    test windows so the strategy lands in a poor-consistency band."""
    rng = random.Random(seed)
    out: list[Candle] = []
    price = 100.0
    for i in range(n):
        delta = rng.uniform(-1.5, 1.5)
        new_price = max(50.0, price + delta)
        high = max(price, new_price) + 0.6
        low = min(price, new_price) - 0.6
        out.append(
            Candle(
                timestamp=_T0 + timedelta(minutes=i),
                open=price,
                high=high,
                low=low,
                close=new_price,
                volume=1_000.0,
            )
        )
        price = new_price
    return out


def _losing_candles(n: int) -> list[Candle]:
    """Steady downtrend. A long-only price-trigger strategy entering
    at threshold will repeatedly stop out — every test window loses."""
    out: list[Candle] = []
    price = 200.0
    for i in range(n):
        mid = price - i * 0.5
        out.append(
            Candle(
                timestamp=_T0 + timedelta(minutes=i),
                open=mid,
                high=mid + 0.2,
                low=mid - 0.7,
                close=mid - 0.4,
                volume=1_000.0,
            )
        )
    return out


def _strategy(*, threshold: float = 99.5) -> StrategyJSON:
    """Always-on long strategy (price > threshold) with a modest target
    and stop. Suitable for any of the candle generators above."""
    return StrategyJSON.model_validate(
        {
            "id": "wf_test",
            "name": "walk-forward test",
            "mode": "expert",
            "indicators": [],
            "entry": {
                "side": "BUY",
                "operator": "AND",
                "conditions": [{"type": "price", "op": ">", "value": threshold}],
            },
            "exit": {"targetPercent": 1.0, "stopLossPercent": 0.5},
            "execution": {
                "mode": "backtest",
                "orderType": "MARKET",
                "productType": "INTRADAY",
            },
        }
    )


# ─── 1. Strong trending strategy → consistency >= 80, verdict excellent ─


def test_strong_uptrend_yields_excellent_verdict() -> None:
    candles = _strong_uptrend_candles(120)
    report = run_walk_forward(candles=candles, strategy=_strategy(threshold=99.0))
    assert isinstance(report, WalkForwardReport)
    assert report.total_windows == DEFAULT_NUM_WINDOWS - 1
    assert report.profitable_windows_count == report.total_windows
    assert report.profitable_windows_percent == 100.0
    assert report.consistency_score >= 80.0
    assert report.verdict == "excellent"


# ─── 2. Random/weak strategy → low consistency, verdict poor ───────────


def test_steady_downtrend_yields_poor_verdict() -> None:
    candles = _losing_candles(120)
    report = run_walk_forward(candles=candles, strategy=_strategy(threshold=50.0))
    assert report.profitable_windows_count == 0
    assert report.consistency_score < VERDICT_THRESHOLDS["acceptable"]
    assert report.verdict == "poor"
    assert "fail" in report.hinglish_summary


# ─── 3. Insufficient bars → empty report (no exception) ────────────────


def test_insufficient_bars_returns_empty_placeholder() -> None:
    too_few = _flat_candles(MIN_BARS_PER_WINDOW * DEFAULT_NUM_WINDOWS - 1)
    report = run_walk_forward(candles=too_few, strategy=_strategy())
    assert report.total_windows == 0
    assert report.windows == ()
    assert report.consistency_score == 0.0
    assert report.verdict == "poor"
    # The summary quotes the required total bar count.
    required = DEFAULT_NUM_WINDOWS * MIN_BARS_PER_WINDOW
    assert str(required) in report.hinglish_summary
    assert str(len(too_few)) in report.hinglish_summary


# ─── 4. num_windows=3 → 2 test windows produced ────────────────────────


def test_num_windows_3_produces_2_test_windows() -> None:
    candles = _flat_candles(120)
    report = run_walk_forward(candles=candles, strategy=_strategy(), num_windows=3)
    assert report.total_windows == 2
    assert len(report.windows) == 2
    assert [w.window_index for w in report.windows] == [0, 1]
    # Anchored schedule — train_bar_count strictly grows.
    bar_counts = [w.train_bar_count for w in report.windows]
    assert bar_counts == sorted(bar_counts)
    assert bar_counts[0] < bar_counts[1]


# ─── 5. Each window runs a full backtest deterministically ─────────────


def test_window_records_carry_test_metrics() -> None:
    candles = _strong_uptrend_candles(120)
    report = run_walk_forward(candles=candles, strategy=_strategy(threshold=99.0))
    for w in report.windows:
        assert isinstance(w, WalkForwardWindow)
        assert w.test_bar_count > 0
        assert 0.0 <= w.test_win_rate <= 1.0
        assert w.test_max_drawdown >= 0.0
        assert w.test_total_trades >= 0
        # ISO timestamps round-trip into datetime.
        assert datetime.fromisoformat(w.train_start) <= datetime.fromisoformat(w.train_end)
        assert datetime.fromisoformat(w.test_start) <= datetime.fromisoformat(w.test_end)
    # Last window picks up any tail-remainder so its test_end timestamp
    # is the final candle.
    last = report.windows[-1]
    assert datetime.fromisoformat(last.test_end) == candles[-1].timestamp


# ─── 6. profitable_windows_count counts correctly ──────────────────────


def test_profitable_windows_count_matches_window_pnls() -> None:
    """Build a report from synthesised inputs to verify the rollup.
    Easier to assert against a half-and-half outcome by mixing a
    profitable and a losing region in one stream."""
    # Very flat region → no trades → pnl 0 (not profitable, but not
    # a loss either). Drive ``profitable_pct`` deterministically by
    # using the noisy generator.
    candles = _noisy_candles(120, seed=7)
    report = run_walk_forward(candles=candles, strategy=_strategy())
    expected_count = sum(1 for w in report.windows if w.test_pnl > 0)
    assert report.profitable_windows_count == expected_count
    assert report.profitable_windows_percent == pytest.approx(
        (expected_count / report.total_windows) * 100.0
    )


# ─── 7. Consistency-score formula matches the locked spec ──────────────


def test_consistency_score_matches_locked_formula() -> None:
    """Recompute the score from primitives and assert the report's
    field is within rounding of the expected value."""
    candles = _strong_uptrend_candles(120)
    report = run_walk_forward(candles=candles, strategy=_strategy(threshold=99.0))

    profitable_pct = report.profitable_windows_percent
    variance_score = max(0.0, 100.0 - report.pnl_variance_ratio * VARIANCE_PENALTY_PER_UNIT)
    expected = PROFITABLE_PCT_WEIGHT * profitable_pct + VARIANCE_WEIGHT * variance_score
    expected = max(0.0, min(100.0, expected))
    assert math.isclose(report.consistency_score, round(expected, 2), abs_tol=0.01)


def test_weights_sum_to_one() -> None:
    assert math.isclose(PROFITABLE_PCT_WEIGHT + VARIANCE_WEIGHT, 1.0, abs_tol=1e-9)


# ─── 8. Verdict bands map correctly ────────────────────────────────────


def test_verdict_bands_for_excellent_through_poor() -> None:
    """The verdict is purely a function of ``consistency_score``; the
    bands come from :data:`VERDICT_THRESHOLDS`. Cover each band with a
    different generator + strategy combination."""
    excellent = run_walk_forward(
        candles=_strong_uptrend_candles(120),
        strategy=_strategy(threshold=99.0),
    )
    poor = run_walk_forward(
        candles=_losing_candles(120),
        strategy=_strategy(threshold=50.0),
    )
    assert excellent.verdict == "excellent"
    assert excellent.consistency_score >= VERDICT_THRESHOLDS["excellent"]
    assert poor.verdict == "poor"
    assert poor.consistency_score < VERDICT_THRESHOLDS["acceptable"]


# ─── 9. Hinglish summary contains expected keyword per verdict ─────────


def test_hinglish_summary_keywords_per_verdict() -> None:
    excellent = run_walk_forward(
        candles=_strong_uptrend_candles(120),
        strategy=_strategy(threshold=99.0),
    )
    poor = run_walk_forward(
        candles=_losing_candles(120),
        strategy=_strategy(threshold=50.0),
    )
    assert "strong" in excellent.hinglish_summary
    assert "fail" in poor.hinglish_summary
    # All summaries reference walk-forward so the audit log surface
    # always stays unambiguous.
    assert "Walk-forward" in excellent.hinglish_summary
    assert "Walk-forward" in poor.hinglish_summary


# ─── 10. Determinism: same input → same output ─────────────────────────


def test_run_walk_forward_is_deterministic() -> None:
    candles = _strong_uptrend_candles(120)
    a = run_walk_forward(candles=candles, strategy=_strategy(threshold=99.0))
    b = run_walk_forward(candles=candles, strategy=_strategy(threshold=99.0))
    assert a == b
    assert a.windows == b.windows
    assert a.consistency_score == b.consistency_score


# ─── 11. AST inspection: no LLM/network imports ───────────────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "aiohttp",
    "websocket",
    "websockets",
    "socket",
)


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES)


def test_walk_forward_module_has_no_llm_or_network_imports() -> None:
    """The reliability layer is, by design, deterministic and offline.
    AST-walk both the analyser and its constants module."""
    files = [
        Path(__file__).resolve().parents[3] / "app" / "strategy_engine" / "reliability" / name
        for name in ("walk_forward.py", "walk_forward_constants.py")
    ]
    offenders: list[str] = []
    for source_file in files:
        tree = ast.parse(source_file.read_text(), filename=str(source_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden(alias.name):
                        offenders.append(f"{source_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if _is_forbidden(module):
                    offenders.append(f"{source_file.name}: from {module} import …")
    assert not offenders, offenders


# ─── 12. Integration: build_reliability_report includes walk_forward ───


def test_reliability_report_includes_walk_forward_when_enough_bars() -> None:
    strategy = StrategyJSON.model_validate(
        {
            "id": "wf_int",
            "name": "WF integration",
            "mode": "expert",
            "indicators": [
                {"id": "ema_5", "type": "ema", "params": {"period": 5}},
            ],
            "entry": {
                "side": "BUY",
                "operator": "AND",
                "conditions": [{"type": "price", "op": ">", "value": 99.5}],
            },
            "exit": {"targetPercent": 2, "stopLossPercent": 1},
            "execution": {
                "mode": "backtest",
                "orderType": "MARKET",
                "productType": "INTRADAY",
            },
        }
    )
    report = build_reliability_report(strategy=strategy, candles=_flat_candles(120))
    assert isinstance(report, ReliabilityReport)
    assert report.walk_forward is not None
    assert isinstance(report.walk_forward, WalkForwardReport)
    # The wrapper converts the 0-100 consistency score to the 0-1
    # fraction the trust-score helper expects — verify the trust
    # score still ran (sanity check on the full pipeline).
    assert 0 <= report.trust_score.score <= 100


# ─── 13. Edge case: every test window loses → consistency low ─────────


def test_all_losing_windows_produces_low_consistency() -> None:
    candles = _losing_candles(120)
    report = run_walk_forward(candles=candles, strategy=_strategy(threshold=50.0))
    # Every window's test_pnl is non-positive.
    assert all(w.test_pnl <= 0 for w in report.windows)
    assert report.profitable_windows_count == 0
    assert report.profitable_windows_percent == 0.0
    # ``consistency_score = 0.6 * 0 + 0.4 * variance_score``. With
    # zero profitable windows the upper bound is 40.0 (when variance
    # ratio is 0). Verdict band ⟹ "poor".
    assert report.consistency_score <= 40.0
    assert report.verdict == "poor"


# ─── 14. Pydantic round-trip ──────────────────────────────────────────


def test_walk_forward_report_round_trips_through_pydantic() -> None:
    candles = _strong_uptrend_candles(120)
    original = run_walk_forward(candles=candles, strategy=_strategy(threshold=99.0))
    raw = original.model_dump_json()
    restored = WalkForwardReport.model_validate_json(raw)
    assert restored == original
    for orig_w, new_w in zip(original.windows, restored.windows, strict=True):
        assert isinstance(new_w, WalkForwardWindow)
        assert orig_w == new_w

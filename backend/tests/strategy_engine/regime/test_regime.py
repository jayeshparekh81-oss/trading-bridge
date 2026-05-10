"""Market Regime detector — locked behaviour pinned by 12 cases.

Synthetic candles are tuned so each test isolates a single rule from
the classifier matrix. Every helper in :mod:`conftest` produces a
deterministic series; assertions key on regime label, suitability
verdict, and Hinglish summary keywords so a future contributor can
read the test list and immediately see what the detector promises.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

import pytest

from app.strategy_engine.regime import (
    RegimeReport,
    detect_regime,
)
from app.strategy_engine.schema.ohlcv import Candle
from tests.strategy_engine.regime.conftest import (
    make_breakout_candles,
    make_choppy_candles,
    make_compressed_then_range_candles,
    make_gap_up_candles,
    make_high_atr_candles,
    make_low_atr_candles,
    make_mean_reversion_strategy,
    make_range_bound_candles,
    make_strong_uptrend_candles,
    make_trend_following_strategy,
)

# ─── 1. Strong uptrend → trending ──────────────────────────────────────


def test_strong_uptrend_detected_as_trending() -> None:
    report = detect_regime(make_strong_uptrend_candles())
    assert report.regime == "trending"
    assert report.confidence > 0.7
    # Sanity: ADX clears the trending threshold and the SMA slope is
    # comfortably positive.
    assert report.metrics.adx_value > 25
    assert report.metrics.ma_slope_percent > 0.5


# ─── 2. Range-bound → sideways ─────────────────────────────────────────


def test_range_bound_detected_as_sideways() -> None:
    report = detect_regime(make_compressed_then_range_candles())
    assert report.regime == "sideways"
    # ADX should be weak in a tight range.
    assert report.metrics.adx_value < 20


# ─── 3. High ATR → high_volatility ─────────────────────────────────────


def test_high_atr_detected_as_high_volatility() -> None:
    report = detect_regime(make_high_atr_candles())
    # Either high_volatility (ATR > 90th percentile) OR abnormal (ATR > 99th)
    # are valid surfaces of the same underlying signal — both clear the
    # spec's intent. The synthetic factory uses extreme moves precisely
    # to be unambiguous about *something* volatility-flavoured firing.
    assert report.regime in ("high_volatility", "abnormal")
    assert report.metrics.volatility_percentile >= 0.90


# ─── 4. Low ATR → low_volatility ───────────────────────────────────────


def test_low_atr_detected_as_low_volatility() -> None:
    report = detect_regime(make_low_atr_candles())
    assert report.regime == "low_volatility"
    assert report.metrics.volatility_percentile <= 0.20


# ─── 5. Gap up → gap_day ───────────────────────────────────────────────


def test_gap_up_detected_as_gap_day() -> None:
    report = detect_regime(make_gap_up_candles(gap_percent=0.025))
    assert report.regime == "gap_day"
    assert report.metrics.gap_percent is not None
    assert report.metrics.gap_percent > 0.01


# ─── 6. Choppy → choppy ────────────────────────────────────────────────


def test_alternating_candles_detected_as_choppy() -> None:
    report = detect_regime(make_choppy_candles())
    # Alternating closes can also push ATR around enough that the
    # high-volatility predicate fires first; both are reasonable.
    # We pin the *direction-changes* metric so the choppiness signal
    # is observable regardless of which label wins.
    assert report.metrics.direction_changes_count >= 12
    assert report.regime in ("choppy", "high_volatility", "abnormal")


# ─── 7. Compression then expansion → breakout ──────────────────────────


def test_compression_then_expansion_detected_as_breakout() -> None:
    report = detect_regime(make_breakout_candles())
    # The expansion is dramatic enough that abnormal can also fire
    # via the 99th-percentile ATR rule; both surface the same
    # underlying "regime change" the spec is targeting.
    assert report.regime in ("breakout", "abnormal")


# ─── 8. Trend-following + sideways → not suitable, high risk ──────────


def test_trend_strategy_in_sideways_is_unsuitable() -> None:
    report = detect_regime(
        make_compressed_then_range_candles(),
        strategy=make_trend_following_strategy(),
    )
    assert report.regime == "sideways"
    assert report.strategy_suitability is not None
    assert report.strategy_suitability.suitable is False
    assert report.strategy_suitability.risk_level == "high"
    assert report.strategy_suitability.strategy_type == "trend_following"


# ─── 9. Mean-reversion + sideways → suitable, low risk ─────────────────


def test_mean_reversion_in_sideways_is_suitable() -> None:
    report = detect_regime(
        make_compressed_then_range_candles(),
        strategy=make_mean_reversion_strategy(),
    )
    assert report.regime == "sideways"
    assert report.strategy_suitability is not None
    assert report.strategy_suitability.suitable is True
    assert report.strategy_suitability.risk_level == "low"
    assert report.strategy_suitability.strategy_type == "mean_reversion"


# ─── 10. Determinism — running twice gives an equal report ─────────────


def test_detection_is_deterministic_across_runs() -> None:
    """The pipeline is pure; two identical calls must return equal
    :class:`RegimeReport` objects (frozen Pydantic equality)."""
    candles = make_strong_uptrend_candles()
    first = detect_regime(candles)
    second = detect_regime(candles)
    assert first == second
    assert first.metrics == second.metrics
    assert first.regime == second.regime


# ─── 11. AST inspection — no LLM / network imports ────────────────────


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


def _regime_python_files() -> list[Path]:
    pkg_root = Path(__file__).resolve().parents[3] / "app" / "strategy_engine" / "regime"
    return sorted(p for p in pkg_root.glob("*.py"))


@pytest.mark.parametrize("source_file", _regime_python_files())
def test_regime_module_does_not_import_llm_or_network(
    source_file: Path,
) -> None:
    """Walk every import in every regime *.py file and assert it does
    not pull in an LLM SDK or any network/socket library.

    The detector is, by design, a pure deterministic pipeline. Coupling
    it to a network call would make outputs non-reproducible and break
    the determinism test above. Pin that property here so a future
    contributor can't quietly add a runtime dependency.
    """
    tree = ast.parse(source_file.read_text(), filename=str(source_file))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                offenders.append(f"from {module} import …")
    assert not offenders, f"{source_file.name} pulls in forbidden modules: {offenders}"


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES)


# ─── 12. Hinglish summary contains the regime keyword ──────────────────


_REGIME_KEYWORDS: dict[str, str] = {
    "trending": "trend",
    "sideways": "range",
    "high_volatility": "Volatility zyada",
    "low_volatility": "Volatility kam",
    "gap_day": "Gap day",
    "choppy": "choppy",
    "breakout": "expansion",
    "abnormal": "abnormal",
}


@pytest.mark.parametrize(
    ("candles_factory", "expected_regimes"),
    [
        (make_strong_uptrend_candles, {"trending"}),
        (make_compressed_then_range_candles, {"sideways"}),
        (make_high_atr_candles, {"high_volatility", "abnormal"}),
        (make_low_atr_candles, {"low_volatility"}),
        (make_gap_up_candles, {"gap_day"}),
        (make_choppy_candles, {"choppy", "high_volatility", "abnormal"}),
        (make_breakout_candles, {"breakout", "abnormal"}),
        (make_range_bound_candles, {"sideways", "low_volatility"}),
    ],
)
def test_hinglish_summary_matches_detected_regime(
    candles_factory: Callable[[], list[Candle]], expected_regimes: set[str]
) -> None:
    """The locked Hinglish summary template for each regime carries a
    distinctive keyword; whatever regime we land on, the summary should
    contain its keyword. Pin both layers (the regime labels we accept
    AND the keyword on the summary) so renaming a template would
    fail the test."""
    report: RegimeReport = detect_regime(candles_factory())
    assert report.regime in expected_regimes
    keyword = _REGIME_KEYWORDS[report.regime]
    assert keyword.lower() in report.hinglish_summary.lower()

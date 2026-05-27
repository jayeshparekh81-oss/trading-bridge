"""Queue PP / D2 — trend template override tests.

Proves the 3 trend templates (``supertrend-rider``, ``hull-ma-trend``,
``triple-ema-crossover``) — FAIL_UNPARSEABLE under the Queue BB prose parser
(visual "flip"/"colour"/"sloping" semantics + a 2-bar window) — now translate
to valid ``StrategyJSON`` via the founder override registry and produce trades
on a synthetic backtest.

The required indicators (supertrend / hull_ma / ema) already existed + were
dispatched in the backtest runner; D2 adds only the translator overrides (see
``app/strategy_engine/translator/trend_overrides.py`` and
``docs/QUEUE_PP_TRANSLATOR_D2.md``).

Synthetic series:
  * sine (oscillating NIFTY-like) → close repeatedly crosses the supertrend band
    and the hull line (covers supertrend + hull);
  * uptrend-with-pullbacks → ema_8 re-crosses ema_21 while the full
    ema_8>ema_21>ema_55 stack stays bullish (covers triple-ema, whose AND-entry
    needs the crossover and the stack to co-occur).
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.strategy_engine.backtest import BacktestInput, run_backtest
from app.strategy_engine.indicators.registry import (
    INDICATOR_REGISTRY,
    get_calculation_function,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import (
    IndicatorCondition,
    IndicatorConditionOp,
    Side,
    StrategyJSON,
)
from app.strategy_engine.translator import translate_template
from app.strategy_engine.translator.trend_overrides import (
    TREND_OVERRIDES,
    register_trend_overrides,
)

_IST = ZoneInfo("Asia/Kolkata")
_TARGET_SLUGS = ["supertrend-rider", "hull-ma-trend", "triple-ema-crossover"]


@pytest.fixture(scope="module")
def seed_templates() -> dict:
    """Real seed templates keyed by slug — we translate the actual shipping
    config_json, not hand-fed dicts."""
    seed = (
        Path(__file__).resolve().parents[3] / "data" / "strategy_templates_seed.json"
    )
    data = json.loads(seed.read_text(encoding="utf-8"))
    return {t["slug"]: t for t in data["templates"] if isinstance(t, dict)}


@pytest.fixture(autouse=True)
def _ensure_overrides() -> None:
    """Guarantee the trend overrides are registered even if another test module
    cleared the in-memory registry. Idempotent."""
    register_trend_overrides()


# ─── Synthetic candle builders ──────────────────────────────────────────


def _candles(closes: list[float]) -> list[Candle]:
    """Stream closes into 5-min IST candles across consecutive trading days
    (72 bars/day, 09:15 start). Bullish bars (close>open)."""
    cands: list[Candle] = []
    idx = 0
    day = 0
    n = len(closes)
    while idx < n:
        day_start = datetime(2026, 1, 5, 9, 15, tzinfo=_IST) + timedelta(days=day)
        for i in range(72):
            if idx >= n:
                break
            c = closes[idx]
            cands.append(
                Candle(
                    timestamp=day_start + timedelta(minutes=5 * i),
                    open=c - 5.0,
                    high=c + 20.0,
                    low=c - 20.0,
                    close=c,
                    volume=1000.0,
                )
            )
            idx += 1
        day += 1
    return cands


def _sine(n: int = 720) -> list[Candle]:
    """Oscillating NIFTY-like price — close repeatedly crosses the supertrend
    band and the hull line."""
    closes = [25000.0 + 200.0 * math.sin((day * 72 + i) / 10.0) for day in range(n // 72) for i in range(72)]
    return _candles(closes)


def _uptrend_pullbacks(n: int = 360) -> list[Candle]:
    """Strong uptrend with shallow oscillating pullbacks: ema_8 dips toward and
    re-crosses ema_21 while ema_21 stays above ema_55 → the full bullish stack
    holds at the crossover (triple-ema's AND-entry)."""
    closes = [24000.0 + 8.0 * t + 140.0 * math.sin(t / 8.0) for t in range(n)]
    return _candles(closes)


_CANDLES_BY_SLUG = {
    "supertrend-rider": _sine,
    "hull-ma-trend": _sine,
    "triple-ema-crossover": _uptrend_pullbacks,
}

#: Per-template (indicator type that must be declared, crossover left→right pair).
_SIGNAL_BY_SLUG = {
    "supertrend-rider": ("supertrend", "close", "supertrend_10_3"),
    "hull-ma-trend": ("hull_ma", "close", "hull_ma_21"),
    "triple-ema-crossover": ("ema", "ema_8", "ema_21"),
}


# ─── 1. Required indicators are registered + dispatchable ───────────────


@pytest.mark.parametrize("type_id", ["supertrend", "hull_ma", "ema"])
def test_trend_indicator_dispatch(type_id: str) -> None:
    assert type_id in INDICATOR_REGISTRY, f"{type_id} not registered"
    assert callable(get_calculation_function(type_id))


# ─── 2. Translator handles the trend conditions ─────────────────────────


@pytest.mark.parametrize("slug", _TARGET_SLUGS)
def test_translator_handles_trend_conditions(seed_templates: dict, slug: str) -> None:
    """Each seed template now translates to a StrategyJSON that declares the
    expected indicator and gates entry on the expected crossover — i.e. the
    override short-circuits the (unparseable) prose parser."""
    strategy = translate_template(seed_templates[slug])
    assert isinstance(strategy, StrategyJSON)
    assert strategy.id == f"template:{slug}"

    ind_type, x_left, x_right = _SIGNAL_BY_SLUG[slug]
    assert any(ind.type == ind_type for ind in strategy.indicators), (
        f"{slug}: no {ind_type} indicator declared"
    )

    crossover_entries = [
        c
        for c in strategy.entry.conditions
        if isinstance(c, IndicatorCondition)
        and c.op is IndicatorConditionOp.CROSSOVER
        and c.left == x_left
        and c.right == x_right
    ]
    assert crossover_entries, f"{slug}: missing entry crossover {x_left}->{x_right}"


def test_supertrend_rider_is_long_only(seed_templates: dict) -> None:
    """The seed has a short side; the override is single-side BUY (prototype)."""
    strategy = translate_template(seed_templates["supertrend-rider"])
    assert strategy.entry.side is Side.BUY


# ─── 3. The 3 targets pass validation + produce trades ──────────────────


@pytest.mark.parametrize("slug", _TARGET_SLUGS)
def test_3_targets_pass_validation(seed_templates: dict, slug: str) -> None:
    """Translate → round-trip through model_validate (zero validation errors)
    → synthetic backtest generates >=1 trade."""
    strategy = translate_template(seed_templates[slug])

    revived = StrategyJSON.model_validate(strategy.model_dump(by_alias=True))
    assert revived == strategy, f"{slug}: did not round-trip cleanly"

    candles = _CANDLES_BY_SLUG[slug]()
    result = run_backtest(BacktestInput(candles=candles, strategy=strategy))
    assert result.total_trades >= 1, (
        f"{slug}: expected >=1 trade on the synthetic harness, "
        f"got {result.total_trades}"
    )


def test_overrides_cover_exactly_the_three_slugs() -> None:
    """Guard against accidental scope creep in the trend override seed."""
    assert set(TREND_OVERRIDES) == set(_TARGET_SLUGS)

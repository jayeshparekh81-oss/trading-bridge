"""Queue OO / C2 — divergence template override tests.

Proves the 3 divergence templates (``rsi-divergence``, ``macd-divergence``,
``obv-divergence``) — FAIL_UNPARSEABLE under the Queue BB prose parser — now
translate to valid ``StrategyJSON`` via the founder override registry and
produce trades on a synthetic backtest.

The divergence indicators already existed + were dispatched in the backtest
runner; C2 adds only the translator overrides (see
``app/strategy_engine/translator/divergence_overrides.py`` and
``docs/QUEUE_OO_TRANSLATOR_C2.md``).

Synthetic series are engineered per template to satisfy each AND-entry at least
once (warmup + the IST 09:30-15:00 gate respected):

  * decelerating decline → repeated *bullish* RSI/MACD divergences with bullish
    reversal candles and MACD line back above its signal (covers rsi + macd);
  * down-drifting oscillation with up-weighted volume → OBV rises while price
    prints lower lows (bullish OBV divergence).
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.strategy_engine.backtest import BacktestInput, run_backtest
from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators.calculations.macd_divergence import macd_divergence
from app.strategy_engine.indicators.calculations.obv_divergence import obv_divergence
from app.strategy_engine.indicators.calculations.rsi_divergence import rsi_divergence
from app.strategy_engine.indicators.registry import (
    INDICATOR_REGISTRY,
    get_calculation_function,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import IndicatorCondition, StrategyJSON
from app.strategy_engine.translator import translate_template
from app.strategy_engine.translator.divergence_overrides import (
    DIVERGENCE_OVERRIDES,
    register_divergence_overrides,
)

_IST = ZoneInfo("Asia/Kolkata")
_TARGET_SLUGS = ["rsi-divergence", "macd-divergence", "obv-divergence"]
_DIVERGENCE_CODES = frozenset({None, -1.0, 0.0, 1.0})


@pytest.fixture(scope="module")
def seed_templates() -> dict:
    """The real seed templates keyed by slug — we translate the *actual*
    shipping config_json, not hand-fed dicts."""
    seed = (
        Path(__file__).resolve().parents[3] / "data" / "strategy_templates_seed.json"
    )
    data = json.loads(seed.read_text(encoding="utf-8"))
    return {t["slug"]: t for t in data["templates"] if isinstance(t, dict)}


@pytest.fixture(autouse=True)
def _ensure_overrides() -> None:
    """Guarantee the divergence overrides are registered even if another test
    module cleared the in-memory registry. Idempotent."""
    register_divergence_overrides()


# ─── Synthetic candle builders ──────────────────────────────────────────


def _candles(
    closes: list[float],
    *,
    opens: list[float] | None = None,
    volumes: list[float] | None = None,
) -> list[Candle]:
    """Stream closes into 5-min IST candles across consecutive trading days
    (72 bars/day, 09:15 start). Default opens make bullish candles (close>open)."""
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
            o = opens[idx] if opens is not None else c - 5.0
            v = volumes[idx] if volumes is not None else 1000.0
            cands.append(
                Candle(
                    timestamp=day_start + timedelta(minutes=5 * i),
                    open=o,
                    high=max(o, c) + 10.0,
                    low=min(o, c) - 10.0,
                    close=c,
                    volume=v,
                )
            )
            idx += 1
        day += 1
    return cands


def _decelerating_decline(n: int = 360) -> list[Candle]:
    """Steep-then-flattening decline: price keeps printing new closing lows but
    momentum recovers → repeated *bullish* RSI/MACD divergences. Bullish candles
    (close>open) satisfy rsi-divergence's 'bullish reversal' clause."""
    closes = [25000.0 - 1500.0 * (1 - math.exp(-t / 60.0)) for t in range(n)]
    return _candles(closes)


def _obv_friendly(n: int = 360) -> list[Candle]:
    """Down-drifting oscillation with up-weighted volume: OBV trends up (up-bars
    carry 4x volume) while price drifts to lower lows → bullish OBV divergence."""
    closes = [25000.0 - 2.0 * t + 100.0 * math.sin(t / 6.0) for t in range(n)]
    volumes = [
        2000.0 if (t > 0 and closes[t] > closes[t - 1]) else 500.0 for t in range(n)
    ]
    return _candles(closes, volumes=volumes)


_CANDLES_BY_SLUG = {
    "rsi-divergence": _decelerating_decline,
    "macd-divergence": _decelerating_decline,
    "obv-divergence": _obv_friendly,
}


# ─── 1. Calc functions return the expected shape ────────────────────────


def test_divergence_calc_outputs() -> None:
    """Each divergence calc returns a same-length series of {+1, -1, 0, None}
    codes, and the decelerating decline elicits at least one bullish (+1)
    RSI/MACD divergence."""
    closes = [25000.0 - 1500.0 * (1 - math.exp(-t / 60.0)) for t in range(120)]
    volumes = [1000.0] * 120

    outputs = {
        "rsi": rsi_divergence(closes, 14, 20),
        "macd": macd_divergence(closes, 12, 26, 9, 25),
        "obv": obv_divergence(closes, volumes, 25),
    }
    for name, out in outputs.items():
        assert len(out) == 120, f"{name}: length mismatch ({len(out)} != 120)"
        assert all(v in _DIVERGENCE_CODES for v in out), f"{name}: non-code value"

    assert any(v == 1.0 for v in outputs["rsi"]), "expected a bullish RSI divergence"
    assert any(v == 1.0 for v in outputs["macd"]), "expected a bullish MACD divergence"


# ─── 2. Registry resolves divergence ids to their calc + the runner emits ───


@pytest.mark.parametrize("type_id", ["rsi_divergence", "macd_divergence", "obv_divergence"])
def test_divergence_indicator_dispatch(type_id: str) -> None:
    """The registry knows each divergence id and resolves it to a callable
    calculation function."""
    assert type_id in INDICATOR_REGISTRY, f"{type_id} not registered"
    fn = get_calculation_function(type_id)
    assert callable(fn)
    assert INDICATOR_REGISTRY[type_id].calculation_function == type_id


def test_runner_emits_divergence_series(seed_templates: dict) -> None:
    """The backtest runner precomputes the divergence indicator under its
    declared id and emits a +1 bullish code somewhere in the series."""
    strategy = translate_template(seed_templates["rsi-divergence"])
    candles = _decelerating_decline(120)
    series, _warnings = precompute_indicators(candles, strategy)
    assert "rsi_div" in series
    assert len(series["rsi_div"]) == len(candles)
    assert any(v == 1.0 for v in series["rsi_div"]), "runner emitted no bullish code"


# ─── 3. Translator handles the divergence conditions ────────────────────


@pytest.mark.parametrize("slug", _TARGET_SLUGS)
def test_translator_handles_divergence_conditions(seed_templates: dict, slug: str) -> None:
    """Each seed template now translates to a StrategyJSON that declares a
    divergence indicator and gates entry on a ``divergence > 0`` condition —
    i.e. the override short-circuits the (unparseable) prose parser."""
    strategy = translate_template(seed_templates[slug])
    assert isinstance(strategy, StrategyJSON)
    assert strategy.id == f"template:{slug}"

    divergence_ids = {
        ind.id for ind in strategy.indicators if ind.type.endswith("_divergence")
    }
    assert divergence_ids, f"{slug}: no divergence indicator declared"

    bullish_entry = [
        c
        for c in strategy.entry.conditions
        if isinstance(c, IndicatorCondition)
        and c.left in divergence_ids
        and c.op.value == ">"
        and c.value == 0.0
    ]
    assert bullish_entry, f"{slug}: no 'divergence > 0' entry condition"


# ─── 4. The 3 targets pass validation + produce trades ──────────────────


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
    """Guard against accidental scope creep in the override registry seed."""
    assert set(DIVERGENCE_OVERRIDES) == set(_TARGET_SLUGS)

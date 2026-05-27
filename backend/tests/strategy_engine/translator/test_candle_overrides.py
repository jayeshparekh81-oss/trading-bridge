"""Queue QQ / E2 — candle-pattern template override tests.

Proves the 2 active candle-pattern templates (``doji-reversal``,
``engulfing-candle-reversal``) — FAIL_UNPARSEABLE under the Queue BB prose
parser — now translate to valid ``StrategyJSON`` via the founder override
registry and produce trades on a synthetic backtest.

The schema's ``CandleCondition`` + the entry engine's ``detect_candle_pattern``
already supported these patterns; E2 adds only the translator overrides (see
``app/strategy_engine/translator/candle_overrides.py`` and
``docs/QUEUE_QQ_TRANSLATOR_E2.md``). ``hammer-hanging-man-pattern`` is out of
scope (inactive + references an unregistered S/R indicator).

Synthetic series are engineered per template (the sine fixture's fixed body
shape never forms dojis/engulfings):
  * doji — steady oversold decline (close<ema_50, rsi<35) with periodic
    zero-body doji bars;
  * engulfing — decline → brief pause → small bullish bar engulfing the prior
    bearish bar (rsi stays deeply oversold across the pause).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.strategy_engine.backtest import BacktestInput, run_backtest
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import (
    CandleCondition,
    CandlePattern,
    StrategyJSON,
)
from app.strategy_engine.translator import translate_template
from app.strategy_engine.translator.candle_overrides import (
    CANDLE_OVERRIDES,
    register_candle_overrides,
)

_IST = ZoneInfo("Asia/Kolkata")
_TARGET_SLUGS = ["doji-reversal", "engulfing-candle-reversal"]


@pytest.fixture(scope="module")
def seed_templates() -> dict:
    seed = (
        Path(__file__).resolve().parents[3] / "data" / "strategy_templates_seed.json"
    )
    data = json.loads(seed.read_text(encoding="utf-8"))
    return {t["slug"]: t for t in data["templates"] if isinstance(t, dict)}


@pytest.fixture(autouse=True)
def _ensure_overrides() -> None:
    register_candle_overrides()


# ─── Synthetic OHLC builders ────────────────────────────────────────────


def _wrap(raw: list[tuple[float, float, float, float]]) -> list[Candle]:
    """(open, high, low, close) tuples → 5-min IST candles across days."""
    cands: list[Candle] = []
    idx = 0
    day = 0
    n = len(raw)
    while idx < n:
        day_start = datetime(2026, 1, 5, 9, 15, tzinfo=_IST) + timedelta(days=day)
        for i in range(72):
            if idx >= n:
                break
            o, h, lo, c = raw[idx]
            cands.append(
                Candle(
                    timestamp=day_start + timedelta(minutes=5 * i),
                    open=o,
                    high=h,
                    low=lo,
                    close=c,
                    volume=1000.0,
                )
            )
            idx += 1
        day += 1
    return cands


def _doji_series(n: int = 300) -> list[Candle]:
    """Steady decline (oversold: close<ema_50, rsi<35) with a zero-body doji
    bar every 10th bar."""
    raw: list[tuple[float, float, float, float]] = []
    for t in range(n):
        c = 25000.0 - 25.0 * t
        o = c if t % 10 == 0 else c + 15.0  # zero body = doji, else small bearish
        raw.append((o, max(o, c) + 20.0, min(o, c) - 20.0, c))
    return _wrap(raw)


def _engulfing_series(n: int = 300, drop: float = 15.0, cyc: int = 15) -> list[Candle]:
    """Decline → 1-bar pause (small bearish) → bullish bar engulfing it → resume
    decline. RSI stays deeply oversold (<40) across the pause, so the bullish
    engulfing bar carries rsi<40."""
    raw: list[tuple[float, float, float, float]] = []
    level = 25000.0
    for t in range(n):
        ph = t % cyc
        if ph == cyc - 3:  # small bearish setup (pause)
            o, c = level + 4.0, level - 4.0
        elif ph == cyc - 2:  # bullish engulfing of the setup
            o, c = level - 8.0, level + 8.0
        elif ph == cyc - 1:  # hold
            o, c = level + 5.0, level - 5.0
        else:  # decline
            o, c = level + 5.0, level - 5.0
            level -= drop
        raw.append((o, max(o, c) + 5.0, min(o, c) - 5.0, c))
    return _wrap(raw)


_CANDLES_BY_SLUG = {
    "doji-reversal": _doji_series,
    "engulfing-candle-reversal": _engulfing_series,
}


# ─── 1. Engine supports the patterns the overrides use ──────────────────


def test_candle_patterns_supported_by_engine() -> None:
    """The patterns the overrides reference are real CandlePattern members."""
    for name in ("doji", "engulfing", "bullish"):
        assert CandlePattern(name) in CandlePattern


# ─── 2. Translator handles the candle conditions ────────────────────────


def test_doji_override_uses_doji_candle_condition(seed_templates: dict) -> None:
    strategy = translate_template(seed_templates["doji-reversal"])
    assert isinstance(strategy, StrategyJSON)
    assert strategy.id == "template:doji-reversal"
    patterns = {
        c.pattern for c in strategy.entry.conditions if isinstance(c, CandleCondition)
    }
    assert CandlePattern.DOJI in patterns


def test_engulfing_override_is_bullish_specific(seed_templates: dict) -> None:
    """Bullish engulfing = ENGULFING ∧ BULLISH (the engine's ENGULFING is
    direction-agnostic, so BULLISH pins it to a bullish engulfing)."""
    strategy = translate_template(seed_templates["engulfing-candle-reversal"])
    patterns = {
        c.pattern for c in strategy.entry.conditions if isinstance(c, CandleCondition)
    }
    assert CandlePattern.ENGULFING in patterns
    assert CandlePattern.BULLISH in patterns


# ─── 3. The 2 targets pass validation + produce trades ──────────────────


@pytest.mark.parametrize("slug", _TARGET_SLUGS)
def test_2_targets_pass_validation(seed_templates: dict, slug: str) -> None:
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


def test_overrides_cover_exactly_the_two_slugs() -> None:
    """Scope guard — hammer-hanging-man-pattern is intentionally excluded."""
    assert set(CANDLE_OVERRIDES) == set(_TARGET_SLUGS)

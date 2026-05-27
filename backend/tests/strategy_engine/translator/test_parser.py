"""Translator parser tests — Queue BB Phase 5.

Covers:
    * Happy path: ema-crossover-9-21 round-trip → engine → trades.
    * Typed errors: UnknownIndicator, UnparseableCondition, MissingField.
    * Override registry short-circuit.
    * Indicator-id grammar edge cases.
    * Pseudo-indicator auto-declare (``close``).

Synthetic candles use an IST trading window so the auto-injected
``TimeCondition(BETWEEN, "09:15", "15:15")`` doesn't suppress entries.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.strategy_engine.backtest import BacktestInput, run_backtest
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import (
    IndicatorCondition,
    IndicatorConditionOp,
    StrategyJSON,
    TimeCondition,
    TimeConditionOp,
)
from app.strategy_engine.translator import (
    MissingFieldError,
    TranslationError,
    UnknownIndicatorError,
    UnparseableConditionError,
    clear_overrides,
    parse_condition,
    parse_conditions,
    parse_indicator_id,
    register_override,
    translate_template,
)


_IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(autouse=True)
def _reset_overrides() -> None:
    """Each test starts with an empty override registry — module-level
    side effects across tests would make per-test reasoning hard."""
    clear_overrides()
    yield
    clear_overrides()


@pytest.fixture
def trading_window_candles() -> list[Candle]:
    """720 5-min bars across 10 days inside the 09:15-15:15 IST window.
    Sine-wave price pattern stimulates EMA / RSI / similar crossovers
    a handful of times per day so smoke tests see non-zero trade counts."""
    candles: list[Candle] = []
    for day in range(10):
        day_start = datetime(2026, 1, 5, 9, 15, tzinfo=_IST) + timedelta(days=day)
        for i in range(72):
            ts = day_start + timedelta(minutes=5 * i)
            phase = (day * 72 + i) / 10.0
            price = 25000.0 + 200.0 * math.sin(phase)
            candles.append(
                Candle(
                    timestamp=ts,
                    open=price - 5,
                    high=price + 20,
                    low=price - 20,
                    close=price + 5,
                    volume=1000.0,
                )
            )
    return candles


@pytest.fixture
def ema_crossover_template() -> dict:
    """The Queue BB Phase 2 spike template — verbatim from seed."""
    return {
        "slug": "ema-crossover-9-21",
        "name": "EMA Crossover 9/21",
        "complexity": "beginner",
        "config_json": {
            "indicators": ["ema_9", "ema_21"],
            "entry_long": {"condition": "ema_9 crosses above ema_21"},
            "exit_long": {"condition": "ema_9 crosses below ema_21"},
            "stop_loss_pct": 1.5,
            "take_profit_pct": 3.0,
            "trading_hours": {"start": "09:15", "end": "15:15"},
        },
    }


# ─── Happy path ─────────────────────────────────────────────────────────


def test_translate_template_happy_path_validates(
    ema_crossover_template: dict,
) -> None:
    """Translated output is a frozen StrategyJSON and round-trips through
    ``model_validate`` cleanly — proves the field map is consistent with
    the schema's structural rules."""
    strategy = translate_template(ema_crossover_template)
    assert isinstance(strategy, StrategyJSON)
    assert strategy.id == "template:ema-crossover-9-21"
    assert strategy.name == "EMA Crossover 9/21"

    # Round-trip via model_dump → model_validate.
    revived = StrategyJSON.model_validate(strategy.model_dump(by_alias=True))
    assert revived == strategy


def test_translate_template_round_trip_through_engine(
    ema_crossover_template: dict, trading_window_candles: list[Candle]
) -> None:
    """Translated strategy must produce >=1 trade on a sine-wave
    synthetic NIFTY series — proves engine end-to-end and that the
    auto-injected trading_hours TimeCondition doesn't silently zero
    the trade count."""
    strategy = translate_template(ema_crossover_template)
    result = run_backtest(
        BacktestInput(candles=trading_window_candles, strategy=strategy)
    )
    assert result.total_trades >= 1, (
        f"Expected >=1 trade, got {result.total_trades}. Likely a regression "
        f"in TimeCondition or EntryRules construction."
    )


# ─── Indicator-id grammar ───────────────────────────────────────────────


def test_parse_indicator_id_single_period() -> None:
    cfg = parse_indicator_id("ema_9")
    assert cfg.id == "ema_9"
    assert cfg.type == "ema"
    assert cfg.params == {"period": 9}


def test_parse_indicator_id_multi_param_macd() -> None:
    cfg = parse_indicator_id("macd_12_26_9")
    assert cfg.type == "macd"
    assert cfg.params == {"fast_period": 12, "slow_period": 26, "signal_period": 9}


def test_parse_indicator_id_paramless() -> None:
    cfg = parse_indicator_id("vwap")
    assert cfg.type == "vwap"
    assert cfg.params == {}


def test_parse_indicator_id_alias_bb() -> None:
    """``bb_20_2`` is template shorthand for ``bollinger_bands`` with
    period=20, std_dev=2 — alias-expansion path. Param names match the
    registry InputSpec (``std_dev``, not ``std``) so the engine accepts them."""
    cfg = parse_indicator_id("bb_20_2")
    assert cfg.type == "bollinger_bands"
    assert cfg.params == {"period": 20, "std_dev": 2}


def test_parse_indicator_id_unknown_raises_typed() -> None:
    with pytest.raises(UnknownIndicatorError) as excinfo:
        parse_indicator_id("totally_made_up_indicator")
    assert excinfo.value.ind_id == "totally_made_up_indicator"
    assert excinfo.value.category == "UNKNOWN_INDICATOR"


# ─── Condition grammar ──────────────────────────────────────────────────


def test_parse_condition_crossover_indicators() -> None:
    cond = parse_condition("ema_9 crosses above ema_21", field="entry_long")
    assert isinstance(cond, IndicatorCondition)
    assert cond.left == "ema_9"
    assert cond.op is IndicatorConditionOp.CROSSOVER
    assert cond.right == "ema_21"


def test_parse_condition_indicator_vs_scalar() -> None:
    cond = parse_condition("rsi_14 > 70", field="exit_long")
    assert isinstance(cond, IndicatorCondition)
    assert cond.left == "rsi_14"
    assert cond.op is IndicatorConditionOp.GT
    assert cond.value == 70.0
    assert cond.right is None


def test_parse_condition_value_crossover_loses_edge_semantics() -> None:
    """``X crosses above N from below`` maps to ``X > N`` because the
    schema's crossover op requires another indicator id. Documented
    intentional approximation."""
    cond = parse_condition(
        "rsi_14 crosses above 30 from below", field="entry_long"
    )
    assert isinstance(cond, IndicatorCondition)
    assert cond.left == "rsi_14"
    assert cond.op is IndicatorConditionOp.GT
    assert cond.value == 30.0


def test_parse_condition_time_compare() -> None:
    cond = parse_condition("timestamp >= 09:30 IST", field="entry_long")
    assert isinstance(cond, TimeCondition)
    assert cond.op is TimeConditionOp.AFTER
    assert cond.value == "09:30"


def test_parse_conditions_and_split() -> None:
    """``AND`` splits into multiple conditions in a flat list."""
    conds = parse_conditions(
        "ema_9 crosses above ema_21 AND rsi_14 > 50", field="entry_long"
    )
    assert len(conds) == 2
    assert isinstance(conds[0], IndicatorCondition)
    assert conds[0].op is IndicatorConditionOp.CROSSOVER
    assert conds[1].op is IndicatorConditionOp.GT


def test_parse_conditions_strip_parenthetical_comment() -> None:
    """Trailing parentheticals like ``(positive money flow)`` are
    decorative and must not break parsing."""
    cond = parse_condition(
        "cmf_20 > 0.05 (positive money flow)", field="entry_long"
    )
    assert isinstance(cond, IndicatorCondition)
    assert cond.value == 0.05


def test_parse_conditions_mixed_and_or_raises() -> None:
    """Schema can't express precedence — translator refuses ambiguous
    mixed prose instead of silently picking an associativity."""
    with pytest.raises(UnparseableConditionError):
        parse_conditions(
            "rsi_14 > 70 OR rsi_14 < 30 AND adx_14 > 25",
            field="entry_long",
        )


def test_parse_condition_garbage_raises_typed() -> None:
    with pytest.raises(UnparseableConditionError) as excinfo:
        parse_condition(
            "look up at the chart and guess", field="entry_long"
        )
    assert excinfo.value.field == "entry_long"
    assert excinfo.value.prose == "look up at the chart and guess"


# ─── Override registry ──────────────────────────────────────────────────


def test_override_short_circuits_parser(
    ema_crossover_template: dict,
) -> None:
    """When an override is registered for a slug, the parser is skipped
    entirely and the override's dict is validated through
    ``StrategyJSON.model_validate``."""
    hand_written = {
        "id": "template:ema-crossover-9-21",
        "name": "Hand-written EMA Crossover",
        "mode": "expert",
        "version": 1,
        "indicators": [
            {"id": "ema_9", "type": "ema", "params": {"period": 9}},
            {"id": "ema_21", "type": "ema", "params": {"period": 21}},
        ],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {
                    "type": "indicator",
                    "left": "ema_9",
                    "op": "crossover",
                    "right": "ema_21",
                }
            ],
        },
        "exit": {
            "stop_loss_percent": 2.0,
            "indicator_exits": [
                {
                    "type": "indicator",
                    "left": "ema_9",
                    "op": "crossunder",
                    "right": "ema_21",
                }
            ],
        },
        "risk": {},
        "execution": {
            "mode": "backtest",
            "order_type": "MARKET",
            "product_type": "INTRADAY",
        },
    }
    register_override("ema-crossover-9-21", hand_written)

    strategy = translate_template(ema_crossover_template)
    # The override wins — mode is "expert" (override), not "beginner" (template).
    assert strategy.mode.value == "expert"
    assert strategy.name == "Hand-written EMA Crossover"


# ─── Top-level guards ──────────────────────────────────────────────────


def test_translate_missing_config_json_raises() -> None:
    with pytest.raises(MissingFieldError) as excinfo:
        translate_template({"slug": "x", "name": "y", "complexity": "beginner"})
    assert excinfo.value.field == "config_json"


def test_translate_missing_slug_raises() -> None:
    with pytest.raises(MissingFieldError) as excinfo:
        translate_template({"config_json": {"indicators": ["ema_9"]}})
    assert excinfo.value.field == "slug"


def test_translate_propagates_indicator_error_with_slug() -> None:
    """Slug context must be attached to bubbled-up errors so the override
    catalog generator can group failures by template."""
    template = {
        "slug": "bogus-template",
        "name": "Bogus",
        "complexity": "beginner",
        "config_json": {
            "indicators": ["totally_made_up_indicator"],
            "entry_long": {"condition": "ema_9 crosses above ema_21"},
            "exit_long": {"condition": "ema_9 crosses below ema_21"},
            "stop_loss_pct": 1.0,
            "take_profit_pct": 2.0,
            "trading_hours": {"start": "09:15", "end": "15:15"},
        },
    }
    with pytest.raises(UnknownIndicatorError) as excinfo:
        translate_template(template)
    assert excinfo.value.slug == "bogus-template"


# ─── Pseudo-indicator auto-declare ─────────────────────────────────────


def test_translate_auto_declares_close_pseudo_indicator() -> None:
    """``close > ema_50`` in prose forces the translator to add a
    ``close`` pseudo-indicator to the indicators list so the schema's
    referential-integrity check passes."""
    template = {
        "slug": "synthetic-close-test",
        "name": "Synthetic close test",
        "complexity": "beginner",
        "config_json": {
            "indicators": ["ema_50"],
            "entry_long": {"condition": "close > ema_50"},
            "exit_long": {"condition": "close < ema_50"},
            "stop_loss_pct": 1.0,
            "take_profit_pct": 2.0,
            "trading_hours": {"start": "09:15", "end": "15:15"},
        },
    }
    strategy = translate_template(template)
    declared_ids = {i.id for i in strategy.indicators}
    assert "close" in declared_ids, (
        f"close pseudo-indicator missing; declared={declared_ids}"
    )
    # The pseudo uses EMA(2) — minimum legal period that approximates
    # the raw close series (see parser.py for rationale).
    close_cfg = next(i for i in strategy.indicators if i.id == "close")
    assert close_cfg.type == "ema"
    assert close_cfg.params["period"] == 2


def test_translate_auto_declares_sub_output_synonyms() -> None:
    """Conditions referencing indicator sub-outputs by bare name
    (``macd_line``/``signal_line``/``macd_histogram``) get auto-declared as
    sub-output IndicatorConfigs (carrying ``output``) so the schema's
    referential-integrity check passes. Queue MM A2 (synonym resolution)."""
    template = {
        "slug": "synthetic-macd-suboutput",
        "name": "Synthetic MACD sub-output",
        "complexity": "intermediate",
        "config_json": {
            "indicators": ["macd_12_26_9"],
            "entry_long": {
                "condition": "macd_line crosses above signal_line AND macd_histogram > 0"
            },
            "exit_long": {"condition": "macd_line crosses below signal_line"},
            "stop_loss_pct": 1.0,
            "take_profit_pct": 2.0,
            "trading_hours": {"start": "09:15", "end": "15:15"},
        },
    }
    strategy = translate_template(template)
    by_id = {i.id: i for i in strategy.indicators}
    for sub_id, output in [
        ("macd_line", "macd"),
        ("signal_line", "signal"),
        ("macd_histogram", "histogram"),
    ]:
        assert sub_id in by_id, f"{sub_id} not declared; have {sorted(by_id)}"
        assert by_id[sub_id].type == "macd"
        assert by_id[sub_id].output == output
        # params inherited verbatim from the declared parent.
        assert by_id[sub_id].params == by_id["macd_12_26_9"].params


def test_translate_auto_declares_orb_suffix_sub_output() -> None:
    """``orb_15_high`` resolves to parent ``orb_15`` + output ``high`` via
    Style-B suffix decomposition. Queue MM A2 (synonym resolution)."""
    template = {
        "slug": "synthetic-orb-suboutput",
        "name": "Synthetic ORB sub-output",
        "complexity": "beginner",
        "config_json": {
            "indicators": ["orb_15"],
            "entry_long": {"condition": "close > orb_15_high AND timestamp >= 09:30 IST"},
            "exit_long": {"condition": "close < orb_15_high"},
            "stop_loss_pct": 1.0,
            "take_profit_pct": 2.0,
            "trading_hours": {"start": "09:15", "end": "15:15"},
        },
    }
    strategy = translate_template(template)
    by_id = {i.id: i for i in strategy.indicators}
    assert "orb_15_high" in by_id, f"have {sorted(by_id)}"
    assert by_id["orb_15_high"].type == "opening_range_breakout"
    assert by_id["orb_15_high"].output == "high"


# ─── Smoke tests for additional translated templates ───────────────────


@pytest.mark.parametrize(
    "slug,indicators,entry,exit",
    [
        (
            "rsi-oversold-bounce",
            ["rsi_14"],
            "rsi_14 crosses above 30 from below",
            "rsi_14 > 70 OR rsi_14 < 50",
        ),
        (
            "aroon-crossover",
            ["aroon_up_14", "aroon_down_14"],
            "aroon_up_14 crosses above aroon_down_14",
            "aroon_up_14 crosses below aroon_down_14",
        ),
    ],
)
def test_translate_additional_known_passing_templates(
    slug: str,
    indicators: list[str],
    entry: str,
    exit: str,
    trading_window_candles: list[Candle],
) -> None:
    """Smoke-run a few additional templates known to translate cleanly
    (rsi-oversold-bounce + aroon-crossover from PROGRESS.md). Catches
    regressions in the parser for the broader set without re-loading
    the full seed JSON."""
    template = {
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "complexity": "beginner",
        "config_json": {
            "indicators": indicators,
            "entry_long": {"condition": entry},
            "exit_long": {"condition": exit},
            "stop_loss_pct": 1.0,
            "take_profit_pct": 2.0,
            "trading_hours": {"start": "09:15", "end": "15:15"},
        },
    }
    strategy = translate_template(template)
    # Must validate.
    assert isinstance(strategy, StrategyJSON)
    # Must run through engine without raising — trade count flexibility
    # because grammar approximations alter trade timing for some shapes.
    result = run_backtest(
        BacktestInput(candles=trading_window_candles, strategy=strategy)
    )
    assert result.total_trades >= 0  # never negative; tautology proves no exception

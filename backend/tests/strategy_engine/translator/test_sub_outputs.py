"""Sub-output synonym resolver tests — Queue MM A2 (synonym resolution).

Covers both resolution styles in ``translator/sub_outputs.py``:
    * Style A — fixed semantic synonyms (macd_line/signal_line/macd_histogram,
      bb_upper/bb_middle/bb_lower) bound to the single declared parent.
    * Style B — ``<parent_id>_<suffix>`` decomposition (orb_15_high/orb_15_low).
    * Ambiguity / miss cases that must return ``None``.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.schema.strategy import IndicatorConfig
from app.strategy_engine.translator.sub_outputs import (
    ResolvedSubOutput,
    resolve_sub_output,
)

_MACD = IndicatorConfig(
    id="macd_12_26_9",
    type="macd",
    params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
)
_BB = IndicatorConfig(
    id="bb_20_2", type="bollinger_bands", params={"period": 20, "std_dev": 2}
)
_RSI = IndicatorConfig(id="rsi_14", type="rsi", params={"period": 14})
_ORB = IndicatorConfig(id="orb_15", type="opening_range_breakout", params={"minutes": 15})


@pytest.mark.parametrize(
    ("token", "output"),
    [("macd_line", "macd"), ("signal_line", "signal"), ("macd_histogram", "histogram")],
)
def test_style_a_macd_synonyms_bind_to_declared_parent(token: str, output: str) -> None:
    r = resolve_sub_output(token, [_MACD, _RSI])
    assert r == ResolvedSubOutput(
        sub_id=token,
        parent_type="macd",
        params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        output=output,
    )


@pytest.mark.parametrize(
    ("token", "output"),
    [("bb_upper", "upper"), ("bb_middle", "middle"), ("bb_lower", "lower")],
)
def test_style_a_bb_synonyms_bind_to_declared_parent(token: str, output: str) -> None:
    r = resolve_sub_output(token, [_BB, _RSI])
    assert r is not None
    assert (r.parent_type, r.output, r.params) == (
        "bollinger_bands",
        output,
        {"period": 20, "std_dev": 2},
    )


def test_style_a_returns_none_when_no_parent_declared() -> None:
    # signal_line needs a macd parent; only RSI is declared.
    assert resolve_sub_output("signal_line", [_RSI]) is None


def test_style_a_returns_none_when_parent_ambiguous() -> None:
    macd_b = IndicatorConfig(
        id="macd_5_35_5",
        type="macd",
        params={"fast_period": 5, "slow_period": 35, "signal_period": 5},
    )
    assert resolve_sub_output("signal_line", [_MACD, macd_b]) is None


@pytest.mark.parametrize(
    ("token", "minutes", "output"),
    [("orb_15_high", 15, "high"), ("orb_15_low", 15, "low"), ("orb_30_high", 30, "high")],
)
def test_style_b_orb_suffix_decomposition(token: str, minutes: int, output: str) -> None:
    # Style B parses the parent id from the token itself; declared list is
    # irrelevant to the parse (passed empty to prove independence). Param name is
    # the registry's ``range_minutes`` so the engine accepts it.
    r = resolve_sub_output(token, [])
    assert r is not None
    assert (r.parent_type, r.params, r.output) == (
        "opening_range_breakout",
        {"range_minutes": minutes},
        output,
    )


def test_style_b_unknown_parent_prefix_returns_none() -> None:
    # "_high" suffix but the prefix isn't a parseable opening_range_breakout id.
    assert resolve_sub_output("frobnicate_high", []) is None


def test_non_suboutput_token_returns_none() -> None:
    # A normal indicator id is not a sub-output reference.
    assert resolve_sub_output("rsi_14", [_MACD, _RSI, _BB]) is None


def test_resolved_params_are_copied_not_aliased() -> None:
    r = resolve_sub_output("signal_line", [_MACD])
    assert r is not None
    r.params["fast_period"] = 999
    assert _MACD.params["fast_period"] == 12  # parent untouched

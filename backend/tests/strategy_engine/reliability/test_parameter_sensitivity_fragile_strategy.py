"""Parameter sensitivity: synthetic-fragile case + path enumeration."""

from __future__ import annotations

from app.strategy_engine.reliability.parameter_sensitivity import (
    VariantOutcome,
    _enumerate_tunables,
    _set_path,
    _summarise,
    _tokenize_path,
)

# ─── Tunable enumeration ───────────────────────────────────────────────


def test_enumerate_tunables_finds_indicator_period() -> None:
    strategy_dict = {
        "indicators": [
            {"id": "ema_20", "type": "ema", "params": {"period": 20, "source": "close"}}
        ],
        "exit": {"targetPercent": 2},
    }
    pairs = _enumerate_tunables(strategy_dict)
    paths = {p for p, _ in pairs}
    assert "indicators[0].params.period" in paths
    assert "exit.targetPercent" in paths


def test_enumerate_tunables_finds_macd_three_periods() -> None:
    strategy_dict = {
        "indicators": [
            {
                "id": "macd_d",
                "type": "macd",
                "params": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "source": "close",
                },
            }
        ],
        "exit": {"stopLossPercent": 1},
    }
    pairs = _enumerate_tunables(strategy_dict)
    paths = {p for p, _ in pairs}
    assert "indicators[0].params.fast_period" in paths
    assert "indicators[0].params.slow_period" in paths
    assert "indicators[0].params.signal_period" in paths


def test_enumerate_tunables_finds_bollinger_period_and_stddev() -> None:
    strategy_dict = {
        "indicators": [
            {
                "id": "bb_d",
                "type": "bollinger_bands",
                "params": {"period": 20, "std_dev": 2.0, "source": "close"},
            }
        ],
        "exit": {"stopLossPercent": 1},
    }
    pairs = _enumerate_tunables(strategy_dict)
    paths = {p for p, _ in pairs}
    assert "indicators[0].params.period" in paths
    assert "indicators[0].params.std_dev" in paths


def test_enumerate_tunables_skips_string_and_bool_params() -> None:
    """``source`` strings and any boolean params must NOT be tunables."""
    strategy_dict = {
        "indicators": [
            {"id": "ema_20", "type": "ema", "params": {"period": 20, "source": "close"}}
        ],
        "exit": {"targetPercent": 2, "reverseSignalExit": True},
    }
    pairs = _enumerate_tunables(strategy_dict)
    paths = {p for p, _ in pairs}
    assert "indicators[0].params.source" not in paths
    assert "exit.reverseSignalExit" not in paths


# ─── _tokenize_path / _set_path ────────────────────────────────────────


def test_tokenize_path_splits_into_string_and_int_tokens() -> None:
    assert _tokenize_path("indicators[0].params.period") == [
        "indicators",
        0,
        "params",
        "period",
    ]


def test_set_path_writes_through_nested_list_and_dict() -> None:
    target: dict[str, object] = {
        "indicators": [{"params": {"period": 20}}],
    }
    _set_path(target, "indicators[0].params.period", 30)
    assert target["indicators"][0]["params"]["period"] == 30  # type: ignore[index]


def test_set_path_writes_top_level_dict_field() -> None:
    target: dict[str, object] = {"exit": {"targetPercent": 2}}
    _set_path(target, "exit.targetPercent", 5)
    assert target["exit"]["targetPercent"] == 5  # type: ignore[index]


# ─── _summarise (fragile branch) ───────────────────────────────────────


def test_summarise_above_fragile_threshold_flags_fragile() -> None:
    """50 % degraded is well above 30 % -> fragile."""
    variants = [
        VariantOutcome(
            param_path=f"p_{i}",
            base_value=10.0,
            variant_value=11.0,
            variation_pct=0.10,
            score=40,
            score_delta=-30 if i < 5 else -10,  # 5 / 10 degraded
            degraded=i < 5,
        )
        for i in range(10)
    ]
    fragile, stability, warning = _summarise(variants)
    assert fragile is True
    assert stability == 0.5
    assert "fragile" in warning.lower()


def test_summarise_warning_includes_percentage() -> None:
    variants = [
        VariantOutcome(
            param_path="p",
            base_value=10.0,
            variant_value=11.0,
            variation_pct=0.10,
            score=40,
            score_delta=-30,
            degraded=True,
        )
    ]
    _, _, warning = _summarise(variants)
    assert "100 %" in warning

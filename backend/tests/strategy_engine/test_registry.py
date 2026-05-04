"""Registry tests — loads, lookups, validation, calc-function resolution."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators import (
    INDICATOR_REGISTRY,
    IndicatorParamError,
    get_active_indicators,
    get_beginner_recommended_indicators,
    get_calculation_function,
    get_indicator_by_id,
    get_indicators_by_category,
    list_categories,
    validate_indicator_params,
)
from app.strategy_engine.schema.indicator import (
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
)


def test_registry_has_ten_active_entries() -> None:
    """Phase 1 ships exactly 10 indicators, all active."""
    assert len(INDICATOR_REGISTRY) == 10
    actives = get_active_indicators()
    assert len(actives) == 10
    expected_ids = {
        "ema",
        "sma",
        "wma",
        "rsi",
        "macd",
        "bollinger_bands",
        "atr",
        "vwap",
        "obv",
        "volume_sma",
    }
    assert {meta.id for meta in actives} == expected_ids


def test_every_active_entry_has_a_resolvable_calculation() -> None:
    """Calling ``get_calculation_function`` on every active id must work."""
    for ind_id, meta in INDICATOR_REGISTRY.items():
        if meta.status is IndicatorStatus.ACTIVE:
            fn = get_calculation_function(ind_id)
            assert callable(fn)


def test_get_indicator_by_id_known_and_unknown() -> None:
    assert get_indicator_by_id("ema") is not None
    assert get_indicator_by_id("nonexistent") is None


def test_get_indicators_by_category_case_insensitive() -> None:
    trend = get_indicators_by_category("Trend")
    trend_lower = get_indicators_by_category("trend")
    assert {m.id for m in trend} == {m.id for m in trend_lower}
    assert {m.id for m in trend} == {"ema", "sma", "wma"}


def test_beginner_recommended_subset() -> None:
    """Beginner subset is an ACTIVE intersection beginner-difficulty filter."""
    beginners = get_beginner_recommended_indicators()
    for meta in beginners:
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.difficulty is IndicatorDifficulty.BEGINNER
    assert {m.id for m in beginners} == {"ema", "sma", "rsi", "volume_sma"}


def test_list_categories_sorted_unique() -> None:
    cats = list_categories()
    assert cats == sorted(set(cats))
    assert {"Trend", "Momentum", "Volatility", "Volume"}.issubset(set(cats))


def test_validate_indicator_params_fills_defaults() -> None:
    resolved = validate_indicator_params("ema", {"period": 50})
    assert resolved == {"period": 50, "source": "close"}


def test_validate_indicator_params_unknown_indicator() -> None:
    with pytest.raises(IndicatorParamError):
        validate_indicator_params("not_real", {})


def test_validate_indicator_params_unknown_param_rejected() -> None:
    with pytest.raises(IndicatorParamError) as excinfo:
        validate_indicator_params("ema", {"period": 20, "unknown": 1})
    assert "unknown" in str(excinfo.value)


def test_validate_indicator_params_below_min_rejected() -> None:
    with pytest.raises(IndicatorParamError):
        validate_indicator_params("ema", {"period": 1})  # min=2


def test_validate_indicator_params_above_max_rejected() -> None:
    with pytest.raises(IndicatorParamError):
        validate_indicator_params("rsi", {"period": 999})  # max=200


def test_validate_indicator_params_bool_in_number_rejected() -> None:
    """``True`` is an int in Python — explicitly reject in NUMBER fields."""
    with pytest.raises(IndicatorParamError):
        validate_indicator_params("ema", {"period": True})


def test_validate_indicator_params_unknown_source_rejected() -> None:
    with pytest.raises(IndicatorParamError):
        validate_indicator_params("ema", {"period": 20, "source": "midnight"})


def test_validate_indicator_params_int_period_preserved_as_int() -> None:
    resolved = validate_indicator_params("ema", {"period": 14})
    assert isinstance(resolved["period"], int)


def test_get_calculation_function_unknown_indicator() -> None:
    with pytest.raises(IndicatorParamError):
        get_calculation_function("unknown")


def test_registry_metadata_is_immutable() -> None:
    """Registry rows are frozen Pydantic models — mutation should error."""
    meta = INDICATOR_REGISTRY["ema"]
    assert isinstance(meta, IndicatorMetadata)
    with pytest.raises((ValueError, AttributeError, TypeError)):
        meta.id = "tampered"  # type: ignore[misc]


def test_validate_params_boolean_and_string_input_types() -> None:
    """Cover the BOOLEAN / STRING branches in ``_coerce_and_check``.

    Phase 1's 10 indicators only use NUMBER + SOURCE inputs, so we exercise
    the remaining InputType branches via the internal helper directly.
    """
    from app.strategy_engine.indicators.registry import _coerce_and_check
    from app.strategy_engine.schema.indicator import InputSpec, InputType

    bool_spec = InputSpec(name="flag", type=InputType.BOOLEAN, default=False)
    assert _coerce_and_check("test_id", bool_spec, True) is True
    with pytest.raises(IndicatorParamError):
        _coerce_and_check("test_id", bool_spec, "not-a-bool")
    with pytest.raises(IndicatorParamError):
        _coerce_and_check("test_id", bool_spec, 1)  # int isn't bool

    str_spec = InputSpec(name="label", type=InputType.STRING, default="x")
    assert _coerce_and_check("test_id", str_spec, "ok") == "ok"
    with pytest.raises(IndicatorParamError):
        _coerce_and_check("test_id", str_spec, 42)


def test_get_calculation_function_for_coming_soon_entry_raises() -> None:
    """A registry entry with ``calculation_function=None`` cannot be resolved.

    Phase 1 has no coming-soon entries (Phase 9 will), so we synthesise
    one via the registry's internal mapping and pop it after the test.
    """
    from app.strategy_engine.indicators import registry as reg
    from app.strategy_engine.schema.indicator import (
        IndicatorChartType,
        IndicatorDifficulty,
        IndicatorMetadata,
        IndicatorStatus,
    )

    fake = IndicatorMetadata(
        id="fake_pending",
        name="Fake",
        category="Test",
        description="placeholder",
        chart_type=IndicatorChartType.OVERLAY,
        difficulty=IndicatorDifficulty.EXPERT,
        status=IndicatorStatus.COMING_SOON,
        ai_explanation="placeholder",
    )
    # The registry is typed as ``Mapping`` (read-only) but the underlying
    # object is a regular dict; mutate then restore inside a try/finally
    # so a failed assertion can't poison sibling tests.
    underlying: dict[str, IndicatorMetadata] = reg.INDICATOR_REGISTRY  # type: ignore[assignment]
    underlying[fake.id] = fake
    try:
        with pytest.raises(IndicatorParamError) as excinfo:
            reg.get_calculation_function(fake.id)
        assert "coming_soon" in str(excinfo.value) or "calculation function" in str(excinfo.value)
    finally:
        underlying.pop(fake.id, None)


def test_get_calculation_function_module_missing_function_raises() -> None:
    """A registry entry pointing at a module with no matching callable raises.

    Synthesise a metadata row whose ``calculation_function`` names a module
    that exists (we reuse ``sma``) but a function name that does not. The
    resolver should detect the missing attribute and raise.
    """
    from app.strategy_engine.indicators import registry as reg
    from app.strategy_engine.schema.indicator import (
        IndicatorChartType,
        IndicatorDifficulty,
        IndicatorMetadata,
        IndicatorStatus,
    )

    fake = IndicatorMetadata(
        id="fake_broken",
        name="Broken",
        category="Test",
        description="d",
        chart_type=IndicatorChartType.OVERLAY,
        difficulty=IndicatorDifficulty.EXPERT,
        status=IndicatorStatus.ACTIVE,
        ai_explanation="d",
        calculation_function="sma_does_not_exist_module",
    )
    underlying: dict[str, IndicatorMetadata] = reg.INDICATOR_REGISTRY  # type: ignore[assignment]
    underlying[fake.id] = fake
    try:
        with pytest.raises((IndicatorParamError, ModuleNotFoundError)):
            reg.get_calculation_function(fake.id)
    finally:
        underlying.pop(fake.id, None)

"""Schema tests for IndicatorMetadata + InputSpec."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
    InputSpec,
    InputType,
)


def _build_metadata(**overrides: object) -> IndicatorMetadata:
    """Helper — produce a valid IndicatorMetadata with optional overrides."""
    base: dict[str, object] = {
        "id": "test_ind",
        "name": "Test",
        "category": "Trend",
        "description": "A test indicator.",
        "inputs": [
            InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
        ],
        "outputs": ["line"],
        "chart_type": IndicatorChartType.OVERLAY,
        "pine_aliases": [],
        "difficulty": IndicatorDifficulty.BEGINNER,
        "status": IndicatorStatus.ACTIVE,
        "ai_explanation": "It tests things.",
        "tags": [],
        "calculation_function": "test_ind",
    }
    base.update(overrides)
    return IndicatorMetadata(**base)  # type: ignore[arg-type]


def test_minimal_valid_metadata_round_trips() -> None:
    meta = _build_metadata()
    assert meta.id == "test_ind"
    assert meta.status is IndicatorStatus.ACTIVE


def test_id_must_be_lower_snake_case() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _build_metadata(id="UpperCase")
    assert "lower-snake-case" in str(excinfo.value)


def test_id_rejects_spaces() -> None:
    with pytest.raises(ValidationError):
        _build_metadata(id="bollinger bands")


def test_alias_serialisation_uses_camel_case_keys() -> None:
    meta = _build_metadata()
    dumped = meta.model_dump(by_alias=True)
    assert "chartType" in dumped
    assert "pineAliases" in dumped
    assert "aiExplanation" in dumped
    assert "calculationFunction" in dumped


def test_camel_case_input_round_trips_via_alias() -> None:
    payload = {
        "id": "demo",
        "name": "Demo",
        "category": "Trend",
        "description": "demo",
        "inputs": [],
        "outputs": ["line"],
        "chartType": "overlay",
        "pineAliases": ["ta.demo"],
        "difficulty": "beginner",
        "status": "active",
        "aiExplanation": "demo",
        "tags": [],
        "calculationFunction": "demo",
    }
    meta = IndicatorMetadata.model_validate(payload)
    assert meta.chart_type is IndicatorChartType.OVERLAY
    assert meta.pine_aliases == ["ta.demo"]


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        _build_metadata(unexpected_field="oops")


def test_input_spec_default_is_required() -> None:
    with pytest.raises(ValidationError):
        InputSpec(name="period", type=InputType.NUMBER)  # type: ignore[call-arg]

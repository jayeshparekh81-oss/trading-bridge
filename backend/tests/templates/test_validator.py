"""Unit tests for :mod:`app.templates.validator`."""

from __future__ import annotations

import pytest

from app.templates.validator import (
    TemplateConfigError,
    validate_config_json,
)


# ─── Inactive path — empty config is fine ─────────────────────────────


def test_inactive_empty_config_passes() -> None:
    validate_config_json({}, is_active=False)


def test_inactive_partial_config_passes() -> None:
    # An inactive row may carry partial config (e.g. work-in-progress).
    # Validator skips the active-path checks.
    validate_config_json({"indicators": ["sma"]}, is_active=False)


def test_inactive_non_dict_fails() -> None:
    with pytest.raises(TemplateConfigError, match="expected object"):
        validate_config_json([1, 2, 3], is_active=False)  # type: ignore[arg-type]


# ─── Active path — minimum viable config ──────────────────────────────


_VALID = {
    "indicators": ["ema_9", "ema_21"],
    "entry_long": {"condition": "ema_9 > ema_21"},
    "exit_long": {"condition": "ema_9 < ema_21"},
    "stop_loss_pct": 1.5,
    "take_profit_pct": 3.0,
    "position_sizing": {"method": "fixed_amount", "amount_inr": 50000},
    "max_open_positions": 1,
    "trading_hours": {"start": "09:15", "end": "15:15"},
}


def test_active_minimal_valid_config_passes() -> None:
    validate_config_json(_VALID, is_active=True)


def test_active_empty_config_fails() -> None:
    with pytest.raises(TemplateConfigError, match="non-empty"):
        validate_config_json({}, is_active=True)


@pytest.mark.parametrize(
    "missing",
    [
        "indicators",
        "entry_long",
        "exit_long",
        "stop_loss_pct",
        "take_profit_pct",
        "position_sizing",
        "max_open_positions",
        "trading_hours",
    ],
)
def test_active_missing_key_fails(missing: str) -> None:
    cfg = {k: v for k, v in _VALID.items() if k != missing}
    with pytest.raises(TemplateConfigError, match=missing):
        validate_config_json(cfg, is_active=True)


def test_indicators_must_be_non_empty_list() -> None:
    cfg = {**_VALID, "indicators": []}
    with pytest.raises(TemplateConfigError, match="non-empty list"):
        validate_config_json(cfg, is_active=True)


def test_indicators_must_be_strings() -> None:
    cfg = {**_VALID, "indicators": ["ema_9", 42]}
    with pytest.raises(TemplateConfigError, match="non-empty string"):
        validate_config_json(cfg, is_active=True)


def test_entry_long_must_have_condition_str() -> None:
    cfg = {**_VALID, "entry_long": {"condition": ""}}
    with pytest.raises(TemplateConfigError, match="non-empty string"):
        validate_config_json(cfg, is_active=True)


def test_short_legs_must_pair() -> None:
    cfg = {**_VALID, "entry_short": {"condition": "ema_9 < ema_21"}}
    # exit_short missing → fail
    with pytest.raises(TemplateConfigError, match="both be present"):
        validate_config_json(cfg, is_active=True)


def test_short_legs_paired_passes() -> None:
    cfg = {
        **_VALID,
        "entry_short": {"condition": "ema_9 < ema_21"},
        "exit_short": {"condition": "ema_9 > ema_21"},
    }
    validate_config_json(cfg, is_active=True)


@pytest.mark.parametrize("bad", [0.0, 0.4, 10.1, 100, -1])
def test_stop_loss_bounds(bad: float) -> None:
    cfg = {**_VALID, "stop_loss_pct": bad}
    with pytest.raises(TemplateConfigError, match="stop_loss"):
        validate_config_json(cfg, is_active=True)


@pytest.mark.parametrize("bad", [0.0, 0.4, 20.1, 100])
def test_take_profit_bounds(bad: float) -> None:
    cfg = {**_VALID, "take_profit_pct": bad}
    with pytest.raises(TemplateConfigError, match="take_profit"):
        validate_config_json(cfg, is_active=True)


def test_position_sizing_amount_must_be_positive_int() -> None:
    for bad in [0, -100, 1.5, "100", True]:
        cfg = {**_VALID, "position_sizing": {"method": "fixed_amount", "amount_inr": bad}}
        with pytest.raises(TemplateConfigError, match="amount_inr"):
            validate_config_json(cfg, is_active=True)


def test_max_open_positions_must_be_one_in_phase_1() -> None:
    for bad in [0, 2, 10]:
        cfg = {**_VALID, "max_open_positions": bad}
        with pytest.raises(TemplateConfigError, match="exactly 1"):
            validate_config_json(cfg, is_active=True)


def test_trading_hours_bad_format() -> None:
    cfg = {**_VALID, "trading_hours": {"start": "9:15", "end": "15:15"}}
    with pytest.raises(TemplateConfigError, match="HH:MM"):
        validate_config_json(cfg, is_active=True)


def test_trading_hours_start_after_end() -> None:
    cfg = {**_VALID, "trading_hours": {"start": "15:15", "end": "09:15"}}
    with pytest.raises(TemplateConfigError, match="before end"):
        validate_config_json(cfg, is_active=True)


def test_trading_hours_out_of_range() -> None:
    cfg = {**_VALID, "trading_hours": {"start": "25:00", "end": "26:00"}}
    with pytest.raises(TemplateConfigError, match="out of range"):
        validate_config_json(cfg, is_active=True)


# ─── Seed file end-to-end ─────────────────────────────────────────────


def test_seed_file_all_entries_validate() -> None:
    """Every shipped seed entry must pass the validator. Catches a
    typo'd config_json at PR time before it ships to prod."""
    import json
    from pathlib import Path

    seed = Path(__file__).resolve().parents[2] / "data" / "strategy_templates_seed.json"
    data = json.loads(seed.read_text(encoding="utf-8"))

    failures: list[str] = []
    for row in data["templates"]:
        try:
            validate_config_json(
                row.get("config_json", {}),
                is_active=bool(row.get("is_active", False)),
            )
        except TemplateConfigError as exc:
            failures.append(f"{row['slug']}: {exc}")

    assert not failures, "Seed validation failures:\n" + "\n".join(failures)

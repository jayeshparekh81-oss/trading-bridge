"""Validators for the Strategy Template ``config_json`` payloads.

Active equity templates ship with a fully-populated ``config_json``
that captures the entry/exit rules, indicator parameters, position
sizing, and trading-hours envelope. This module enforces shape
guarantees at seed-load time so a malformed seed entry fails fast
with a clear message instead of slipping into the catalog and
producing garbage downstream.

Inactive entries (``is_active=False``) are allowed to carry an
empty ``config_json={}`` — the validator gates the check on the
``is_active`` flag.

Rules (Phase 1 — minimal viable enforcement):

    1. If ``is_active=True``, ``config_json`` MUST be non-empty.
    2. Top-level required keys when active:
        - ``indicators`` (list[str], non-empty)
        - ``entry_long`` (dict with ``condition`` str)
        - ``exit_long`` (dict with ``condition`` str)
        - ``stop_loss_pct`` (number, 0.5 <= x <= 10)
        - ``take_profit_pct`` (number, 0.5 <= x <= 20)
        - ``position_sizing`` (dict with ``method`` + ``amount_inr``)
        - ``max_open_positions`` (int, exactly 1 for Phase 1)
        - ``trading_hours`` (dict with ``start`` HH:MM, ``end`` HH:MM)
    3. ``entry_short`` / ``exit_short`` optional but if either is
       present both must be.

The validator is invoked at:
    * Seed import time (``registry.load_from_seed_file``)
    * Clone time (``clone_service.clone_template``) — defensive
      re-check before we materialise a strategy from the config

Validation failures raise :class:`TemplateConfigError` with a
field-path-prefixed message ("config.position_sizing.amount_inr:
must be positive integer").
"""

from __future__ import annotations

from typing import Any


class TemplateConfigError(ValueError):
    """Raised when ``config_json`` violates the Phase 1 shape rules."""


# ─── Constants ─────────────────────────────────────────────────────────


_REQUIRED_ACTIVE_KEYS: tuple[str, ...] = (
    "indicators",
    "entry_long",
    "exit_long",
    "stop_loss_pct",
    "take_profit_pct",
    "position_sizing",
    "max_open_positions",
    "trading_hours",
)

_SL_BOUNDS = (0.5, 10.0)
_TP_BOUNDS = (0.5, 20.0)


# ─── Helpers ───────────────────────────────────────────────────────────


def _require_keys(
    where: str, obj: dict[str, Any], keys: tuple[str, ...]
) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise TemplateConfigError(
            f"{where}: missing required key(s): {', '.join(missing)}"
        )


def _require_dict(where: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TemplateConfigError(
            f"{where}: expected object, got {type(value).__name__}"
        )
    return value


def _require_number(
    where: str, value: Any, *, lower: float, upper: float
) -> None:
    if not isinstance(value, (int, float)):
        raise TemplateConfigError(
            f"{where}: expected number, got {type(value).__name__}"
        )
    if isinstance(value, bool):
        raise TemplateConfigError(
            f"{where}: expected number, got bool"
        )
    if not (lower <= value <= upper):
        raise TemplateConfigError(
            f"{where}: must be in [{lower}, {upper}], got {value}"
        )


def _require_hhmm(where: str, value: Any) -> None:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise TemplateConfigError(
            f"{where}: expected HH:MM string, got {value!r}"
        )
    try:
        hh = int(value[0:2])
        mm = int(value[3:5])
    except ValueError as exc:
        raise TemplateConfigError(
            f"{where}: HH:MM must be numeric, got {value!r}"
        ) from exc
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise TemplateConfigError(
            f"{where}: HH or MM out of range in {value!r}"
        )


# ─── Public entry point ────────────────────────────────────────────────


def validate_config_json(
    config: dict[str, Any], *, is_active: bool
) -> None:
    """Validate a template's ``config_json``.

    Raises :class:`TemplateConfigError` on any rule violation.
    Returns ``None`` on success.

    Inactive templates may carry ``config = {}``. Active templates
    must carry the full Phase-1 shape.
    """
    if not isinstance(config, dict):
        raise TemplateConfigError(
            f"config: expected object, got {type(config).__name__}"
        )

    if not is_active:
        # Inactive — only constraint is that config is a dict (possibly empty).
        return

    # Active path — full validation.
    if not config:
        raise TemplateConfigError(
            "config: active templates must have non-empty config_json"
        )

    _require_keys("config", config, _REQUIRED_ACTIVE_KEYS)

    # indicators: non-empty list[str]
    indicators = config["indicators"]
    if not isinstance(indicators, list) or not indicators:
        raise TemplateConfigError(
            "config.indicators: must be non-empty list"
        )
    for i, ind in enumerate(indicators):
        if not isinstance(ind, str) or not ind:
            raise TemplateConfigError(
                f"config.indicators[{i}]: must be non-empty string"
            )

    # entry_long, exit_long: dict with `condition`
    for key in ("entry_long", "exit_long"):
        node = _require_dict(f"config.{key}", config[key])
        _require_keys(f"config.{key}", node, ("condition",))
        if not isinstance(node["condition"], str) or not node["condition"].strip():
            raise TemplateConfigError(
                f"config.{key}.condition: must be non-empty string"
            )

    # Optional shorts — if either present both must be
    has_es = "entry_short" in config
    has_xs = "exit_short" in config
    if has_es != has_xs:
        raise TemplateConfigError(
            "config: entry_short and exit_short must both be present "
            "or both absent"
        )
    if has_es:
        for key in ("entry_short", "exit_short"):
            node = _require_dict(f"config.{key}", config[key])
            _require_keys(f"config.{key}", node, ("condition",))

    # SL / TP bounds
    _require_number(
        "config.stop_loss_pct",
        config["stop_loss_pct"],
        lower=_SL_BOUNDS[0],
        upper=_SL_BOUNDS[1],
    )
    _require_number(
        "config.take_profit_pct",
        config["take_profit_pct"],
        lower=_TP_BOUNDS[0],
        upper=_TP_BOUNDS[1],
    )

    # position_sizing
    sizing = _require_dict("config.position_sizing", config["position_sizing"])
    _require_keys(
        "config.position_sizing",
        sizing,
        ("method", "amount_inr"),
    )
    if not isinstance(sizing["method"], str) or not sizing["method"]:
        raise TemplateConfigError(
            "config.position_sizing.method: must be non-empty string"
        )
    amount = sizing["amount_inr"]
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise TemplateConfigError(
            "config.position_sizing.amount_inr: must be positive integer"
        )

    # max_open_positions
    mop = config["max_open_positions"]
    if not isinstance(mop, int) or isinstance(mop, bool) or mop != 1:
        raise TemplateConfigError(
            "config.max_open_positions: must be exactly 1 in Phase 1"
        )

    # trading_hours
    hours = _require_dict("config.trading_hours", config["trading_hours"])
    _require_keys("config.trading_hours", hours, ("start", "end"))
    _require_hhmm("config.trading_hours.start", hours["start"])
    _require_hhmm("config.trading_hours.end", hours["end"])
    if hours["start"] >= hours["end"]:
        raise TemplateConfigError(
            "config.trading_hours: start must be before end"
        )


__all__ = ["TemplateConfigError", "validate_config_json"]

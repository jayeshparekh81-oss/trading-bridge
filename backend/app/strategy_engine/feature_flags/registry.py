"""Locked flag registry — name → (default, description).

The registry is the single source of truth for *which* flags exist.
Adding a new flag means editing this module; the manager refuses to
read or write any name that isn't here, so a typo can't silently
toggle behavior.

Defaults are chosen so a fresh process with empty env / no overrides
boots into the safest possible state. Flags that gate live order
flow, real money, or LLM API spend default to ``False``.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final


class _FlagDefinition:
    """Internal record. Not exported — callers see :class:`FeatureFlag`
    via the manager, which adds source/last_updated metadata."""

    __slots__ = ("default", "description")

    def __init__(self, *, default: bool, description: str) -> None:
        self.default = default
        self.description = description


_REGISTRY: Final[dict[str, _FlagDefinition]] = {
    "PINE_IMPORT_ENABLED": _FlagDefinition(
        default=True,
        description="Allow users to import TradingView Pine Script strategies.",
    ),
    "LIVE_TRADING_ENABLED": _FlagDefinition(
        default=False,
        description="Permit live (real-money) order placement. Off by default — must be explicitly opted in.",
    ),
    "MARKETPLACE_ENABLED": _FlagDefinition(
        default=False,
        description="Show the strategy marketplace UI. Post-launch feature.",
    ),
    "AUTO_DISCOVERY_ENABLED": _FlagDefinition(
        default=False,
        description="Run automatic strategy discovery jobs. Post-launch feature.",
    ),
    "EXPERT_MODE_ENABLED": _FlagDefinition(
        default=True,
        description="Expose advanced UI controls (raw indicator params, manual overrides).",
    ),
    "LLM_ADVISOR_ENABLED": _FlagDefinition(
        default=False,
        description="Enable AI advisor calls. Off by default — requires API key configuration.",
    ),
    "STRATEGY_TRUTH_ENABLED": _FlagDefinition(
        default=True,
        description="Compute and display the Strategy Truth Score on backtests.",
    ),
    "MARKET_REGIME_ENABLED": _FlagDefinition(
        default=True,
        description="Run market-regime detection during backtests and live monitoring.",
    ),
    "DEVIATION_MONITOR_ENABLED": _FlagDefinition(
        default=True,
        description="Monitor live-vs-backtest deviation and surface drift alerts.",
    ),
    "PAPER_TRADING_ENABLED": _FlagDefinition(
        default=True,
        description="Allow paper-trading sessions against live market data.",
    ),
    "BROKER_GUARD_ENABLED": _FlagDefinition(
        default=True,
        description="Pre-trade safety gate (risk limits, kill switch, sanity checks). Disabling it is a security event.",
    ),
    "AUDIT_LOG_ENABLED": _FlagDefinition(
        default=True,
        description="Record audit events for security-critical actions.",
    ),
    "HYPNOTIC_POLISH_ENABLED": _FlagDefinition(
        default=True,
        description="Enable polished UI animations and micro-interactions.",
    ),
}

REGISTRY: Final[MappingProxyType[str, _FlagDefinition]] = MappingProxyType(_REGISTRY)
"""Read-only view of the locked registry. The manager looks up
``flag_name`` here on every operation; a missing key is the contract
violation that surfaces as :class:`UnknownFlagError`."""


class UnknownFlagError(KeyError):
    """Raised when a caller references a flag not in the registry.

    Subclassing :class:`KeyError` keeps backwards-compat with any
    code that catches dict-style misses, while still being
    distinguishable in tests via ``isinstance``.
    """


def known_flags() -> tuple[str, ...]:
    """Return the locked flag names in registry order. Used by
    :func:`get_all_flags` to keep snapshot ordering deterministic."""
    return tuple(_REGISTRY.keys())


def definition(flag_name: str) -> _FlagDefinition:
    """Return the registry record for ``flag_name`` or raise."""
    try:
        return _REGISTRY[flag_name]
    except KeyError as exc:
        raise UnknownFlagError(
            f"unknown feature flag {flag_name!r}; expected one of {sorted(_REGISTRY)}"
        ) from exc


__all__ = [
    "REGISTRY",
    "UnknownFlagError",
    "definition",
    "known_flags",
]

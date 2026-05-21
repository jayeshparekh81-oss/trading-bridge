"""Founder override registry — for templates the parser cannot translate.

Per Queue AA's Option Z hybrid recommendation: the parser handles the
mechanical ~80%, and the remaining gnarly templates ship a hand-written
``StrategyJSON`` dict under their slug. At translation time the parser
consults this registry FIRST; if a slug is present, the override wins
and parsing is skipped entirely.

The registry is intentionally an in-memory dict in this prototype.
Production form would move to ``backend/data/strategy_templates_overrides.json``
and load via the standard seed loader pipeline.
"""

from __future__ import annotations

from typing import Any


#: Slug → fully-formed StrategyJSON dict (as it would be stored in
#: ``Strategy.strategy_json``). Empty in this prototype — populate as
#: founder-supplied overrides arrive.
_OVERRIDES: dict[str, dict[str, Any]] = {}


def get_override(slug: str) -> dict[str, Any] | None:
    """Return the hand-written StrategyJSON dict for ``slug``, or
    ``None`` if no override is registered. Callers should let the
    parser run when ``None`` is returned.
    """
    override = _OVERRIDES.get(slug)
    return dict(override) if override is not None else None


def register_override(slug: str, strategy_json: dict[str, Any]) -> None:
    """Register a hand-written override for ``slug``. Replaces any
    existing entry. Used by future seed-loader integration tests.
    """
    _OVERRIDES[slug] = dict(strategy_json)


def clear_overrides() -> None:
    """Reset the registry. Test fixture helper."""
    _OVERRIDES.clear()


def list_overrides() -> list[str]:
    """Return slugs with registered overrides — for diagnostic logs."""
    return sorted(_OVERRIDES.keys())


__all__ = [
    "clear_overrides",
    "get_override",
    "list_overrides",
    "register_override",
]

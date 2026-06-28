"""Regression tests for ``resolve_instrument_type`` — the instrument-router
classifier (first brick; NOT yet wired into execution).

SAFETY INVARIANT (the reason this test exists):
    Any strategy with no clear instrument marker MUST resolve to "futures" so
    the live real-money strategies BSE/CDSL/ANGELONE — which have
    ``strategy_json IS NULL`` — are never routed off the futures path.

Uses lightweight ``SimpleNamespace`` stand-ins for ``Strategy`` (the classifier
duck-types via ``getattr``), so these tests need no database.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.strategy_engine.instrument_router import resolve_instrument_type

# Sentinel so a stand-in can omit the ``instrument_type`` attribute entirely
# (the live Strategy ORM has no such column → ``getattr`` returns None).
_UNSET = object()


def _strategy(strategy_json: object, instrument_type: object = _UNSET) -> SimpleNamespace:
    """Build a Strategy stand-in. ``instrument_type`` attr omitted unless given."""
    ns = SimpleNamespace(strategy_json=strategy_json)
    if instrument_type is not _UNSET:
        ns.instrument_type = instrument_type
    return ns


@pytest.mark.parametrize(
    "strategy_json, expected",
    [
        # ── THE critical invariant: live BSE/CDSL/ANGELONE have strategy_json IS NULL ──
        (None, "futures"),
        # Empty / ambiguous → safe default.
        ({}, "futures"),
        # Explicit markers (first-match-wins).
        ({"instrument_type": "cash"}, "cash"),
        ({"instrument_type": "options"}, "options"),
        ({"instrument_type": "futures"}, "futures"),
        # Options config block, no explicit marker → options (mirrors is_options_strategy).
        ({"options": {"option_type": "auto", "expiry": "current_week"}}, "options"),
        # Unknown marker → safe default (never error, never off-futures).
        ({"instrument_type": "garbage"}, "futures"),
        # Case-insensitive.
        ({"instrument_type": "CASH"}, "cash"),
        # Whitespace-tolerant.
        ({"instrument_type": "  options  "}, "options"),
        # Defensive: non-dict strategy_json must not crash → futures.
        ("not-a-dict", "futures"),
        (123, "futures"),
        # Defensive: instrument_type present but non-string → ignore → futures.
        ({"instrument_type": 42}, "futures"),
        # Both marker + options block: explicit marker wins.
        ({"instrument_type": "cash", "options": {"option_type": "auto"}}, "cash"),
    ],
)
def test_resolve_from_strategy_json(strategy_json: object, expected: str) -> None:
    assert resolve_instrument_type(_strategy(strategy_json)) == expected


def test_strategy_none_returns_futures() -> None:
    # A None strategy must never route off futures.
    assert resolve_instrument_type(None) == "futures"


def test_live_strategy_json_null_resolves_futures() -> None:
    # THE safety invariant, named explicitly: BSE/CDSL/ANGELONE (strategy_json
    # IS NULL) MUST classify as "futures" so they stay on the live path.
    assert resolve_instrument_type(_strategy(None)) == "futures"


def test_forward_compat_top_level_attribute() -> None:
    # Forward-compat: a top-level instrument_type attribute (a future migration
    # may add the column) is honoured the same way as the strategy_json marker.
    assert resolve_instrument_type(_strategy(None, instrument_type="cash")) == "cash"
    assert resolve_instrument_type(_strategy(None, instrument_type="options")) == "options"
    assert resolve_instrument_type(_strategy(None, instrument_type="futures")) == "futures"


def test_forward_compat_unknown_attribute_falls_back_to_futures() -> None:
    # An unknown / empty top-level marker must fall through to the futures
    # default — not error, not route off futures.
    assert resolve_instrument_type(_strategy(None, instrument_type="garbage")) == "futures"
    assert resolve_instrument_type(_strategy(None, instrument_type="")) == "futures"
    assert resolve_instrument_type(_strategy(None, instrument_type=None)) == "futures"


def test_forward_compat_attribute_overrides_json_marker() -> None:
    # getattr is read first (mirrors is_options_strategy): a recognised
    # top-level marker wins over the strategy_json marker.
    s = _strategy({"instrument_type": "futures"}, instrument_type="cash")
    assert resolve_instrument_type(s) == "cash"

"""``instrument_type`` on a listing — a FACT about the strategy.

Segment is a property OF THE STRATEGY, never a customer choice. The signal names
one instrument, and the platform cannot honestly translate a futures signal into
a cash or options order: wrong price basis (futures trade at a basis to spot),
no share-quantity path (everything is lots x lot_size), cash cannot be shorted
at all (so a cash subscriber would silently lose the short third of the system),
and every certified number we publish is futures-basis.

So this field is DISPLAY + FILTER only. It rides ``strategy_json`` — no
migration — and an undeclared or unrecognised value yields None, because
defaulting to "futures" would print a guess as a fact on a public listing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.strategy_engine.api.marketplace import _instrument_type_of

APP = Path(__file__).resolve().parents[2] / "app"


@pytest.mark.parametrize(
    ("strategy_json", "expected"),
    [
        ({"instrument_type": "futures"}, "futures"),
        ({"instrument_type": "cash"}, "cash"),
        ({"instrument_type": "options"}, "options"),
        ({"instrument_type": "FUTURES"}, "futures"),      # normalised
        ({"instrument_type": "  Futures  "}, "futures"),
    ],
)
def test_declared_types_are_read(strategy_json, expected):
    assert _instrument_type_of(strategy_json) == expected


@pytest.mark.parametrize(
    "strategy_json",
    [
        None,                              # no json at all
        {},                                # json without the key
        {"instrument_type": None},
        {"instrument_type": 7},            # not a string
        {"instrument_type": "equity"},     # not one of ours
        {"instrument_type": ""},
        "not-a-dict",
        {"options": {"option_type": "CE"}},  # an options CONFIG is not a declaration
    ],
)
def test_undeclared_or_unrecognised_is_none_never_a_guess(strategy_json):
    """A typo must not become a confident claim on a public listing."""
    assert _instrument_type_of(strategy_json) is None


def test_it_never_defaults_to_futures():
    """The tempting default is the dangerous one: most strategies ARE futures,
    so defaulting would look right almost always and be a lie exactly when it
    mattered."""
    assert _instrument_type_of({}) is None
    assert _instrument_type_of({"instrument_type": "unknown"}) is None


def test_listing_read_exposes_it_as_optional():
    from app.strategy_engine.api.marketplace import ListingRead

    field = ListingRead.model_fields["instrument_type"]
    assert field.default is None, "must be optional — existing consumers unaffected"


def test_the_lookup_reads_only_strategy_json_never_the_name():
    """The marketplace mask depends on the strategy's NAME never leaving the
    server ('BSE LTD Futures'). This lookup must select strategy_json only."""
    src = (APP / "strategy_engine" / "api" / "marketplace.py").read_text(encoding="utf-8")
    for fn in ("_instrument_types_for_listings", "_strategy_json_for"):
        start = src.index(f"async def {fn}(")
        body = src[start : src.index("\n\n\n", start)]
        assert "Strategy.name" not in body, f"{fn} selects the strategy name"
        assert "Strategy.strategy_json" in body


def test_no_migration_was_added():
    """It rides strategy_json — the same column the options config uses."""
    versions = (APP.parent / "migrations" / "versions")
    latest = sorted(p.name for p in versions.glob("0*.py"))[-1]
    assert latest.startswith("041_"), (
        f"latest migration is {latest} — this feature must not add one"
    )

"""End-to-end shape tests for the strategy_templates_seed.json file.

These are content-asserting tests — they confirm the catalog matches
the Phase 1 product spec at the file level, separate from the
validator's structural rules.

Three buckets the spec requires:
    * 15 active equity templates with full config_json
    * 35 inactive equity entries with empty config_json={}
    * 63 inactive options entries with requires_options_builder=true
      and empty config_json={}

Total catalog size: 113. Any drift in the seed file triggers a CI
failure with a clear diagnostic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def seed_data() -> dict:
    seed = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "strategy_templates_seed.json"
    )
    return json.loads(seed.read_text(encoding="utf-8"))


def test_top_level_keys(seed_data: dict) -> None:
    assert "templates" in seed_data
    assert "_meta" in seed_data


def test_total_count_is_113(seed_data: dict) -> None:
    assert len(seed_data["templates"]) == 113


def test_active_count_is_15(seed_data: dict) -> None:
    active = [t for t in seed_data["templates"] if t.get("is_active")]
    assert len(active) == 15


def test_active_are_all_equity(seed_data: dict) -> None:
    active = [t for t in seed_data["templates"] if t.get("is_active")]
    non_equity = [t for t in active if t["segment"] != "EQUITY"]
    assert (
        not non_equity
    ), f"Phase 1 active templates must be EQUITY only; found: {non_equity}"


def test_options_count_is_63(seed_data: dict) -> None:
    options = [
        t
        for t in seed_data["templates"]
        if t.get("requires_options_builder")
    ]
    assert len(options) == 63


def test_options_segment_check(seed_data: dict) -> None:
    """Every requires_options_builder row must have segment=OPTIONS."""
    options = [
        t
        for t in seed_data["templates"]
        if t.get("requires_options_builder")
    ]
    bad = [t["slug"] for t in options if t["segment"] != "OPTIONS"]
    assert not bad, f"Options templates with wrong segment: {bad}"


def test_options_are_all_inactive(seed_data: dict) -> None:
    """Phase 1 ships zero active options templates."""
    options = [
        t
        for t in seed_data["templates"]
        if t.get("requires_options_builder")
    ]
    active = [t["slug"] for t in options if t.get("is_active")]
    assert not active, f"Active options templates in Phase 1 (should be none): {active}"


def test_inactive_equity_count_is_35(seed_data: dict) -> None:
    inactive_equity = [
        t
        for t in seed_data["templates"]
        if not t.get("is_active") and not t.get("requires_options_builder")
    ]
    assert len(inactive_equity) == 35


def test_inactive_entries_have_empty_config_json(seed_data: dict) -> None:
    for t in seed_data["templates"]:
        if not t.get("is_active"):
            assert t.get("config_json", {}) == {}, (
                f"Inactive {t['slug']} must have empty config_json={{}}; "
                f"got {t['config_json']!r}"
            )


def test_active_entries_have_non_empty_config_json(seed_data: dict) -> None:
    for t in seed_data["templates"]:
        if t.get("is_active"):
            assert (
                t.get("config_json", {}) != {}
            ), f"Active {t['slug']} must have populated config_json"


def test_all_slugs_unique(seed_data: dict) -> None:
    slugs = [t["slug"] for t in seed_data["templates"]]
    dups = [s for s in set(slugs) if slugs.count(s) > 1]
    assert not dups, f"Duplicate slugs: {dups}"


def test_all_slugs_are_kebab_case(seed_data: dict) -> None:
    """Slugs must be lowercase kebab — URL-safe, predictable."""
    import re

    pattern = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    bad = [
        t["slug"]
        for t in seed_data["templates"]
        if not pattern.match(t["slug"])
    ]
    assert not bad, f"Non-kebab slugs: {bad}"


def test_active_template_slugs_match_spec(seed_data: dict) -> None:
    """The 15 explicit slugs from the Phase 1 spec must all be active."""
    expected_active_slugs = {
        "ema-crossover-9-21",
        "ema-crossover-20-50",
        "macd-trend-signal",
        "supertrend-rider",
        "rsi-oversold-bounce",
        "bb-mean-reversion",
        "bb-squeeze-breakout",
        "orb-15min",
        "pdh-pdl-breakout",
        "vwap-bounce",
        "macd-histogram-momentum",
        "banknifty-weekly-equity",
        "premarket-gap",
        "rsi-macd-confluence",
        "bb-rsi-oversold",
    }
    actual_active = {
        t["slug"] for t in seed_data["templates"] if t.get("is_active")
    }
    assert actual_active == expected_active_slugs, (
        f"Active slug set drifted from spec. "
        f"Missing: {expected_active_slugs - actual_active}. "
        f"Extra: {actual_active - expected_active_slugs}."
    )

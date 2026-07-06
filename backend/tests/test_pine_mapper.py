"""Pine Script v4.8.1 → TRADETRI payload mapper unit tests.

Covers the eight (action, type) combinations the production strategy
emits, the score-extraction path through ``compute_score``, the symbol
and price fallbacks when Pine omits them, and a passthrough sanity
check that native TRADETRI payloads are not mistaken for Pine.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.ai_validator import compute_score
from app.services.pine_mapper import (
    PineMappingError,
    is_pine_payload,
    map_to_tradetri_payload,
)

# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────


_PINE_INDICATORS_FULL: dict[str, float] = {
    "PriceSpd": 5.2,
    "RSI": 62,
    "GaussL": 745,
    "GaussS": 750,
    "DeltaPwr": 12.5,
    "OFInten": 1.8,
    "VWAPDist": 0.85,
    "FastMA": 745,
    "SlowMA": 743,
    "LongMA": 736,
    "ATR": 5.5,
    "RVOL": 1.7,
    "BodyPct": 68,
    "Squeeze": 5.8,
    "BearGap": 110,
    "BullGap": 185,
    "IndiaVIX": 14.2,
    "Vol": 350000,
}


def _pine_long_entry(**overrides: Any) -> dict[str, Any]:
    """Production-shaped LONG_ENTRY Pine payload, with optional overrides."""
    payload: dict[str, Any] = {
        "action": "ENTRY",
        "type": "LONG_ENTRY",
        "qty": 4,
        "useDhan": True,
        "symbol": "NIFTY24500CE",
        "price": 250.0,
        "indicators": dict(_PINE_INDICATORS_FULL),
    }
    payload.update(overrides)
    return payload


def _strategy(allowed: list[str] | None = None) -> Any:
    """Lightweight Strategy stub — only ``allowed_symbols`` is read."""
    return SimpleNamespace(allowed_symbols=allowed or [])


# ───────────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────────


def test_pine_long_entry_maps_to_buy_with_correct_score() -> None:
    payload = _pine_long_entry()
    mapped = map_to_tradetri_payload(payload, _strategy())

    # Post direct-exit refactor (Sun 2026-05-03), Pine maps to canonical
    # ENTRY/PARTIAL/EXIT/SL_HIT vocabulary; side carried separately.
    assert mapped["action"] == "ENTRY"
    assert mapped["side"] == "long"
    assert mapped["quantity"] == 4
    assert mapped["symbol"] == "NIFTY24500CE"
    assert mapped["price"] == 250.0
    assert mapped["use_dhan"] is True
    assert mapped["pine_type"] == "LONG_ENTRY"
    assert mapped["_source"] == "pine_v4.8.1"
    # Score is on the bot's 0-100 scale; LONG indicators in this fixture
    # earn well above the 30-baseline, but we don't pin to an exact
    # number because the underlying weights can shift over time.
    assert 30.0 < mapped["score"] <= 100.0
    # No inbound score in the fixture → server-side compute_score path.
    assert mapped["score_source"] == "computed"


def test_pine_short_entry_maps_to_sell() -> None:
    payload = _pine_long_entry(type="SHORT_ENTRY")
    mapped = map_to_tradetri_payload(payload, _strategy())

    assert mapped["action"] == "ENTRY"
    assert mapped["side"] == "short"
    assert mapped["pine_type"] == "SHORT_ENTRY"


@pytest.mark.parametrize(
    ("pine_type", "expected_side"),
    [
        ("LONG_PARTIAL", "long"),
        ("SHORT_PARTIAL", "short"),
    ],
)
def test_pine_partial_maps_correctly(
    pine_type: str, expected_side: str
) -> None:
    payload = _pine_long_entry(action="PARTIAL", type=pine_type)
    mapped = map_to_tradetri_payload(payload, _strategy())
    # Action is the canonical PARTIAL; side disambiguates LONG vs SHORT.
    assert mapped["action"] == "PARTIAL"
    assert mapped["side"] == expected_side


@pytest.mark.parametrize(
    ("pine_type", "expected_side"),
    [("LONG_SL", "long"), ("SHORT_SL", "short")],
)
def test_pine_sl_maps_to_sl_hit(pine_type: str, expected_side: str) -> None:
    payload = _pine_long_entry(action="EXIT", type=pine_type)
    mapped = map_to_tradetri_payload(payload, _strategy())
    assert mapped["action"] == "SL_HIT"
    assert mapped["side"] == expected_side


@pytest.mark.parametrize(
    ("pine_type", "expected_side"),
    [("LONG_EXIT", "long"), ("SHORT_EXIT", "short")],
)
def test_pine_exit_maps_to_exit(pine_type: str, expected_side: str) -> None:
    payload = _pine_long_entry(action="EXIT", type=pine_type)
    mapped = map_to_tradetri_payload(payload, _strategy())
    assert mapped["action"] == "EXIT"
    assert mapped["side"] == expected_side


def test_pine_score_extraction_from_17_indicators() -> None:
    """Score must come from compute_score over the full indicator dict.

    A degraded indicator dict (one strong key absent / weak) must score
    strictly lower than the production-shape full dict — proves the
    mapper actually feeds the indicators in, not just defaults.
    """
    full = map_to_tradetri_payload(_pine_long_entry(), _strategy())
    weak_indicators = dict(_PINE_INDICATORS_FULL)
    # Knock out indicators that contribute heavily to the LONG score.
    for k in ("PriceSpd", "RSI", "GaussL", "GaussS", "BullGap", "Vol"):
        weak_indicators[k] = 0
    weak = map_to_tradetri_payload(
        _pine_long_entry(indicators=weak_indicators), _strategy()
    )
    assert full["score"] > weak["score"]
    assert weak["score"] >= 30.0  # baseline floor from compute_score
    assert full["score_source"] == "computed"
    assert weak["score_source"] == "computed"


def test_inbound_score_wins_over_computed() -> None:
    """Alert-supplied score passes through verbatim, beating compute_score.

    The full fixture computes well above 76.7, so an exact 76.7 result
    proves the inbound value won.
    """
    baseline = map_to_tradetri_payload(_pine_long_entry(), _strategy())
    mapped = map_to_tradetri_payload(_pine_long_entry(score=76.7), _strategy())
    assert mapped["score"] == 76.7
    assert mapped["score_source"] == "pine"
    assert baseline["score"] != 76.7  # computed path really differs


def test_absent_score_computes_identically_to_before() -> None:
    """Core invariant: no inbound score → byte-identical mapper output to
    the pre-passthrough behaviour, except the new score_source tag."""
    payload = _pine_long_entry()
    assert "score" not in payload
    mapped = map_to_tradetri_payload(payload, _strategy())
    assert mapped["score"] == compute_score(_PINE_INDICATORS_FULL, "LONG")
    assert mapped["score_source"] == "computed"


def test_inbound_score_zero_passes_through() -> None:
    # 0.0 is a VALID inbound score (gate rejects it downstream) — a
    # truthiness bug here would silently recompute.
    mapped = map_to_tradetri_payload(_pine_long_entry(score=0.0), _strategy())
    assert mapped["score"] == 0.0
    assert mapped["score_source"] == "pine"


def test_inbound_score_hundred_passes_through() -> None:
    mapped = map_to_tradetri_payload(_pine_long_entry(score=100.0), _strategy())
    assert mapped["score"] == 100.0
    assert mapped["score_source"] == "pine"


@pytest.mark.parametrize("garbage", ["abc", True, 101, -5, None, ""])
def test_invalid_inbound_score_falls_back_to_computed(garbage: Any) -> None:
    baseline = map_to_tradetri_payload(_pine_long_entry(), _strategy())
    mapped = map_to_tradetri_payload(
        _pine_long_entry(score=garbage), _strategy()
    )
    assert mapped["score"] == baseline["score"]
    assert mapped["score_source"] == "computed"


def test_inbound_score_passthrough_is_side_agnostic() -> None:
    mapped = map_to_tradetri_payload(
        _pine_long_entry(type="SHORT_ENTRY", score=64.2), _strategy()
    )
    assert mapped["side"] == "short"
    assert mapped["score"] == 64.2
    assert mapped["score_source"] == "pine"


def test_pine_missing_symbol_uses_strategy_default() -> None:
    payload = _pine_long_entry()
    payload.pop("symbol")
    strategy = _strategy(allowed=["NIFTY-FUT", "BANKNIFTY-FUT"])

    mapped = map_to_tradetri_payload(payload, strategy)
    assert mapped["symbol"] == "NIFTY-FUT"


def test_pine_missing_price_uses_longma_indicator() -> None:
    payload = _pine_long_entry()
    payload.pop("price")
    mapped = map_to_tradetri_payload(payload, _strategy())
    # LongMA in the fixture is 736 — that's what we must fall back to.
    assert mapped["price"] == 736.0

    # And if LongMA is missing too, SlowMA wins.
    indicators_no_longma = dict(_PINE_INDICATORS_FULL)
    indicators_no_longma.pop("LongMA")
    payload2 = _pine_long_entry(indicators=indicators_no_longma)
    payload2.pop("price")
    mapped2 = map_to_tradetri_payload(payload2, _strategy())
    assert mapped2["price"] == 743.0


def test_native_tradetri_payload_passthrough_unchanged() -> None:
    """Native payloads must NOT be detected as Pine and the mapper must
    refuse to translate them — proving the webhook's `if is_pine_payload`
    branch leaves native bodies alone."""
    native = {
        "symbol": "NIFTY24500CE",
        "action": "BUY",
        "quantity": 4,
        "score": 65,
        "price": 250.0,
        "order_type": "market",
        "timestamp": "2026-04-30T18:30:00+05:30",
    }
    assert is_pine_payload(native) is False
    with pytest.raises(PineMappingError):
        map_to_tradetri_payload(native, _strategy())

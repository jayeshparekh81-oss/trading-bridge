"""Monthly option legs — the format Dhan actually returns on the live account.

WHY THIS FILE EXISTS. ``_OPTION`` only matched the DAY-STAMPED (weekly) form,
``BSE-16JUL2026-2400-CE``. Dhan returns monthly legs as ``BSE-Aug2026-3200-CE``
— no day stamp — and those went unparsed. That was not cosmetic: an unparsed
sibling row poisons ``total_matching_quantity`` to UNKNOWN, and UNKNOWN is never
drift, so every pass on an account carrying monthly options returned "cannot
tell". Drift protection was inert exactly where it was needed.

The spellings below are the real ones read off the account's pre-open position
dump, not invented examples.

The fail-safe direction is unchanged and is re-asserted here: a format we still
do not understand is UNKNOWN, never "flat".
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.symbol_match import (
    find_matching_position,
    normalize_symbol,
    symbols_match,
    total_matching_quantity,
)

FUT = "BSE-AUG2026-FUT"

#: Verbatim from the account's pre-open dump.
REAL_LEGS = [
    "BSE-Aug2026-3200-CE",
    "BSE-Aug2026-3300-CE",
    "BSE-Sep2026-3400-PE",
]


@dataclass
class Pos:
    symbol: str
    quantity: int


# ═══════════════════════════════════════════════════════════════════════
# 1. The real spellings parse
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("raw", "kind", "year", "month", "strike"),
    [
        ("BSE-Aug2026-3200-CE", "CE", 2026, 8, "3200"),
        ("BSE-Aug2026-3300-CE", "CE", 2026, 8, "3300"),
        ("BSE-Sep2026-3400-PE", "PE", 2026, 9, "3400"),
        ("NSE:BSE-SEP2026-3400-PE", "PE", 2026, 9, "3400"),  # exchange prefix
        ("bse-sep2026-3400-pe", "PE", 2026, 9, "3400"),      # lowercase input
    ],
)
def test_the_real_monthly_spellings_parse(raw, kind, year, month, strike):
    got = normalize_symbol(raw)
    assert got is not None, f"{raw} still unparsed"
    assert (got.root, got.kind, got.year, got.month, got.strike) == (
        "BSE", kind, year, month, strike,
    )
    assert got.day is None, "a monthly leg has no day stamp"


def test_the_day_stamped_form_still_parses():
    """The weekly form must not regress — both shapes coexist."""
    got = normalize_symbol("BSE-16JUL2026-2400-CE")
    assert got is not None
    assert (got.kind, got.day, got.month, got.year, got.strike) == (
        "CE", 16, 7, 2026, "2400",
    )


@pytest.mark.parametrize(
    "raw", ["BSE-AUG2026-3200.0-CE", "BSE-AUG2026-3200.00-CE", "BSE-AUG2026-3200-CE"]
)
def test_strike_spellings_normalise_to_one_identity(raw):
    """Two rows in the same contract must compare EQUAL, or the aggregate would
    count them as different instruments and under-report the holding."""
    assert normalize_symbol(raw).strike == "3200"
    assert symbols_match("BSE-AUG2026-3200-CE", raw) is True


# ═══════════════════════════════════════════════════════════════════════
# 2. 🔴 An option must never satisfy a futures position
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("leg", REAL_LEGS)
def test_an_option_never_matches_the_futures(leg):
    """Same underlying, same month, still a different instrument. If an option
    satisfied the futures, a closed futures leg would look open and the customer
    would keep auto-trading a position they no longer hold."""
    assert symbols_match(FUT, leg) is False


def test_a_call_never_matches_a_put_at_the_same_strike():
    assert symbols_match("BSE-AUG2026-3200-CE", "BSE-AUG2026-3200-PE") is False


def test_different_strikes_never_match():
    assert symbols_match("BSE-AUG2026-3200-CE", "BSE-AUG2026-3300-CE") is False


def test_a_monthly_leg_never_matches_a_weekly_leg():
    """Different expiries in the same month are different contracts; the day
    stamp is part of the identity key."""
    assert symbols_match("BSE-AUG2026-3200-CE", "BSE-16AUG2026-3200-CE") is False


# ═══════════════════════════════════════════════════════════════════════
# 3. The effect that matters: his account is no longer poisoned
# ═══════════════════════════════════════════════════════════════════════


def test_his_real_shape_now_resolves_confidently():
    """Option legs + the bot's futures. Previously (None, False) — UNKNOWN, so
    the pass could never reach a verdict on his account."""
    rows = [Pos(s, -400) for s in REAL_LEGS] + [Pos(FUT, 400)]
    assert total_matching_quantity(FUT, rows) == (400, True)


def test_options_only_is_now_a_confident_zero():
    """The bot's futures genuinely closed, only his options left. A real 0 is a
    DETECTABLE close; UNKNOWN was not."""
    rows = [Pos(s, -400) for s in REAL_LEGS]
    assert total_matching_quantity(FUT, rows) == (0, True)


def test_split_rows_are_still_summed_with_options_present():
    rows = [Pos(s, -400) for s in REAL_LEGS] + [Pos(FUT, 200), Pos(FUT, 800)]
    assert total_matching_quantity(FUT, rows) == (1000, True)


def test_find_matching_position_still_finds_the_futures():
    """The fan-out's presence gate is unaffected."""
    rows = [Pos(s, -400) for s in REAL_LEGS] + [Pos(FUT, 400)]
    match, certain = find_matching_position(FUT, rows)
    assert certain is True
    assert match is not None and match.symbol == FUT


# ═══════════════════════════════════════════════════════════════════════
# 4. 🔴 The fail-safe direction is UNCHANGED
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "raw",
    [
        "SOME-WEIRD-MANUAL-LEG",
        "BSE-XYZ2026-3200-CE",     # month is nonsense
        "BSE-AUG2026-3200-XX",     # not CE/PE
        "BSE-AUG20267-3200-CE",    # malformed year
        "",
        None,
    ],
)
def test_still_unparseable_stays_unknown_never_flat(raw):
    """Parsing more formats must not become guessing at the rest."""
    assert normalize_symbol(raw) is None
    assert symbols_match(FUT, raw) is None


def test_one_unknown_leg_still_poisons_the_total_to_unknown():
    """An unreadable row could be another leg of the same contract, so the
    total is refused rather than under-reported."""
    rows = [Pos("SOME-WEIRD-MANUAL-LEG", 100), Pos(FUT, 400)]
    assert total_matching_quantity(FUT, rows) == (None, False)


def test_equities_ending_in_ce_are_not_mistaken_for_options():
    """RELIANCE ends in CE. The monthly-option pattern requires the full
    ROOT-MMMYYYY-STRIKE-CE shape, so a bare equity cannot drift into it."""
    got = normalize_symbol("RELIANCE")
    assert got is None or got.kind == "EQ"
    assert symbols_match(FUT, "RELIANCE") is not True

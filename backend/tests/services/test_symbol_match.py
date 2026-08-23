"""Symbol normalisation — real shapes from this codebase.

The safety property: an unparseable symbol yields UNKNOWN (``None``), never
"flat" and never "different". Reading a mismatch as flat would wrongly flip a
customer to MANUAL or skip a legitimate exit.

Shapes below are taken from actual fixtures/tests in this repo:
  canonical  BSE-AUG2026-FUT, NIFTY-MAY2026-FUT, BANKNIFTY-MAY2026-FUT
  compact    NIFTY24DECFUT, GOLD24DECFUT, SENSEX24DECFUT, USDINR24DECFUT
  options    BSE-16JUL2026-2400-CE, BSE-23JUL2026-2400-PE
  bad month  BSE-XYZ2026-FUT
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.symbol_match import (
    find_matching_position,
    normalize_symbol,
    symbols_match,
)


@dataclass
class FakePos:
    symbol: str


# ═══════════════════════════════════════════════════════════════════════
# Parsing the real shapes
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("raw", "root", "year", "month"),
    [
        ("BSE-AUG2026-FUT", "BSE", 2026, 8),
        ("NIFTY-MAY2026-FUT", "NIFTY", 2026, 5),
        ("BANKNIFTY-MAY2026-FUT", "BANKNIFTY", 2026, 5),
        ("CDSL-JUL2026-FUT", "CDSL", 2026, 7),
    ],
)
def test_canonical_future(raw, root, year, month):
    n = normalize_symbol(raw)
    assert n is not None
    assert (n.root, n.kind, n.year, n.month) == (root, "FUT", year, month)


@pytest.mark.parametrize(
    ("raw", "root", "year", "month"),
    [
        ("BSE26AUGFUT", "BSE", 2026, 8),
        ("NIFTY24DECFUT", "NIFTY", 2024, 12),
        ("NIFTY25JANFUT", "NIFTY", 2025, 1),
        ("GOLD24DECFUT", "GOLD", 2024, 12),
        ("SENSEX24DECFUT", "SENSEX", 2024, 12),
        ("USDINR24DECFUT", "USDINR", 2024, 12),
    ],
)
def test_compact_broker_future(raw, root, year, month):
    n = normalize_symbol(raw)
    assert n is not None
    assert (n.root, n.kind, n.year, n.month) == (root, "FUT", year, month)


@pytest.mark.parametrize(
    ("raw", "root", "kind", "day", "strike"),
    [
        ("BSE-16JUL2026-2400-CE", "BSE", "CE", 16, "2400"),
        ("BSE-23JUL2026-2400-PE", "BSE", "PE", 23, "2400"),
    ],
)
def test_option_leg(raw, root, kind, day, strike):
    n = normalize_symbol(raw)
    assert n is not None
    assert (n.root, n.kind, n.day, n.strike) == (root, kind, day, strike)


@pytest.mark.parametrize(
    ("raw", "root"),
    [
        ("BSE", "BSE"),
        ("NSE:RELIANCE", "RELIANCE"),
        ("RELIANCE-EQ", "RELIANCE"),
        # Real equities ending in CE/PE must NOT be mistaken for option legs.
        ("RELIANCE", "RELIANCE"),
        ("NSE:JUSTDIAL", "JUSTDIAL"),
        ("NIFTY50", "NIFTY50"),
    ],
)
def test_equity(raw, root):
    n = normalize_symbol(raw)
    assert n is not None
    assert (n.root, n.kind) == (root, "EQ")


def test_digit_bearing_ce_suffix_is_unknown_not_equity():
    """An unparsed compact option must be UNKNOWN, not silently 'equity'."""
    assert normalize_symbol("BSE24AUG2400CE") is None
    assert normalize_symbol("BSE24AUG2400PE") is None


# ═══════════════════════════════════════════════════════════════════════
# THE POINT — the two spellings must match
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("stored", "broker"),
    [
        ("BSE-AUG2026-FUT", "BSE26AUGFUT"),
        ("NIFTY-DEC2024-FUT", "NIFTY24DECFUT"),
        ("BSE-AUG2026-FUT", "bse26augfut"),        # case-insensitive
        ("BSE-AUG2026-FUT", "  BSE26AUGFUT  "),    # whitespace
        ("BSE-AUG2026-FUT", "NFO:BSE26AUGFUT"),    # exchange prefix
    ],
)
def test_canonical_matches_compact(stored, broker):
    assert symbols_match(stored, broker) is True


@pytest.mark.parametrize(
    ("stored", "broker"),
    [
        ("BSE-AUG2026-FUT", "BSE-JUL2026-FUT"),    # different month
        ("BSE-AUG2026-FUT", "BSE26SEPFUT"),        # different month, compact
        ("BSE-AUG2026-FUT", "CDSL26AUGFUT"),       # different root
        ("BSE-AUG2026-FUT", "BSE25AUGFUT"),        # different year
        ("BSE-16JUL2026-2400-CE", "BSE-16JUL2026-2400-PE"),   # CE vs PE
        ("BSE-16JUL2026-2400-CE", "BSE-16JUL2026-2500-CE"),   # strike
    ],
)
def test_genuinely_different_contracts(stored, broker):
    assert symbols_match(stored, broker) is False


def test_strike_spelling_is_normalised():
    assert symbols_match("BSE-16JUL2026-2400-CE", "BSE-16JUL2026-2400.00-CE") is True


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ SAFETY — unparseable must be UNKNOWN (None), never False
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "bad",
    [
        None, "", "   ",
        "BSE-XYZ2026-FUT",      # shape ok, month nonsense
        "BSE26XYZFUT",          # compact, month nonsense
        "???",
        "BSE-2026-FUT",         # missing month token
        "SOMETHINGFUT",         # ends FUT but no expiry — not understood
    ],
)
def test_unparseable_returns_none(bad):
    assert normalize_symbol(bad) is None


@pytest.mark.parametrize(
    ("stored", "broker"),
    [
        ("BSE-XYZ2026-FUT", "BSE26AUGFUT"),
        ("BSE-AUG2026-FUT", "BSE26XYZFUT"),
        ("BSE-AUG2026-FUT", None),
        (None, "BSE26AUGFUT"),
        ("???", "!!!"),
    ],
)
def test_unmatchable_is_none_not_false(stored, broker):
    """The critical distinction: 'cannot tell' != 'different'."""
    verdict = symbols_match(stored, broker)
    assert verdict is None
    assert verdict is not False


# ═══════════════════════════════════════════════════════════════════════
# find_matching_position — certainty flag drives POSITION_UNKNOWN
# ═══════════════════════════════════════════════════════════════════════


def test_finds_match_across_spellings():
    pos, certain = find_matching_position(
        "BSE-AUG2026-FUT", [FakePos("CDSL26AUGFUT"), FakePos("BSE26AUGFUT")]
    )
    assert certain is True
    assert pos is not None and pos.symbol == "BSE26AUGFUT"


def test_confidently_absent():
    pos, certain = find_matching_position(
        "BSE-AUG2026-FUT", [FakePos("CDSL26AUGFUT")]
    )
    assert (pos, certain) == (None, True)   # genuinely flat


def test_empty_broker_list_is_confidently_absent():
    assert find_matching_position("BSE-AUG2026-FUT", []) == (None, True)


def test_unparseable_broker_symbol_is_uncertain():
    """A garbled broker row must NOT be reported as 'flat'."""
    pos, certain = find_matching_position(
        "BSE-AUG2026-FUT", [FakePos("GARBAGE-!!!")]
    )
    assert pos is None
    assert certain is False       # → caller uses POSITION_UNKNOWN


def test_unparseable_stored_symbol_is_uncertain():
    pos, certain = find_matching_position("BSE-XYZ2026-FUT", [FakePos("BSE26AUGFUT")])
    assert pos is None
    assert certain is False


def test_match_wins_even_if_another_row_is_garbled():
    """A confident hit is still a hit, even beside an unparseable row."""
    pos, certain = find_matching_position(
        "BSE-AUG2026-FUT", [FakePos("BSE26AUGFUT"), FakePos("!!!")]
    )
    assert certain is True
    assert pos is not None

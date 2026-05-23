"""Scrip-master parser — options column retention.

Pins the behaviour added for Audit Critical #1: the Dhan scrip-master
parser must retain ``SEM_OPTION_TYPE`` / ``SEM_STRIKE_PRICE`` /
``SEM_EXPIRY_DATE`` for option rows, while leaving the existing
futures/equity lookup + lot path byte-for-byte unchanged.

All tests drive the real parser through ``load_from_text`` with inline
CSV — no HTTP round-trip, no DB, no Docker.

    pytest backend/tests/brokers/test_dhan_scrip_master.py -v
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.brokers import dhan as dhan_mod
from app.brokers.dhan import ScripMeta, _parse_expiry, _parse_strike

# Shared CSV header — the column set Dhan ships in the compact master.
_HEADER = (
    "SEM_SMST_SECURITY_ID,SEM_TRADING_SYMBOL,SEM_EXM_EXCH_ID,SEM_SEGMENT,"
    "SEM_INSTRUMENT_NAME,SEM_LOT_UNITS,SEM_OPTION_TYPE,SEM_STRIKE_PRICE,"
    "SEM_EXPIRY_DATE\n"
)

# A representative slice: NIFTY weekly CE + PE options, a stock future
# (the live BSE LTD shape), and a cash equity. Futures/equity carry an
# empty option type — the canonical "not an option" marker.
_CE_ROW = "44321,NIFTY-May2026-25000-CE,NSE,D,OPTIDX,75.0,CE,25000.000000,2026-05-28\n"
_PE_ROW = "44322,NIFTY-May2026-25000-PE,NSE,D,OPTIDX,75.0,PE,25000.000000,2026-05-28\n"
_FUT_ROW = "66109,BSE-May2026-FUT,NSE,D,FUTSTK,375.0,,0.000000,2026-05-28\n"
_EQ_ROW = "11536,RELIANCE,NSE,E,EQUITY,1.0,,,\n"


@pytest.fixture(autouse=True)
def _fresh_scrip_master() -> None:
    """Reset the module-level scrip-master cache between tests."""
    sm = dhan_mod._SCRIP_MASTER
    sm._by_symbol.clear()
    sm._by_id.clear()
    sm._lot_sizes.clear()
    sm._meta.clear()
    sm._loaded_at = None


def _load(*rows: str) -> dhan_mod._ScripMaster:
    """Parse ``_HEADER`` + ``rows`` and return the shared cache."""
    dhan_mod._SCRIP_MASTER.load_from_text(_HEADER + "".join(rows))
    return dhan_mod._SCRIP_MASTER


# ═══════════════════════════════════════════════════════════════════════
# Option rows — the new behaviour
# ═══════════════════════════════════════════════════════════════════════


class TestOptionRowParsing:
    def test_ce_option_row_retains_triplet(self) -> None:
        sm = _load(_CE_ROW)
        m = sm.meta("44321")
        assert m is not None
        assert m.option_type == "CE"
        assert m.strike_price == Decimal("25000")
        assert m.expiry_date == date(2026, 5, 28)
        # And it's still resolvable as a normal symbol → securityId.
        assert sm.lookup("NIFTY-MAY2026-25000-CE", "NSE_FNO") == "44321"

    def test_pe_option_row_retains_triplet(self) -> None:
        sm = _load(_PE_ROW)
        m = sm.meta("44322")
        assert m is not None
        assert m.option_type == "PE"
        assert m.strike_price == Decimal("25000")
        assert m.expiry_date == date(2026, 5, 28)

    def test_option_type_lowercase_is_normalised(self) -> None:
        """Dhan emits upper-case, but the parser upper-cases defensively."""
        sm = _load(
            "44323,NIFTY-May2026-25100-CE,NSE,D,OPTIDX,75.0,ce,25100.000000,2026-05-28\n"
        )
        assert sm.is_option_symbol("44323")
        assert sm.meta("44323").option_type == "CE"  # type: ignore[union-attr]

    def test_invalid_option_type_collapses_to_none(self) -> None:
        """``XX`` (and any non-CE/PE token) is not an option."""
        sm = _load(
            "44324,JUNK,NSE,D,OPTIDX,75.0,XX,25000.000000,2026-05-28\n"
        )
        m = sm.meta("44324")
        assert m is not None
        assert m.option_type is None
        # Triplet is gated on a valid option type → strike/expiry dropped too.
        assert m.strike_price is None
        assert m.expiry_date is None
        assert sm.is_option_symbol("44324") is False

    def test_option_row_with_malformed_expiry_keeps_option(self) -> None:
        """A bad date never aborts the row — option stays, expiry is None."""
        sm = _load(
            "44325,NIFTY-May2026-25000-CE,NSE,D,OPTIDX,75.0,CE,25000.000000,not-a-date\n"
        )
        m = sm.meta("44325")
        assert m is not None
        assert m.option_type == "CE"
        assert m.strike_price == Decimal("25000")
        assert m.expiry_date is None


# ═══════════════════════════════════════════════════════════════════════
# Futures / equity — regression: nothing about them changes
# ═══════════════════════════════════════════════════════════════════════


class TestFuturesRegression:
    def test_future_row_has_no_option_triplet(self) -> None:
        sm = _load(_FUT_ROW)
        m = sm.meta("66109")
        assert m is not None
        assert m.option_type is None
        assert m.strike_price is None
        # Futures DO carry an expiry in the CSV, but we deliberately do not
        # store it here — futures rollover is symbol-driven elsewhere.
        assert m.expiry_date is None

    def test_future_lookup_and_lot_size_unchanged(self) -> None:
        """The pre-existing futures path must be byte-for-byte intact."""
        sm = _load(_FUT_ROW)
        assert sm.lookup("BSE-MAY2026-FUT", "NSE_FNO") == "66109"
        assert sm.lookup("BSE-MAY2026-FUT", "NSE_EQ") is None
        assert sm.lot_size("66109") == 375

    def test_equity_row_is_neither_option_nor_future(self) -> None:
        sm = _load(_EQ_ROW)
        m = sm.meta("11536")
        assert m is not None
        assert m.option_type is None
        assert m.strike_price is None
        assert m.expiry_date is None
        assert sm.is_option_symbol("11536") is False
        assert sm.is_future_symbol("11536") is False

    def test_mixed_master_keeps_each_kind_separate(self) -> None:
        """CE + PE + FUT + EQ in one file all coexist correctly."""
        sm = _load(_CE_ROW, _PE_ROW, _FUT_ROW, _EQ_ROW)
        assert sm.is_option_symbol("44321") is True
        assert sm.is_option_symbol("44322") is True
        assert sm.is_future_symbol("66109") is True
        assert sm.is_option_symbol("66109") is False
        assert sm.is_future_symbol("44321") is False
        # Lookups for every kind still resolve.
        assert sm.lookup("RELIANCE", "NSE_EQ") == "11536"
        assert sm.lookup("BSE-MAY2026-FUT", "NSE_FNO") == "66109"
        assert sm.lot_size("66109") == 375


# ═══════════════════════════════════════════════════════════════════════
# Strike + expiry value parsing
# ═══════════════════════════════════════════════════════════════════════


class TestStrikeParsing:
    def test_strike_is_decimal_not_float(self) -> None:
        sm = _load(_CE_ROW)
        strike = sm.meta("44321").strike_price  # type: ignore[union-attr]
        assert isinstance(strike, Decimal)
        assert strike == Decimal("25000")

    def test_fractional_strike_preserved(self) -> None:
        sm = _load(
            "55001,STOCKOPT-2487.5-CE,NSE,D,OPTSTK,1000.0,CE,2487.500000,2026-05-28\n"
        )
        assert sm.meta("55001").strike_price == Decimal("2487.5")  # type: ignore[union-attr]

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("25000.000000", Decimal("25000")),
            ("2487.500000", Decimal("2487.5")),
            ("0.000000", None),  # futures-style zero strike → None
            ("0", None),
            ("", None),  # absent
            ("garbage", None),  # unparseable → None, never raises
        ],
    )
    def test_parse_strike_helper(self, raw: str, expected: Decimal | None) -> None:
        assert _parse_strike(raw) == expected


class TestExpiryParsing:
    def test_iso_date_parsed_end_to_end(self) -> None:
        sm = _load(_CE_ROW)
        assert sm.meta("44321").expiry_date == date(2026, 5, 28)  # type: ignore[union-attr]

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2026-05-28", date(2026, 5, 28)),  # compact master
            ("2026-05-28 14:30:00", date(2026, 5, 28)),  # detailed master
            ("28-MAY-2026", date(2026, 5, 28)),  # legacy DD-MMM-YYYY
            ("28/05/2026", date(2026, 5, 28)),  # DD/MM/YYYY variant
            ("", None),  # absent
            ("not-a-date", None),  # unparseable → None, never raises
        ],
    )
    def test_parse_expiry_helper(self, raw: str, expected: date | None) -> None:
        assert _parse_expiry(raw) == expected


# ═══════════════════════════════════════════════════════════════════════
# Classification helpers
# ═══════════════════════════════════════════════════════════════════════


class TestClassificationHelpers:
    def test_unknown_security_id_classifies_as_neither(self) -> None:
        sm = _load(_CE_ROW)
        assert sm.meta("00000") is None
        assert sm.is_option_symbol("00000") is False
        assert sm.is_future_symbol("00000") is False

    def test_futidx_classified_as_future(self) -> None:
        sm = _load(
            "66071,NIFTY-May2026-FUT,NSE,D,FUTIDX,65.0,,0.000000,2026-05-28\n"
        )
        assert sm.is_future_symbol("66071") is True
        assert sm.is_option_symbol("66071") is False

    def test_scripmeta_is_immutable(self) -> None:
        """ScripMeta is frozen — callers cannot mutate cached metadata."""
        m = ScripMeta(
            security_id="1", symbol="X", segment="NSE_FNO", instrument="OPTIDX"
        )
        with pytest.raises((AttributeError, TypeError)):
            m.option_type = "CE"  # type: ignore[misc]

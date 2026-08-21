"""Parse-time scrip-master trim: option rows never enter memory.

WHY THE TRIM EXISTS. Measured against the live master (21 Aug 2026,
212,285 rows) option chains are 187,098 rows — 88.1% of the file — costing
~276 MB resident on a 3.8 GB box already 2.2 GB into swap. A cold
``resolve_or_passthrough`` on the ENTRY path took 9.2 s faulting those
pages back in, against 0.20 ms warm.

WHAT IS DELIBERATELY KEPT. Equity and futures. ``get_security_id`` is the
platform-wide symbol resolver (charts, indicator candles, any equity
strategy) and ``reverse()`` maps broker positions back to symbols, so a
filter narrowed to the three traded roots would break both. The cut is by
INSTRUMENT, not by root, precisely so those paths are untouched.

THE RULE THAT MATTERS. A symbol removed by the filter must FAIL LOUDLY.
``resolve_or_passthrough`` returns its input unchanged on any failure, so
a ``None`` from :meth:`lookup` would be handed to the broker as an
unresolved symbol. :class:`ScripMasterFilteredError` makes that
impossible, and :class:`TestRaiseIsLoadBearing` proves the raise is what
does the work by cutting it out of the real source and showing the shared
assertion then fails.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from _pytest.outcomes import Failed

from app.brokers import dhan as dhan_mod
from app.brokers.dhan import _EXCLUDED_INSTRUMENTS, ScripMasterFilteredError, _ScripMaster

_HEADER = (
    "SEM_SMST_SECURITY_ID,SEM_TRADING_SYMBOL,SEM_EXM_EXCH_ID,SEM_SEGMENT,"
    "SEM_INSTRUMENT_NAME,SEM_LOT_UNITS,SEM_OPTION_TYPE,SEM_STRIKE_PRICE,"
    "SEM_EXPIRY_DATE\n"
)

#: The three roots that actually trade, with the real security ids, lot
#: sizes and expiries read from the live master on 21 Aug 2026.
_LIVE_FUT_ROWS = (
    "58141,BSE-Aug2026-FUT,NSE,D,FUTSTK,200.0,,0.000000,2026-08-25\n"
    "68456,BSE-Sep2026-FUT,NSE,D,FUTSTK,200.0,,0.000000,2026-09-29\n"
    "58144,CDSL-Aug2026-FUT,NSE,D,FUTSTK,475.0,,0.000000,2026-08-25\n"
    "68459,CDSL-Sep2026-FUT,NSE,D,FUTSTK,475.0,,0.000000,2026-09-29\n"
    "58103,ANGELONE-Aug2026-FUT,NSE,D,FUTSTK,2500.0,,0.000000,2026-08-25\n"
    "68424,ANGELONE-Sep2026-FUT,NSE,D,FUTSTK,2500.0,,0.000000,2026-09-29\n"
)
#: The 88% that gets dropped — one row per excluded instrument.
_OPTION_ROWS = (
    "44321,NIFTY-Aug2026-25000-CE,NSE,D,OPTIDX,75.0,CE,25000.000000,2026-08-25\n"
    "44322,NIFTY-Aug2026-25000-PE,NSE,D,OPTIDX,75.0,PE,25000.000000,2026-08-25\n"
    "55001,BSE-Aug2026-2400-CE,NSE,D,OPTSTK,200.0,CE,2400.000000,2026-08-25\n"
    "77001,USDINR-Aug2026-88-CE,NSE,C,OPTCUR,1000.0,CE,88.000000,2026-08-25\n"
    "88001,CRUDEOIL-Aug2026-5000-CE,MCX,M,OPTFUT,100.0,CE,5000.000000,2026-08-25\n"
)
#: Kept — the paths a root-based filter would have broken.
_EQUITY_ROWS = (
    "11536,RELIANCE,NSE,E,EQUITY,1.0,,,\n"
    "19585,BSE,NSE,E,EQUITY,1.0,,,\n"
)
_ALL_ROWS = _LIVE_FUT_ROWS + _OPTION_ROWS + _EQUITY_ROWS


def _filtered() -> _ScripMaster:
    """A master parsed the way PRODUCTION parses — filter applied."""
    m = _ScripMaster()
    m.load_from_text(_HEADER + _ALL_ROWS, exclude=_EXCLUDED_INSTRUMENTS)
    return m


def _unfiltered() -> _ScripMaster:
    """A master parsed the way FIXTURES parse — no filter."""
    m = _ScripMaster()
    m.load_from_text(_HEADER + _ALL_ROWS)
    return m


# ═══════════════════════════════════════════════════════════════════════
# What the filter removes, and what it must not
# ═══════════════════════════════════════════════════════════════════════


class TestFilterShape:
    def test_option_rows_never_enter_memory(self) -> None:
        m = _filtered()
        assert m.filtered_rows == 5
        assert m._filtered_by_instrument == {
            "OPTIDX": 2,
            "OPTSTK": 1,
            "OPTCUR": 1,
            "OPTFUT": 1,
        }
        # Not merely absent from lookups — absent from every structure,
        # which is the difference between filtering and post-load pruning.
        for sid in ("44321", "44322", "55001", "77001", "88001"):
            assert m.reverse(sid) is None
            assert m.meta(sid) is None
            assert m.lot_size(sid) is None

    def test_futures_and_equity_survive(self) -> None:
        m = _filtered()
        assert len(m._by_symbol) == 8  # 6 futures + 2 equity
        # Equity is KEPT: get_security_id serves charts and any equity
        # strategy, and reverse() maps positions back to symbols.
        assert m.lookup("RELIANCE", "NSE_EQ") == "11536"
        assert m.reverse("11536") == ("RELIANCE", "NSE_EQ")

    def test_unfiltered_parse_is_unchanged(self) -> None:
        """The fixture path keeps every row — existing suites rely on it."""
        m = _unfiltered()
        assert m.filtered_rows == 0
        assert m._excluded == frozenset()
        assert m.lookup("NIFTY-AUG2026-25000-CE", "NSE_FNO") == "44321"
        assert m.is_option_symbol("44321") is True


# ═══════════════════════════════════════════════════════════════════════
# 🔴 The rule that matters: filtered out ⇒ raises, never passes through
# ═══════════════════════════════════════════════════════════════════════


def _assert_filtered_symbol_raises(master: _ScripMaster) -> None:
    """SHARED ASSERTION BODY — used by the real test and by its twin.

    A filtered-out option symbol must RAISE. Returning None is the
    failure mode being guarded: ``resolve_or_passthrough`` turns a failed
    resolve into the input symbol unchanged, which would send an
    unresolved option leg to the broker.
    """
    with pytest.raises(ScripMasterFilteredError) as exc:
        master.lookup("NIFTY-AUG2026-25000-CE", "NSE_FNO")
    assert "option leg" in str(exc.value)


class TestOutOfFilterSymbolRaises:
    def test_dashed_option_symbol_raises(self) -> None:
        _assert_filtered_symbol_raises(_filtered())

    def test_compact_option_symbol_raises(self) -> None:
        """The other Dhan shape — ``NIFTY24500CE``, no separator."""
        with pytest.raises(ScripMasterFilteredError):
            _filtered().lookup("NIFTY24500CE", "NSE_FNO")

    def test_unknown_non_option_still_returns_none(self) -> None:
        """A genuinely unlisted future is NOT the filter's doing.

        It must stay a clean miss so ``get_security_id`` raises its own
        BrokerInvalidSymbolError, unchanged from before the trim.
        """
        assert _filtered().lookup("WIPRO-AUG2026-FUT", "NSE_FNO") is None

    def test_equity_ending_in_ce_is_not_mistaken_for_an_option(self) -> None:
        """``_OPTION_SYMBOL_RE`` needs a strike DIGIT before CE/PE."""
        assert _filtered().lookup("ACE", "NSE_EQ") is None

    def test_unfiltered_master_never_raises(self) -> None:
        """No filter applied ⇒ no filter-attributable failure to report."""
        assert _unfiltered().lookup("BOGUS-AUG2026-25000-CE", "NSE_FNO") is None


class TestRaiseIsLoadBearing:
    """FALSIFICATION TWIN — cut the raise out of the real source.

    Proves the assertion is carried by the raise and not by something
    incidental: the twin is built from ``dhan.py``'s own text with the
    ``raise ScripMasterFilteredError`` branch replaced by the pre-trim
    ``return None``, and the SAME shared assertion body must then fail.
    """

    @staticmethod
    def _twin_module(tmp_path: Path):
        src = Path(dhan_mod.__file__).read_text(encoding="utf-8")
        needle = "        if self._excluded and _OPTION_SYMBOL_RE.search(upper):"
        assert needle in src, "lookup guard not found — twin is stale"
        head, _, tail = src.partition(needle)
        # Drop the guard's whole body, restoring the pre-trim behaviour:
        # fall straight through to the method's closing `return None`.
        _cut, sep, rest = tail.partition("        return None")
        assert sep, "could not locate the trailing return — twin is stale"
        mutated = head + "        return None" + rest
        assert "raise ScripMasterFilteredError" not in mutated.split(
            "def expiry_for"
        )[0], "surgery did not remove the raise from lookup()"

        path = tmp_path / "_dhan_twin_no_raise.py"
        path.write_text(mutated, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("_dhan_twin", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_dhan_twin"] = mod
        try:
            spec.loader.exec_module(mod)
            return mod
        finally:
            sys.modules.pop("_dhan_twin", None)

    def test_twin_without_the_raise_fails_the_shared_assertion(
        self, tmp_path: Path
    ) -> None:
        twin = self._twin_module(tmp_path)
        m = twin._ScripMaster()
        m.load_from_text(_HEADER + _ALL_ROWS, exclude=twin._EXCLUDED_INSTRUMENTS)
        # Same rows, same filter, same call — ONLY the raise is missing,
        # and that is enough to hand the broker an unresolved option leg.
        assert m.lookup("NIFTY-AUG2026-25000-CE", "NSE_FNO") is None
        # The shared body must now FAIL — pytest.raises() finding nothing
        # raised is reported as Failed.
        with pytest.raises(Failed):
            _assert_filtered_symbol_raises(m)


# ═══════════════════════════════════════════════════════════════════════
# The three live roots still resolve, with the right lot sizes
# ═══════════════════════════════════════════════════════════════════════


class TestLiveRootsStillResolve:
    @pytest.fixture(autouse=True)
    def _seed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Point the resolver at a FILTERED master and skip the download."""
        from app.brokers.dhan import _SCRIP_MASTER
        from app.services import futures_resolver

        m = _filtered()
        monkeypatch.setattr(futures_resolver, "_RESOLUTION_CACHE", {})
        monkeypatch.setattr(_SCRIP_MASTER, "_by_symbol", m._by_symbol)
        monkeypatch.setattr(_SCRIP_MASTER, "_expiry_by_symbol", m._expiry_by_symbol)
        monkeypatch.setattr(_SCRIP_MASTER, "_lot_sizes", m._lot_sizes)
        monkeypatch.setattr(_SCRIP_MASTER, "_meta", m._meta)
        monkeypatch.setattr(_SCRIP_MASTER, "_loaded_at", datetime.now(UTC))

    @pytest.mark.parametrize(
        ("tv_symbol", "expected"),
        [
            ("NSE:BSE", "BSE-Sep2026-FUT"),
            ("CDSL1!", "CDSL-Sep2026-FUT"),
            ("ANGELONE1!", "ANGELONE-Sep2026-FUT"),
        ],
    )
    @pytest.mark.asyncio
    async def test_entry_resolves_to_the_n5_contract(
        self, tv_symbol: str, expected: str
    ) -> None:
        """21 Aug is T-4 to the 25 Aug expiry, so N=5 rolls to September."""
        from app.services.futures_resolver import _IST, resolve_or_passthrough

        now = datetime(2026, 8, 21, 10, 0, tzinfo=_IST)
        got = await resolve_or_passthrough(tv_symbol, now_ist=now)
        assert got.upper() == expected.upper()

    @pytest.mark.parametrize(
        ("symbol", "lot"),
        [
            ("BSE-SEP2026-FUT", 200),
            ("CDSL-SEP2026-FUT", 475),
            ("ANGELONE-SEP2026-FUT", 2500),
        ],
    )
    def test_lot_size_survives_the_filter(self, symbol: str, lot: int) -> None:
        from app.brokers.dhan import _SCRIP_MASTER

        sid = _SCRIP_MASTER.lookup(symbol, "NSE_FNO")
        assert sid is not None, f"{symbol} vanished from the trimmed master"
        assert _SCRIP_MASTER.lot_size(sid) == lot

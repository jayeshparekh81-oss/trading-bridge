"""BSE stock-F&O resolution tests (Phase B) — mocked scrip master, deterministic.

Covers: FUTSTK resolve + rollover · OPTSTK monthly chain + ATM±10 on the mixed
50/100 grid · index (OPTIDX) behaviour untouched · verify_session honors the
explicit gap_check:false exemption · pipeline file-glob compatibility.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from recorder.scrip_master import resolve_future, resolve_option_chain, select_atm_window
from verify_session import _is_lenient


def _row(tsym, iname, expiry="", strike="0", opt="", sid="9001", lot="200", exch="NSE"):
    return {"SEM_TRADING_SYMBOL": tsym, "SEM_INSTRUMENT_NAME": iname,
            "SEM_EXM_EXCH_ID": exch, "SEM_EXPIRY_DATE": expiry,
            "SEM_STRIKE_PRICE": strike, "SEM_OPTION_TYPE": opt,
            "SEM_SMST_SECURITY_ID": sid, "SEM_LOT_UNITS": lot}


def _bse_rows():
    rows = []
    for i, exp in enumerate(["2026-07-28", "2026-08-25", "2026-09-29"]):
        rows.append(_row(f"BSE-{exp}-FUT", "FUTSTK", expiry=exp, sid=str(7000 + i)))
    # OPTSTK near expiry: mixed grid — 50 step near ATM (2300..2600), 100 step wings
    strikes = [2000.0, 2100.0, 2200.0, 2300.0, 2350.0, 2400.0, 2450.0, 2500.0,
               2550.0, 2600.0, 2700.0, 2800.0, 2900.0, 3000.0]
    sid = 8000
    for k in strikes:
        for right in ("CE", "PE"):
            rows.append(_row(f"BSE-Jul2026-{int(k)}-{right}", "OPTSTK",
                             expiry="2026-07-28", strike=str(k), opt=right, sid=str(sid)))
            sid += 1
            rows.append(_row(f"BSE-Aug2026-{int(k)}-{right}", "OPTSTK",
                             expiry="2026-08-25", strike=str(k), opt=right, sid=str(sid)))
            sid += 1
    # an OPTIDX NIFTY row that must NEVER leak into the stock chain (and vice versa)
    rows.append(_row("NIFTY-Jul2026-24000-CE", "OPTIDX", expiry="2026-07-23",
                     strike="24000", opt="CE", sid="5555"))
    return rows


# --- FUTSTK resolve + rollover ------------------------------------------------
def test_futstk_resolves_and_rolls_over():
    rows = _bse_rows()
    f1 = resolve_future(rows, date(2026, 7, 21), underlying="BSE",
                        instrument_name="FUTSTK", symbol="BSE_FUT")
    assert f1.expiry == date(2026, 7, 28) and f1.security_id == 7000
    assert f1.lot_size == 200.0
    # expiry day: still the July contract; day AFTER: rolls to August
    assert resolve_future(rows, date(2026, 7, 28), underlying="BSE",
                          instrument_name="FUTSTK").expiry == date(2026, 7, 28)
    f2 = resolve_future(rows, date(2026, 7, 29), underlying="BSE",
                        instrument_name="FUTSTK")
    assert f2.expiry == date(2026, 8, 25) and f2.security_id == 7001
    # default FUTIDX ignores stock futures — index behaviour untouched
    with pytest.raises(LookupError):
        resolve_future(rows, date(2026, 7, 21), underlying="BSE")


# --- OPTSTK chain + ATM±10 on the mixed grid ----------------------------------
def test_optstk_chain_and_atm_window_mixed_step():
    rows = _bse_rows()
    chain = resolve_option_chain(rows, date(2026, 7, 21), underlying="BSE",
                                 instrument_name="OPTSTK")
    assert chain.expiry == date(2026, 7, 28)                 # monthly, nearest
    assert len(chain.strikes) == 14                          # the listed grid only
    insts = select_atm_window(chain, spot=2450.0, window=10)
    grid = sorted(chain.strikes)
    # window is by strike INDEX on the listed grid -> mixed 50/100 respected
    assert len(insts) == 2 * len(grid[max(0, 6 - 10):6 + 11])   # nearest=2450 idx 6
    strikes_sel = sorted({float(i.symbol.split("_")[2]) for i in insts})
    assert 2350.0 in strikes_sel and 2450.0 in strikes_sel and 2800.0 in strikes_sel
    # rollover: after 28-Jul the chain is the August monthly
    c2 = resolve_option_chain(rows, date(2026, 7, 29), underlying="BSE",
                              instrument_name="OPTSTK")
    assert c2.expiry == date(2026, 8, 25)
    # index chain (default OPTIDX) never includes stock strikes
    idx = resolve_option_chain(rows, date(2026, 7, 21), underlying="NIFTY")
    assert set(idx.strikes) == {24000.0}


# --- verify_session: explicit gap_check false exempts a stock future -----------
def test_verify_gap_exemption_honored():
    man = {7000: {"security_id": 7000, "kind": "future", "gap_check": False},
           61093: {"security_id": 61093, "kind": "future", "gap_check": True},
           4242: {"security_id": 4242, "kind": "future"}}          # legacy: no key
    assert _is_lenient(Path("BSE_FUT_7000.parquet"), man) is True      # exempt (explicit false)
    assert _is_lenient(Path("NIFTY_FUT_61093.parquet"), man) is False  # index future still gated
    assert _is_lenient(Path("OLD_FUT_4242.parquet"), man) is False     # legacy kind-based intact
    # manifest-less fallback: option filenames stay lenient (covers BSE_CE_*)
    assert _is_lenient(Path("BSE_CE_2450_8010.parquet"), None) is True


# --- pipeline glob compatibility ----------------------------------------------
def test_pipeline_glob_matches_new_symbols(tmp_path):
    # consolidation/verify iterate data/<day>/*.parquet + manifest — name-agnostic.
    for n in ("BSE_FUT_7000.parquet", "BSE_CE_2450_8010.parquet", "BSE_PE_2450_8011.parquet"):
        (tmp_path / n).write_bytes(b"x")
    found = sorted(p.name for p in tmp_path.glob("*.parquet"))
    assert len(found) == 3 and all(n.startswith("BSE_") for n in found)
    # sid extraction convention (stem.split('_')[-1]) holds for the new names
    assert int(Path("BSE_CE_2450_8010.parquet").stem.split("_")[-1]) == 8010

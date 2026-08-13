"""Scrip-master resolution tests: nearest-expiry, expiry-day rollover, index verify."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from recorder import scrip_master as SM

FIX = Path(__file__).parent / "fixtures" / "mini_scrip.csv"


@pytest.fixture()
def rows():
    return SM.load_rows(FIX)


def test_resolve_picks_nearest_future(rows):
    inst = SM.resolve_future(rows, ref_date=date(2026, 7, 8))
    assert inst.security_id == 61093            # July contract
    assert inst.trading_symbol == "NIFTY-Jul2026-FUT"
    assert inst.expiry == date(2026, 7, 28)
    assert inst.exchange_segment == "NSE_FNO"
    assert inst.lot_size == 65.0


def test_expiry_day_still_selects_expiring_contract(rows):
    # On the July expiry date, the July contract is still valid.
    inst = SM.resolve_future(rows, ref_date=date(2026, 7, 28))
    assert inst.security_id == 61093


def test_day_after_expiry_rolls_forward(rows):
    inst = SM.resolve_future(rows, ref_date=date(2026, 7, 29))
    assert inst.security_id == 58072            # rolls to August
    assert inst.trading_symbol == "NIFTY-Aug2026-FUT"


def test_does_not_pick_banknifty(rows):
    # Even if we asked for July, the resolver must not confuse BANKNIFTY.
    inst = SM.resolve_future(rows, ref_date=date(2026, 7, 8))
    assert "BANKNIFTY" not in inst.trading_symbol


def test_no_contract_raises(rows):
    with pytest.raises(LookupError):
        SM.resolve_future(rows, ref_date=date(2027, 1, 1))


def test_verify_index_ids(rows):
    nifty = SM.verify_index(rows, 13, "NIFTY_50")
    vix = SM.verify_index(rows, 21, "INDIA_VIX")
    assert nifty.exchange_segment == "IDX_I"
    assert vix.security_id == 21


def test_verify_index_missing_raises(rows):
    with pytest.raises(LookupError):
        SM.verify_index(rows, 999999, "BOGUS")


def test_verify_bse_index_sensex(rows):
    sx = SM.verify_index(rows, 51, "SENSEX", exch="BSE")
    assert sx.security_id == 51
    assert sx.kind == "spot"


def test_resolve_bse_sensex_future(rows):
    inst = SM.resolve_future(rows, ref_date=date(2026, 7, 8), underlying="SENSEX",
                             exch="BSE", segment="BSE_FNO", symbol="SENSEX_FUT")
    assert inst.security_id == 111222
    assert inst.exchange_segment == "BSE_FNO"
    assert inst.kind == "future"


def test_resolve_option_chain_picks_nearest_weekly(rows):
    chain = SM.resolve_option_chain(rows, ref_date=date(2026, 7, 8), underlying="NIFTY")
    assert chain.expiry == date(2026, 7, 14)          # weekly, not the 28th monthly
    assert set(chain.strikes) == {24400.0, 24450.0, 24500.0, 24550.0, 24600.0}
    assert chain.strikes[24500.0] == {"CE": 40005, "PE": 40006}


def test_select_atm_window(rows):
    chain = SM.resolve_option_chain(rows, ref_date=date(2026, 7, 8), underlying="NIFTY")
    insts = SM.select_atm_window(chain, spot=24512.0, window=1)  # ATM=24500, +/-1
    strikes = sorted({int(i.symbol.split("_")[-1]) for i in insts})
    assert strikes == [24450, 24500, 24550]
    # each strike has CE and PE
    assert len(insts) == 6
    syms = {i.symbol for i in insts}
    assert "NIFTY_CE_24500" in syms and "NIFTY_PE_24500" in syms
    assert all(i.kind == "option" and i.exchange_segment == "NSE_FNO" for i in insts)


def test_select_atm_window_clamps_at_edges(rows):
    chain = SM.resolve_option_chain(rows, ref_date=date(2026, 7, 8), underlying="NIFTY")
    # spot below the lowest strike -> window clamps, no crash
    insts = SM.select_atm_window(chain, spot=1.0, window=5)
    assert len(insts) == 10  # all 5 strikes x CE/PE


def test_resolve_option_chain_no_options_raises(rows):
    with pytest.raises(LookupError):
        SM.resolve_option_chain(rows, ref_date=date(2027, 1, 1), underlying="NIFTY")


def test_resolve_equity(rows):
    eq = SM.resolve_equity(rows, "HDFCBANK")
    assert eq.security_id == 1333
    assert eq.exchange_segment == "NSE_EQ"
    assert eq.kind == "equity"
    # matches the EQ series, not the BE (trade-to-trade) row
    assert SM.resolve_equity(rows, "BSE").security_id == 19585


def test_resolve_equity_missing_raises(rows):
    with pytest.raises(LookupError):
        SM.resolve_equity(rows, "NOTAREALSYMBOL")


def _dl_stamping(at_ts, calls):
    """Downloader that writes the file and sets its mtime to the sim clock,
    so staleness (mtime vs injected now_ts) is deterministic."""
    import os

    def fake_dl(url, dest):
        calls["n"] += 1
        dest.write_text("header\n")
        os.utime(dest, (at_ts[0], at_ts[0]))
    return fake_dl


def test_fetch_uses_fresh_cache(tmp_path):
    calls = {"n": 0}
    at = [1_000_000.0]
    dl = _dl_stamping(at, calls)

    p1 = SM.fetch_scrip_master(tmp_path, today=date(2026, 7, 8),
                               now_ts=1_000_000.0, downloader=dl)
    assert calls["n"] == 1
    # Second fetch 1h later -> reuse cache, no download.
    p2 = SM.fetch_scrip_master(tmp_path, today=date(2026, 7, 8),
                               now_ts=1_000_000.0 + 3600, downloader=dl)
    assert calls["n"] == 1
    assert p1 == p2


def test_fetch_redownloads_when_stale(tmp_path):
    calls = {"n": 0}
    at = [1_000_000.0]
    dl = _dl_stamping(at, calls)

    SM.fetch_scrip_master(tmp_path, today=date(2026, 7, 8),
                          now_ts=1_000_000.0, downloader=dl)
    # 21h later -> stale (>20h) -> re-download.
    at[0] = 1_000_000.0 + 21 * 3600
    SM.fetch_scrip_master(tmp_path, today=date(2026, 7, 9),
                          now_ts=1_000_000.0 + 21 * 3600, downloader=dl)
    assert calls["n"] == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

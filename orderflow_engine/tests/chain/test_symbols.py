"""Symbol parsing (Module R5)."""

from __future__ import annotations

from chain.symbols import parse_symbol


def test_option_ce():
    p = parse_symbol("NIFTY_CE_23700")
    assert (p.kind, p.index, p.right, p.strike) == ("option", "NIFTY", "CE", 23700)


def test_option_pe_multitoken_index():
    p = parse_symbol("BANKNIFTY_PE_57000")
    assert (p.kind, p.index, p.right, p.strike) == ("option", "BANKNIFTY", "PE", 57000)


def test_spot_and_future():
    assert parse_symbol("NIFTY_SPOT").kind == "spot"
    assert parse_symbol("NIFTY_SPOT").index == "NIFTY"
    assert parse_symbol("BANKNIFTY_FUT").kind == "future"
    assert parse_symbol("BANKNIFTY_FUT").index == "BANKNIFTY"


def test_equity_or_other():
    assert parse_symbol("HDFCBANK").kind == "other"
    assert parse_symbol("INDIA_VIX").kind == "other"

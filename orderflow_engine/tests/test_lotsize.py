"""Lot-size root fix (2026-07-17): chain reads the scrip master's SEM_LOT_UNITS, not the
hardcoded config dict. These guards ensure the resolved lot MATCHES SEM_LOT_UNITS for the
recorded contracts and can never silently drift back to the (wrong) config value.
"""

from __future__ import annotations

import csv
from datetime import date

import pytest

from chain.config import ChainConfig
from chain.engine import ChainEngine
from chain.lotsize import resolve_lot_by_index
from recorder.scrip_master import load_rows

FIXTURE = "tests/fixtures/mini_scrip.csv"
REF = date(2026, 7, 17)


@pytest.fixture
def rows():
    return load_rows(FIXTURE)


def _sem_lot_units(sym: str) -> float:
    """Read SEM_LOT_UNITS straight from the fixture for a trading symbol — the truth."""
    with open(FIXTURE, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("SEM_TRADING_SYMBOL", "").strip() == sym:
                return float(r["SEM_LOT_UNITS"])
    raise KeyError(sym)


def test_resolved_lot_matches_sem_lot_units(rows):
    """The GUARD: resolver output == the scrip master's SEM_LOT_UNITS, per index."""
    got = resolve_lot_by_index(rows, REF, ["NIFTY", "BANKNIFTY", "SENSEX"])
    assert got["NIFTY"] == int(_sem_lot_units("NIFTY-Jul2026-FUT"))
    assert got["BANKNIFTY"] == int(_sem_lot_units("BANKNIFTY-Jul2026-FUT"))
    assert got["SENSEX"] == int(_sem_lot_units("SENSEX-Jul2026-FUT"))       # BSE product


def test_resolver_reads_scrip_master_not_config(rows):
    """It must NOT be returning the config dict values (that was the bug)."""
    got = resolve_lot_by_index(rows, REF, ["NIFTY", "BANKNIFTY"])
    cfg = ChainConfig({})
    # fixture NIFTY lot 65 != config 75; fixture BANKNIFTY 15 != config 35 — proves source
    assert got["NIFTY"] != cfg.contract_size("NIFTY")
    assert got["BANKNIFTY"] != cfg.contract_size("BANKNIFTY")
    assert got["NIFTY"] == 65 and got["BANKNIFTY"] == 15


def test_engine_prefers_scrip_master_then_falls_back_loud():
    """ChainEngine.contract_size: scrip-master lot when present; config fallback otherwise."""
    eng = ChainEngine(ChainConfig({}), meta_by_id={}, session_date=REF,
                      lot_by_index={"NIFTY": 65})
    assert eng.contract_size("NIFTY") == 65                     # scrip-master wins over config 75
    assert eng.contract_size("BANKNIFTY") == ChainConfig({}).contract_size("BANKNIFTY")  # fallback


def test_empty_scrip_master_falls_back_never_zero():
    """Unresolved index -> config default (never 0/lot-less)."""
    eng = ChainEngine(ChainConfig({}), meta_by_id={}, session_date=REF, lot_by_index={})
    assert eng.contract_size("NIFTY") == ChainConfig({}).contract_size("NIFTY")
    assert eng.contract_size("NIFTY") > 0

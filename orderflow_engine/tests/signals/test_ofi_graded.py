"""book_ofi graded activation (2026-07-15 fix).

Was a binary 0/25 gate: _clamp01(signed - 0) saturated to 1.0 on OFI SIGN alone.
Now: a magnitude floor filters noise, and activation scales by a per-instrument
typical per-bar OFI magnitude -> strong OFI ~1.0, weak ~0.3, below-floor 0.
"""

from __future__ import annotations

from types import SimpleNamespace

from signals.components import book_ofi
from signals.config import SignalConfig


def _ctx(ofi, inst="NIFTY_FUT"):
    return SimpleNamespace(book_ofi=ofi, instrument=inst)


def _cfg():
    return SignalConfig({})          # per-instrument ofi_min/ofi_scale from DEFAULTS


def test_graded_not_binary():
    cfg = _cfg()                     # NIFTY: floor 2000, scale 15000
    assert book_ofi(_ctx(1500), cfg, "long") == 0.0                 # below floor
    assert abs(book_ofi(_ctx(2000 + 0.3 * 15000), cfg, "long") - 0.3) < 1e-6   # graded
    assert book_ofi(_ctx(2000 + 15000), cfg, "long") == 1.0        # floor+scale -> 1.0
    assert book_ofi(_ctx(2000 + 40000), cfg, "long") == 1.0        # clamped
    vals = {round(book_ofi(_ctx(o), cfg, "long"), 3) for o in (3000, 6000, 10000, 17000)}
    assert len(vals) >= 3 and vals != {0.0, 1.0}                   # a real gradient


def test_wrong_side_is_zero_right_side_graded():
    cfg = _cfg()
    assert book_ofi(_ctx(-10000), cfg, "long") == 0.0              # long but flow is down
    assert book_ofi(_ctx(-10000), cfg, "short") > 0.0             # short + down flow -> fires


def test_per_instrument_scale():
    cfg = _cfg()                     # NIFTY scale 15000, BANKNIFTY scale 7000
    ofi = 5000
    n = book_ofi(_ctx(ofi, "NIFTY_FUT"), cfg, "long")
    b = book_ofi(_ctx(ofi, "BANKNIFTY_FUT"), cfg, "long")
    assert b > n > 0                                              # same OFI, BANKNIFTY higher


def test_none_is_neutral():
    assert book_ofi(_ctx(None), _cfg(), "long") == 0.0

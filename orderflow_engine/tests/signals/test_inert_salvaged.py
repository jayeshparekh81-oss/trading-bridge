"""Salvaged 2026-07-09: the engine EVALUATES but fires ZERO at the inert threshold.

Evaluating-without-firing is the pass — it proves the full R3+R4+R5+R6 composite
runs end to end on real (sparse) data without firing anything uncalibrated.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource

from chain.config import ChainConfig
from chain.engine import ChainEngine
from levels.config import LevelsConfig
from levels.engine import LevelsEngine
from signals.config import SignalConfig
from signals.engine import SignalEngine
from signals.pipeline import MultiConsumer, build_meta
from tape.config import TapeConfig
from tape.engine import TapeEngine

HERE = Path(__file__).resolve().parent.parent.parent


@pytest.mark.skipif(not (HERE / "data" / "2026-07-09").is_dir(),
                    reason="salvaged 2026-07-09 day not present (gitignored raw data)")
def test_evaluates_but_fires_zero_at_inert_threshold():
    day = HERE / "data" / "2026-07-09"
    meta = build_meta(day)
    sym = {k: v["symbol"] for k, v in meta.items()}
    chain_meta = {k: v for k, v in meta.items() if v["kind"] in ("spot", "future", "option")}
    # small bars so bars actually close on the sparse day -> candidates get evaluated
    tape = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 5}}), sym)
    lv = LevelsEngine(LevelsConfig({}), sym, date="2026-07-09")
    ch = ChainEngine(ChainConfig({}), chain_meta, date(2026, 7, 9))
    # default (inert) signal config: fire_threshold 999 + first_minutes 0 so we evaluate broadly
    scfg = SignalConfig({"signal": {"tradeable": ["BANKNIFTY_FUT", "NIFTY_FUT"],
                                    "gates": {"first_minutes_no_entry": 0}}})
    sig = SignalEngine(scfg, tape, lv, ch, meta, date(2026, 7, 9))
    multi = MultiConsumer([tape, lv, ch, sig])
    ReplayEngine(ReplaySource(day)).drive(multi, speed="max")
    summary = sig.finalize()

    assert summary["counts"]["candidates"] > 0        # it EVALUATED
    assert summary["counts"]["fired"] == 0            # and fired NOTHING at inert 999
    assert summary["net_simulated_r"] == 0.0
    assert not any(r["fired"] for r in sig.rows)      # explicit: zero fires in the glass box

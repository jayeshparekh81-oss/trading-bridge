"""Score-distribution baseline tool — histogram, component status, ceiling.

Guards the classifications the analysis turns on: a weight>0 always-zero component
is flagged ALWAYS-ZERO (silently not contributing), a weight-0 one is INERT, and the
achievable ceiling excludes the always-zero weights.
"""

from __future__ import annotations

from research.score_distribution import (component_stats, max_achievable,
                                         score_histogram)


def _cand(score, side="long", inst="NIFTY_FUT", comps=None):
    return {"score": score, "side": side, "instrument": inst, "ts_ns": 0,
            "gate_reason": "", "fired": False, "threshold": 999.0,
            "comp": comps or {}}


def _c(act, weight, enabled=True):
    return {"activation": act, "contribution": act * weight, "weight": weight,
            "enabled": enabled}


def test_histogram_buckets_and_percentiles():
    rows = [_cand(s) for s in [1, 6, 6, 12, 27, 27, 27]]
    h = score_histogram(rows)
    assert h["hist"]["0-5"] == 1 and h["hist"]["5-10"] == 2 and h["hist"]["25-30"] == 3
    assert h["max"] == 27 and h["n"] == 7


def test_component_status_classification():
    rows = [
        _cand(10, comps={"live": _c(1.0, 10), "dead": _c(0.0, 25), "inert": _c(0.1, 0)}),
        _cand(0,  comps={"live": _c(0.0, 10), "dead": _c(0.0, 25), "inert": _c(0.1, 0)}),
    ]
    cs = component_stats(rows)
    assert cs["dead"]["status"].startswith("ALWAYS-ZERO")     # weight>0, never fires
    assert cs["inert"]["status"].startswith("INERT")          # weight 0
    assert cs["live"]["status"] == "LIVE"
    assert cs["live"]["fire_rate"] == 0.5                     # 1 of 2 nonzero


def test_ceiling_excludes_always_zero_weights():
    rows = [_cand(15, comps={"live": _c(1.0, 40), "dead1": _c(0.0, 25),
                             "dead2": _c(0.0, 15), "inert": _c(0.1, 0)})]
    m = max_achievable(rows)
    assert m["total_weight"] == 80                            # 40+25+15+0
    assert set(m["dead"]) == {"dead1", "dead2"}
    assert m["ceiling_with_dead_removed"] == 40               # only the LIVE 40 is reachable
    assert m["observed_max"] == 15

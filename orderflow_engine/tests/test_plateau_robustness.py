"""P3 plateau-robustness — per-candidate PE/PD/PR + eligibility (tests t1..t5).

PE_i = median(E_{i-1},E_i,E_{i+1}); PD_i = MAD(...); PR_i = PE_i − 0.5·PD_i.
Eligible iff INTERIOR and E_i AND both neighbours > 0; isolated peaks rejected; edges flagged.
Deterministic — all curves are hand-built literals.
"""

from __future__ import annotations

import pytest

from research.walkforward import _mad, _median, best_plateau, plateau_robustness


# t1) broad plateau -> an INTERIOR center is eligible with the top PR
def test_t1_broad_plateau_interior_center_top_pr_and_eligible():
    curve = [(0.0, 0.2), (0.15, 0.9), (0.30, 1.0), (0.45, 0.95), (0.60, 0.3)]
    rows = plateau_robustness(curve)
    bp = best_plateau(rows)
    assert bp is not None and bp["eligible"] and bp["interior"]
    assert bp["value"] in (0.15, 0.30, 0.45)                 # somewhere on the shelf, not the edges
    # best PR is the max PR among eligible, and it is interior
    assert bp["PR"] == max(r["PR"] for r in rows if r["eligible"])
    assert all(rows[i]["eligible"] for i in (1, 2, 3))        # the all-positive interior shelf
    assert rows[0]["flag"] == "limited-neighbor evidence"     # edges never eligible-full
    assert rows[-1]["flag"] == "limited-neighbor evidence"


# t2) isolated spike: highest E but negative neighbours -> REJECTED regardless of height
def test_t2_isolated_spike_rejected():
    curve = [(0.0, -0.5), (0.15, -0.4), (0.30, 5.0), (0.45, -0.4), (0.60, -0.5)]
    rows = plateau_robustness(curve)
    peak = next(r for r in rows if r["value"] == 0.30)
    assert peak["E"] == 5.0 and peak["eligible"] is False and peak["flag"] == "isolated-peak"
    assert best_plateau(rows) is None                         # nothing eligible


# t3) edge candidate (missing a neighbour) -> flagged limited-neighbor, never eligible-full
def test_t3_edge_flagged_never_eligible_full():
    curve = [(0.0, 2.0), (0.15, 1.5), (0.30, 1.0)]            # index 0 is a high edge
    rows = plateau_robustness(curve)
    assert rows[0]["flag"] == "limited-neighbor evidence" and rows[0]["eligible"] is False
    assert rows[-1]["flag"] == "limited-neighbor evidence" and rows[-1]["eligible"] is False
    # only the interior (index 1) can be eligible
    assert rows[1]["interior"] and rows[1]["eligible"] is True
    bp = best_plateau(rows)
    assert bp["value"] == 0.15                                # prefer interior over the taller edge


# t4) all-negative neighbourhood -> nothing eligible
def test_t4_all_negative_nothing_eligible():
    curve = [(0.0, -0.1), (0.15, -0.2), (0.30, -0.05), (0.45, -0.3)]
    rows = plateau_robustness(curve)
    assert all(not r["eligible"] for r in rows)
    assert best_plateau(rows) is None
    assert any(r["flag"] == "below-zero" for r in rows)


# t5) hand-computed PE/PD/PR golden trio (exact)
def test_t5_hand_computed_golden():
    # helper primitives first
    assert _median([1.0, 3.0, 2.0]) == 2.0
    assert _median([4.0, 1.0]) == 2.5
    # window {0.8, 1.0, 0.6}: median 0.8; MAD = median(|.8-.8|,|1-.8|,|.6-.8|)=median(0,.2,.2)=0.2
    # PE=0.8, PD=0.2, PR=0.8-0.5*0.2=0.7
    assert _mad([0.8, 1.0, 0.6]) == pytest.approx(0.2)
    curve = [(0, 0.6), (1, 0.8), (2, 1.0), (3, 0.6)]          # candidate i=1 -> window {0.6,0.8,1.0}
    r1 = plateau_robustness(curve)[1]
    # window for i=1 is {E1=0.8, E0=0.6, E2=1.0}: median 0.8, MAD 0.2, PR 0.7
    assert r1["PE"] == pytest.approx(0.8)
    assert r1["PD"] == pytest.approx(0.2)
    assert r1["PR"] == pytest.approx(0.7)
    assert r1["eligible"] is True and r1["interior"] is True

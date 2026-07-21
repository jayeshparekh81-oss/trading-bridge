"""P4 stress-gate teeth (t1..t6) — deterministic, per spec.

t1 fat-tail-concentrated edge dies after best-5 removal; spread edge survives
t2 best-day guardrail refusal on short series
t3 marginal system: net>0 @1.0x, net<0 @1.5x; robust system positive at both
t4 paired bootstrap: A>B by construction -> CI excludes 0; A==B -> CI includes 0
t5 stored-seed determinism -> identical CI on re-run
t6 --stress-gates off -> byte-identical CLI output
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from research.stress_gates import (REFUSAL_BEST, REFUSAL_PAIRED, daily_net_series,
                                   paired_block_bootstrap, remove_best_days,
                                   slippage_stress)
from research.walkforward import Trade, _day_open_ns, main as wf_main

DAYS15 = [f"2026-06-{d:02d}" for d in range(1, 16)]


def _series(vals):
    return [(d, v) for d, v in zip(DAYS15, vals)]


# ---------------------------------------------------------------- t1
def test_t1_fat_tail_edge_dies_spread_edge_survives():
    # fat-tail: 2 monsters carry it, the other 13 days bleed
    fat = _series([7.0, 2.4] + [-0.35] * 13)
    r = remove_best_days(fat, n=5)
    assert not r["refused"]
    assert r["total_before"] > 0 and r["total_after"] < 0 and r["survives"] is False
    # spread edge: same total, evenly earned -> survives removal
    spread = _series([0.35] * 15)
    r2 = remove_best_days(spread, n=5)
    assert not r2["refused"] and r2["total_after"] > 0 and r2["survives"] is True


# ---------------------------------------------------------------- t2
def test_t2_best_day_guardrail_refuses_short_series():
    short = _series([0.1] * 15)[:14]                 # 14 < 3*5
    r = remove_best_days(short, n=5)
    assert r["refused"] and REFUSAL_BEST in r["reason"]


# ---------------------------------------------------------------- t3
def _ci(gross, r_unit=10.0):
    return {"gross": gross, "r_unit": r_unit, "premium": 300.0, "delta": 0.5,
            "delta_source": "fallback", "lot": 65}


def test_t3_marginal_dies_at_stress_robust_survives():
    marginal = [_ci(0.5)] * 4                        # cost@1.0 ≈ 0.457R -> net +; @1.5 ≈ 0.557R -> net −
    m = slippage_stress(marginal)
    assert m["n_costed"] == 4
    assert m["survives_1p0x"] is True and m["net_1p0x"] > 0
    assert m["survives_stress"] is False and m["net_stress"] < 0
    robust = [_ci(2.0)] * 4
    r = slippage_stress(robust)
    assert r["survives_1p0x"] and r["survives_stress"]
    # uncosted entries are counted, never estimated
    part = slippage_stress([_ci(1.0), {"gross": 1.0}])
    assert part["n_costed"] == 1 and part["n_uncosted"] == 1


# ---------------------------------------------------------------- t4
def test_t4_paired_bootstrap_superiority_and_tie():
    b = [0.1, -0.2, 0.3, 0.0, 0.15, -0.1, 0.2, 0.05, -0.05, 0.1,
         0.0, 0.12, -0.08, 0.2, 0.1]
    a = [x + 0.3 for x in b]                         # A better by +0.3/day everywhere
    sup = paired_block_bootstrap(a, b)
    assert not sup["refused"]
    assert sup["ci_low"] > 0 and sup["verdict"] == "A superior"
    tie = paired_block_bootstrap(b, list(b))
    assert tie["ci_low"] <= 0 <= tie["ci_high"] and tie["verdict"] == "no clear superiority"
    assert abs(tie["mean_delta"]) < 1e-9
    # guardrails: length mismatch + too-few days
    assert paired_block_bootstrap(a, b[:-1])["refused"]
    short = paired_block_bootstrap(a[:9], b[:9])
    assert short["refused"] and REFUSAL_PAIRED in short["reason"]


# ---------------------------------------------------------------- t5
def test_t5_stored_seed_determinism():
    b = [0.05 * ((i % 5) - 2) for i in range(15)]
    a = [x + 0.1 for x in b]
    r1 = paired_block_bootstrap(a, b, seed=777)
    r2 = paired_block_bootstrap(a, b, seed=777)
    assert (r1["ci_low"], r1["ci_high"], r1["mean_delta"]) == \
           (r2["ci_low"], r2["ci_high"], r2["mean_delta"])
    assert r1["seed"] == 777                          # seed stored in the output


# ---------------------------------------------------------------- helper coverage
def test_daily_net_series_stitches_by_day():
    o = _day_open_ns(DAYS15[0])
    trades = [Trade(DAYS15[0], o, o + 1, 0.5), Trade(DAYS15[0], o + 2, o + 3, -0.2),
              Trade(DAYS15[1], o, o + 1, 1.0)]
    assert daily_net_series(trades) == [(DAYS15[0], 0.3), (DAYS15[1], 1.0)]


# ---------------------------------------------------------------- t6
def test_t6_flags_off_byte_identical():
    argv = ["prog", "--days", ",".join(DAYS15[:4]), "--n-perm", "3"]
    b1, b2 = io.StringIO(), io.StringIO()
    with redirect_stdout(b1):
        wf_main(argv)
    with redirect_stdout(b2):
        wf_main(argv)
    assert b1.getvalue() == b2.getvalue()             # deterministic
    assert "STRESS GATES" not in b1.getvalue()        # flag off -> zero stress output
    b3 = io.StringIO()
    with redirect_stdout(b3):
        wf_main(argv + ["--stress-gates"])
    out3 = b3.getvalue()
    assert out3.startswith(b1.getvalue()[:200]) and "STRESS GATES" in out3
    assert REFUSAL_BEST.split(" — ")[0] in out3       # 4 days -> loud refusal, no silent number

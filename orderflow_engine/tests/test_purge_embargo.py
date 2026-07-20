"""P2 leakage teeth — purge + embargo must actually bite (tests t1..t4 per spec).

The audit (embargo_test docstring) concludes required cross-boundary embargo = 0 because
all feature/holding/label horizons are SESSION-SCOPED with per-day-fresh engines. These
tests keep the machinery honest anyway: if anyone ever introduces cross-boundary trades
or features, the primitives must drop them — and a PLANTED leak must be provably caught.
"""

from __future__ import annotations

from research.walkforward import (SweepSpec, Trade, _day_open_ns, embargo_test,
                                  profit_factor, purge_train, walk_forward_sweep)

NS = 1_000_000_000
MIN60 = 60 * 60 * NS
D = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"]
BOUNDARY = _day_open_ns(D[2])                      # test day open = the IS/OOS boundary


# t1) feature window crosses the boundary -> embargo (= the feature lookback) excludes it
def test_t1_feature_window_crossing_trade_is_embargoed():
    lookback_ns = MIN60                            # e.g. a 60-min feature window
    inside = Trade(D[2], BOUNDARY + lookback_ns // 2, BOUNDARY + lookback_ns, 1.0)
    kept = embargo_test([inside], BOUNDARY, lookback_ns)
    assert kept == []                              # its features reach back across the boundary


# t2) trade HELD across the boundary -> purged from train
def test_t2_boundary_crossing_hold_is_purged():
    crosses = Trade(D[1], BOUNDARY - 2 * MIN60, BOUNDARY + MIN60, 2.0)   # exits in test window
    clean = Trade(D[1], BOUNDARY - 3 * MIN60, BOUNDARY - MIN60, 0.5)
    assert purge_train([crosses, clean], BOUNDARY) == [clean]


# t3) embargo length exact: inside -> excluded; at/after the edge -> included
def test_t3_embargo_edge_exact():
    just_inside = Trade(D[2], BOUNDARY + MIN60 - 1, BOUNDARY + MIN60, 1.0)
    at_edge = Trade(D[2], BOUNDARY + MIN60, BOUNDARY + 2 * MIN60, 1.0)
    outside = Trade(D[2], BOUNDARY + MIN60 + 1, BOUNDARY + 2 * MIN60, 1.0)
    kept = embargo_test([just_inside, at_edge, outside], BOUNDARY, MIN60)
    assert kept == [at_edge, outside]
    # zero embargo (the audited default) keeps everything entered at/after the boundary
    assert embargo_test([just_inside], BOUNDARY, 0) == [just_inside]


# t4) DELIBERATE LEAK — the tests must bite both ways
def test_t4_planted_leak_inflates_without_guard_not_with_it():
    # (a) EMBARGO side: a +10R trade entered BEFORE the boundary is planted into the test
    # list. Unguarded (embargo 0 keeps anything entered >= boundary; this one is earlier
    # and slips in only if nobody filters) OOS PF is inflated; embargo >= its age drops it.
    leak = Trade(D[2], BOUNDARY - MIN60, BOUNDARY + MIN60, 10.0)   # pre-boundary entry
    honest = [Trade(D[2], BOUNDARY + 2 * MIN60 + i * 60 * NS, BOUNDARY + 3 * MIN60, r)
              for i, r in enumerate([0.5, -1.0, 0.4])]
    unguarded = profit_factor([t.r for t in [leak] + honest])          # leak counted
    guarded = profit_factor([t.r for t in embargo_test([leak] + honest, BOUNDARY, 0)])
    assert unguarded > guarded                     # the leak was flattering the OOS metric
    assert leak not in embargo_test([leak] + honest, BOUNDARY, 0)      # entry < boundary
    # (b) PURGE side inside the real sweep: config B's train edge exists ONLY via a trade
    # whose outcome resolves inside the test window. Purge ON (the sweep default) must
    # drop it so selection prefers honest config A; skipping purge flips the choice.
    def ev(v: float, days: list[str]) -> list[Trade]:
        out: list[Trade] = []
        for d in days:
            o = _day_open_ns(d)
            if v == 1.0:                                       # honest config A: +0.3/day
                out.append(Trade(d, o + MIN60, o + 2 * MIN60, 0.3))
            else:                                              # leaky config B: flat...
                out.append(Trade(d, o + MIN60, o + 2 * MIN60, 0.0))
                if d == D[1]:                                  # ...plus a boundary-crossing +10R
                    out.append(Trade(d, o + 5 * MIN60, BOUNDARY + MIN60, 10.0))
        return out
    spec = SweepSpec(knob="k", values=(1.0, 2.0))
    wf = walk_forward_sweep(D[:3], ev, spec, train_size=2, test_size=1)
    assert wf.per_split[0]["chosen_value"] == 1.0              # purge dropped B's leak
    # without purge, B's train metric would dominate (the leak is its only edge):
    train = [t for t in ev(2.0, D[:2])]
    mean = lambda xs: sum(xs) / len(xs)
    assert mean([t.r for t in train]) > 0.3                    # unpurged B beats honest A
    assert mean([t.r for t in purge_train(train, BOUNDARY)]) < 0.3   # purged B does not

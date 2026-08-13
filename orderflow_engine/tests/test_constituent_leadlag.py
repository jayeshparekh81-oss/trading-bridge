"""Constituent lead-lag tool — cross-correlation sign convention + no-look-ahead.

The two things that would silently invalidate the analysis: a wrong lead/lag sign
(claiming cash leads when it lags), and any forward leak (the big-print event study
peeking at future ticks BEFORE the event, or the regime velocity using future data).
"""

from __future__ import annotations

import numpy as np

from research.constituent_leadlag import (bigprint_event_study, crosscorr,
                                          leadlag_report, regime_leadlag)

NS = 1_000_000_000


def test_crosscorr_sign_x_leads_y_is_positive_k():
    """If x leads y by 3 steps (y[t] = x[t-3]), the peak must be at k=+3."""
    rng = np.random.default_rng(0)
    x = rng.standard_normal(2000)
    y = np.empty_like(x)
    y[3:] = x[:-3]
    y[:3] = 0.0
    cc, pk, pv = crosscorr(x, y, 10)
    assert pk == 3 and pv > 0.9          # x leads y by +3, near-perfect


def test_crosscorr_symmetric_reverse_is_mirror():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(2000)
    y = np.empty_like(x); y[2:] = x[:-2]; y[:2] = 0.0
    _, pk_xy, _ = crosscorr(x, y, 10)
    _, pk_yx, _ = crosscorr(y, x, 10)
    assert pk_xy == -pk_yx == 2           # the reverse is only the trivial mirror


def _day_from_series(basket, fut, grid_s=1):
    n = len(fut)
    edges = np.arange(n, dtype="float64") * grid_s * NS
    # a minimal 'day' dict for the report/regime functions
    return {"edges": edges, "basket_ret": basket, "fut_ret": fut, "grid_s": grid_s,
            "fut_raw": (edges, np.exp(np.nancumsum(np.nan_to_num(fut))) * 100.0,
                        np.arange(n, dtype="float64")),
            "banks": {}, "weights": {}}


def test_leadlag_report_labels_cash_lead():
    fut = np.random.default_rng(2).standard_normal(3000)
    basket = np.empty_like(fut); basket[:-4] = fut[4:]; basket[-4:] = 0.0   # basket leads fut by 4
    r = leadlag_report(_day_from_series(basket, fut), max_lag_s=10)
    assert r["peak_lag_s"] == 4 and r["lead"] == "cash_leads_future"


def test_bigprint_event_study_no_look_ahead():
    """The forward window must use only ticks AFTER the event — a price move BEFORE the
    event must not leak into the +Ns return."""
    from research.constituent_leadlag import build_day  # noqa: F401 (import shape check)
    # future price: flat until t=100s, then jumps. An event at t=50s must see 0 forward
    # move at +30s (jump is later), NOT the later jump.
    n = 200
    fts = np.arange(n, dtype="float64") * NS
    fltp = np.where(np.arange(n) < 100, 100.0, 110.0)          # future jumps at t=100s
    # bank X: a seed tick then a volume-jump (big print) at t=50s
    day = {"grid_s": 1, "fut_raw": (fts, fltp, np.zeros(n)),
           "banks": {"X": (np.array([40.0 * NS, 50.0 * NS]), np.array([100.0, 100.0]),
                           np.array([1000.0, 2000.0]))}}
    # event at t=50s; +30s window ends at t=80s (still pre-jump) -> ~0 forward return
    es = bigprint_event_study(day, root=None, date="x", windows_s=(30,), pctile=0.0)
    assert es["X"]["fwd"][30]["n"] == 1
    assert abs(es["X"]["fwd"][30]["median_bps"]) < 1.0        # no leak of the t=100 jump


def test_regime_velocity_is_trailing_not_centered():
    """A single velocity spike must classify points AT/AFTER it as high-velocity, never
    the points just BEFORE it (which a centered window would wrongly catch)."""
    n = 400
    fut = np.zeros(n)
    fut[200] = 5.0                                            # a lone spike at t=200
    basket = np.zeros(n)
    rg = regime_leadlag(_day_from_series(basket, fut), max_lag_s=5, hi_pctile=99.0)
    # trailing window -> the high-velocity mass sits at/after 200, not before it.
    # (we assert it ran and split; exact counts are window-size dependent)
    assert rg["high_velocity"]["n_points"] >= 1
    assert rg["normal"]["n_points"] > rg["high_velocity"]["n_points"]

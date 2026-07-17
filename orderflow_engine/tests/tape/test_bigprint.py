"""Tests for the big-print detector + cluster (Module R3)."""

from __future__ import annotations

from tape.bigprint import BigPrintDetector
from tape.classify import BUY, SELL
from tape.trades import Trade


def _t(ts_ns, notional, side=BUY):
    return Trade(ts_ns=ts_ns, price=100.0, size=int(notional / 100),
                 side=side, notional=notional)


def test_inert_when_threshold_zero():
    d = BigPrintDetector(notional_threshold=0, cluster_k=3, cluster_window_s=10)
    assert d.on_trade(_t(1, 10_000_000)) == []


def test_emits_big_print_above_threshold():
    d = BigPrintDetector(notional_threshold=1_000_000, cluster_k=99, cluster_window_s=10)
    assert d.on_trade(_t(1, 999_999)) == []            # below
    evs = d.on_trade(_t(2, 1_000_000))                 # at threshold
    assert len(evs) == 1 and not evs[0].is_cluster
    assert evs[0].notional == 1_000_000


def test_cluster_k_in_window():
    ns = 1_000_000_000
    d = BigPrintDetector(notional_threshold=1_000_000, cluster_k=3, cluster_window_s=10)
    assert len(d.on_trade(_t(0 * ns, 2_000_000))) == 1        # print 1
    assert len(d.on_trade(_t(2 * ns, 2_000_000))) == 1        # print 2
    evs = d.on_trade(_t(4 * ns, 2_000_000))                   # print 3 within 10s -> cluster
    assert len(evs) == 2
    assert evs[1].is_cluster and evs[1].cluster_count == 3


def test_prints_outside_window_do_not_cluster():
    ns = 1_000_000_000
    d = BigPrintDetector(notional_threshold=1_000_000, cluster_k=3, cluster_window_s=10)
    d.on_trade(_t(0 * ns, 2_000_000))
    d.on_trade(_t(2 * ns, 2_000_000))
    evs = d.on_trade(_t(20 * ns, 2_000_000))     # 20s later -> first two aged out
    assert len(evs) == 1 and not evs[0].is_cluster


# ============================ PERCENTILE mode (2026-07-17) ===================
def _pctl_detector(percentile=99.0, lookback=2000, min_samples=100):
    return BigPrintDetector(notional_threshold=0, cluster_k=99, cluster_window_s=10,
                            mode="percentile", percentile=percentile,
                            lookback=lookback, min_samples=min_samples)


def _warm(d, base, n, side=BUY, start_ts=0):
    """Feed n small-ish trades (uniform 1..n * base) to warm + shape the window."""
    for i in range(1, n + 1):
        d.on_trade(_t(start_ts + i, base * i, side))


def test_percentile_is_per_instrument():
    """Same notional is BIG for a low-notional instrument, NOT for a high-notional one —
    each detector uses its OWN distribution (per-instrument by construction)."""
    lo = _pctl_detector(min_samples=100); hi = _pctl_detector(min_samples=100)
    _warm(lo, base=1_000, n=200)               # lo window: 1k..200k  (p99 ~ 198k)
    _warm(hi, base=1_000_000, n=200)           # hi window: 1M..200M  (p99 ~ 198M)
    probe = 5_000_000                          # 5M: huge for lo, tiny for hi
    assert lo.on_trade(_t(999, probe)) != []   # BIG on the low-notional instrument
    assert hi.on_trade(_t(999, probe)) == []   # NOT big on the high-notional instrument


def test_no_look_ahead_future_print_cannot_move_earlier_threshold():
    """LEAK GUARD: classify a stream; then classify the SAME stream with a colossal print
    APPENDED at the end. Every earlier classification must be byte-identical — the future
    print cannot raise the threshold that judged the earlier ones."""
    def run(stream):
        d = _pctl_detector(min_samples=100)
        return [bool(d.on_trade(_t(ts, n))) for ts, n in stream]
    base = [(i, 1_000 * i) for i in range(1, 151)]          # 150 warming trades
    base += [(200, 500_000), (201, 2_000)]                  # a real big print + a small one
    without = run(base)
    with_future = run(base + [(999, 10_000_000_000)])       # colossal print at the END
    assert with_future[:len(base)] == without                # earlier verdicts unchanged


def test_graded_not_binary():
    """A deeper-tail print scores HIGHER than a boundary print — both in (0,1), not clamped
    to 1.0 (OFI's lesson)."""
    d = _pctl_detector(percentile=95.0, min_samples=100)
    _warm(d, base=1_000, n=200)                # window 1k..200k
    near = d.on_trade(_t(500, 191_000))        # ~p95.5, just past the cut -> small strength
    deep = d.on_trade(_t(501, 200_000))        # the tail extreme -> ~1.0
    assert near and deep
    assert 0.0 <= near[0].strength < deep[0].strength <= 1.0
    assert near[0].strength < 1.0              # NOT clamped to a flag


def test_warmup_contributes_nothing_until_min_samples():
    """Below min_samples the percentile is not estimable -> NO event, even for a huge print
    (the honest '0 until warm', not day-1 leaky self-data)."""
    d = _pctl_detector(min_samples=100)
    for i in range(1, 100):                     # 99 trades < min_samples
        assert d.on_trade(_t(i, 1_000)) == []
    assert d.on_trade(_t(100, 1_000_000_000)) == []   # still cold at the 100th check
    for i in range(101, 260):                   # warm the window past min_samples
        d.on_trade(_t(i, 1_000 + i))
    assert d.on_trade(_t(999, 1_000_000_000)) != []   # now warm -> fires


def test_percentile_inert_when_mode_fixed_and_threshold_zero():
    """The shipped default: mode 'fixed' + threshold 0 -> the percentile path never runs."""
    d = BigPrintDetector(notional_threshold=0, cluster_k=3, cluster_window_s=10)  # mode defaults fixed
    for i in range(1, 500):
        assert d.on_trade(_t(i, 1_000_000_000)) == []     # nothing, ever

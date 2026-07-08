"""Watchdog gap-detection tests (deterministic; injected clock)."""

from __future__ import annotations

import pytest

from recorder.watchdog import NS_PER_S, Watchdog


def _s(sec):
    return int(sec * NS_PER_S)


def test_no_gap_when_ticks_are_frequent():
    wd = Watchdog(threshold_s=3.0)
    wd.register(1, seed_ns=0)
    for t in range(1, 10):
        assert wd.on_packet(1, _s(t)) is None
        assert wd.poll(_s(t)) == []
    assert wd.open_gaps == {}


def test_gap_opens_after_threshold():
    wd = Watchdog(threshold_s=3.0)
    wd.register(1, seed_ns=0)
    wd.on_packet(1, _s(1))
    # 3.5s later, no packet
    newly = wd.poll(_s(4.5))
    assert newly == [1]
    # polling again does not re-open
    assert wd.poll(_s(5.0)) == []


def test_gap_closes_on_next_packet_with_duration():
    wd = Watchdog(threshold_s=3.0)
    wd.register(1, seed_ns=0)
    wd.on_packet(1, _s(1))
    wd.poll(_s(4.5))          # gap opens (start=1s)
    gap = wd.on_packet(1, _s(6))  # packet resumes at 6s
    assert gap is not None
    assert gap.security_id == 1
    assert gap.start_ns == _s(1)
    assert gap.end_ns == _s(6)
    assert gap.duration_s == pytest.approx(5.0)
    assert wd.open_gaps == {}


def test_silent_from_start_is_detected():
    wd = Watchdog(threshold_s=3.0)
    wd.register(99, seed_ns=_s(0))
    assert wd.poll(_s(4)) == [99]  # never got a packet


def test_close_all_flags_open_ended():
    wd = Watchdog(threshold_s=3.0)
    wd.register(1, seed_ns=0)
    wd.on_packet(1, _s(1))
    wd.poll(_s(5))
    gaps = wd.close_all(_s(10))
    assert len(gaps) == 1
    assert gaps[0].open_ended is True
    assert gaps[0].duration_s == pytest.approx(9.0)
    assert wd.open_gaps == {}


def test_independent_instruments():
    wd = Watchdog(threshold_s=3.0)
    wd.register(1, seed_ns=0)
    wd.register(2, seed_ns=0)
    wd.on_packet(1, _s(1))
    wd.on_packet(2, _s(1))
    wd.on_packet(1, _s(4.5))  # keep 1 alive
    newly = wd.poll(_s(4.6))
    assert newly == [2]       # only 2 is silent
    assert 1 not in wd.open_gaps


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

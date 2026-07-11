"""Pacer: max = no sleep; 1x/Nx sleep proportional to inter-event ns gaps."""

from __future__ import annotations

import pytest

from replayer.clock import Pacer, parse_speed


def test_parse_speed():
    assert parse_speed("max") is None
    assert parse_speed(None) is None
    assert parse_speed("1x") == 1.0
    assert parse_speed("10x") == 10.0
    assert parse_speed("2.5x") == 2.5
    assert parse_speed(5) == 5.0
    with pytest.raises(ValueError):
        parse_speed("fast")


def test_max_speed_never_sleeps():
    calls = []
    p = Pacer("max", sleep=calls.append)
    for ts in (0, 1_000_000_000, 3_000_000_000):
        p.wait(ts)
    assert calls == []


def test_realtime_sleeps_full_gap():
    calls = []
    p = Pacer("1x", sleep=calls.append)
    p.wait(0)                       # first: no sleep (no prev)
    p.wait(2_000_000_000)           # +2s -> sleep 2.0
    p.wait(2_500_000_000)           # +0.5s -> sleep 0.5
    assert calls == pytest.approx([2.0, 0.5])


def test_nx_scales_gap_down():
    calls = []
    p = Pacer("10x", sleep=calls.append)
    p.wait(0)
    p.wait(10_000_000_000)          # +10s at 10x -> sleep 1.0
    assert calls == pytest.approx([1.0])


def test_non_monotonic_or_equal_ts_does_not_sleep():
    calls = []
    p = Pacer("1x", sleep=calls.append)
    p.wait(1_000_000_000)
    p.wait(1_000_000_000)           # equal -> no sleep
    p.wait(500_000_000)             # earlier -> no sleep
    assert calls == []

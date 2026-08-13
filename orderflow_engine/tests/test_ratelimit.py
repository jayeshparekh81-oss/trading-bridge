"""ThrottledLogger tests: one record per interval per key, rest aggregated."""

from __future__ import annotations

import logging

from recorder.ratelimit import ThrottledLogger


class _FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _capture(caplog):
    return [r.getMessage() for r in caplog.records]


def test_first_emits_then_suppresses_within_interval(caplog):
    clk = _FakeClock()
    tl = ThrottledLogger(logging.getLogger("t.rl1"), interval_s=300.0, clock=clk)
    caplog.set_level(logging.ERROR, logger="t.rl1")

    tl.error("k", "boom %d", 1)          # emits
    for _ in range(9):                   # all within window -> suppressed
        tl.error("k", "boom %d", 1)
    assert len(_capture(caplog)) == 1
    assert tl.suppressed_count("k") == 9


def test_emits_again_after_interval_with_suppressed_suffix(caplog):
    clk = _FakeClock()
    tl = ThrottledLogger(logging.getLogger("t.rl2"), interval_s=300.0, clock=clk)
    caplog.set_level(logging.ERROR, logger="t.rl2")

    tl.error("k", "boom")                # emit @0
    for _ in range(5):
        tl.error("k", "boom")            # suppressed
    clk.t = 301.0
    tl.error("k", "boom")                # emit again, folds suppressed count
    msgs = _capture(caplog)
    assert len(msgs) == 2
    assert "+5 suppressed in last 300s" in msgs[1]
    assert tl.suppressed_count("k") == 0


def test_distinct_keys_are_independent(caplog):
    clk = _FakeClock()
    tl = ThrottledLogger(logging.getLogger("t.rl3"), interval_s=300.0, clock=clk)
    caplog.set_level(logging.ERROR, logger="t.rl3")

    tl.error("a", "a")   # emit
    tl.error("b", "b")   # emit (different key)
    tl.error("a", "a")   # suppressed
    assert len(_capture(caplog)) == 2


def test_exception_emits_traceback_once(caplog):
    clk = _FakeClock()
    tl = ThrottledLogger(logging.getLogger("t.rl4"), interval_s=300.0, clock=clk)
    caplog.set_level(logging.ERROR, logger="t.rl4")

    for i in range(4):
        try:
            raise ValueError(f"disk full {i}")
        except ValueError:
            tl.exception("part", "part flush failed")
    records = [r for r in caplog.records]
    assert len(records) == 1
    assert records[0].exc_info is not None   # full traceback captured once
    assert tl.suppressed_count("part") == 3

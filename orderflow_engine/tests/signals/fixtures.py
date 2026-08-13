"""Fixtures for signal-engine tests."""

from __future__ import annotations

from signals.context import SignalContext


def make_ctx(**kw) -> SignalContext:
    # recent_big_print_strength defaults to 1.0 so a present big print (side set) is FULL
    # strength — the fixed-mode / binary case. Graded tests pass an explicit fractional value.
    base = dict(instrument="NIFTY_FUT", index="NIFTY", sid=1, ts_ns=0, price=100.0,
                recent_big_print_strength=1.0)
    base.update(kw)
    return SignalContext(**base)

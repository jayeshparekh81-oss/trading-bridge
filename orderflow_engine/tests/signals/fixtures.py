"""Fixtures for signal-engine tests."""

from __future__ import annotations

from signals.context import SignalContext


def make_ctx(**kw) -> SignalContext:
    base = dict(instrument="NIFTY_FUT", index="NIFTY", sid=1, ts_ns=0, price=100.0)
    base.update(kw)
    return SignalContext(**base)

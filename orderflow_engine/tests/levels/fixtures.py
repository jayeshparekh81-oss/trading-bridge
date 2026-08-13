"""Fixtures for levels tests."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from levels.ohlcv import Bar
from tape.classify import BUY
from tape.trades import Trade

_IST = timezone(timedelta(hours=5, minutes=30))


def trade(price: float, size: int, side: int = BUY, ts_ns: int = 0) -> Trade:
    return Trade(ts_ns=ts_ns, price=price, size=size, side=side, notional=price * size)


def ist_ts(d: date) -> int:
    """Epoch seconds for noon IST on date d (so _ist_date round-trips to d)."""
    return int(datetime.combine(d, time(12, 0), tzinfo=_IST).timestamp())


def bar(d: date, o: float, h: float, l: float, c: float, v: int = 1000) -> Bar:
    return Bar(ist_ts(d), o, h, l, c, v)

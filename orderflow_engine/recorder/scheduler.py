"""Session scheduling — all times in Asia/Kolkata, never naive.

Daily plan (IST):
  09:05  connect
  09:07  start recording
  15:35  stop recording
  15:40  disconnect + consolidate + verify, then sleep

Weekdays only; dates in ``holidays.yaml`` are skipped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

log = logging.getLogger("recorder.scheduler")

IST = ZoneInfo("Asia/Kolkata")


class Phase(Enum):
    WAIT = "wait"          # outside session; sleep until next connect
    CONNECT = "connect"    # connect window opened (09:05–09:07)
    RECORD = "record"      # active recording window (09:07–15:35)
    WIND_DOWN = "wind_down"  # post-record, pre-verify (15:35–15:40)
    VERIFY = "verify"      # run consolidation + verification (>=15:40)


@dataclass
class Scheduler:
    connect_time: time = time(9, 5)
    record_start: time = time(9, 7)
    record_end: time = time(15, 35)
    verify_time: time = time(15, 40)
    holidays: frozenset[date] = frozenset()
    tz: ZoneInfo = IST

    def is_trading_day(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays

    def _at(self, d: date, t: time) -> datetime:
        return datetime.combine(d, t, tzinfo=self.tz)

    def next_connect(self, now: datetime) -> datetime:
        """Datetime of the next connect boundary at/after ``now``."""
        d = now.date()
        if self.is_trading_day(d) and now < self._at(d, self.connect_time):
            return self._at(d, self.connect_time)
        # advance to the next trading day
        d = d + timedelta(days=1)
        for _ in range(14):  # look ahead up to two weeks
            if self.is_trading_day(d):
                return self._at(d, self.connect_time)
            d += timedelta(days=1)
        raise RuntimeError("no trading day found within 14 days")

    def phase(self, now: datetime) -> Phase:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        now = now.astimezone(self.tz)
        d = now.date()
        if not self.is_trading_day(d):
            return Phase.WAIT
        t = now.timetz().replace(tzinfo=None)
        if t < self.connect_time:
            return Phase.WAIT
        if t < self.record_start:
            return Phase.CONNECT
        if t < self.record_end:
            return Phase.RECORD
        if t < self.verify_time:
            return Phase.WIND_DOWN
        return Phase.VERIFY

    def seconds_until_connect(self, now: datetime) -> float:
        return (self.next_connect(now) - now.astimezone(self.tz)).total_seconds()

    def record_end_at(self, d: date) -> datetime:
        return self._at(d, self.record_end)


def load_holidays(path: str | Path) -> frozenset[date]:
    """Load NSE holiday dates from a YAML file (list under key 'holidays')."""
    import yaml

    p = Path(path)
    if not p.exists():
        log.warning("holidays file %s not found; assuming no holidays", p)
        return frozenset()
    data = yaml.safe_load(p.read_text()) or {}
    out = set()
    for item in data.get("holidays", []) or []:
        if isinstance(item, date):
            out.add(item)
        elif isinstance(item, str):
            out.add(date.fromisoformat(item.strip()))
    return frozenset(out)

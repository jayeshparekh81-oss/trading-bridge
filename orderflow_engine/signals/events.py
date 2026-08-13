"""Event-calendar guard (Module R6).

Loads a hand-maintained events.yaml (committed to the repo) and answers whether a
given instant falls inside an event window. The engine uses this to block fresh
signals during high-event-risk windows (a toggle can downgrade-to-warn instead).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/
IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class Event:
    date: date
    window_start: time
    window_end: time
    label: str
    flow_bias: str = "none"


def _parse_time(s) -> time:
    hh, mm = str(s).split(":")
    return time(int(hh), int(mm))


def load_events(path: str | Path | None = None) -> list[Event]:
    p = Path(path) if path else HERE / "events.yaml"
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text()) or {}
    out = []
    for e in data.get("events", []) or []:
        d = e["date"]
        d = d if isinstance(d, date) else date.fromisoformat(str(d))
        out.append(Event(
            date=d,
            window_start=_parse_time(e.get("window_start", "09:15")),
            window_end=_parse_time(e.get("window_end", "15:30")),
            label=str(e.get("label", "")),
            flow_bias=str(e.get("flow_bias", "none")),
        ))
    return out


def active_event(events: list[Event], ts_ns: int) -> Optional[Event]:
    dt = datetime.fromtimestamp(ts_ns / 1e9, tz=IST)
    t = dt.time()
    for e in events:
        if e.date == dt.date() and e.window_start <= t <= e.window_end:
            return e
    return None

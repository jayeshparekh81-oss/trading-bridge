"""ReplayEngine — merge a recorded day into one deterministic event stream.

All instruments' tick rows plus the recorded events are merged into a single
time-ordered stream and delivered through a :class:`~replayer.consumer.Consumer`.

Ordering key (total order -> byte-identical G1 determinism):
    (primary_ts, ltt_or_-1, class, security_id_or_-1, tiebreak)
  * primary_ts = ts_recv_ns for ticks, ts_ns for events   (spec: ts primary)
  * ltt        = exchange last-trade-time, -1 for events   (spec: ltt tiebreak)
  * class      = 0 tick, 1 event (ticks lead events at an identical instant)
  * security_id then a per-source monotonic index          (final stable tiebreak)

The last two are an explicit EXTENSION of the spec's (ts, ltt) rule so that rows
sharing an identical (ts, ltt) still emit in one fixed order — required for a
reproducible stream. Merge is a heap over per-source sorted iterators: O(N log k)
with k = number of sources.
"""

from __future__ import annotations

import heapq
import logging
import time
from dataclasses import dataclass
from typing import Iterator

from recorder.schema import EVENT_COLUMNS, TICK_COLUMNS

from replayer.clock import Pacer
from replayer.consumer import Consumer
from replayer.source import Coverage, ReplaySource

log = logging.getLogger("replayer.engine")

CLASS_TICK = 0
CLASS_EVENT = 1
# ltt is epoch-seconds (< 2^31). Events carry no ltt; assigning them a sentinel
# ABOVE any real ltt keeps ltt literally the 2nd sort key (spec) while making
# events trail ticks at an identical instant.
EVENT_LTT_SENTINEL = 1 << 62


@dataclass
class EmittedEvent:
    key: tuple
    is_tick: bool
    ts_ns: int
    security_id: int | None
    payload: dict          # tick: reconstructed parsed row; event: {kind,detail,value_num}


@dataclass
class ReplaySummary:
    date: str
    status: str | None
    packets: int
    events: int
    instruments: int
    first_ts_ns: int | None
    last_ts_ns: int | None
    wall_s: float
    coverage: Coverage

    @property
    def total(self) -> int:
        return self.packets + self.events

    @property
    def span_s(self) -> float | None:
        if self.first_ts_ns is None or self.last_ts_ns is None:
            return None
        return (self.last_ts_ns - self.first_ts_ns) / 1e9

    @property
    def throughput(self) -> float:
        return self.total / self.wall_s if self.wall_s > 0 else 0.0


def _sorted_rows(table, columns, ts_col: str, is_tick: bool) -> list[tuple]:
    """Materialize a source's rows as (key, EmittedEvent) sorted by key.

    Sorting per-source (rather than trusting file order) guarantees a correct +
    deterministic merge even if a salvaged/consolidated file isn't perfectly
    time-ordered.
    """
    cols = {c: table.column(c).to_pylist() for c in columns if c in table.column_names}
    n = table.num_rows
    out: list[tuple] = []
    for i in range(n):
        row = {c: cols.get(c, [None] * n)[i] for c in columns}
        ts = row.get(ts_col)
        ts = int(ts) if ts is not None else 0
        sid = row.get("security_id")
        sid = int(sid) if sid is not None else -1
        if is_tick:
            ltt = row.get("ltt")
            ltt = int(ltt) if ltt is not None else -1
            key = (ts, ltt, CLASS_TICK, sid, i)
            parsed = dict(row)
            parsed["is_tick"] = True
            ev = EmittedEvent(key, True, ts, sid, parsed)
        else:
            key = (ts, EVENT_LTT_SENTINEL, CLASS_EVENT, sid, i)
            payload = {"kind": row.get("kind"), "detail": row.get("detail") or "",
                       "value_num": row.get("value_num")}
            ev = EmittedEvent(key, False, ts, None if sid < 0 else sid, payload)
        out.append((key, ev))
    out.sort(key=lambda t: t[0])
    return out


class ReplayEngine:
    def __init__(self, source: ReplaySource):
        self.source = source

    def _sources(self) -> list[list[tuple]]:
        streams: list[list[tuple]] = []
        for f in self.source.instrument_files():
            table = self.source.read_table(f)
            if table is None or table.num_rows == 0:
                continue
            streams.append(_sorted_rows(table, TICK_COLUMNS, "ts_recv_ns", True))
        ev = self.source.event_file()
        if ev is not None:
            table = self.source.read_table(ev)
            if table is not None and table.num_rows > 0:
                streams.append(_sorted_rows(table, EVENT_COLUMNS, "ts_ns", False))
        return streams

    def iter_events(self) -> Iterator[EmittedEvent]:
        """Yield every recorded tick + event in total-order. Deterministic."""
        streams = self._sources()
        # heapq merge of pre-sorted (key, EmittedEvent) lists; keys are a total
        # order so ties never depend on heap internals.
        for _key, ev in heapq.merge(*streams, key=lambda t: t[0]):
            yield ev

    def drive(self, consumer: Consumer, speed: str | float | None = "max",
              pacer: Pacer | None = None) -> ReplaySummary:
        """Replay the whole day into ``consumer`` at ``speed``; return a summary."""
        pacer = pacer if pacer is not None else Pacer(speed)
        packets = events = 0
        first_ts = last_ts = None
        t0 = time.monotonic()
        for ev in self.iter_events():
            pacer.wait(ev.ts_ns)
            if first_ts is None:
                first_ts = ev.ts_ns
            last_ts = ev.ts_ns
            if ev.is_tick:
                consumer.on_packet(ev.payload, ev.ts_ns)
                packets += 1
            else:
                p = ev.payload
                consumer.on_event(p["kind"], p["detail"], p["value_num"])
                events += 1
        wall = time.monotonic() - t0
        cov = self.source.coverage()
        return ReplaySummary(
            date=self.source.day_dir.name, status=cov.status, packets=packets,
            events=events, instruments=cov.tick_instruments, first_ts_ns=first_ts,
            last_ts_ns=last_ts, wall_s=wall, coverage=cov)

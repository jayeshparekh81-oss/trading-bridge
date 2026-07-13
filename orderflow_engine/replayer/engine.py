"""ReplayEngine — merge a recorded day into one deterministic event stream.

All instruments' tick rows, R1 depth rows, plus the recorded events are merged
into a single time-ordered stream and delivered through a
:class:`~replayer.consumer.Consumer`.

Ordering key (total order -> byte-identical G1 determinism):
    (primary_ts, ltt_or_sentinel, class, security_id_or_-1, tiebreak)
  * primary_ts = ts_recv_ns for ticks/depth, ts_ns for events   (spec: ts primary)
  * ltt        = exchange last-trade-time for ticks; graduated sentinels for depth
                 and events so that at an identical ts the emission order is
                 always tick -> depth -> event
  * class      = 0 tick, 1 depth, 2 event  (stable order at an identical key)
  * security_id then the row's GLOBAL index within its file  (final stable tiebreak)

Depth carries no ltt, so it uses a sentinel ABOVE any real ltt (< 2^31) but below
the event sentinel — this keeps ltt literally the 2nd sort key while making depth
trail ticks and lead events at an identical instant. The last two keys are an
explicit EXTENSION of the spec's (ts, ltt) rule so rows sharing an identical
(ts, ltt) still emit in one fixed order.

MEMORY/CPU (2026-07-13 full-day fix): the original implementation materialized
EVERY row of EVERY file as python dicts before merging (tens of GB on an 11M-event
day) and hid an O(n²·cols) allocation in the row builder (``.get``'s list default
was evaluated per cell). The merge is now TIME-SLICED: a cheap pre-pass reads only
each file's ts column, global slice boundaries are derived from the sorted ts
values (~SLICE_TARGET_ROWS rows per slice), and each slice materializes / merges /
frees only its own rows via row-group-pruned reads. The ordering key is IDENTICAL —
slices partition on the primary key (ts) and the tiebreak uses the row's global
index within its file — so the emitted stream is byte-identical to the original
algorithm (proven by the R2 determinism hash). Peak memory is one slice, not the
day.
"""

from __future__ import annotations

import heapq
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from recorder.depth_schema import DEPTH_COLUMNS
from recorder.schema import EVENT_COLUMNS, TICK_COLUMNS

from replayer.clock import Pacer
from replayer.consumer import Consumer
from replayer.source import Coverage, ReplaySource

log = logging.getLogger("replayer.engine")

CLASS_TICK = 0
CLASS_DEPTH = 1
CLASS_EVENT = 2
# ltt is epoch-seconds (< 2^31). Depth and events carry no ltt; graduated
# sentinels ABOVE any real ltt keep ltt literally the 2nd sort key (spec) while
# forcing tick -> depth -> event order at an identical instant.
DEPTH_LTT_SENTINEL = 1 << 40   # above any real ltt, below the event sentinel
EVENT_LTT_SENTINEL = 1 << 62

# Target rows per merge slice — bounds peak memory to roughly one slice's dicts.
SLICE_TARGET_ROWS = 150_000
# Heartbeat cadence for drive() progress lines (stderr).
HEARTBEAT_S = 30.0


def _rss_mb() -> float:
    try:
        with open("/proc/self/statm") as fh:
            pages = int(fh.read().split()[1])
        return pages * os.sysconf("SC_PAGESIZE") / (1024 ** 2)
    except (OSError, IndexError, ValueError):
        return 0.0


@dataclass
class EmittedEvent:
    key: tuple
    stream: str            # "tick" | "depth" | "event"
    ts_ns: int
    security_id: int | None
    payload: dict          # tick/depth: reconstructed row; event: {kind,detail,value_num}

    @property
    def is_tick(self) -> bool:
        """Back-compat: True only for tick rows (not depth, not events)."""
        return self.stream == "tick"

    @property
    def is_depth(self) -> bool:
        return self.stream == "depth"


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
    depth: int = 0

    @property
    def total(self) -> int:
        return self.packets + self.events + self.depth

    @property
    def span_s(self) -> float | None:
        if self.first_ts_ns is None or self.last_ts_ns is None:
            return None
        return (self.last_ts_ns - self.first_ts_ns) / 1e9

    @property
    def throughput(self) -> float:
        return self.total / self.wall_s if self.wall_s > 0 else 0.0


def _rows_to_events(table, columns, ts_col: str, stream: str,
                    global_idx: Optional[Sequence[int]] = None) -> list[tuple]:
    """Materialize a table's rows as (key, EmittedEvent) sorted by key.

    ``global_idx`` maps each table row to its GLOBAL row index within the source
    file (the deterministic tiebreak); None means the table IS the whole file
    (tiebreak = enumeration index, identical to the original algorithm). Sorting
    per-source (rather than trusting file order) guarantees a correct +
    deterministic merge even if a salvaged/consolidated file isn't perfectly
    time-ordered.
    """
    n = table.num_rows
    cols = {c: table.column(c).to_pylist() for c in columns if c in table.column_names}
    # 2026-07-13 fix: the previous per-row dict build used
    # ``cols.get(c, [None] * n)`` — python evaluates the default EAGERLY, so a
    # fresh n-element list was allocated per column per row -> O(n²·cols), which
    # made a full recorded day computationally unfinishable. Hoist it once.
    none_col = [None] * n
    arrs = [(c, cols.get(c, none_col)) for c in columns]
    out: list[tuple] = []
    for j in range(n):
        row = {c: a[j] for c, a in arrs}
        i = int(global_idx[j]) if global_idx is not None else j
        ts = row.get(ts_col)
        ts = int(ts) if ts is not None else 0
        sid = row.get("security_id")
        sid = int(sid) if sid is not None else -1
        if stream == "tick":
            ltt = row.get("ltt")
            ltt = int(ltt) if ltt is not None else -1
            key = (ts, ltt, CLASS_TICK, sid, i)
            parsed = dict(row)
            parsed["is_tick"] = True
            ev = EmittedEvent(key, "tick", ts, sid, parsed)
        elif stream == "depth":
            # depth has no ltt; a sentinel above real ltt puts it after ticks and
            # before events at an identical ts (deterministic total order).
            key = (ts, DEPTH_LTT_SENTINEL, CLASS_DEPTH, sid, i)
            parsed = dict(row)
            parsed["is_depth"] = True
            ev = EmittedEvent(key, "depth", ts, None if sid < 0 else sid, parsed)
        else:  # event
            key = (ts, EVENT_LTT_SENTINEL, CLASS_EVENT, sid, i)
            payload = {"kind": row.get("kind"), "detail": row.get("detail") or "",
                       "value_num": row.get("value_num")}
            ev = EmittedEvent(key, "event", ts, None if sid < 0 else sid, payload)
        out.append((key, ev))
    out.sort(key=lambda t: t[0])
    return out


def _sorted_rows(table, columns, ts_col: str, stream: str) -> list[tuple]:
    """Back-compat wrapper: whole-table conversion (tiebreak = row index)."""
    return _rows_to_events(table, columns, ts_col, stream, global_idx=None)


class _FileStream:
    """Per-file lazy source: ts pre-pass + row-group-pruned slice reads."""

    __slots__ = ("path", "columns", "ts_col", "stream", "ts", "_pf", "_rg_ends")

    def __init__(self, path, columns, ts_col: str, stream: str):
        self.path = path
        self.columns = columns
        self.ts_col = ts_col
        self.stream = stream
        self._pf = pq.ParquetFile(str(path))
        # ts pre-pass: ONLY the timestamp column. Nulls -> 0, matching the row
        # builder's ``int(ts) if ts is not None else 0`` so slice membership and
        # sort keys always agree.
        col = pq.read_table(str(path), columns=[ts_col]).column(ts_col)
        self.ts = pc.fill_null(col, 0).cast(pa.int64()).to_numpy(zero_copy_only=False)
        self._rg_ends = np.cumsum(
            [self._pf.metadata.row_group(i).num_rows
             for i in range(self._pf.metadata.num_row_groups)])

    @property
    def num_rows(self) -> int:
        return int(self.ts.size)

    def slice_events(self, lo: int, hi: int) -> list[tuple]:
        """(key, EmittedEvent) rows with lo <= ts < hi, sorted; [] if none."""
        mask = (self.ts >= lo) & (self.ts < hi)
        if not mask.any():
            return []
        gidx = np.nonzero(mask)[0]
        # contiguous row-group span covering the needed rows (pruned read)
        rg_lo = int(np.searchsorted(self._rg_ends, gidx[0], side="right"))
        rg_hi = int(np.searchsorted(self._rg_ends, gidx[-1], side="right"))
        start = 0 if rg_lo == 0 else int(self._rg_ends[rg_lo - 1])
        tbl = self._pf.read_row_groups(list(range(rg_lo, rg_hi + 1)))
        local = mask[start:start + tbl.num_rows]
        sub = tbl.filter(pa.array(local))
        return _rows_to_events(sub, self.columns, self.ts_col, self.stream, gidx)


class ReplayEngine:
    def __init__(self, source: ReplaySource):
        self.source = source

    def _file_streams(self) -> list[_FileStream]:
        """Build per-file streams; an unreadable/corrupt file is logged and
        skipped, never fatal (same tolerance as ReplaySource.read_table)."""
        specs = [(f, TICK_COLUMNS, "ts_recv_ns", "tick")
                 for f in self.source.instrument_files()]
        specs += [(f, DEPTH_COLUMNS, "ts_recv_ns", "depth")
                  for f in self.source.depth_files()]
        ev = self.source.event_file()
        if ev is not None:
            specs.append((ev, EVENT_COLUMNS, "ts_ns", "event"))
        streams: list[_FileStream] = []
        for path, columns, ts_col, stream in specs:
            try:
                fs = _FileStream(path, columns, ts_col, stream)
            except Exception as exc:  # noqa: BLE001 - corrupt/truncated file
                log.warning("replay: skipping unreadable file %s (%s)",
                            Path(path).name, exc)
                continue
            if fs.num_rows:
                streams.append(fs)
        return streams

    @staticmethod
    def _slice_bounds(streams: list[_FileStream]) -> list[int]:
        """Half-open slice boundaries derived from the sorted global ts values
        (~SLICE_TARGET_ROWS rows per slice). Data-derived, so a null-ts outlier
        or a clustered burst can't explode the slice count."""
        all_ts = np.sort(np.concatenate([fs.ts for fs in streams]))
        bounds = np.unique(all_ts[::SLICE_TARGET_ROWS]).tolist()
        bounds.append(int(all_ts[-1]) + 1)
        return [int(b) for b in bounds]

    def iter_events(self, _streams: list[_FileStream] | None = None) -> Iterator[EmittedEvent]:
        """Yield every recorded tick + depth + event in total-order. Deterministic.

        Slices partition on the primary sort key (ts), so emitting slice-by-slice
        preserves the exact total order of a whole-day merge.
        """
        streams = _streams if _streams is not None else self._file_streams()
        if not streams:
            return
        bounds = self._slice_bounds(streams)
        for lo, hi in zip(bounds[:-1], bounds[1:]):
            slice_lists = [fs.slice_events(lo, hi) for fs in streams]
            slice_lists = [s for s in slice_lists if s]
            if not slice_lists:
                continue
            for _key, ev in heapq.merge(*slice_lists, key=lambda t: t[0]):
                yield ev

    def drive(self, consumer: Consumer, speed: str | float | None = "max",
              pacer: Pacer | None = None) -> ReplaySummary:
        """Replay the whole day into ``consumer`` at ``speed``; return a summary.

        Emits a heartbeat to stderr every HEARTBEAT_S seconds — events done/total
        (%), elapsed, RSS — so a long replay is never silent/ambiguous.
        """
        pacer = pacer if pacer is not None else Pacer(speed)
        streams = self._file_streams()
        total = sum(fs.num_rows for fs in streams)
        packets = events = depth = 0
        first_ts = last_ts = None
        t0 = time.monotonic()
        next_beat = t0 + HEARTBEAT_S
        for ev in self.iter_events(_streams=streams):
            pacer.wait(ev.ts_ns)
            if first_ts is None:
                first_ts = ev.ts_ns
            last_ts = ev.ts_ns
            if ev.stream == "tick":
                consumer.on_packet(ev.payload, ev.ts_ns)
                packets += 1
            elif ev.stream == "depth":
                consumer.on_depth(ev.payload, ev.ts_ns)
                depth += 1
            else:
                p = ev.payload
                consumer.on_event(p["kind"], p["detail"], p["value_num"])
                events += 1
            now = time.monotonic()
            if now >= next_beat:
                done = packets + events + depth
                pct = 100.0 * done / total if total else 100.0
                print(f"replay heartbeat: {done:,}/{total:,} events ({pct:.1f}%) "
                      f"elapsed={now - t0:.0f}s rss={_rss_mb():.0f}MB",
                      file=sys.stderr, flush=True)
                next_beat = now + HEARTBEAT_S
        wall = time.monotonic() - t0
        cov = self.source.coverage()
        return ReplaySummary(
            date=self.source.day_dir.name, status=cov.status, packets=packets,
            events=events, depth=depth, instruments=cov.tick_instruments,
            first_ts_ns=first_ts, last_ts_ns=last_ts, wall_s=wall, coverage=cov)

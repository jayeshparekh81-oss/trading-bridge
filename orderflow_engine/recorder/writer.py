"""Buffered, crash-safe parquet writer (one per instrument, plus an events writer).

Design (per R0 spec):
  * In-memory buffer, flushed every ``flush_interval`` seconds (driven by the
    caller) or when the buffer exceeds ``max_buffer`` rows.
  * Primary mode: a single daily file built incrementally with
    ``pyarrow.ParquetWriter`` row-groups, written to ``<name>.parquet.tmp``.
    Each flush is followed by ``fsync``. On clean close the footer is written
    and the file is atomically promoted (``os.replace``) to ``<name>.parquet``.
    => a mid-flush kill never leaves a corrupt *final* file (only a .tmp).
  * Fallback mode: on ANY writer error, the instrument switches to part-files
    (``parts/<name>/part-0001.parquet`` ...). Each part is a complete, closed,
    atomically-written parquet. At EOD these are consolidated into the single
    daily file. This bounds data loss to at most one flush interval.

Atomic write primitive everywhere: write ``*.tmp`` -> fsync -> ``os.replace``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import pyarrow as pa
import pyarrow.parquet as pq

from recorder.ratelimit import ThrottledLogger
from recorder.schema import (
    EVENT_COLUMNS, EVENT_SCHEMA, TICK_SCHEMA, normalize_event_row,
    normalize_tick_row,
)

log = logging.getLogger("recorder.writer")

# Writer exceptions during a disk-full episode fire on EVERY flush (per 5s, per
# instrument). Throttle the full tracebacks to 1 per site per interval so the
# error path can't itself spam the disk/logs (2026-07-09 incident). Overridable
# via ``set_error_log_interval`` from config at startup.
_throttle = ThrottledLogger(log, interval_s=300.0)


def set_error_log_interval(interval_s: float) -> None:
    """Set the writer's throttled-error interval (called once from config)."""
    _throttle.interval_s = float(interval_s)

# All parquet output (parts, consolidated instrument files, events) is written
# with zstd. zstd level 3 gives ~3-4x better ratio than the pyarrow default
# (snappy) at negligible CPU — the 2026-07-09 disk-full incident showed the raw
# footprint matters. Kept as module constants so every write path stays in sync
# and the unit test can assert the codec.
PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 3


def _fsync_path(path: Path) -> None:
    """fsync a file and its parent directory so the rename is durable."""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _atomic_write_table(table: pa.Table, dest: Path) -> None:
    """Write a complete parquet file atomically (tmp -> fsync -> replace)."""
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    pq.write_table(table, str(tmp), compression=PARQUET_COMPRESSION,
                   compression_level=PARQUET_COMPRESSION_LEVEL)
    _fsync_path(tmp)
    os.replace(str(tmp), str(dest))
    # durability of the directory entry for the rename
    dfd = os.open(str(dest.parent), os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


class InstrumentWriter:
    """Buffered writer for a single instrument's daily ticks."""

    def __init__(self, out_dir: Path, symbol: str, security_id: int,
                 schema: pa.Schema = TICK_SCHEMA, max_buffer: int = 20_000):
        self.out_dir = Path(out_dir)
        self.symbol = symbol
        self.security_id = security_id
        self.schema = schema
        self.max_buffer = max_buffer

        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._base = f"{symbol}_{security_id}"
        self.final_path = self.out_dir / f"{self._base}.parquet"
        self.tmp_path = self.out_dir / f"{self._base}.parquet.tmp"
        self.parts_dir = self.out_dir / "parts" / self._base

        self._buffer: list[dict] = []
        self._writer: Optional[pq.ParquetWriter] = None
        self._writer_fh = None
        self.rows_written = 0
        self.part_mode = False
        self._part_idx = 0
        self.closed = False

    # -- buffering -----------------------------------------------------------
    def add(self, row: dict) -> None:
        self._buffer.append(normalize_tick_row(row))
        if len(self._buffer) >= self.max_buffer:
            self.flush()

    def _buffer_table(self) -> pa.Table:
        return pa.Table.from_pylist(self._buffer, schema=self.schema)

    # -- flushing ------------------------------------------------------------
    def flush(self) -> None:
        if not self._buffer:
            return
        table = self._buffer_table()
        try:
            if self.part_mode:
                self._flush_part(table)
            else:
                self._flush_primary(table)
        except Exception as exc:  # noqa: BLE001 - any writer error -> fallback
            if not self.part_mode:
                # One-time transition per instrument (not the spam source).
                log.error("writer flush failed for %s (%s); switching to part-file mode",
                          self._base, exc)
                self._enter_part_mode()
            try:
                self._flush_part(table)
            except Exception:  # noqa: BLE001
                # Spam source during disk-full: fires every flush. Throttle the
                # traceback to 1 per interval per instrument; the rest aggregate.
                _throttle.exception(f"partfail:{self._base}",
                                    "part-file flush failed for %s; %d rows dropped",
                                    self._base, len(self._buffer))
        self.rows_written += len(self._buffer)
        self._buffer.clear()

    def _flush_primary(self, table: pa.Table) -> None:
        if self._writer is None:
            self._writer_fh = open(self.tmp_path, "wb")
            self._writer = pq.ParquetWriter(
                self._writer_fh, self.schema,
                compression=PARQUET_COMPRESSION,
                compression_level=PARQUET_COMPRESSION_LEVEL)
        self._writer.write_table(table)
        self._writer_fh.flush()
        os.fsync(self._writer_fh.fileno())

    def _enter_part_mode(self) -> None:
        self.part_mode = True
        self.parts_dir.mkdir(parents=True, exist_ok=True)
        # Best-effort: finalize whatever the primary writer already wrote so it
        # isn't lost, then abandon primary mode.
        if self._writer is not None:
            try:
                self._writer.close()
                self._writer_fh.flush()
                os.fsync(self._writer_fh.fileno())
                self._writer_fh.close()
                # Promote the partial-but-valid primary file into a part so it
                # participates in consolidation.
                salvage = self.parts_dir / "part-0000.parquet"
                os.replace(str(self.tmp_path), str(salvage))
            except Exception:  # noqa: BLE001
                log.warning("could not salvage primary writer for %s", self._base)
            finally:
                self._writer = None
                self._writer_fh = None

    def _flush_part(self, table: pa.Table) -> None:
        self._part_idx += 1
        dest = self.parts_dir / f"part-{self._part_idx:04d}.parquet"
        _atomic_write_table(table, dest)

    # -- close / consolidate -------------------------------------------------
    def close(self) -> None:
        """Flush remaining buffer and produce the final daily file atomically."""
        if self.closed:
            return
        self.flush()
        if self.part_mode:
            self._consolidate_parts()
        else:
            self._finalize_primary()
        self.closed = True

    def _finalize_primary(self) -> None:
        if self._writer is None:
            # Nothing was ever written; emit an empty-but-valid file so the
            # session verifier sees the instrument.
            _atomic_write_table(pa.Table.from_pylist([], schema=self.schema),
                                self.final_path)
            return
        self._writer.close()          # writes the parquet footer
        self._writer_fh.flush()
        os.fsync(self._writer_fh.fileno())
        self._writer_fh.close()
        self._writer = None
        self._writer_fh = None
        _fsync_path(self.tmp_path)
        os.replace(str(self.tmp_path), str(self.final_path))
        dfd = os.open(str(self.final_path.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    def _consolidate_parts(self) -> None:
        parts = sorted(self.parts_dir.glob("part-*.parquet"))
        if not parts:
            _atomic_write_table(pa.Table.from_pylist([], schema=self.schema),
                                self.final_path)
            return
        tables = []
        for p in parts:
            try:
                tables.append(pq.read_table(str(p)))
            except Exception:  # noqa: BLE001
                log.error("skipping unreadable part %s during consolidation", p)
        merged = pa.concat_tables(tables) if tables else \
            pa.Table.from_pylist([], schema=self.schema)
        _atomic_write_table(merged, self.final_path)


class EventWriter:
    """Append-only events writer (parts always; consolidated at close)."""

    def __init__(self, out_dir: Path):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.final_path = self.out_dir / "events.parquet"
        self.parts_dir = self.out_dir / "parts" / "events"
        self._buffer: list[dict] = []
        self._idx = 0
        self.closed = False

    def add(self, ts_ns: int, kind: str, detail: str = "",
            security_id: Optional[int] = None, value_num: Optional[float] = None) -> None:
        self._buffer.append(normalize_event_row({
            "ts_ns": ts_ns, "kind": kind, "security_id": security_id,
            "detail": detail, "value_num": value_num,
        }))
        # Events are low-volume and high-value: persist each batch immediately.
        self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        self.parts_dir.mkdir(parents=True, exist_ok=True)
        self._idx += 1
        table = pa.Table.from_pylist(self._buffer, schema=EVENT_SCHEMA)
        _atomic_write_table(table, self.parts_dir / f"part-{self._idx:04d}.parquet")
        self._buffer.clear()

    def close(self) -> None:
        if self.closed:
            return
        self.flush()
        parts = sorted(self.parts_dir.glob("part-*.parquet"))
        if parts:
            tables = [pq.read_table(str(p)) for p in parts]
            merged = pa.concat_tables(tables)
        else:
            merged = pa.Table.from_pylist([], schema=EVENT_SCHEMA)
        _atomic_write_table(merged, self.final_path)
        self.closed = True

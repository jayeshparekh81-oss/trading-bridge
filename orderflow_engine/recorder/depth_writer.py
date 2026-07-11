"""Journal-style depth writer (Module R1) — one per instrument.

PRIMARY (and only) path is part-file journaling, per the kdb+tick doctrine
adopted after the 2026-07-10 OOM: buffer a bounded number of rows, then
open -> write_table -> close -> fsync -> atomic-rename a complete part, retaining
NOTHING. No long-lived ``ParquetWriter`` ever exists, so the writer-metadata leak
that hung the host in R0 is structurally impossible here. Parts consolidate into
the single daily file at close (streaming, one batch at a time).

Reuses the crash-safe primitives from ``recorder.writer`` (atomic write, streaming
consolidation, throttled error logging) WITHOUT modifying that shared module, so
R0's InstrumentWriter is byte-for-byte untouched.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pyarrow as pa

from recorder.depth_schema import DEPTH_SCHEMA, normalize_depth_row
from recorder.ratelimit import ThrottledLogger
from recorder.writer import _atomic_write_table, _stream_consolidate

log = logging.getLogger("recorder.depth_writer")
_throttle = ThrottledLogger(log, interval_s=300.0)


def set_error_log_interval(interval_s: float) -> None:
    _throttle.interval_s = float(interval_s)


class DepthWriter:
    """Buffered, journal-only writer for one instrument's depth stream."""

    def __init__(self, out_dir: Path, symbol: str, security_id: int,
                 schema: pa.Schema = DEPTH_SCHEMA, max_buffer: int = 5_000):
        self.out_dir = Path(out_dir)
        self.symbol = symbol
        self.security_id = security_id
        self.schema = schema
        self.max_buffer = max_buffer

        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._base = f"{symbol}_{security_id}"
        self.final_path = self.out_dir / f"{self._base}.parquet"
        self.parts_dir = self.out_dir / "parts" / self._base

        self._buffer: list[dict] = []
        self._part_idx = 0
        self.rows_written = 0
        self.dropped = 0
        self.parts_sealed = 0
        # journal writer is ALWAYS in part mode — the attribute mirrors R0's
        # InstrumentWriter so shared tooling (mem watermark) reads it uniformly.
        self.rotated = True
        self.closed = False

    def add(self, row: dict) -> None:
        self._buffer.append(normalize_depth_row(row))
        if len(self._buffer) >= self.max_buffer:
            self.flush()

    def _next_part(self) -> Path:
        self._part_idx += 1
        return self.parts_dir / f"part-{self._part_idx:04d}.parquet"

    def flush(self) -> None:
        """Seal the buffer as a complete part, retaining nothing on success."""
        if not self._buffer:
            return
        table = pa.Table.from_pylist(self._buffer, schema=self.schema)
        try:
            self.parts_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_table(table, self._next_part())
            self.rows_written += len(self._buffer)
            self.parts_sealed += 1
        except Exception:  # noqa: BLE001 - disk-full etc.: drop + count, never raise
            self.dropped += len(self._buffer)
            _throttle.exception(f"depthpart:{self._base}",
                                "depth part flush failed for %s; %d rows dropped",
                                self._base, len(self._buffer))
        self._buffer.clear()

    def close(self) -> None:
        """Flush the tail and consolidate all parts into the daily file."""
        if self.closed:
            return
        self.flush()
        parts = sorted(self.parts_dir.glob("part-*.parquet"))
        if parts:
            _stream_consolidate(parts, self.final_path, self.schema)
        else:
            _atomic_write_table(pa.Table.from_pylist([], schema=self.schema),
                                self.final_path)
        self.closed = True

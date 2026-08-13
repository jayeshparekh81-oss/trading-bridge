"""Writer tests: atomicity, part-file fallback, consolidation, round-trip."""

from __future__ import annotations

import pyarrow.parquet as pq
import pytest

from recorder.schema import TICK_COLUMNS
from recorder.writer import EventWriter, InstrumentWriter
from tests.fixtures import synthetic as S
from recorder import parser as P


def _rows(n, sid=53001, start_seq=0):
    rows = []
    for i in range(n):
        t = P.parse_packet(S.make_full(sid, volume=1000 + i, ltp=100.0 + i))
        t["ts_recv_ns"] = 1_700_000_000_000_000_000 + i
        t["seq_local"] = start_seq + i
        rows.append(t)
    return rows


def test_roundtrip_primary(tmp_path):
    w = InstrumentWriter(tmp_path, "NIFTY", 53001)
    for r in _rows(10):
        w.add(r)
    w.flush()
    w.close()
    assert w.final_path.exists()
    assert not w.tmp_path.exists()
    table = pq.read_table(str(w.final_path))
    assert table.num_rows == 10
    assert set(table.column_names) == set(TICK_COLUMNS)
    # values preserved
    assert table.column("volume").to_pylist()[0] == 1000
    assert table.column("seq_local").to_pylist() == list(range(10))


def test_no_final_file_until_close(tmp_path):
    """Mid-flush kill (never call close) must leave NO corrupt final file."""
    w = InstrumentWriter(tmp_path, "NIFTY", 53001)
    for r in _rows(5):
        w.add(r)
    w.flush()  # data on disk in .tmp, footer not yet written
    assert w.tmp_path.exists()
    assert not w.final_path.exists()  # final only appears atomically at close
    # simulate crash: process dies here. The .tmp is not a valid final file,
    # but crucially there is no half-written *.parquet a reader would trust.


def test_empty_instrument_produces_valid_file(tmp_path):
    w = InstrumentWriter(tmp_path, "VIX", 21)
    w.close()
    assert w.final_path.exists()
    assert pq.read_table(str(w.final_path)).num_rows == 0


def test_part_mode_fallback_and_consolidation(tmp_path, monkeypatch):
    w = InstrumentWriter(tmp_path, "NIFTY", 53001)
    # First flush uses primary; force primary to fail so it switches to parts.
    orig = w._flush_primary
    calls = {"n": 0}

    def boom(table):
        calls["n"] += 1
        raise IOError("simulated disk error")

    monkeypatch.setattr(w, "_flush_primary", boom)
    for r in _rows(4):
        w.add(r)
    w.flush()
    assert w.part_mode is True
    assert calls["n"] >= 1
    # more data after switch -> part files
    for r in _rows(3, start_seq=100):
        w.add(r)
    w.flush()
    w.close()
    assert w.final_path.exists()
    table = pq.read_table(str(w.final_path))
    assert table.num_rows == 7  # all rows recovered across the failure


def test_event_writer_roundtrip(tmp_path):
    ew = EventWriter(tmp_path)
    ew.add(1, "SESSION", "start")
    ew.add(2, "SUBSCRIBE", "NIFTY", security_id=53001)
    ew.add(3, "GAP", "gap>3s", security_id=53001, value_num=4.2)
    ew.close()
    assert ew.final_path.exists()
    t = pq.read_table(str(ew.final_path))
    assert t.num_rows == 3
    assert t.column("kind").to_pylist() == ["SESSION", "SUBSCRIBE", "GAP"]
    assert t.column("value_num").to_pylist()[2] == pytest.approx(4.2)


def _column_codecs(path):
    """Return the set of compression codecs used across all row-group columns."""
    md = pq.ParquetFile(str(path)).metadata
    codecs = set()
    for rg in range(md.num_row_groups):
        for col in range(md.num_columns):
            codecs.add(md.row_group(rg).column(col).compression)
    return codecs


def test_instrument_file_is_zstd_and_readable(tmp_path):
    """Primary (single-writer) daily file is zstd-compressed and round-trips."""
    w = InstrumentWriter(tmp_path, "NIFTY", 53001)
    for r in _rows(50):
        w.add(r)
    w.flush()
    w.close()
    assert _column_codecs(w.final_path) == {"ZSTD"}
    assert pq.read_table(str(w.final_path)).num_rows == 50


def test_part_files_and_consolidated_are_zstd(tmp_path):
    """Part-mode parts AND the consolidated output are both zstd."""
    w = InstrumentWriter(tmp_path, "NIFTY", 53001)
    w._enter_part_mode()
    for r in _rows(20):
        w.add(r)
    w.flush()
    parts = sorted(w.parts_dir.glob("part-*.parquet"))
    assert parts, "expected at least one part file"
    assert _column_codecs(parts[0]) == {"ZSTD"}
    w.close()
    assert _column_codecs(w.final_path) == {"ZSTD"}
    assert pq.read_table(str(w.final_path)).num_rows == 20


def test_event_file_is_zstd(tmp_path):
    ew = EventWriter(tmp_path)
    ew.add(1, "SESSION", "start")
    ew.add(2, "GAP", "gap>3s", security_id=53001, value_num=4.2)
    ew.close()
    assert _column_codecs(ew.final_path) == {"ZSTD"}


# --- writer rotation (2026-07-10 OOM/hang) ---------------------------------

def _flush_each(w, rows, per_flush):
    """Feed rows in batches of `per_flush`, flushing after each batch."""
    for i in range(0, len(rows), per_flush):
        for r in rows[i:i + per_flush]:
            w.add(r)
        w.flush()


def test_rotation_seals_parts_and_bounds_open_rowgroups(tmp_path):
    w = InstrumentWriter(tmp_path, "NIFTY", 53001, rotate_after_rowgroups=2)
    _flush_each(w, _rows(10), per_flush=1)   # 10 flushes => 10 row-groups
    assert w.rotated is True
    # 10 row-groups / rotate-every-2 => 5 sealed parts, nothing left open beyond
    # the rotation bound.
    assert len(sorted(w.parts_dir.glob("part-*.parquet"))) == 5
    assert w._rowgroups < 2
    w.close()
    assert w.final_path.exists()
    assert not w.tmp_path.exists()
    assert pq.read_table(str(w.final_path)).num_rows == 10


def test_rotation_output_parity_with_single_writer(tmp_path):
    """Rotated+consolidated output must equal the old single-writer output."""
    rows = _rows(37)
    a = InstrumentWriter(tmp_path / "norot", "NIFTY", 53001)
    _flush_each(a, rows, per_flush=4)
    a.close()

    b = InstrumentWriter(tmp_path / "rot", "NIFTY", 53001, rotate_after_rowgroups=3)
    _flush_each(b, rows, per_flush=4)
    b.close()

    ta = pq.read_table(str(a.final_path))
    tb = pq.read_table(str(b.final_path))
    assert ta.num_rows == tb.num_rows == 37
    assert ta.schema.equals(tb.schema)
    # full value parity, including row ORDER (parts must merge chronologically)
    assert ta.to_pydict() == tb.to_pydict()
    assert tb.column("seq_local").to_pylist() == list(range(37))
    assert _column_codecs(b.final_path) == {"ZSTD"}


def test_rotation_tail_rows_are_not_lost(tmp_path):
    """Rows written after the last rotation still land in the final file."""
    w = InstrumentWriter(tmp_path, "NIFTY", 53001, rotate_after_rowgroups=2)
    _flush_each(w, _rows(5), per_flush=1)   # 5 row-groups: 2 rotations + 1 open
    w.close()
    assert pq.read_table(str(w.final_path)).column("seq_local").to_pylist() == \
        list(range(5))


def test_part_mode_after_rotation_preserves_order(tmp_path, monkeypatch):
    """A disk error mid-session must not sort its salvaged part before earlier ones."""
    w = InstrumentWriter(tmp_path, "NIFTY", 53001, rotate_after_rowgroups=2)
    _flush_each(w, _rows(4), per_flush=1)          # rotates twice -> parts 1,2
    assert w.rotated is True
    monkeypatch.setattr(w, "_flush_primary",
                        lambda table: (_ for _ in ()).throw(IOError("disk full")))
    _flush_each(w, _rows(3, start_seq=100), per_flush=3)   # -> part mode
    assert w.part_mode is True
    w.close()
    seqs = pq.read_table(str(w.final_path)).column("seq_local").to_pylist()
    assert seqs == [0, 1, 2, 3, 100, 101, 102]     # chronological, not scrambled


def test_consolidation_skips_unreadable_part(tmp_path):
    w = InstrumentWriter(tmp_path, "NIFTY", 53001, rotate_after_rowgroups=1)
    _flush_each(w, _rows(4), per_flush=2)          # -> 2 sealed parts
    parts = sorted(w.parts_dir.glob("part-*.parquet"))
    assert len(parts) == 2
    parts[1].write_bytes(b"not a parquet file")    # corrupt the second part
    w.close()
    # the readable part still consolidates; the corrupt one is skipped, not fatal
    assert pq.read_table(str(w.final_path)).num_rows == 2


def test_event_writer_streaming_consolidation_orders_and_counts(tmp_path):
    ew = EventWriter(tmp_path)
    for i in range(50):
        ew.add(i, "GAP", f"g{i}", security_id=53001, value_num=float(i))
    ew.close()
    t = pq.read_table(str(ew.final_path))
    assert t.num_rows == 50
    assert t.column("value_num").to_pylist() == [float(i) for i in range(50)]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

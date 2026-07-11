"""Tests for the journal-only DepthWriter (Module R1)."""

from __future__ import annotations

import pyarrow.parquet as pq

from recorder import depth_writer as DW
from recorder.depth_schema import DEPTH_COLUMNS, SIDE_ASK, SIDE_BID
from recorder.depth_writer import DepthWriter


def _row(ts, side=SIDE_BID, **extra):
    r = {"ts_recv_ns": ts, "side": side, "security_id": 1333}
    for i in range(1, 21):
        r[f"price_{i}"] = 100.0 + i
        r[f"qty_{i}"] = i
        r[f"orders_{i}"] = 1
    r.update(extra)
    return r


def test_journal_writes_parts_never_holds_writer(tmp_path):
    w = DepthWriter(tmp_path, "NIFTY_FUT", 1333, max_buffer=1000)
    for k in range(5):
        w.add(_row(k))
    w.flush()
    parts = list((tmp_path / "parts" / "NIFTY_FUT_1333").glob("part-*.parquet"))
    assert len(parts) == 1               # one sealed part per flush
    assert w.parts_sealed == 1
    # writer holds no open handle — journal retains nothing
    assert not hasattr(w, "_writer") or getattr(w, "_writer", None) is None


def test_max_buffer_auto_flush(tmp_path):
    w = DepthWriter(tmp_path, "X", 7, max_buffer=3)
    for k in range(7):
        w.add(_row(k))
    # 7 rows, buffer 3 -> two auto-flushes (rows 0-2, 3-5), 1 buffered
    assert w.parts_sealed == 2
    w.close()
    assert w.parts_sealed == 3           # tail flushed on close


def test_close_consolidates_parity(tmp_path):
    w = DepthWriter(tmp_path, "Y", 9, max_buffer=2)
    rows = [_row(k, side=(SIDE_BID if k % 2 == 0 else SIDE_ASK)) for k in range(10)]
    for r in rows:
        w.add(r)
    w.close()
    final = tmp_path / "Y_9.parquet"
    assert final.exists()
    tbl = pq.read_table(str(final))
    assert tbl.num_rows == 10                       # no rows lost
    assert tbl.column_names == DEPTH_COLUMNS
    # order + values preserved through part -> consolidate
    assert tbl.column("ts_recv_ns").to_pylist() == list(range(10))
    assert tbl.column("side").to_pylist() == [r["side"] for r in rows]


def test_empty_close_writes_valid_empty_file(tmp_path):
    w = DepthWriter(tmp_path, "Z", 3)
    w.close()
    final = tmp_path / "Z_3.parquet"
    assert final.exists()
    assert pq.read_table(str(final)).num_rows == 0


def test_write_error_drops_not_raises(tmp_path, monkeypatch):
    w = DepthWriter(tmp_path, "E", 1, max_buffer=100)
    w.add(_row(1))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(DW, "_atomic_write_table", boom)
    w.flush()                     # must not raise
    assert w.dropped == 1
    assert w.rows_written == 0

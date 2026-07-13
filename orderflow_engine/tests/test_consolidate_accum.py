"""Regression: _stream_consolidate must ACCUMULATE tiny parts into big row-groups.

2026-07-13: the depth recorder's 2s journal flush produced ~8,800 tiny parts per
instrument; the naive per-part path wrote one near-empty row-group per part, so
per-row-group metadata dominated the output (127MB half-file) and risked the 1G
container cap. The fix buffers input rows to ~CONSOLIDATE_BATCH_ROWS before each
write, so a many-tiny-parts day consolidates into a handful of healthy row-groups.
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

from recorder.depth_schema import DEPTH_SCHEMA, normalize_depth_row
from recorder.writer import CONSOLIDATE_BATCH_ROWS, _stream_consolidate

N_PARTS = 500
ROWS_PER_PART = 10


def _write_parts(parts_dir):
    parts_dir.mkdir(parents=True)
    paths = []
    seq = 0
    for i in range(N_PARTS):
        rows = []
        for _ in range(ROWS_PER_PART):
            rows.append(normalize_depth_row(
                {"ts_recv_ns": seq, "seq_local": seq, "security_id": 1,
                 "side": seq % 2, "price_1": 100.0 + seq}))
            seq += 1
        p = parts_dir / f"part-{i:05d}.parquet"
        pq.write_table(pa.Table.from_pylist(rows, schema=DEPTH_SCHEMA), str(p))
        paths.append(p)
    return paths


def test_many_tiny_parts_accumulate_into_few_row_groups(tmp_path):
    parts = _write_parts(tmp_path / "parts")
    dest = tmp_path / "final.parquet"
    total = N_PARTS * ROWS_PER_PART                     # 5,000 rows

    rows = _stream_consolidate(parts, dest, DEPTH_SCHEMA)
    assert rows == total

    pf = pq.ParquetFile(str(dest))
    assert pf.metadata.num_rows == total
    # the whole point: NOT one row-group per part (500) — accumulated (5000 rows
    # < 65,536 -> a single row-group)
    expected_groups = -(-total // CONSOLIDATE_BATCH_ROWS)   # ceil
    assert pf.metadata.num_row_groups == expected_groups
    assert pf.metadata.num_row_groups < N_PARTS

    # order + content preserved across the accumulation boundary
    t = pq.read_table(str(dest))
    assert t.column("ts_recv_ns").to_pylist() == list(range(total))
    assert t.column("price_1").to_pylist()[0] == 100.0
    assert t.column("price_1").to_pylist()[-1] == 100.0 + total - 1


def test_unreadable_part_still_skipped(tmp_path):
    parts = _write_parts(tmp_path / "parts")
    bad = tmp_path / "parts" / "part-00250.parquet"
    bad.write_bytes(b"corrupt")                          # overwrite one mid-list
    dest = tmp_path / "final.parquet"
    skipped = []
    rows = _stream_consolidate(sorted((tmp_path / "parts").glob("part-*.parquet")),
                               dest, DEPTH_SCHEMA, on_unreadable=skipped.append)
    assert len(skipped) == 1 and skipped[0].name == "part-00250.parquet"
    assert rows == (N_PARTS - 1) * ROWS_PER_PART

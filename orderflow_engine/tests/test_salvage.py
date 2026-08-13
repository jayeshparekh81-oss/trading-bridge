"""Salvage tests: consolidate readable parts, quarantine corrupt ones, PARTIAL."""

from __future__ import annotations

import json

import pyarrow.parquet as pq

from recorder import parser as P
from recorder.salvage import salvage_day
from recorder.writer import _atomic_write_table, InstrumentWriter
from tests.fixtures import synthetic as S


def _write_parts(day_dir, name, sid, n_parts, rows_per=5, start=0):
    """Create n_parts good part-files for an instrument under parts/<name>_<sid>."""
    w = InstrumentWriter(day_dir, name, sid)
    w._enter_part_mode()
    seq = start
    for _ in range(n_parts):
        for i in range(rows_per):
            t = P.parse_packet(S.make_full(sid, volume=1000 + seq, ltp=100.0 + seq))
            t["ts_recv_ns"] = 1_700_000_000_000_000_000 + seq
            t["seq_local"] = seq
            w.add(t)
            seq += 1
        w.flush()
    return w.parts_dir


def test_salvage_consolidates_readable_parts(tmp_path):
    day = tmp_path / "2026-07-09"
    day.mkdir()
    parts_dir = _write_parts(day, "NIFTY_FUT", 61093, n_parts=3, rows_per=5)
    assert len(list(parts_dir.glob("part-*.parquet"))) == 3

    summary = salvage_day(day)

    final = day / "NIFTY_FUT_61093.parquet"
    assert final.exists()
    assert pq.read_table(str(final)).num_rows == 15
    assert summary["instruments_consolidated"] == 1
    # readable raw parts are NOT deleted
    assert len(list(parts_dir.glob("part-*.parquet"))) == 3
    # verify ran and marked PARTIAL (salvage always incomplete)
    assert summary["verify_status"] == "PARTIAL"
    assert (day / "report.json").exists()
    assert (day / "salvage.json").exists()


def test_salvage_quarantines_corrupt_part(tmp_path):
    day = tmp_path / "2026-07-09"
    day.mkdir()
    parts_dir = _write_parts(day, "BANKNIFTY_FUT", 61094, n_parts=2, rows_per=5)
    # inject a corrupt part
    bad = parts_dir / "part-0099.parquet"
    bad.write_bytes(b"not a parquet file at all")

    summary = salvage_day(day)

    final = day / "BANKNIFTY_FUT_61094.parquet"
    assert pq.read_table(str(final)).num_rows == 10  # only the 2 good parts
    # corrupt part moved to corrupt/, preserving relative path; NOT deleted
    assert not bad.exists()
    moved = day / "corrupt" / "parts" / "BANKNIFTY_FUT_61094" / "part-0099.parquet"
    assert moved.exists()
    assert summary["corrupt_count"] == 1
    rel = "parts/BANKNIFTY_FUT_61094/part-0099.parquet"
    assert rel in summary["corrupt_parts"]


def test_salvage_all_parts_corrupt_yields_empty_final(tmp_path):
    day = tmp_path / "2026-07-09"
    (day / "parts" / "DEADSTOCK_999").mkdir(parents=True)
    (day / "parts" / "DEADSTOCK_999" / "part-0001.parquet").write_bytes(b"garbage")

    summary = salvage_day(day, run_verify=False)

    final = day / "DEADSTOCK_999.parquet"
    assert final.exists()
    assert pq.read_table(str(final)).num_rows == 0
    assert summary["corrupt_count"] == 1


def test_salvage_quarantines_stray_tmp(tmp_path):
    day = tmp_path / "2026-07-09"
    day.mkdir()
    # A pure primary-mode crash: an instrument that never entered part mode
    # leaves a footer-less <name>.parquet.tmp and NO parts/ dir.
    (day / "NIFTY_SPOT_13.parquet.tmp").write_bytes(b"incomplete-no-footer")

    summary = salvage_day(day, run_verify=False)
    assert "NIFTY_SPOT_13.parquet.tmp" in summary["stray_tmp"]
    assert (day / "corrupt" / "NIFTY_SPOT_13.parquet.tmp").exists()

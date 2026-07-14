"""Regression: manifest MERGE across sessions + reader/consolidation robustness.

2026-07-14 multi-session pipeline bug: a core-only manifest write (restart /
post-record_end empty session) overwrote the complete manifest → chain saw
SID<n> → 0 indices; and an empty session's writer zeroed a prior session's
final. These tests pin: manifest merge never drops options/expiries; a no-data
writer never clobbers a non-empty final; readers fall back to file-stems; and an
offline rebuild reconstructs a complete manifest with expiries.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from recorder.manifest import (expiries_from_events, merge_entries,
                               rebuild_from_disk)
from recorder.schema import EVENT_SCHEMA, TICK_SCHEMA
from recorder.writer import InstrumentWriter


def _tick_file(day: Path, symbol: str, sid: int, rows: int) -> None:
    day.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist(
        [{"security_id": sid, "ts_recv_ns": i, "seq_local": i} for i in range(rows)],
        schema=TICK_SCHEMA)
    pq.write_table(tbl, day / f"{symbol}_{sid}.parquet")


def _events_file(day: Path, armed: list[tuple[str, str]]) -> None:
    rows = [{"ts_ns": 1, "kind": "OPTIONS_ARMED",
             "detail": f"{idx} exp={exp} spot=1.0 strikes=[1,2]", "value_num": None,
             "security_id": -1} for idx, exp in armed]
    pq.write_table(pa.Table.from_pylist(rows, schema=EVENT_SCHEMA),
                   day / "events.parquet")


def test_merge_is_union_and_keeps_expiry():
    complete = [{"security_id": 13, "symbol": "NIFTY_SPOT", "expiry": ""},
                {"security_id": 51347, "symbol": "NIFTY_CE_23500", "expiry": "2026-07-14"}]
    core_only = [{"security_id": 13, "symbol": "NIFTY_SPOT", "expiry": ""}]   # a restart
    merged = {e["security_id"]: e for e in merge_entries(complete, core_only)}
    assert set(merged) == {13, 51347}                     # option NOT dropped
    assert merged[51347]["expiry"] == "2026-07-14"        # expiry preserved


def test_merge_recovers_expiry_from_either_side():
    a = [{"security_id": 9, "symbol": "X_CE_100", "expiry": "2026-07-14"}]
    b = [{"security_id": 9, "symbol": "X_CE_100", "expiry": ""}]
    assert merge_entries(b, a)[0]["expiry"] == "2026-07-14"
    assert merge_entries(a, b)[0]["expiry"] == "2026-07-14"


def test_rebuild_from_disk_reconstructs_options_with_expiry(tmp_path):
    day = tmp_path / "2026-07-14"
    _tick_file(day, "NIFTY_SPOT", 13, 5)
    _tick_file(day, "NIFTY_CE_23500", 51347, 3)
    _tick_file(day, "NIFTY_PE_23500", 51348, 3)
    _events_file(day, [("NIFTY", "2026-07-14")])
    # a stale core-only manifest on disk (no options)
    (day / "manifest.json").write_text(json.dumps(
        {"date": "2026-07-14",
         "instruments": [{"security_id": 13, "symbol": "NIFTY_SPOT", "expiry": ""}]}))

    m = {e["security_id"]: e for e in rebuild_from_disk(day)}
    assert set(m) == {13, 51347, 51348}                   # options recovered from stems
    assert m[51347]["expiry"] == "2026-07-14"             # expiry from OPTIONS_ARMED
    assert m[51347]["symbol"] == "NIFTY_CE_23500"


def test_expiries_from_events(tmp_path):
    day = tmp_path / "d"
    day.mkdir()
    _events_file(day, [("NIFTY", "2026-07-14"), ("BANKNIFTY", "2026-07-28")])
    exp = expiries_from_events(day)
    assert exp == {"NIFTY": "2026-07-14", "BANKNIFTY": "2026-07-28"}


def test_no_data_writer_does_not_clobber_nonempty_final(tmp_path):
    """A later empty session's writer.close() must NOT overwrite a prior
    session's non-empty final (the 2026-07-14 spot-zeroing bug)."""
    day = tmp_path / "2026-07-14"
    # session 1: real data
    w1 = InstrumentWriter(day, "NIFTY_SPOT", 13)
    for i in range(50):
        w1.add({"security_id": 13, "ts_recv_ns": i, "seq_local": i})
    w1.close()
    assert pq.ParquetFile(day / "NIFTY_SPOT_13.parquet").metadata.num_rows == 50

    # session 2: opens the same instrument, records NOTHING, closes
    w2 = InstrumentWriter(day, "NIFTY_SPOT", 13)
    w2.close()
    assert pq.ParquetFile(day / "NIFTY_SPOT_13.parquet").metadata.num_rows == 50  # preserved


def test_fresh_no_data_writer_still_emits_empty_placeholder(tmp_path):
    day = tmp_path / "d"
    w = InstrumentWriter(day, "NIFTY_SPOT", 13)
    w.close()
    assert (day / "NIFTY_SPOT_13.parquet").exists()
    assert pq.ParquetFile(day / "NIFTY_SPOT_13.parquet").metadata.num_rows == 0


def test_chain_meta_falls_back_to_stems_and_events(tmp_path):
    """chain._meta_by_id must classify options from file-stems + recover expiry
    from events even when manifest.json is stale/core-only (2026-07-14)."""
    from chain.run import _meta_by_id
    day = tmp_path / "2026-07-14"
    _tick_file(day, "NIFTY_SPOT", 13, 5)
    _tick_file(day, "NIFTY_CE_23500", 51347, 3)
    _tick_file(day, "NIFTY_FUT", 61093, 3)
    _events_file(day, [("NIFTY", "2026-07-14")])
    (day / "manifest.json").write_text(json.dumps(       # core-only, no options
        {"date": "2026-07-14",
         "instruments": [{"security_id": 13, "symbol": "NIFTY_SPOT", "expiry": ""}]}))

    meta = _meta_by_id(day, only_index="NIFTY")
    assert meta[13]["kind"] == "spot"
    assert meta[51347]["kind"] == "option" and meta[51347]["strike"] == 23500
    assert meta[51347]["expiry"] == "2026-07-14"          # recovered from events
    assert meta[61093]["kind"] == "future"

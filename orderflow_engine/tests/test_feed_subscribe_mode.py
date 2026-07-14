"""Regression: IDX_I instruments must subscribe in Quote(17), not Full(21).

2026-07-14 root cause — index (IDX_I) instruments have no order book, so Dhan
emits NO Full(21) packet for them; a blanket Full subscription starved
NIFTY_SPOT / BANKNIFTY_SPOT / INDIA_VIX of every packet (no error, no
disconnect). The fix routes IDX_I -> Quote(17) in FeedClient._messages_for while
leaving every other segment on the client's request_code (Full/21). These tests
pin the routing and prove a non-index list is byte-identical to the old path.
"""

from __future__ import annotations

import json

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from recorder.feed import FeedClient
from recorder.parser import REQ_FULL, REQ_QUOTE, parse_packet
from recorder import main as M
from recorder import scrip_master as SM
from tests.fixtures import synthetic as S
from tests.test_session_integration import FIX, _config


def _decode(msgs: list[str]) -> list[dict]:
    return [json.loads(m) for m in msgs]


def _client(instruments):
    return FeedClient("cid", "tok", list(instruments),
                      on_packet=lambda *_: None, request_code=REQ_FULL)


def test_idx_i_routed_to_quote_others_stay_full():
    fc = _client([("IDX_I", 13), ("NSE_FNO", 61093), ("IDX_I", 21), ("NSE_EQ", 1333)])
    by_code = {m["RequestCode"]: m["InstrumentList"] for m in _decode(fc._subscribe_messages())}

    assert set(by_code) == {REQ_QUOTE, REQ_FULL}          # exactly two modes
    quote_ids = {int(i["SecurityId"]) for i in by_code[REQ_QUOTE]}
    full_ids = {int(i["SecurityId"]) for i in by_code[REQ_FULL]}
    assert quote_ids == {13, 21}                          # both index ids -> Quote(17)
    assert full_ids == {61093, 1333}                      # FNO + EQ -> Full(21)
    # every Quote instrument is an index; no index leaked into Full
    assert all(i["ExchangeSegment"] == "IDX_I" for i in by_code[REQ_QUOTE])
    assert all(i["ExchangeSegment"] != "IDX_I" for i in by_code[REQ_FULL])


def test_non_index_list_is_byte_identical_to_old_path():
    """No IDX_I -> a single Full(21) block in original order (FNO/EQ untouched)."""
    insts = [("NSE_FNO", 61093), ("NSE_EQ", 1333), ("NSE_FNO", 61088)]
    msgs = _decode(_client(insts)._subscribe_messages())
    assert len(msgs) == 1
    assert msgs[0]["RequestCode"] == REQ_FULL
    assert [(i["ExchangeSegment"], int(i["SecurityId"])) for i in msgs[0]["InstrumentList"]] == insts


def test_dynamic_option_add_stays_full():
    """Option chains (NSE_FNO) armed on a live connection keep Full(21)."""
    fc = _client([])
    msgs = _decode(fc._messages_for([("NSE_FNO", 51355), ("NSE_FNO", 51356)]))
    assert len(msgs) == 1 and msgs[0]["RequestCode"] == REQ_FULL


def test_index_quote_packet_records_to_spot_writer(tmp_path, monkeypatch):
    """Once a Quote(17) packet for an index arrives, it persists to the spot
    writer with rows > 0 (proves the chosen mode yields a recordable tick)."""
    monkeypatch.setattr(M, "_now", lambda: datetime(2026, 7, 8, 9, 20, tzinfo=M.IST))
    monkeypatch.setattr(SM, "fetch_scrip_master", lambda *a, **k: FIX)

    rec = M.Recorder(_config(), root=tmp_path)
    rec.creds = SimpleNamespace(client_id="c", access_token="t")
    rec.resolve_instruments()
    rec._open_session(tmp_path / "data" / "2026-07-08")

    seg = S.P.EXCHANGE_SEGMENTS["IDX_I"]
    base = 1_700_000_000 * 10**9
    for i in range(5):
        pkt = parse_packet(S.make_quote(13, segment=seg, ltp=24500.0 + i))  # NIFTY_SPOT
        rec._on_packet(pkt, base + i * 10**9)

    spot_writer = rec._writers[13]
    for w in rec._writers.values():
        w.flush()
    assert spot_writer.symbol == "NIFTY_SPOT"
    assert spot_writer.rows_written > 0

"""Vendored Dhan v2 historical client: parse, chunk, cache (mocked http)."""

from __future__ import annotations

from datetime import date

import pytest

from levels.historical import DhanHistorical, _chunks, parse_columnar


class FakePost:
    """Records calls and returns a canned columnar body per call."""

    def __init__(self, body: dict):
        self.body = body
        self.calls: list[dict] = []

    def __call__(self, url, payload, headers, timeout=30.0):
        self.calls.append({"url": url, "payload": payload, "headers": headers})
        return self.body


_BODY = {"open": [100.0, 101.0], "high": [102.0, 103.0], "low": [99.0, 100.0],
         "close": [101.0, 102.0], "volume": [1000, 1100],
         "timestamp": [1_700_000_000, 1_700_086_400]}


def test_parse_columnar():
    bars = parse_columnar(_BODY)
    assert len(bars) == 2
    assert bars[0].open == 100.0 and bars[0].close == 101.0 and bars[0].volume == 1000
    assert bars[1].ts == 1_700_086_400


def test_parse_skips_bad_rows():
    body = {"open": [100.0, None], "high": [102.0, 103.0], "low": [99.0, 100.0],
            "close": [101.0, 102.0], "volume": [1000, 1100],
            "timestamp": [1_700_000_000, 1_700_086_400]}
    assert len(parse_columnar(body)) == 1     # the None open row is skipped


def test_start_time_variant():
    body = dict(_BODY)
    body["start_Time"] = body.pop("timestamp")
    assert len(parse_columnar(body)) == 2


def test_chunking_intraday_90_days():
    chunks = _chunks(date(2026, 1, 1), date(2026, 6, 1), max_days=90)
    assert len(chunks) == 2                    # 152 days -> 90 + 62
    assert chunks[0][0] == date(2026, 1, 1)
    assert chunks[1][1] == date(2026, 6, 1)
    # contiguous, non-overlapping
    assert (chunks[1][0] - chunks[0][1]).days == 1


def test_daily_fetch_single_chunk_and_headers(tmp_path):
    fake = FakePost(_BODY)
    c = DhanHistorical("CID", "TOK", tmp_path, http_post=fake)
    bars = c.fetch(61093, "NSE_FNO", "FUTIDX", date(2026, 7, 1), date(2026, 7, 5))
    assert len(bars) == 2
    assert len(fake.calls) == 1
    hdr = fake.calls[0]["headers"]
    assert hdr["client-id"] == "CID" and hdr["access-token"] == "TOK"
    pl = fake.calls[0]["payload"]
    assert pl["securityId"] == "61093" and pl["fromDate"] == "2026-07-01"
    assert "interval" not in pl                # daily endpoint has no interval


def test_cache_hit_avoids_second_http(tmp_path):
    fake = FakePost(_BODY)
    c = DhanHistorical("CID", "TOK", tmp_path, http_post=fake)
    c.fetch(61093, "NSE_FNO", "FUTIDX", date(2026, 7, 1), date(2026, 7, 5))
    c.fetch(61093, "NSE_FNO", "FUTIDX", date(2026, 7, 1), date(2026, 7, 5))
    assert len(fake.calls) == 1                # second fetch served from parquet cache


def test_intraday_multi_chunk_multiple_posts(tmp_path):
    fake = FakePost(_BODY)
    c = DhanHistorical("CID", "TOK", tmp_path, http_post=fake)
    c.fetch(1, "NSE_FNO", "FUTIDX", date(2026, 1, 1), date(2026, 6, 1),
            timeframe="5m", use_cache=False)
    assert len(fake.calls) == 2                # two 90-day chunks -> two POSTs
    assert fake.calls[0]["payload"]["interval"] == "5"


@pytest.mark.skip(reason="real network + live token; run manually with --run-online")
def test_real_fetch_skip_if_offline():
    # Placeholder for the manual online check; the daily real-data path is
    # exercised in test_daily_realdata.py with a skip-if-offline guard.
    pass

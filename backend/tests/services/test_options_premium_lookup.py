"""OPTIONS BRICK #4 — SLICE ③-a: pure ``premium_at()`` lookup, FIXTURES ONLY.

Fixture day-dirs are generated in-test with the EXACT recorder layout —
``manifest.json`` + ``{SYMBOL}_{security_id}.parquet`` files whose schema is a
verbatim mirror of the recorder's ``TICK_SCHEMA``
(``feat/orderflow-r0-recorder @ 00fc4fe : orderflow_engine/recorder/schema.py``:
ts_recv_ns/packet_type/seq_local/security_id/ltt/ltp/ltq/atp/volume/
total_buy_qty/total_sell_qty/oi + 5 depth levels x {bid,ask}_{price,qty,orders}
with 1-BASED suffixes). No real orderflow data is touched — it is not reachable
from this branch (audit-confirmed).

Policy under test (§4 of the audit): manifest → expiry check → file →
last-at-or-before ts → staleness-bounded ltp → depth-mid fallback → TYPED
no-data. The fn NEVER raises for missing data.
"""

from __future__ import annotations

import json
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.services.options_premium_lookup import (
    LTP_MAX_STALENESS_S,
    MID_MAX_STALENESS_S,
    PremiumLookup,
    premium_at,
)

# ─── Verbatim TICK_SCHEMA mirror (recorder schema.py @ 00fc4fe) ────────────
_DEPTH_FIELDS = []
for _i in range(1, 6):  # DEPTH_LEVELS = 5, 1-based suffixes
    _DEPTH_FIELDS += [
        pa.field(f"bid_price_{_i}", pa.float64()),
        pa.field(f"bid_qty_{_i}", pa.int64()),
        pa.field(f"bid_orders_{_i}", pa.int32()),
        pa.field(f"ask_price_{_i}", pa.float64()),
        pa.field(f"ask_qty_{_i}", pa.int64()),
        pa.field(f"ask_orders_{_i}", pa.int32()),
    ]
TICK_SCHEMA = pa.schema(
    [
        pa.field("ts_recv_ns", pa.int64()),
        pa.field("packet_type", pa.int8()),
        pa.field("seq_local", pa.int64()),
        pa.field("security_id", pa.int32()),
        pa.field("ltt", pa.int32()),
        pa.field("ltp", pa.float64()),
        pa.field("ltq", pa.int32()),
        pa.field("atp", pa.float64()),
        pa.field("volume", pa.int64()),
        pa.field("total_buy_qty", pa.int64()),
        pa.field("total_sell_qty", pa.int64()),
        pa.field("oi", pa.int64()),
        *_DEPTH_FIELDS,
    ]
)
_COLUMNS = [f.name for f in TICK_SCHEMA]

#: A base signal timestamp: 2026-07-15 10:00:00 UTC in epoch-ns.
_TS = 1_784_109_600_000_000_000
_SEC = 1_000_000_000  # ns per second

_EXPIRY = date(2026, 7, 16)


def _tick(ts_ns, *, ltp=None, bid1=None, ask1=None, sid=49081):
    row = dict.fromkeys(_COLUMNS)
    row.update({"ts_recv_ns": ts_ns, "packet_type": 8, "seq_local": 1,
                "security_id": sid, "ltp": ltp,
                "bid_price_1": bid1, "ask_price_1": ask1})
    return row


def _write_day(tmp_path, *, instruments, ticks_by_symbol):
    """Build a fixture day-dir: manifest.json + one parquet per instrument."""
    day = tmp_path / "2026-07-15"
    day.mkdir()
    (day / "manifest.json").write_text(json.dumps(
        {"date": "2026-07-15", "instruments": instruments}, indent=2))
    for symbol, (sid, rows) in ticks_by_symbol.items():
        table = pa.Table.from_pylist(rows, schema=TICK_SCHEMA)
        pq.write_table(table, day / f"{symbol}_{sid}.parquet",
                       compression="zstd")
    return day


def _inst(symbol, sid, *, kind="option", expiry="2026-07-16"):
    return {"symbol": symbol, "security_id": sid, "exchange_segment": "NSE_FNO",
            "kind": kind, "gap_check": False, "expiry": expiry}


def _lookup(day, **overrides):
    kw = {"underlying": "NIFTY", "strike": 24800, "opt_type": "CE",
          "expiry": _EXPIRY, "ts_ns": _TS}
    kw.update(overrides)
    return premium_at(day, **kw)


# ═══════════════════════════════════════════════════════════════════════
# Happy paths — provenance
# ═══════════════════════════════════════════════════════════════════════


def test_fresh_ltp_at_or_before_ts(tmp_path):
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081)],
        ticks_by_symbol={"NIFTY_CE_24800": (49081, [
            _tick(_TS - 30 * _SEC, ltp=142.55),
        ])})
    res = _lookup(day)
    assert isinstance(res, PremiumLookup)
    assert res.source == "ltp" and res.reason is None
    assert res.premium == 142.55
    assert res.staleness_s == pytest.approx(30.0)


def test_ts_between_ticks_takes_last_at_or_before_not_future(tmp_path):
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081)],
        ticks_by_symbol={"NIFTY_CE_24800": (49081, [
            _tick(_TS - 60 * _SEC, ltp=140.0),
            _tick(_TS - 10 * _SEC, ltp=141.0),   # ← last at-or-before
            _tick(_TS + 5 * _SEC, ltp=999.0),    # future tick — must NOT be used
        ])})
    res = _lookup(day)
    assert res.premium == 141.0 and res.source == "ltp"


def test_stale_ltp_with_depth_falls_back_to_mid(tmp_path):
    stale_age = int(LTP_MAX_STALENESS_S + 60)      # past ltp bound, inside mid bound
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081)],
        ticks_by_symbol={"NIFTY_CE_24800": (49081, [
            _tick(_TS - stale_age * _SEC, ltp=140.0, bid1=141.0, ask1=143.0),
        ])})
    res = _lookup(day)
    assert res.source == "depth_mid" and res.reason is None
    assert res.premium == pytest.approx(142.0)     # mid of 141/143


def test_ce_and_pe_resolve_independently(tmp_path):
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081),
                     _inst("NIFTY_PE_24800", 49082)],
        ticks_by_symbol={
            "NIFTY_CE_24800": (49081, [_tick(_TS - 5 * _SEC, ltp=142.0)]),
            "NIFTY_PE_24800": (49082, [_tick(_TS - 5 * _SEC, ltp=87.5, sid=49082)]),
        })
    assert _lookup(day, opt_type="CE").premium == 142.0
    assert _lookup(day, opt_type="PE").premium == 87.5


# ═══════════════════════════════════════════════════════════════════════
# Typed no-data — every reason, never an exception
# ═══════════════════════════════════════════════════════════════════════


def test_absent_strike_no_manifest_entry(tmp_path):
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24700", 40001)],   # different strike only
        ticks_by_symbol={"NIFTY_CE_24700": (40001, [_tick(_TS - _SEC, ltp=1.0)])})
    res = _lookup(day)                                   # 24800 not recorded
    assert res.premium is None
    assert res.source == "no_data" and res.reason == "absent_strike"


def test_absent_file_despite_manifest_entry(tmp_path):
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081)],
        ticks_by_symbol={})                              # no parquet written
    res = _lookup(day)
    assert res.source == "no_data" and res.reason == "absent_strike"


def test_expiry_mismatch_guard(tmp_path):
    """One armed chain expiry per day — strike alone is ambiguous."""
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081, expiry="2026-07-23")],
        ticks_by_symbol={"NIFTY_CE_24800": (49081, [_tick(_TS - _SEC, ltp=99.0)])})
    res = _lookup(day, expiry=_EXPIRY)                   # wants 2026-07-16
    assert res.source == "no_data" and res.reason == "expiry_mismatch"
    assert res.premium is None                           # never the wrong contract


def test_manifest_missing(tmp_path):
    day = tmp_path / "2026-07-15"
    day.mkdir()                                          # no manifest.json at all
    res = _lookup(day)
    assert res.source == "no_data" and res.reason == "manifest_missing"


def test_core_only_day(tmp_path):
    """Disk-guard CORE-ONLY session: manifest exists but has NO option rows."""
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_FUT", 35001, kind="future", expiry="2026-07-30")],
        ticks_by_symbol={"NIFTY_FUT": (35001, [_tick(_TS - _SEC, ltp=24810.0)])})
    res = _lookup(day)
    assert res.source == "no_data" and res.reason == "core_only_day"


def test_stale_beyond_second_bound(tmp_path):
    too_old = int(MID_MAX_STALENESS_S + 120)
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081)],
        ticks_by_symbol={"NIFTY_CE_24800": (49081, [
            _tick(_TS - too_old * _SEC, ltp=140.0, bid1=141.0, ask1=143.0),
        ])})
    res = _lookup(day)
    assert res.source == "no_data" and res.reason == "stale_beyond_bound"


def test_no_tick_at_or_before_ts_is_stale_beyond_bound(tmp_path):
    """Only FUTURE ticks exist (e.g. pre-open signal) → nothing usable at ts."""
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081)],
        ticks_by_symbol={"NIFTY_CE_24800": (49081, [
            _tick(_TS + 60 * _SEC, ltp=150.0),
        ])})
    res = _lookup(day)
    assert res.source == "no_data" and res.reason == "stale_beyond_bound"


def test_unreadable_parquet_is_typed_no_data_not_exception(tmp_path):
    day = _write_day(tmp_path,
        instruments=[_inst("NIFTY_CE_24800", 49081)],
        ticks_by_symbol={})
    (day / "NIFTY_CE_24800_49081.parquet").write_bytes(b"NOT A PARQUET FILE")
    res = _lookup(day)                                   # must not raise
    assert res.source == "no_data" and res.reason == "absent_strike"


def test_never_raises_on_any_missing_data_path(tmp_path):
    """Sweep every no-data shape through the fn — all return PremiumLookup."""
    empty = tmp_path / "empty-day"
    empty.mkdir()
    bad_manifest = tmp_path / "bad-manifest"
    bad_manifest.mkdir()
    (bad_manifest / "manifest.json").write_text("{{{ not json")

    for day in (empty, bad_manifest, tmp_path / "does-not-exist"):
        res = _lookup(day)
        assert isinstance(res, PremiumLookup)
        assert res.source == "no_data" and res.premium is None
        assert res.reason == "manifest_missing"


# ═══════════════════════════════════════════════════════════════════════
# Environment
# ═══════════════════════════════════════════════════════════════════════


def test_pyarrow_importable_as_backend_dependency():
    import pyarrow

    assert tuple(int(x) for x in pyarrow.__version__.split(".")[:1]) >= (17,)

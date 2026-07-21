"""P8 bar-quality tests (t1..t4) — deterministic hand-built bars."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from research.bar_quality import MIN_BARS, bar_quality, regime_of
from tape.config import TapeConfig
from tape.engine import TapeEngine

NS = 1_000_000_000
IST = timezone(timedelta(hours=5, minutes=30))


def _ts(h, m):
    return int(datetime(2026, 7, 21, h, m, tzinfo=IST).timestamp() * NS)


def bar(ts_end, dur, h, lo, vol=100, trades=10):
    return {"start_ts_ns": ts_end - int(dur * NS), "end_ts_ns": ts_end, "duration_s": dur,
            "open": lo, "high": h, "low": lo, "close": h, "volume": vol, "trade_count": trades}


# t1) hand-built set -> exact flat rate + exact quantiles
def test_t1_exact_flat_rate_and_quantiles():
    s0 = _ts(9, 15)
    durs = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]        # Q10=20 Q50=60 Q90=100 (index picks)
    bars = []
    for i, d in enumerate(durs):
        hi = 101.0 if i < 8 else 100.0                       # last 2 bars flat (high==low==100)
        bars.append(bar(s0 + (i + 1) * 120 * NS, d, hi, 100.0, vol=100 + i, trades=10))
    q = bar_quality(bars, session_start_ns=s0)
    assert q["n_bars"] == 10
    assert q["flat_bar_rate"] == pytest.approx(0.2)          # 2 of 10 zero-range
    d = q["duration_s"]
    # floor-index quantile convention: idx = int(p*(n-1)) -> q10=durs[0], q50=durs[4], q90=durs[8]
    assert (d["q10"], d["q50"], d["q90"]) == (10.0, 50.0, 90.0)
    assert d["q90_q10_ratio"] == pytest.approx(9.0)
    assert q["range_pts"]["median"] == pytest.approx(1.0)    # 8 bars range 1.0, 2 bars 0
    assert q["trades_per_bar"]["median"] == 10.0


# t2) regime split: bars land in the right buckets (IB 60m open; >=14:45 close)
def test_t2_regime_split_buckets():
    s0 = _ts(9, 15)
    assert regime_of(_ts(9, 30), s0, 60, "14:45") == "open"      # inside IB hour
    assert regime_of(_ts(10, 16), s0, 60, "14:45") == "mid"      # just after IB
    assert regime_of(_ts(14, 45), s0, 60, "14:45") == "close"    # at cutoff
    assert regime_of(_ts(15, 10), s0, 60, "14:45") == "close"
    bars = [bar(_ts(9, 30), 10, 101, 100)] * 6 + [bar(_ts(11, 0), 20, 101, 100)] * 6 \
        + [bar(_ts(15, 0), 30, 101, 100)] * 6
    q = bar_quality(bars, session_start_ns=s0)
    br = q["duration_by_regime"]
    assert br["open"]["n"] == 6 and br["mid"]["n"] == 6 and br["close"]["n"] == 6
    assert br["open"]["q50"] == 10.0 and br["mid"]["q50"] == 20.0 and br["close"]["q50"] == 30.0


# t3) empty/short guard — no crash, honest note
def test_t3_empty_and_short_guards():
    assert bar_quality([]) == {"n_bars": 0, "note": "EMPTY bar stream — no stats"}
    short = [bar(_ts(9, 30) + i * NS, 10, 101, 100) for i in range(MIN_BARS - 1)]
    q = bar_quality(short, session_start_ns=_ts(9, 15))
    assert q["n_bars"] == MIN_BARS - 1 and "SHORT" in q["note"]
    assert "duration_s" not in q                              # no quantile claims


# t4) flag off -> pipeline byte-identical (no quality keys; import changes nothing)
def test_t4_flag_off_pipeline_untouched():
    def run_bars():
        eng = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 2}}), {61093: "NIFTY_FUT"})
        vol = 1000
        for i in range(1, 7):
            vol += 10
            eng.on_packet({"is_tick": True, "security_id": 61093, "ts_recv_ns": i * NS,
                           "volume": vol, "ltp": 100.0 + i * 0.1, "ltq": 0,
                           "bid_price_1": 99.9, "ask_price_1": 100.1, "ltt": i}, i * NS)
        return eng.bar_rows
    rows = run_bars()
    assert rows and all("flat" not in str(sorted(r)) and "quality" not in str(sorted(r))
                        for r in rows)
    import research.bar_quality  # noqa: F401
    assert run_bars() == rows

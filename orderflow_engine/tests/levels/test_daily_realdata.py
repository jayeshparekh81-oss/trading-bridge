"""REAL-DATA daily path: fetch NIFTY-future daily OHLCV -> pivots.

Skip-if-offline so the suite stays green without network / a live token (on a
non-trading day the recorder token is expired, which also trips the skip).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from levels.historical import DhanHistorical
from levels.pivots import classic_pivots

HERE = Path(__file__).resolve().parent.parent.parent  # orderflow_engine/
IST = ZoneInfo("Asia/Kolkata")


def _resolve_nifty_future():
    from recorder import scrip_master as SM
    import yaml
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())["scrip_master"]
    csv = SM.fetch_scrip_master(HERE / cfg["cache_dir"], url=cfg["url"],
                                today=datetime.now(IST).date(),
                                stale_hours=int(cfg["stale_hours"]))
    rows = SM.load_rows(csv)
    fut = SM.resolve_future(rows, ref_date=datetime.now(IST).date(),
                            underlying="NIFTY", exch="NSE", segment="NSE_FNO", symbol="NIFTY")
    return fut.security_id, fut.exchange_segment


def test_daily_pivots_from_real_nifty_future(tmp_path):
    try:
        from recorder.creds import load_env_files
        load_env_files([HERE.parent / ".env", HERE.parent / "backend" / ".env"])
        sid, seg = _resolve_nifty_future()
        client = DhanHistorical.from_creds(tmp_path)
        to = datetime.now(IST).date()
        bars = client.fetch(sid, seg, "FUTIDX", to - timedelta(days=20), to, timeframe="1d")
    except Exception as exc:  # noqa: BLE001 - offline / no creds / expired token / resolution
        pytest.skip(f"daily real-data path unavailable offline: {type(exc).__name__}: {exc}")

    if len(bars) < 2:
        pytest.skip(f"insufficient bars returned ({len(bars)})")

    prior = bars[-2]
    assert prior.high >= prior.low
    piv = classic_pivots(prior.high, prior.low, prior.close)
    # pivots must be strictly ordered R3>R2>R1>P>S1>S2>S3 for a normal H>L bar
    assert piv["PIVOT_R3"] > piv["PIVOT_R2"] > piv["PIVOT_R1"] > piv["PIVOT_P"]
    assert piv["PIVOT_P"] > piv["PIVOT_S1"] > piv["PIVOT_S2"] > piv["PIVOT_S3"]
    # a cache parquet should now exist (atomic caching worked)
    assert list(Path(tmp_path).glob("*_1d_*.parquet"))

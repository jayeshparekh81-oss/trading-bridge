"""Edge-case coverage for :mod:`app.schemas.indicator`.

The discriminated-union happy paths + every Params bounds check
are exercised via the API + service tests; these tests target the
two response-schema branches the upstream tests don't reach (the
naive-timestamp rejection on ``last_closed_candle_ts`` and the
series-length mismatch in ``IndicatorResponse``).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.candle import Timeframe
from app.schemas.indicator import IndicatorName, IndicatorResponse


def _base_kwargs() -> dict:
    return {
        "symbol": "NIFTY",
        "timeframe": Timeframe.FIVE_MIN,
        "indicator": IndicatorName.SMA,
        "from_ts": datetime(2026, 5, 11, 0, 0, tzinfo=UTC),
        "to_ts": datetime(2026, 5, 11, 23, 59, tzinfo=UTC),
        "last_closed_candle_ts": datetime(2026, 5, 11, 9, 15, tzinfo=UTC),
        "candle_timestamps": [datetime(2026, 5, 11, 9, 15, tzinfo=UTC)],
        "series": {"value": [22500.0]},
    }


def test_response_naive_last_closed_candle_ts_rejected() -> None:
    kw = _base_kwargs()
    kw["last_closed_candle_ts"] = datetime(2026, 5, 11, 9, 15)  # naive
    with pytest.raises(ValidationError) as excinfo:
        IndicatorResponse(**kw)
    assert "timezone-aware" in str(excinfo.value).lower()


def test_response_none_last_closed_candle_ts_accepted() -> None:
    kw = _base_kwargs()
    kw["last_closed_candle_ts"] = None
    kw["candle_timestamps"] = []
    kw["series"] = {"value": []}
    resp = IndicatorResponse(**kw)
    assert resp.last_closed_candle_ts is None


def test_response_series_length_mismatch_rejected() -> None:
    kw = _base_kwargs()
    kw["candle_timestamps"] = [datetime(2026, 5, 11, 9, 15, tzinfo=UTC)]
    kw["series"] = {"value": [100.0, 101.0]}  # length 2 vs 1 ts
    with pytest.raises(ValidationError) as excinfo:
        IndicatorResponse(**kw)
    assert "length" in str(excinfo.value).lower()

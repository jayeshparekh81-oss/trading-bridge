"""Tests for :mod:`app.schemas.candle`.

The schemas are pure Pydantic v2 with strict + frozen + extra=forbid.
There is no I/O to mock — every test constructs models with literal
values and asserts on validators, serialisation round-trips, and the
custom OHLC invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.candle import (
    BrokerDisconnectedEvent,
    BrokerReconnectedEvent,
    Candle,
    ChartEventType,
    ChartHistoryResponse,
    TickData,
    Timeframe,
)
from tests._chart_helpers import make_candle, make_tick, utc_datetime


# ═══════════════════════════════════════════════════════════════════════
# Timeframe
# ═══════════════════════════════════════════════════════════════════════


class TestTimeframe:
    def test_enum_values_are_url_safe(self) -> None:
        # URL safety = no slashes, spaces, or path separators.
        for tf in Timeframe:
            assert "/" not in tf.value
            assert " " not in tf.value
            assert tf.value == tf.value.strip()

    @pytest.mark.parametrize(
        ("tf", "expected_seconds"),
        [
            (Timeframe.ONE_MIN, 60),
            (Timeframe.THREE_MIN, 180),
            (Timeframe.FIVE_MIN, 300),
            (Timeframe.FIFTEEN_MIN, 900),
            (Timeframe.THIRTY_MIN, 1_800),
            (Timeframe.ONE_HOUR, 3_600),
            (Timeframe.ONE_DAY, 86_400),
        ],
    )
    def test_seconds_property(self, tf: Timeframe, expected_seconds: int) -> None:
        assert tf.seconds == expected_seconds

    def test_string_construction(self) -> None:
        assert Timeframe("5m") is Timeframe.FIVE_MIN
        with pytest.raises(ValueError):
            Timeframe("4m")  # not in the enum


# ═══════════════════════════════════════════════════════════════════════
# TickData
# ═══════════════════════════════════════════════════════════════════════


class TestTickData:
    def test_valid_construction(self, sample_tick: TickData) -> None:
        assert sample_tick.symbol == "NIFTY"
        assert sample_tick.exchange_segment == "NSE_EQ"
        assert sample_tick.ltp == Decimal("22500.50")

    def test_symbol_is_upper_cased(self) -> None:
        tick = make_tick(symbol="nifty")
        assert tick.symbol == "NIFTY"

    def test_exchange_segment_is_upper_cased(self) -> None:
        tick = make_tick(exchange_segment="nse_eq")
        assert tick.exchange_segment == "NSE_EQ"

    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            TickData(
                symbol="NIFTY",
                exchange_segment="NSE_EQ",
                ltp=Decimal("100"),
                timestamp=datetime(2026, 1, 1),
            )
        assert "timezone-aware" in str(excinfo.value).lower()

    def test_zero_ltp_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TickData(
                symbol="NIFTY",
                exchange_segment="NSE_EQ",
                ltp=Decimal("0"),
                timestamp=utc_datetime(),
            )

    def test_negative_ltp_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TickData(
                symbol="NIFTY",
                exchange_segment="NSE_EQ",
                ltp=Decimal("-1"),
                timestamp=utc_datetime(),
            )

    def test_negative_volume_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TickData(
                symbol="NIFTY",
                exchange_segment="NSE_EQ",
                ltp=Decimal("100"),
                volume=-1,
                timestamp=utc_datetime(),
            )

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TickData(
                symbol="NIFTY",
                exchange_segment="NSE_EQ",
                ltp=Decimal("100"),
                timestamp=utc_datetime(),
                unknown_field="x",  # type: ignore[call-arg]
            )

    def test_frozen(self, sample_tick: TickData) -> None:
        with pytest.raises(ValidationError):
            sample_tick.symbol = "OTHER"  # type: ignore[misc]

    def test_json_round_trip_via_model_validate_json(
        self, sample_tick: TickData
    ) -> None:
        # CRITICAL: model_validate_json preserves Decimal/datetime
        # round-trip; json.loads + model_validate would NOT.
        raw_json = sample_tick.model_dump_json()
        restored = TickData.model_validate_json(raw_json)
        assert restored == sample_tick
        assert restored.ltp == sample_tick.ltp

    def test_empty_symbol_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TickData(
                symbol="",
                exchange_segment="NSE_EQ",
                ltp=Decimal("100"),
                timestamp=utc_datetime(),
            )


# ═══════════════════════════════════════════════════════════════════════
# Candle
# ═══════════════════════════════════════════════════════════════════════


class TestCandle:
    def test_valid_construction(self, sample_candle: Candle) -> None:
        assert sample_candle.symbol == "NIFTY"
        assert sample_candle.timeframe == Timeframe.FIVE_MIN

    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Candle(
                symbol="NIFTY",
                timeframe=Timeframe.ONE_MIN,
                timestamp=datetime(2026, 1, 1),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("100"),
                close=Decimal("100"),
                volume=0,
            )

    def test_high_less_than_low_rejected(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            make_candle(high="100.00", low="200.00")
        assert "high" in str(excinfo.value).lower()

    def test_open_above_high_rejected(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            make_candle(open="300.00", high="200.00", low="100.00", close="150.00")
        assert "open" in str(excinfo.value).lower()

    def test_open_below_low_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_candle(open="50.00", high="200.00", low="100.00", close="150.00")

    def test_close_above_high_rejected(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            make_candle(open="150.00", high="200.00", low="100.00", close="300.00")
        assert "close" in str(excinfo.value).lower()

    def test_close_below_low_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_candle(open="150.00", high="200.00", low="100.00", close="50.00")

    def test_equal_high_low_valid(self) -> None:
        # Single-tick bar: high == low == open == close. Valid.
        c = make_candle(
            open="100.00", high="100.00", low="100.00", close="100.00"
        )
        assert c.high == c.low

    def test_symbol_upper_cased(self) -> None:
        c = make_candle(symbol="nifty")
        assert c.symbol == "NIFTY"

    def test_zero_volume_valid(self) -> None:
        c = make_candle(volume=0)
        assert c.volume == 0

    def test_negative_volume_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_candle(volume=-1)

    def test_frozen(self, sample_candle: Candle) -> None:
        with pytest.raises(ValidationError):
            sample_candle.close = Decimal("999")  # type: ignore[misc]

    def test_json_round_trip(self, sample_candle: Candle) -> None:
        raw_json = sample_candle.model_dump_json()
        restored = Candle.model_validate_json(raw_json)
        assert restored == sample_candle

    def test_decimal_precision_preserved(self) -> None:
        c = make_candle(
            open="100.12345678",
            high="100.12345679",
            low="100.12345677",
            close="100.12345678",
        )
        restored = Candle.model_validate_json(c.model_dump_json())
        assert restored.open == Decimal("100.12345678")


# ═══════════════════════════════════════════════════════════════════════
# ChartHistoryResponse
# ═══════════════════════════════════════════════════════════════════════


class TestChartHistoryResponse:
    def _base_kwargs(self) -> dict[str, object]:
        return {
            "symbol": "NIFTY",
            "timeframe": Timeframe.FIVE_MIN,
            "from_ts": utc_datetime(hour=9, minute=15),
            "to_ts": utc_datetime(hour=15, minute=30),
            "cached": False,
            "candles": [],
        }

    def test_empty_candles_valid(self) -> None:
        resp = ChartHistoryResponse(**self._base_kwargs())  # type: ignore[arg-type]
        assert resp.candles == []
        assert resp.cached is False

    def test_window_order_enforced(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["from_ts"] = utc_datetime(hour=15, minute=30)
        kwargs["to_ts"] = utc_datetime(hour=9, minute=15)
        with pytest.raises(ValidationError) as excinfo:
            ChartHistoryResponse(**kwargs)  # type: ignore[arg-type]
        assert "from_ts" in str(excinfo.value).lower()

    def test_equal_from_to_valid(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["from_ts"] = kwargs["to_ts"] = utc_datetime(hour=10)
        resp = ChartHistoryResponse(**kwargs)  # type: ignore[arg-type]
        assert resp.from_ts == resp.to_ts

    def test_naive_from_rejected(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["from_ts"] = datetime(2026, 5, 11, 9, 15)
        with pytest.raises(ValidationError):
            ChartHistoryResponse(**kwargs)  # type: ignore[arg-type]

    def test_naive_to_rejected(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["to_ts"] = datetime(2026, 5, 11, 15, 30)
        with pytest.raises(ValidationError):
            ChartHistoryResponse(**kwargs)  # type: ignore[arg-type]

    def test_with_candles(self, sample_candle: Candle) -> None:
        kwargs = self._base_kwargs()
        kwargs["candles"] = [sample_candle]
        resp = ChartHistoryResponse(**kwargs)  # type: ignore[arg-type]
        assert resp.candles[0] == sample_candle

    def test_cached_flag_default_false(self) -> None:
        kwargs = self._base_kwargs()
        del kwargs["cached"]
        resp = ChartHistoryResponse(**kwargs)  # type: ignore[arg-type]
        assert resp.cached is False

    def test_json_round_trip_preserves_cached_flag(
        self, sample_candle: Candle
    ) -> None:
        kwargs = self._base_kwargs()
        kwargs["candles"] = [sample_candle]
        kwargs["cached"] = True
        resp = ChartHistoryResponse(**kwargs)  # type: ignore[arg-type]
        restored = ChartHistoryResponse.model_validate_json(resp.model_dump_json())
        assert restored.cached is True
        assert restored.candles == [sample_candle]

    def test_model_copy_can_flip_cached(self, sample_candle: Candle) -> None:
        # The chart route does this on cache hit.
        kwargs = self._base_kwargs()
        kwargs["candles"] = [sample_candle]
        kwargs["cached"] = False
        resp = ChartHistoryResponse(**kwargs)  # type: ignore[arg-type]
        cached_copy = resp.model_copy(update={"cached": True})
        assert resp.cached is False
        assert cached_copy.cached is True
        # Frozen model — must produce a new object, not mutate.
        assert cached_copy is not resp


# ═══════════════════════════════════════════════════════════════════════
# Control events
# ═══════════════════════════════════════════════════════════════════════


class TestBrokerDisconnectedEvent:
    def test_event_field_default(self) -> None:
        evt = BrokerDisconnectedEvent(
            symbol="NIFTY",
            reason="TimeoutError",
            failed_attempts=3,
            since=utc_datetime(),
        )
        assert evt.event == ChartEventType.BROKER_DISCONNECTED

    def test_failed_attempts_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            BrokerDisconnectedEvent(
                symbol="NIFTY",
                reason="X",
                failed_attempts=0,
                since=utc_datetime(),
            )

    def test_symbol_upper_cased(self) -> None:
        evt = BrokerDisconnectedEvent(
            symbol="nifty",
            reason="X",
            failed_attempts=1,
            since=utc_datetime(),
        )
        assert evt.symbol == "NIFTY"

    def test_naive_since_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrokerDisconnectedEvent(
                symbol="NIFTY",
                reason="X",
                failed_attempts=1,
                since=datetime(2026, 1, 1),
            )

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrokerDisconnectedEvent(
                symbol="NIFTY",
                reason="",
                failed_attempts=1,
                since=utc_datetime(),
            )

    def test_reason_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrokerDisconnectedEvent(
                symbol="NIFTY",
                reason="x" * 513,  # max_length=512
                failed_attempts=1,
                since=utc_datetime(),
            )

    def test_frozen(self) -> None:
        evt = BrokerDisconnectedEvent(
            symbol="NIFTY",
            reason="X",
            failed_attempts=1,
            since=utc_datetime(),
        )
        with pytest.raises(ValidationError):
            evt.failed_attempts = 99  # type: ignore[misc]

    def test_json_round_trip(self) -> None:
        evt = BrokerDisconnectedEvent(
            symbol="NIFTY",
            reason="Some reason",
            failed_attempts=5,
            since=utc_datetime(),
        )
        restored = BrokerDisconnectedEvent.model_validate_json(evt.model_dump_json())
        assert restored == evt


class TestBrokerReconnectedEvent:
    def test_construction(self) -> None:
        evt = BrokerReconnectedEvent(symbol="NIFTY", at=utc_datetime())
        assert evt.event == ChartEventType.BROKER_RECONNECTED

    def test_symbol_upper_cased(self) -> None:
        evt = BrokerReconnectedEvent(symbol="nifty", at=utc_datetime())
        assert evt.symbol == "NIFTY"

    def test_naive_at_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrokerReconnectedEvent(symbol="NIFTY", at=datetime(2026, 1, 1))

    def test_frozen(self) -> None:
        evt = BrokerReconnectedEvent(symbol="NIFTY", at=utc_datetime())
        with pytest.raises(ValidationError):
            evt.symbol = "OTHER"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════
# ChartEventType
# ═══════════════════════════════════════════════════════════════════════


class TestChartEventType:
    def test_known_values_present(self) -> None:
        # The five members the chart module switches on.
        assert ChartEventType("tick") is ChartEventType.TICK
        assert ChartEventType("candle") is ChartEventType.CANDLE
        assert (
            ChartEventType("broker_disconnected")
            is ChartEventType.BROKER_DISCONNECTED
        )
        assert (
            ChartEventType("broker_reconnected")
            is ChartEventType.BROKER_RECONNECTED
        )
        assert ChartEventType("heartbeat") is ChartEventType.HEARTBEAT

    def test_unknown_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            ChartEventType("not_a_real_event")


# ═══════════════════════════════════════════════════════════════════════
# Cross-model sanity
# ═══════════════════════════════════════════════════════════════════════


def test_candle_timeframe_aligns_with_window() -> None:
    """Sanity: a 5m bar's timestamp is on a 5-min boundary by convention.

    Our schemas don't enforce this (the broker may emit any timestamp);
    just confirm the helper produces an on-boundary default.
    """
    c = make_candle(timeframe=Timeframe.FIVE_MIN)
    epoch = int(c.timestamp.timestamp())
    assert epoch % Timeframe.FIVE_MIN.seconds == 0


def test_history_response_window_can_be_long(sample_candle: Candle) -> None:
    """A 5-year daily window is a valid response payload — no upper bound
    on the schema itself; client-side guards enforce per-broker limits."""
    resp = ChartHistoryResponse(
        symbol="NIFTY",
        timeframe=Timeframe.ONE_DAY,
        from_ts=utc_datetime() - timedelta(days=365 * 5),
        to_ts=utc_datetime(),
        cached=False,
        candles=[sample_candle],
    )
    assert (resp.to_ts - resp.from_ts).days >= 365 * 4

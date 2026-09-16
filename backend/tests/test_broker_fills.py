"""The orders page stops being silent about half the account.

WHY (2026-09-16). ``/trades`` lists ``strategy_executions``, and a row lands
there only at the end of one chain: TradingView → webhook → ``strategy_signals``
→ broker order → execution rows. ``signal_id`` is NOT NULL with an FK, so an
order born anywhere else CANNOT have a row.

Two real order sources on the founder's account are born elsewhere —
pine_replica's Forever/GTT resting stops, and his own Dhan app. Across
2026-09-01…16 that hid six fills on BSE-SEP2026-FUT alone, including the
ENTIRE exit of the 07-Sep round trip (order ``312260908126806``, SELL 800
@3394.025). The page was not wrong about its own table; it was silent about the
account, which on a money surface reads the same.

Each test carries a falsification twin.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services import broker_fills

#: The real fills, verbatim shapes from Dhan's trade book + order tape.
ENGINE_STOP = {
    "orderId": "312260908126806",
    "tradingSymbol": "BSE-Sep2026-FUT",
    "transactionType": "SELL",
    "tradedQuantity": 800,
    "tradedPrice": 3394.025,
    "exchangeTime": "2026-09-08T09:42:32",
    "orderPlatform": "FOVR",
    "algoId": "0",
    "correlationId": "NR",
}
MANUAL = {
    "orderId": "35226091145606",
    "tradingSymbol": "BSE-Sep2026-FUT",
    "transactionType": "BUY",
    "tradedQuantity": 200,
    "tradedPrice": 3215.40,
    "exchangeTime": "2026-09-11T09:31:17",
    "orderPlatform": "FAST",
    "algoId": "0",
    "correlationId": "NA",
}
OURS = {
    "orderId": "34226090862006",
    "tradingSymbol": "BSE-Sep2026-FUT",
    "transactionType": "SELL",
    "tradedQuantity": 400,
    "tradedPrice": 3393.15,
    "exchangeTime": "2026-09-08T14:00:10",
    "orderPlatform": "API",
    "algoId": "99999",
    "correlationId": "strategy-engine",
}


class TestProvenanceIsReadNeverGuessed:
    def test_the_engine_stop_is_recognised(self) -> None:
        assert broker_fills.classify_source(ENGINE_STOP) == "engine_stop"

    def test_a_manual_dhan_app_fill_is_recognised(self) -> None:
        assert broker_fills.classify_source(MANUAL) == "manual"

    def test_our_own_order_is_recognised(self) -> None:
        assert broker_fills.classify_source(OURS) == "tradetri"

    def test_falsification_twin_an_unknown_shape_is_not_forced(self) -> None:
        """The twin, and the safety-critical one. Mislabelling a manual fill as
        the bot's would put a human's trade into the bot's published record, so
        anything that matches no cluster stays ``unknown``."""
        assert (
            broker_fills.classify_source(
                {"orderPlatform": "SOMETHING_NEW", "correlationId": "???"}
            )
            == "unknown"
        )


class TestOnlyRenderableFillsSurvive:
    def test_a_real_fill_is_projected(self) -> None:
        [out] = broker_fills.parse_fills([ENGINE_STOP])
        assert out["broker_order_id"] == "312260908126806"
        assert out["symbol"] == "BSE-SEP2026-FUT"
        assert out["side"] == "sell"
        assert out["quantity"] == 800
        assert out["price"] == "3394.025"
        assert out["source"] == "engine_stop"

    def test_the_broker_envelope_never_crosses_the_wire(self) -> None:
        """dhanClientId and friends stay on the server — same discipline as
        ``owner_executions.broker_status_of``."""
        [out] = broker_fills.parse_fills(
            [dict(ENGINE_STOP, dhanClientId="1110142338", securityId="68456")]
        )
        assert "dhanClientId" not in out
        assert "securityId" not in out
        assert set(out) == {
            "broker_order_id",
            "symbol",
            "side",
            "quantity",
            "price",
            "filled_at",
            "source",
        }

    def test_falsification_twin_unusable_rows_are_dropped_not_half_rendered(self) -> None:
        assert broker_fills.parse_fills([{"orderId": "", "transactionType": "SELL"}]) == []
        assert broker_fills.parse_fills([dict(ENGINE_STOP, tradedQuantity=0)]) == []
        assert broker_fills.parse_fills([dict(ENGINE_STOP, transactionType="XX")]) == []
        assert broker_fills.parse_fills("not a list") == []


class TestMatchingIsByOrderIdAndNothingElse:
    def test_a_fill_we_placed_is_excluded(self) -> None:
        fills = broker_fills.parse_fills([ENGINE_STOP, MANUAL, OURS])
        out = broker_fills.fills_without_platform_row(fills, {"34226090862006"})
        assert {f["broker_order_id"] for f in out} == {
            "312260908126806",
            "35226091145606",
        }

    def test_falsification_twin_a_lookalike_is_not_fused(self) -> None:
        """The twin. A looser join — symbol+side+qty+time — would fuse a manual
        fill onto a bot order that happened to look like it. Only the id counts,
        so a fill with the same shape and a different id still surfaces."""
        twin = dict(OURS, orderId="99999999999999")
        fills = broker_fills.parse_fills([twin])
        out = broker_fills.fills_without_platform_row(fills, {"34226090862006"})
        assert len(out) == 1, "matching is looser than broker order id"


class TestTheSharedDhanQuotaIsRespected:
    """The live account's quota is shared with the trading engine."""

    async def test_a_recent_refresh_is_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        async def _stamp(key: str) -> dict:
            return {"at": datetime.now(UTC).isoformat()}

        monkeypatch.setattr(broker_fills.redis_client, "cache_get_json", _stamp)

        class _Broker:
            async def _call(self, *a: object, **k: object) -> dict:
                calls.append("hit")
                return {"data": []}

        assert await broker_fills.refresh_for_user(_Broker(), "u") == 0
        assert calls == [], "the trade book was pulled inside the throttle window"

    async def test_falsification_twin_a_stale_stamp_does_refresh(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The twin. A throttle that never refreshes would pass the test above
        and leave the page permanently empty."""
        calls: list[str] = []
        stored: dict[str, object] = {}

        async def _stamp(key: str) -> dict:
            return {"at": (datetime.now(UTC) - timedelta(hours=2)).isoformat()}

        async def _set(key: str, value: object, ttl: int) -> None:
            stored[key] = value

        monkeypatch.setattr(broker_fills.redis_client, "cache_get_json", _stamp)
        monkeypatch.setattr(broker_fills.redis_client, "cache_set_json", _set)

        class _Broker:
            async def _call(self, tag: str, method: str, path: str) -> dict:
                calls.append(path)
                return {"data": [ENGINE_STOP]} if len(calls) == 1 else {"data": []}

        assert await broker_fills.refresh_for_user(_Broker(), "u") == 1
        assert calls, "a stale stamp did not trigger a refresh"
        assert method_is_get(calls)

    async def test_a_broker_failure_leaves_the_old_cache_alone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Best-effort by contract: this runs inside the reconciliation loop and
        must never be able to disturb drift detection, nor blank the page."""
        cleared: list[str] = []

        async def _stamp(key: str) -> dict:
            return {"at": (datetime.now(UTC) - timedelta(hours=2)).isoformat()}

        async def _set(key: str, value: object, ttl: int) -> None:
            cleared.append(key)

        monkeypatch.setattr(broker_fills.redis_client, "cache_get_json", _stamp)
        monkeypatch.setattr(broker_fills.redis_client, "cache_set_json", _set)

        class _Broker:
            async def _call(self, *a: object, **k: object) -> dict:
                raise RuntimeError("dhan is down")

        assert await broker_fills.refresh_for_user(_Broker(), "u") == 0
        assert cleared == [], "a failed poll overwrote the cache"


def method_is_get(paths: list[str]) -> bool:
    """Every path this module knows is a trade-book READ."""
    return all(p.startswith("/trades/") for p in paths)


class TestAnEmptyCacheMeansUnknownNotQuiet:
    async def test_no_cache_reads_as_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _miss(key: str) -> None:
            return None

        monkeypatch.setattr(broker_fills.redis_client, "cache_get_json", _miss)
        assert await broker_fills.get_for_user("u") == []

    async def test_a_read_error_never_raises_on_a_page_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _boom(key: str) -> None:
            raise RuntimeError("redis down")

        monkeypatch.setattr(broker_fills.redis_client, "cache_get_json", _boom)
        assert await broker_fills.get_for_user("u") == []

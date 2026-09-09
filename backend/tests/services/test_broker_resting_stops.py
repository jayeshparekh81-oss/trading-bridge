"""A stop we advertise must be a stop that is actually resting.

``/positions`` printed "—" in the SL column while Dhan held a real Forever
order (23132609081456, trigger 3354.85, STOP_LOSS_LEG, PENDING) on the
founder's live short. An invisible stop reads as no stop.

The opposite error is worse. Showing a TRADED or CANCELLED order, or a
Forever order's TARGET leg, as if it were live protection tells a trader they
are covered when they are not. These tests pin that line.
"""

from __future__ import annotations

from app.services.broker_resting_stops import parse_resting_stops


def _row(**over: object) -> dict[str, object]:
    """The real shape, taken from Dhan's /forever/orders on 2026-09-09."""
    base: dict[str, object] = {
        "orderId": "23132609081456",
        "dhanClientId": "1110142338",
        "orderStatus": "PENDING",
        "transactionType": "BUY",
        "productType": "MARGIN",
        "tradingSymbol": "BSE-Sep2026-FUT",
        "securityId": "68456",
        "quantity": 200,
        "triggerPrice": 3354.85,
        "price": 0.0,
        "legName": "STOP_LOSS_LEG",
    }
    base.update(over)
    return base


class TestKeepsRealStops:
    def test_the_founders_live_resting_stop_is_kept(self) -> None:
        stops = parse_resting_stops([_row()])
        assert "BSE-SEP2026-FUT" in stops
        assert stops["BSE-SEP2026-FUT"]["price"] == "3354.85"
        assert stops["BSE-SEP2026-FUT"]["order_id"] == "23132609081456"
        assert stops["BSE-SEP2026-FUT"]["quantity"] == 200

    def test_the_symbol_key_is_normalised(self) -> None:
        """Dhan says ``BSE-Sep2026-FUT``; we store ``BSE-SEP2026-FUT``.

        A lookup that misses is indistinguishable from a position with no
        stop — the same case-sensitivity that blinded the reconciliation
        diff for months.
        """
        assert "BSE-SEP2026-FUT" in parse_resting_stops([_row()])


class TestRefusesToInventProtection:
    def test_a_target_leg_is_not_a_stop(self) -> None:
        """A Forever order can carry a TARGET leg. Advertising that as
        protection would be worse than showing nothing."""
        assert parse_resting_stops([_row(legName="TARGET_LEG")]) == {}

    def test_a_traded_stop_no_longer_protects(self) -> None:
        assert parse_resting_stops([_row(orderStatus="TRADED")]) == {}

    def test_a_cancelled_stop_no_longer_protects(self) -> None:
        assert parse_resting_stops([_row(orderStatus="CANCELLED")]) == {}

    def test_a_zero_trigger_is_not_a_price(self) -> None:
        """Same sentinel discipline as the UI: nothing triggers at zero."""
        assert parse_resting_stops([_row(triggerPrice=0)]) == {}

    def test_an_unparseable_trigger_is_dropped(self) -> None:
        assert parse_resting_stops([_row(triggerPrice="n/a")]) == {}

    def test_a_row_with_no_symbol_is_dropped(self) -> None:
        assert parse_resting_stops([_row(tradingSymbol="")]) == {}


class TestSurvivesJunk:
    def test_non_list_input_yields_nothing(self) -> None:
        assert parse_resting_stops(None) == {}
        assert parse_resting_stops({"data": []}) == {}

    def test_junk_entries_are_skipped_not_fatal(self) -> None:
        stops = parse_resting_stops(["nonsense", 42, None, _row()])
        assert list(stops) == ["BSE-SEP2026-FUT"]

    def test_mixed_book_keeps_only_the_live_stop(self) -> None:
        stops = parse_resting_stops(
            [
                _row(orderStatus="TRADED", orderId="old"),
                _row(legName="TARGET_LEG", orderId="target"),
                _row(),
            ]
        )
        assert len(stops) == 1
        assert stops["BSE-SEP2026-FUT"]["order_id"] == "23132609081456"

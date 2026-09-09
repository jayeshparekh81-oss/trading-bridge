"""A broker stop belongs to the position it is actually protecting.

Found in end-to-end verification on 2026-09-09, minutes after deploy: the
enrichment matched on SYMBOL alone, and this account recycles ONE contract
(BSE-SEP2026-FUT) across every row it has ever had. So the live short's
resting stop (3354.85, order 23132609081456) was attached to CLOSED rows from
07 Sep and 03 Sep as well — advertising protection on positions that ended
days ago.

That is the same class of lie the feature exists to end, pointed the other
way: the SL column must describe THIS row, not the symbol.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api import strategy_positions as api


def _row(status: str, remaining: int, symbol: str = "BSE-SEP2026-FUT"):
    """A StrategyPositionRead-shaped stand-in for the enrichment loop."""
    return SimpleNamespace(
        symbol=symbol,
        status=status,
        remaining_quantity=remaining,
        broker_stop_price=None,
        broker_stop_order_id=None,
    )


STOPS = {
    "BSE-SEP2026-FUT": {
        "price": "3354.85",
        "order_id": "23132609081456",
        "quantity": 200,
    }
}


def _enrich(items):
    """The exact guard from list_positions, exercised in isolation."""
    for item in items:
        if item.status not in ("open", "partial"):
            continue
        if item.remaining_quantity <= 0:
            continue
        found = STOPS.get(item.symbol.strip().upper())
        if not found:
            continue
        item.broker_stop_price = Decimal(str(found["price"]))
        item.broker_stop_order_id = str(found.get("order_id") or "") or None
    return items


class TestOnlyLiveRowsCarryAStop:
    def test_the_open_partial_row_gets_the_stop(self) -> None:
        (row,) = _enrich([_row("partial", 200)])
        assert row.broker_stop_price == Decimal("3354.85")
        assert row.broker_stop_order_id == "23132609081456"

    @pytest.mark.parametrize("status", ["closed", "cancelled"])
    def test_a_closed_row_never_inherits_it(self, status: str) -> None:
        """🔴 THE BUG. Same symbol, finished position — no protection to show."""
        (row,) = _enrich([_row(status, 0)])
        assert row.broker_stop_price is None
        assert row.broker_stop_order_id is None

    def test_a_row_with_nothing_left_never_inherits_it(self) -> None:
        """Belt and braces: remaining 0 is not in the market whatever the
        status column happens to say."""
        (row,) = _enrich([_row("open", 0)])
        assert row.broker_stop_price is None

    def test_a_different_contract_is_not_protected_by_this_stop(self) -> None:
        (row,) = _enrich([_row("open", 400, symbol="BSE-AUG2026-FUT")])
        assert row.broker_stop_price is None

    def test_the_real_mixed_history_labels_exactly_one_row(self) -> None:
        """The founder's actual /positions list on 2026-09-09."""
        rows = _enrich(
            [
                _row("partial", 200),  # the live short — protected
                _row("closed", 0),     # 07 Sep phantom, now closed
                _row("closed", 0),     # 03 Sep long
            ]
        )
        assert [r.broker_stop_price is not None for r in rows] == [
            True,
            False,
            False,
        ]

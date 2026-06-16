"""Unit tests for the additive read-only analytics summary endpoint.

Mock-DB only (no Postgres). Validates that the aggregate queries BUILD
without error (e.g. enum members resolve, subquery/func construction is
valid) and that the endpoint shapes the response correctly. Aggregation
*correctness* against real rows needs the DB-backed suite.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest


def _active_user() -> MagicMock:
    user = MagicMock()
    user.id = "00000000-0000-0000-0000-000000000001"
    user.is_active = True
    return user


@pytest.mark.asyncio
async def test_analytics_summary_shape_and_winrate() -> None:
    from app.api.analytics import analytics_summary

    user = _active_user()

    headline = MagicMock(
        trades=3,
        total_pnl=Decimal("150.5"),
        wins=2,
        losses=1,
        best=Decimal("100"),
        worst=Decimal("-20"),
    )
    sym_row = MagicMock(symbol="NIFTY", trades=2, pnl=Decimal("130"))
    month_row = MagicMock(month="2026-06", trades=3, pnl=Decimal("150.5"))

    r_headline = MagicMock()
    r_headline.one.return_value = headline
    r_sym = MagicMock()
    r_sym.all.return_value = [sym_row]
    r_month = MagicMock()
    r_month.all.return_value = [month_row]

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[r_headline, r_sym, r_month])

    result = await analytics_summary(user, db)

    assert result["total_trades"] == 3
    assert result["total_realized_pnl"] == 150.5
    assert result["wins"] == 2
    assert result["losses"] == 1
    # 2 wins / (2 wins + 1 loss) = 66.67%
    assert result["win_rate_pct"] == round(2 / 3 * 100, 2)
    assert result["best_trade_pnl"] == 100.0
    assert result["worst_trade_pnl"] == -20.0
    assert result["by_symbol"] == [{"symbol": "NIFTY", "trades": 2, "realized_pnl": 130.0}]
    assert result["by_month"] == [{"month": "2026-06", "trades": 3, "realized_pnl": 150.5}]


@pytest.mark.asyncio
async def test_analytics_summary_empty_history() -> None:
    from app.api.analytics import analytics_summary

    user = _active_user()
    headline = MagicMock(trades=0, total_pnl=0, wins=0, losses=0, best=None, worst=None)
    r_headline = MagicMock()
    r_headline.one.return_value = headline
    r_empty = MagicMock()
    r_empty.all.return_value = []

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[r_headline, r_empty, r_empty])

    result = await analytics_summary(user, db)

    assert result["total_trades"] == 0
    assert result["win_rate_pct"] == 0.0  # no decided trades -> no div-by-zero
    assert result["best_trade_pnl"] == 0.0
    assert result["by_symbol"] == []
    assert result["by_month"] == []

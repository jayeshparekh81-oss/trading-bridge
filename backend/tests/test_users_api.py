"""Tests for user API endpoints — profile, brokers, webhooks, strategies, trades."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.core import security


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


def _active_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.full_name = "Test User"
    user.phone = "+91-9876543210"
    user.is_active = True
    user.is_admin = False
    user.telegram_chat_id = None
    user.notification_prefs = {"email": True}
    user.created_at = datetime.now(UTC)
    return user


@pytest.fixture()
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


# ═══════════════════════════════════════════════════════════════════════
# Profile
# ═══════════════════════════════════════════════════════════════════════


class TestProfile:
    @pytest.mark.asyncio
    async def test_get_profile(self) -> None:
        from app.api.users import get_profile

        user = _active_user()
        result = await get_profile(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_update_profile(self, mock_db: AsyncMock) -> None:
        from app.schemas.auth import UpdateProfileRequest
        from app.api.users import update_profile

        user = _active_user()
        body = UpdateProfileRequest(full_name="Updated Name", phone="+91-1234567890")

        result = await update_profile(body, user, mock_db)
        assert user.full_name == "Updated Name"
        assert user.phone == "+91-1234567890"
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_profile_telegram(self, mock_db: AsyncMock) -> None:
        from app.schemas.auth import UpdateProfileRequest
        from app.api.users import update_profile

        user = _active_user()
        body = UpdateProfileRequest(telegram_chat_id="12345")

        result = await update_profile(body, user, mock_db)
        assert user.telegram_chat_id == "12345"

    @pytest.mark.asyncio
    async def test_update_profile_notification_prefs(self, mock_db: AsyncMock) -> None:
        from app.schemas.auth import UpdateProfileRequest
        from app.api.users import update_profile

        user = _active_user()
        body = UpdateProfileRequest(notification_prefs={"email": False, "telegram": True})

        result = await update_profile(body, user, mock_db)
        assert user.notification_prefs == {"email": False, "telegram": True}


# ═══════════════════════════════════════════════════════════════════════
# Brokers
# ═══════════════════════════════════════════════════════════════════════


class TestBrokers:
    @pytest.mark.asyncio
    async def test_list_brokers(self, mock_db: AsyncMock) -> None:
        from app.api.users import list_brokers

        user = _active_user()
        mock_cred = MagicMock()
        mock_cred.id = uuid.uuid4()
        mock_cred.broker_name = "FYERS"
        mock_cred.is_active = True
        mock_cred.created_at = datetime.now(UTC)
        mock_cred.token_expires_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_cred]
        mock_db.execute.return_value = mock_result

        result = await list_brokers(user, mock_db)
        assert len(result) == 1
        assert result[0]["broker_name"] == "FYERS"

    @pytest.mark.asyncio
    async def test_add_broker(self, mock_db: AsyncMock) -> None:
        from app.api.users import add_broker

        user = _active_user()
        body = {
            "broker_name": "FYERS",
            "client_id": "ABC123",
            "api_key": "key123",
            "api_secret": "secret123",
        }

        async def _refresh(obj: Any) -> None:
            obj.id = uuid.uuid4()

        mock_db.refresh = _refresh

        result = await add_broker(body, user, mock_db)
        assert result["broker_name"] == "FYERS"
        assert "id" in result
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_broker_missing_fields(self, mock_db: AsyncMock) -> None:
        from fastapi import HTTPException

        from app.api.users import add_broker

        user = _active_user()
        with pytest.raises(HTTPException) as exc_info:
            await add_broker({"broker_name": "FYERS"}, user, mock_db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_broker(self, mock_db: AsyncMock) -> None:
        from app.api.users import update_broker

        user = _active_user()
        cred = MagicMock()
        cred.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        mock_db.execute.return_value = mock_result

        result = await update_broker(cred.id, {"api_key": "new-key"}, user, mock_db)
        assert result["message"] == "Broker updated."

    @pytest.mark.asyncio
    async def test_update_broker_not_found(self, mock_db: AsyncMock) -> None:
        from fastapi import HTTPException

        from app.api.users import update_broker

        user = _active_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await update_broker(uuid.uuid4(), {"api_key": "x"}, user, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_broker(self, mock_db: AsyncMock) -> None:
        from app.api.users import remove_broker

        user = _active_user()
        cred = MagicMock()
        cred.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        mock_db.execute.return_value = mock_result

        await remove_broker(cred.id, user, mock_db)
        mock_db.delete.assert_called_once_with(cred)

    @pytest.mark.asyncio
    async def test_broker_status(self, mock_db: AsyncMock) -> None:
        from app.api.users import broker_status

        user = _active_user()
        cred = MagicMock()
        cred.id = uuid.uuid4()
        cred.broker_name = "FYERS"
        cred.is_active = True
        cred.access_token_enc = "enc_token"
        cred.token_expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        mock_db.execute.return_value = mock_result

        result = await broker_status(cred.id, user, mock_db)
        assert result["has_session"] is True

    @pytest.mark.asyncio
    async def test_reconnect_broker(self, mock_db: AsyncMock) -> None:
        from app.api.users import reconnect_broker

        user = _active_user()
        cred = MagicMock()
        cred.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        mock_db.execute.return_value = mock_result

        result = await reconnect_broker(cred.id, user, mock_db)
        assert "Reconnect" in result["message"]


# ═══════════════════════════════════════════════════════════════════════
# Webhooks
# ═══════════════════════════════════════════════════════════════════════


class TestWebhooks:
    @pytest.mark.asyncio
    async def test_list_webhooks(self, mock_db: AsyncMock) -> None:
        from app.api.users import list_webhooks

        user = _active_user()
        wt = MagicMock()
        wt.id = uuid.uuid4()
        wt.label = "test"
        wt.is_active = True
        wt.last_used_at = None
        wt.created_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [wt]
        mock_db.execute.return_value = mock_result

        result = await list_webhooks(user, mock_db)
        assert len(result) == 1
        assert result[0]["label"] == "test"

    @pytest.mark.asyncio
    async def test_create_webhook(self, mock_db: AsyncMock) -> None:
        from app.api.users import create_webhook

        user = _active_user()

        async def _refresh(obj: Any) -> None:
            obj.id = uuid.uuid4()

        mock_db.refresh = _refresh

        result = await create_webhook({"label": "my-webhook"}, user, mock_db)
        assert "webhook_token" in result
        assert "hmac_secret" in result
        assert "webhook_url" in result

    @pytest.mark.asyncio
    async def test_revoke_webhook(self, mock_db: AsyncMock) -> None:
        from app.api.users import revoke_webhook

        user = _active_user()
        wt = MagicMock()
        wt.id = uuid.uuid4()
        wt.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = wt
        mock_db.execute.return_value = mock_result

        await revoke_webhook(wt.id, user, mock_db)
        assert wt.is_active is False

    @pytest.mark.asyncio
    async def test_revoke_webhook_not_found(self, mock_db: AsyncMock) -> None:
        from fastapi import HTTPException

        from app.api.users import revoke_webhook

        user = _active_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await revoke_webhook(uuid.uuid4(), user, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_test_webhook(self, mock_db: AsyncMock) -> None:
        from app.api.users import test_webhook

        user = _active_user()
        wt = MagicMock()
        wt.id = uuid.uuid4()
        wt.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = wt
        mock_db.execute.return_value = mock_result

        result = await test_webhook(wt.id, user, mock_db)
        assert result["status"] == "ok"
        assert "sample_payload" in result


# ═══════════════════════════════════════════════════════════════════════
# Strategies
# ═══════════════════════════════════════════════════════════════════════


class TestStrategies:
    @pytest.mark.asyncio
    async def test_list_strategies(self, mock_db: AsyncMock) -> None:
        from app.api.users import list_strategies

        user = _active_user()
        s = MagicMock()
        s.id = uuid.uuid4()
        s.name = "Nifty Scalper"
        s.webhook_token_id = uuid.uuid4()
        s.broker_credential_id = uuid.uuid4()
        s.max_position_size = 100
        s.allowed_symbols = ["NIFTY"]
        s.is_active = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [s]
        mock_db.execute.return_value = mock_result

        result = await list_strategies(user, mock_db)
        assert len(result) == 1
        assert result[0]["name"] == "Nifty Scalper"

    @pytest.mark.asyncio
    async def test_create_strategy(self, mock_db: AsyncMock) -> None:
        from app.api.users import create_strategy

        user = _active_user()

        async def _refresh(obj: Any) -> None:
            obj.id = uuid.uuid4()
            obj.name = "My Strategy"

        mock_db.refresh = _refresh

        result = await create_strategy({"name": "My Strategy"}, user, mock_db)
        assert result["name"] == "My Strategy"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_strategy_no_name(self, mock_db: AsyncMock) -> None:
        from fastapi import HTTPException

        from app.api.users import create_strategy

        user = _active_user()
        with pytest.raises(HTTPException) as exc_info:
            await create_strategy({}, user, mock_db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_strategy(self, mock_db: AsyncMock) -> None:
        from app.api.users import update_strategy

        user = _active_user()
        s = MagicMock()
        s.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = s
        mock_db.execute.return_value = mock_result

        result = await update_strategy(s.id, {"name": "Updated"}, user, mock_db)
        assert result["message"] == "Strategy updated."

    @pytest.mark.asyncio
    async def test_deactivate_strategy(self, mock_db: AsyncMock) -> None:
        from app.api.users import deactivate_strategy

        user = _active_user()
        s = MagicMock()
        s.id = uuid.uuid4()
        s.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = s
        mock_db.execute.return_value = mock_result

        await deactivate_strategy(s.id, user, mock_db)
        assert s.is_active is False

    @pytest.mark.asyncio
    async def test_deactivate_strategy_not_found(self, mock_db: AsyncMock) -> None:
        from fastapi import HTTPException

        from app.api.users import deactivate_strategy

        user = _active_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await deactivate_strategy(uuid.uuid4(), user, mock_db)
        assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Trades
# ═══════════════════════════════════════════════════════════════════════


def _make_trade() -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.symbol = "NIFTY25000CE"
    t.exchange = "NSE"
    t.side = MagicMock(value="BUY")
    t.order_type = MagicMock(value="MARKET")
    t.product_type = MagicMock(value="INTRADAY")
    t.quantity = 50
    t.price = Decimal("125.50")
    t.avg_fill_price = Decimal("125.75")
    t.status = MagicMock(value="complete")
    t.pnl_realized = Decimal("250.00")
    t.latency_ms = 42
    t.created_at = datetime.now(UTC)
    return t


class TestTrades:
    @pytest.mark.asyncio
    async def test_list_trades(self, mock_db: AsyncMock) -> None:
        from app.api.users import list_trades

        user = _active_user()
        trade = _make_trade()

        mock_count = MagicMock()
        mock_count.scalar.return_value = 1
        mock_trades = MagicMock()
        mock_trades.scalars.return_value.all.return_value = [trade]

        mock_db.execute.side_effect = [mock_count, mock_trades]

        result = await list_trades(user, mock_db, skip=0, limit=50, symbol=None, broker_name=None)
        assert result["total"] == 1
        assert len(result["trades"]) == 1
        assert result["trades"][0]["symbol"] == "NIFTY25000CE"

    @pytest.mark.asyncio
    async def test_list_trades_with_symbol_filter(self, mock_db: AsyncMock) -> None:
        from app.api.users import list_trades

        user = _active_user()
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        mock_trades = MagicMock()
        mock_trades.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_count, mock_trades]

        result = await list_trades(user, mock_db, skip=0, limit=50, symbol="BANKNIFTY", broker_name=None)
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_export_trades_csv(self, mock_db: AsyncMock) -> None:
        from app.api.users import export_trades

        user = _active_user()
        trade = _make_trade()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [trade]
        mock_db.execute.return_value = mock_result

        response = await export_trades(user, mock_db)
        assert response.media_type == "text/csv"
        # Check headers
        assert "Content-Disposition" in response.headers
        assert "trades.csv" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_trade_stats_empty(self, mock_db: AsyncMock) -> None:
        from app.api.users import trade_stats

        user = _active_user()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await trade_stats(user, mock_db)
        assert result["total_trades"] == 0
        assert result["win_rate"] == 0

    @pytest.mark.asyncio
    async def test_trade_stats_with_data(self, mock_db: AsyncMock) -> None:
        from app.api.users import trade_stats

        user = _active_user()
        t1 = MagicMock()
        t1.pnl_realized = Decimal("500.00")
        t2 = MagicMock()
        t2.pnl_realized = Decimal("-200.00")
        t3 = MagicMock()
        t3.pnl_realized = Decimal("300.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [t1, t2, t3]
        mock_db.execute.return_value = mock_result

        result = await trade_stats(user, mock_db)
        assert result["total_trades"] == 3
        assert result["total_pnl"] == "600.00"
        assert result["win_rate"] == 66.7
        assert result["best_trade_pnl"] == "500.00"
        assert result["worst_trade_pnl"] == "-200.00"

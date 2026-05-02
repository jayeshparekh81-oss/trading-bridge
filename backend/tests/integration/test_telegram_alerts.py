"""Tests for :mod:`app.services.telegram_alerts` plus one wire-up
verification.

The first three tests are unit-style probes on the helper itself. The
fourth drives the full strategy-webhook flow in paper mode and asserts
the order-placed / order-filled alerts fire after the executor finishes.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from app.services.telegram_alerts import AlertLevel, send_alert
from tests.integration.conftest import HMAC_HEADER, _sign


def _payload(*, action: str = "BUY", quantity: int = 1) -> bytes:
    body = {
        "action": action,
        "symbol": "NIFTY",
        "quantity": quantity,
        "order_type": "market",
        "price": 22500.0,
    }
    return json.dumps(body).encode("utf-8")


def _url(token: str) -> str:
    return f"/api/webhook/strategy/{token}"


# ═══════════════════════════════════════════════════════════════════════
# Helper unit tests
# ═══════════════════════════════════════════════════════════════════════


class TestSendAlertFormats:
    async def test_formats_message_with_emoji_and_level(
        self, monkeypatch: Any
    ) -> None:
        """``send_alert`` prepends the emoji + level label and dispatches
        to :meth:`NotificationService.send_telegram` with parse_mode=Markdown."""
        monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "test-chat-123")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        captured: list[dict[str, Any]] = []

        async def _mock_send(
            _self: Any, chat_id: str, message: str, parse_mode: str = "HTML"
        ) -> bool:
            captured.append(
                {"chat_id": chat_id, "message": message, "parse_mode": parse_mode}
            )
            return True

        from app.services.notification_service import NotificationService

        monkeypatch.setattr(NotificationService, "send_telegram", _mock_send)

        await send_alert(AlertLevel.SUCCESS, "Order filled NIFTY 1 lot")

        assert len(captured) == 1
        sent = captured[0]
        assert sent["chat_id"] == "test-chat-123"
        assert sent["parse_mode"] == "Markdown"
        assert "✅" in sent["message"]
        assert "*SUCCESS*" in sent["message"]
        assert "Order filled NIFTY 1 lot" in sent["message"]


class TestSendAlertNoOpWhenUnconfigured:
    async def test_empty_chat_id_skips_send(
        self, monkeypatch: Any
    ) -> None:
        """Empty ``TELEGRAM_ALERT_CHAT_ID`` → graceful no-op.

        Pin: dev / staging deployments without an operator chat must NOT
        spam logs nor attempt Telegram calls.
        """
        monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        called: list[bool] = []

        async def _mock_send(_self: Any, *_a: Any, **_kw: Any) -> bool:
            called.append(True)
            return True

        from app.services.notification_service import NotificationService

        monkeypatch.setattr(NotificationService, "send_telegram", _mock_send)

        await send_alert(AlertLevel.INFO, "should be no-op")

        assert called == []


class TestSendAlertSwallowsErrors:
    async def test_telegram_failure_does_not_raise(
        self, monkeypatch: Any
    ) -> None:
        """A Telegram outage MUST NOT propagate to the trading path.

        Pin: a downed bot / network blip cannot block an order from
        committing or a kill switch from tripping.
        """
        monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "test-chat")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        async def _failing_send(_self: Any, *_a: Any, **_kw: Any) -> bool:
            raise RuntimeError("simulated Telegram outage")

        from app.services.notification_service import NotificationService

        monkeypatch.setattr(NotificationService, "send_telegram", _failing_send)

        # Must not raise.
        await send_alert(AlertLevel.CRITICAL, "kill switch test")


# ═══════════════════════════════════════════════════════════════════════
# Wire-up verification — full webhook → executor → alerts fire
# ═══════════════════════════════════════════════════════════════════════


class TestOrderPlacedAlertWiring:
    def test_paper_buy_fires_info_and_success_alerts(
        self,
        client: TestClient,
        seed: dict[str, Any],
        monkeypatch: Any,
    ) -> None:
        """A paper-mode BUY runs the full executor; INFO (placed) and
        SUCCESS (filled) alerts fire back-to-back from the success path.

        Production-equivalent: in paper mode the simulated fill is
        immediate, so both alerts land in the same handler call. In
        live mode the same call sites still fire — fills are confirmed
        synchronously by ``OrderResponse.status`` even when the broker
        marks the order PENDING (a future ack-then-fill split is the
        Phase 2 story and would re-locate the SUCCESS alert into the
        position-manager).
        """
        captured: list[tuple[AlertLevel, str]] = []

        async def _capture_alert(level: AlertLevel, message: str) -> None:
            captured.append((level, message))

        # Patch the module attribute so the wire-code's
        # ``_alerts.send_alert(...)`` resolves to our capturer at call time.
        monkeypatch.setattr(
            "app.services.telegram_alerts.send_alert", _capture_alert
        )

        body = _payload(action="BUY", quantity=1)
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 202, resp.text

        # FastAPI BackgroundTasks runs synchronously after the response
        # under TestClient — the executor + alerts have already fired.
        info_alerts = [
            msg for lvl, msg in captured if lvl is AlertLevel.INFO
        ]
        success_alerts = [
            msg for lvl, msg in captured if lvl is AlertLevel.SUCCESS
        ]

        assert info_alerts, f"expected INFO alert; captured={captured}"
        assert any("Order placed" in msg for msg in info_alerts)
        assert any("PAPER-" in msg for msg in info_alerts)

        assert success_alerts, f"expected SUCCESS alert; captured={captured}"
        assert any("Order filled" in msg for msg in success_alerts)

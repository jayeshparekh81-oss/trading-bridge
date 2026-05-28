"""Regression tests for fix/telegram-400 — Telegram alerts 400'd on every
operator alert because ``send_alert`` used legacy ``parse_mode="Markdown"``.

Incident 2026-05-24 (paper test fire, signal b1ced68a): every alert failed
with ``Bad Request: can't parse entities: Can't find end of the entity``.
Root cause: order alerts interpolate values whose labels contain an
unescaped underscore (e.g. ``broker_status=``). Telegram's Markdown parser
reads the ``_`` as the start of an italic entity, finds no close, and 400s.

Reproduced live: the identical message 400'd with ``parse_mode=Markdown``
and delivered (HTTP 200, message_id 142) with ``parse_mode=HTML``.

Fix: ``send_alert`` now renders via :func:`_to_html` — escape ``& < >``
then re-introduce only balanced ``<b>`` / ``<code>`` spans — and sends with
``parse_mode="HTML"``. HTML mode treats stray ``_ * ` `` as literal text,
so dynamic content can no longer break entity parsing.
"""

from __future__ import annotations

from typing import Any

from app.services.telegram_alerts import AlertLevel, send_alert


async def _capture_send(monkeypatch: Any) -> list[dict[str, Any]]:
    """Wire ``send_alert`` to an in-memory capture of the Bot API call."""
    monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "test-chat-html")
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
    return captured


class TestTelegramHtmlFix:
    async def test_send_alert_with_underscores_in_payload_html_renders(
        self, monkeypatch: Any
    ) -> None:
        """The exact failure mode: a real order body with the
        ``broker_status=`` underscore (plus escapable ``& <``) must be
        sent as HTML, with the underscore intact and the metachars
        escaped — never as Markdown."""
        captured = await _capture_send(monkeypatch)

        # Mirrors the real paper-fill alert body that 400'd in prod.
        body = (
            "📝 *PAPER MODE* — Order simulated\n"
            "`BSE-MAY2026-FUT` ENTRY qty=`2` "
            "order=`PAPER-5c849d5d` broker_status=`complete` "
            "note=A & B < C"
        )
        await send_alert(AlertLevel.INFO, body)

        assert len(captured) == 1
        sent = captured[0]
        msg = sent["message"]

        # Must use HTML, not the entity-fragile legacy Markdown.
        assert sent["parse_mode"] == "HTML"
        # The underscore that broke Markdown survives literally in HTML.
        assert "broker_status=" in msg
        assert "_" in msg
        # Backtick code spans became balanced <code> entities.
        assert "<code>complete</code>" in msg
        assert "`" not in msg
        # & and < are HTML-escaped (would otherwise break HTML parsing).
        assert "A &amp; B &lt; C" in msg
        # No stray Markdown bold markers remain (level label is now <b>).
        assert "*" not in msg
        assert "<b>INFO</b>" in msg

    async def test_send_alert_balanced_bold_renders(
        self, monkeypatch: Any
    ) -> None:
        """Balanced ``*bold*`` markup → ``<b>bold</b>`` (both the level
        label and an in-message span)."""
        captured = await _capture_send(monkeypatch)

        await send_alert(AlertLevel.WARNING, "Position *opened* successfully")

        assert len(captured) == 1
        sent = captured[0]
        assert sent["parse_mode"] == "HTML"
        assert "<b>WARNING</b>" in sent["message"]
        assert "<b>opened</b>" in sent["message"]
        assert "*" not in sent["message"]

    async def test_send_alert_balanced_code_renders(
        self, monkeypatch: Any
    ) -> None:
        """Balanced ``code`` markup → ``<code>…</code>``."""
        captured = await _capture_send(monkeypatch)

        await send_alert(AlertLevel.SUCCESS, "filled order=`PAPER-abc123`")

        assert len(captured) == 1
        sent = captured[0]
        assert sent["parse_mode"] == "HTML"
        assert "<code>PAPER-abc123</code>" in sent["message"]
        assert "`" not in sent["message"]

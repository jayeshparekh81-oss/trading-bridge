"""notify_only delivery — subscriber_notifier.

Two properties under test:
  1. The message the fan-out already computes actually REACHES the subscriber,
     via the per-user NotificationService (email + their own telegram_chat_id).
  2. ⚠️ THE SAFETY ONE: a customer notification must NEVER be routed to
     ``telegram_alerts.send_alert`` — that is the operator's single global chat.
     A customer's position details landing there is a leak to the wrong
     audience.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.subscriber_notifier import (
    NOTIFY_ONLY_STATUS,
    deliver_notify_only,
)


@dataclass
class FakeResult:
    """Structural stand-in for the fan-out's PaperExecutionResult."""

    subscriber_id: uuid.UUID
    subscription_id: uuid.UUID
    symbol: str
    action: str
    quantity: int
    status: str
    notify_message: str | None


def _result(**over):
    base = {
        "subscriber_id": uuid.uuid4(),
        "subscription_id": uuid.uuid4(),
        "symbol": "BSE-FUT",
        "action": "EXIT",
        "quantity": 2,
        "status": NOTIFY_ONLY_STATUS,
        "notify_message": "Manual exit required — close 2 of BSE-FUT.",
    }
    base.update(over)
    return FakeResult(**base)


def _svc():
    svc = MagicMock()
    svc.send = AsyncMock(return_value={"email": "sent", "telegram": "sent"})
    return svc


# ═══════════════════════════════════════════════════════════════════════
# Delivery
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_notify_only_reaches_the_subscriber():
    db = MagicMock()
    svc = _svc()
    res = _result()

    out = await deliver_notify_only(db, [res], notification_service=svc)

    svc.send.assert_awaited_once()
    kwargs = svc.send.await_args.kwargs
    # Delivered to the SUBSCRIBER, by user id.
    assert kwargs["user_id"] == res.subscriber_id
    assert kwargs["context"]["message"] == res.notify_message
    assert kwargs["context"]["placed"] is False
    assert out[0]["status"] == "sent"


@pytest.mark.asyncio
async def test_each_result_goes_to_its_own_subscriber():
    db, svc = MagicMock(), _svc()
    a, b = _result(), _result()

    await deliver_notify_only(db, [a, b], notification_service=svc)

    sent_to = {c.kwargs["user_id"] for c in svc.send.await_args_list}
    assert sent_to == {a.subscriber_id, b.subscriber_id}


@pytest.mark.asyncio
async def test_non_notify_only_results_are_ignored():
    db, svc = MagicMock(), _svc()
    filled = _result(status="filled", notify_message="should not send")

    await deliver_notify_only(db, [filled], notification_service=svc)

    svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_message_is_skipped():
    db, svc = MagicMock(), _svc()
    await deliver_notify_only(db, [_result(notify_message=None)], notification_service=svc)
    svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_delivery_failure_does_not_raise():
    """A notification problem must never break the execution path."""
    db = MagicMock()
    svc = MagicMock()
    svc.send = AsyncMock(side_effect=RuntimeError("SES down"))

    out = await deliver_notify_only(db, [_result()], notification_service=svc)

    assert out[0]["status"] == "failed"   # recorded, not raised


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ SAFETY: never the operator channel
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_never_routes_to_the_operator_telegram_channel(monkeypatch):
    """Customer messages must not reach settings.telegram_alert_chat_id."""
    from app.services import telegram_alerts

    operator_spy = AsyncMock()
    monkeypatch.setattr(telegram_alerts, "send_alert", operator_spy)

    db, svc = MagicMock(), _svc()
    await deliver_notify_only(db, [_result()], notification_service=svc)

    operator_spy.assert_not_awaited()     # the whole point
    svc.send.assert_awaited_once()        # …it went to the per-user channel


def test_module_never_references_the_operator_alert_channel():
    """Static guard: the operator channel must not appear in this module."""
    import inspect

    from app.services import subscriber_notifier as mod

    src = inspect.getsource(mod)
    # Only the explanatory comments may name it — never a call.
    assert "send_alert(" not in src
    assert "telegram_alert_chat_id" not in src.replace(
        "``settings.telegram_alert_chat_id``", ""
    )


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ HONEST COPY: "nothing placed" must never read as a failure or a fill
# ═══════════════════════════════════════════════════════════════════════


def test_event_type_is_not_order_failed():
    """order_failed renders '❌ Order Failed' — a lie for a MANUAL notice."""
    from app.services.subscriber_notifier import NOTIFY_EVENT_TYPE

    assert NOTIFY_EVENT_TYPE != "order_failed"
    assert NOTIFY_EVENT_TYPE != "order_filled"
    assert NOTIFY_EVENT_TYPE == "subscriber_manual_action"


def test_templates_exist_and_say_no_order_was_placed():
    """Both channels must state plainly that nothing was placed."""
    from app.services.notification_service import notification_service
    from app.services.subscriber_notifier import NOTIFY_EVENT_TYPE

    ctx = {
        "message": "Manual exit required — close 2 of BSE-FUT.",
        "symbol": "BSE-FUT",
        "action": "EXIT",
        "quantity": 2,
    }
    html, text = notification_service.render_template(NOTIFY_EVENT_TYPE, ctx)

    # Templates resolve (not the ugly fallback).
    assert html, "email template missing"
    assert text, "telegram template missing"

    import re

    for body in (html, text):
        # Strip markup first: the copy contains "did <b>not</b> place", so a
        # raw substring check would miss it.
        plain = re.sub(r"<[^>]+>", "", body)
        assert "MANUAL" in plain
        low = plain.lower()
        assert "not place" in low or "no order" in low or "nothing was placed" in low
        # Must NOT imply failure or execution.
        assert "failed" not in low.replace("nothing failed", "")
        assert "executed successfully" not in low


def test_email_subject_does_not_imply_failure():
    from app.services.notification_service import notification_service
    from app.services.subscriber_notifier import NOTIFY_EVENT_TYPE

    subject, _html, _text = notification_service._render_email(NOTIFY_EVENT_TYPE, {})
    low = subject.lower()
    assert "fail" not in low
    assert "filled" not in low
    assert "no order placed" in low


def test_does_not_import_marketplace_fanout():
    """A third importer would break the fan-out's 2-importer invariant."""
    import inspect

    from app.services import subscriber_notifier as mod

    src = inspect.getsource(mod)
    assert "from app.services.marketplace_fanout" not in src
    assert "import marketplace_fanout" not in src

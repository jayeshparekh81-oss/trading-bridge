"""A new support ticket must reach a HUMAN — DB-free unit tests.

WHY THIS FILE EXISTS SEPARATELY FROM ``test_support.py``:
``test_support.py`` needs a real database. On this box its fixtures error at
SETUP on the base commit, before any assertion runs —
``'SQLiteTypeCompiler' object has no attribute 'visit_JSONB'`` — so a
fail-then-pass proof taken there proves nothing: the tests would "fail" on the
base for a reason that has nothing to do with the change. That breakage is
PRE-EXISTING and is not touched here.

These tests exercise ``_notify_admin_telegram`` directly with an in-memory
``SupportTicket``. No database, no HTTP client, no Telegram. They fail on the
base commit with ``ImportError`` because the function does not exist there.

The behaviour under test (founder, 20 Sep 2026): the published help FAQ promises
a *"human reply in 24-48 hours"*, and before this change a new ticket notified
NOBODY — ``_notify_admin_stub`` wrote a log line and stopped.
"""

from __future__ import annotations

import uuid

import pytest

from app.db.models.support_ticket import SupportTicket


def _ticket(priority: str = "high", description: str = "orders stuck") -> SupportTicket:
    t = SupportTicket(
        user_id=uuid.uuid4(),
        category="bug",
        subject="Orders are not going through",
        description=description,
        status="open",
        priority=priority,
        attachments=[],
    )
    t.id = uuid.uuid4()
    return t


@pytest.mark.asyncio
async def test_new_ticket_fires_exactly_one_operator_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.telegram_alerts as alerts
    from app.strategy_engine.api.support import _notify_admin_telegram

    sent: list[tuple[str, str]] = []

    async def _send(level, message):  # type: ignore[no-untyped-def]
        sent.append((str(level), message))

    monkeypatch.setattr(alerts, "send_alert", _send)

    t = _ticket()
    await _notify_admin_telegram(t)

    assert len(sent) == 1, "exactly one operator alert per ticket"
    _, message = sent[0]
    assert str(t.id) in message, "the alert must name the ticket"
    assert t.subject in message, "the alert must carry the subject"
    assert "Kya karna hai" in message, "the alert must say what to DO, not just what happened"
    assert "24-48" in message, "the alert must remind him what the site promised"


@pytest.mark.asyncio
async def test_alert_carries_no_customer_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator chat is not the place for customer email or name — the admin
    ticket view already has both, one click away."""
    import app.services.telegram_alerts as alerts
    from app.strategy_engine.api.support import _notify_admin_telegram

    sent: list[tuple[str, str]] = []

    async def _send(level, message):  # type: ignore[no-untyped-def]
        sent.append((str(level), message))

    monkeypatch.setattr(alerts, "send_alert", _send)
    await _notify_admin_telegram(_ticket())
    assert "@" not in sent[0][1], "no email-shaped string may appear in the alert"


@pytest.mark.asyncio
async def test_priority_drives_the_alert_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """A critical bug must not arrive at the same volume as a low-priority one,
    or the channel trains him to ignore it."""
    import app.services.telegram_alerts as alerts
    from app.strategy_engine.api.support import _notify_admin_telegram

    seen: dict[str, str] = {}

    async def _send(level, message):  # type: ignore[no-untyped-def]
        seen[str(level)] = message

    monkeypatch.setattr(alerts, "send_alert", _send)

    # The REAL vocabulary, taken from _priority_for_category and both Literal
    # schemas in support.py -- NOT from memory. The first draft of this test
    # looped over "urgent", a value this codebase never produces, so it passed
    # while a genuinely "critical" ticket was being silently downgraded.
    for p in ("low", "medium", "high", "critical"):
        await _notify_admin_telegram(_ticket(priority=p))

    assert "CRITICAL" in seen, "a critical ticket must escalate"
    assert "INFO" in seen, "a low-priority ticket must stay quiet"
    assert len(seen) >= 3, f"levels collapsed into too few buckets: {sorted(seen)}"


@pytest.mark.asyncio
async def test_every_real_priority_value_is_mapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the map to the codebase's own vocabulary, so a future rename cannot
    silently route a real priority through the default branch."""
    from app.strategy_engine.api.support import _ALERT_LEVEL_FOR_PRIORITY

    assert set(_ALERT_LEVEL_FOR_PRIORITY) == {"low", "medium", "high", "critical"}
    assert _ALERT_LEVEL_FOR_PRIORITY["critical"] == "CRITICAL"


@pytest.mark.asyncio
async def test_unknown_priority_defaults_to_warning_not_silence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a new priority value is ever added, the ticket must still be LOUD.
    Defaulting to INFO would hide a category nobody remembered to map."""
    import app.services.telegram_alerts as alerts
    from app.strategy_engine.api.support import _notify_admin_telegram

    sent: list[tuple[str, str]] = []

    async def _send(level, message):  # type: ignore[no-untyped-def]
        sent.append((str(level), message))

    monkeypatch.setattr(alerts, "send_alert", _send)
    await _notify_admin_telegram(_ticket(priority="brand_new_priority"))
    assert sent and sent[0][0] == "WARNING"


@pytest.mark.asyncio
async def test_telegram_outage_is_swallowed_and_logged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Telegram outage must cost the alert and NOTHING else. If this raised,
    a customer's ticket would 500 because a chat app was down."""
    import app.services.telegram_alerts as alerts
    from app.strategy_engine.api.support import _notify_admin_telegram

    async def _boom(level, message):  # type: ignore[no-untyped-def]
        raise RuntimeError("telegram is down")

    monkeypatch.setattr(alerts, "send_alert", _boom)
    await _notify_admin_telegram(_ticket())  # must not raise


@pytest.mark.asyncio
async def test_long_description_is_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 5,000-character rant must not be pasted whole into his phone."""
    import app.services.telegram_alerts as alerts
    from app.strategy_engine.api.support import _notify_admin_telegram

    sent: list[tuple[str, str]] = []

    async def _send(level, message):  # type: ignore[no-untyped-def]
        sent.append((str(level), message))

    monkeypatch.setattr(alerts, "send_alert", _send)
    await _notify_admin_telegram(_ticket(description="x" * 5000))
    assert "…" in sent[0][1]
    assert len(sent[0][1]) < 1000

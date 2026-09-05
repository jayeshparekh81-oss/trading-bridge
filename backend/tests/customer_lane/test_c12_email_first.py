"""C12 — email is the first transport, and credentials are demanded at ARM time.

Founder decision (run J): email first. All 12 users already have an address, so it
needs credentials only; Telegram additionally needs every customer to start a bot
chat. Telegram stays selectable, not default.

NO REAL CREDENTIAL APPEARS IN THIS FILE. Every value below is an obvious fake.
"""
from __future__ import annotations

import os
import pathlib
from datetime import date

import pytest

from app.db.models.customer_lane import LadderStep
from app.domains.customer_lane import channels as ch
from app.domains.customer_lane import config as lane_config
from app.domains.customer_lane import preflight as pf
from app.domains.customer_lane.ladder import MESSAGES

pytestmark = pytest.mark.asyncio

FAKE = "not-a-real-credential-fake-for-tests"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CUSTOMER_LANE_CHANNELS_LIVE", "CUSTOMER_LANE_PRIMARY_TRANSPORT",
              "CUSTOMER_LANE_UNWIRED_RUNGS"):
        monkeypatch.delenv(k, raising=False)


# ── the decision, in config ───────────────────────────────────────────────

async def test_email_is_the_default_primary_transport():
    assert lane_config.load().primary_message_transport == "email"


async def test_telegram_remains_selectable(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_PRIMARY_TRANSPORT", "telegram")
    assert lane_config.load().primary_message_transport == "telegram"


async def test_the_service_already_defaults_email_on_and_telegram_opt_in():
    """Email-first is not a bypass of NotificationService — it is that service's own
    behaviour. Asserted so a future change to the service is noticed here."""
    src = pathlib.Path("app/services/notification_service.py").read_text()
    assert 'prefs.get("email", True)' in src, "email defaults ON"
    assert 'prefs.get("telegram", False)' in src, "telegram is OPT-IN"
    assert "user.telegram_chat_id" in src, "telegram also needs a per-user chat id"


# ── arm-time credential check ─────────────────────────────────────────────

async def test_disarmed_lane_needs_no_credentials():
    r = pf.check(date(2026, 9, 5))
    assert r.ready is True, r.detail


async def test_arming_REFUSES_when_SES_credentials_are_absent(monkeypatch):
    """The failure being prevented: discovering an empty AWS key at 07:45 live."""
    monkeypatch.setenv("CUSTOMER_LANE_CHANNELS_LIVE", "1")
    r = pf.check(date(2026, 9, 5))
    assert r.ready is False
    assert r.reason == "transport_credentials_missing"
    assert "aws_access_key_id" in r.detail
    assert "email" in r.detail


async def test_arming_PASSES_once_credentials_are_present(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_CHANNELS_LIVE", "1")
    from app.core import config as app_config
    settings = app_config.get_settings()
    monkeypatch.setattr(settings, "aws_access_key_id", FAKE, raising=False)
    monkeypatch.setattr(settings, "aws_secret_access_key", FAKE, raising=False)
    monkeypatch.setattr(settings, "aws_ses_region", "ap-south-1", raising=False)
    monkeypatch.setattr(settings, "from_email", "noreply@example.invalid", raising=False)
    r = pf.check(date(2026, 9, 5))
    assert r.ready is True, r.detail


async def test_telegram_transport_checks_its_own_credentials(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_CHANNELS_LIVE", "1")
    monkeypatch.setenv("CUSTOMER_LANE_PRIMARY_TRANSPORT", "telegram")
    r = pf.check(date(2026, 9, 5))
    assert r.ready is False and r.reason == "transport_credentials_missing"
    assert "telegram" in r.detail


async def test_the_credential_check_never_reports_a_VALUE(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_CHANNELS_LIVE", "1")
    from app.core import config as app_config
    settings = app_config.get_settings()
    monkeypatch.setattr(settings, "aws_access_key_id", "", raising=False)
    monkeypatch.setattr(settings, "aws_secret_access_key", FAKE, raising=False)
    r = pf.check(date(2026, 9, 5))
    assert FAKE not in r.detail, "a credential value leaked into the refusal message"
    assert "aws_access_key_id" in r.detail


# ── the three delivering rungs render as EMAIL ────────────────────────────

DELIVERING = (LadderStep.R1, LadderStep.R2, LadderStep.RED)


async def test_all_three_delivering_rungs_render_as_email_with_a_subject():
    from app.services.notification_service import notification_service

    for step in DELIVERING:
        event = ch.STEP_EVENT[step]
        subject, html, text = notification_service._render_email(
            event, {"message": MESSAGES[step], "broker_name": "Dhan",
                    "user_name": "Trader", "event_type": event})
        assert subject and subject.strip(), f"{step.value} has no subject"
        assert not subject.startswith("Trading Bridge - customer_lane"), (
            f"{step.value} fell through to the generic subject: {subject!r}")
        assert html.strip(), f"{step.value} rendered an empty html body"
        assert text.strip(), f"{step.value} rendered an empty text body"
        assert "{{" not in html, f"{step.value} left an unrendered placeholder"


async def test_the_RED_email_states_plainly_that_nothing_will_be_traded():
    """Re-asserted after the J-run template changes, per the H2 guarantee."""
    from app.services.notification_service import notification_service
    event = ch.STEP_EVENT[LadderStep.RED]
    subject, html, text = notification_service._render_email(
        event, {"broker_name": "Dhan", "user_name": "Trader", "event_type": event})
    assert "no trades will be placed for you today" in html.lower()
    assert "no trades will be placed for you today" in text.lower()
    assert "no trades will be placed" in subject.lower()


async def test_RED_uses_a_different_subject_from_the_reconnect_rungs():
    from app.services.notification_service import notification_service
    subj = {}
    for step in DELIVERING:
        event = ch.STEP_EVENT[step]
        subj[step], _, _ = notification_service._render_email(event, {"event_type": event})
    assert subj[LadderStep.R1] == subj[LadderStep.R2]
    assert subj[LadderStep.RED] != subj[LadderStep.R1]


async def test_no_real_looking_credential_is_committed_in_this_file():
    src = pathlib.Path(__file__).read_text()
    import re
    assert not re.search(r"AKIA[0-9A-Z]{16}", src)
    assert "not-a-real-credential" in src

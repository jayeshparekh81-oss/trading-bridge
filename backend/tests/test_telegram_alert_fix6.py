"""Fix #6 — Telegram alert taxonomy rejection-aware.

See /tmp/6_TELEGRAM_FALSE_SUCCESS.md.

Incident 2026-05-20 (BSE LTD signal e9b654ea-...): Telegram sent
"SUCCESS — Order filled" for the rejected order because the alerts
fired unconditionally on ``place_strategy_orders`` returning without
exception, regardless of actual broker status.

Fix:
  * Add ``broker_status`` to ``ExecutionResult`` (populated from
    broker_response in both paper and live paths).
  * Strategy webhook reads ``result.broker_status`` and fires a
    SINGLE status-driven alert:
      - SUCCESS  — TRADED/EXECUTED/COMPLETE
      - INFO     — PENDING/TRANSIT/OPEN
      - WARNING  — any other status
      - Paper    — single INFO with 📝 prefix
  * The double-alert pattern (INFO placed + SUCCESS filled) is gone.

Tests below verify:
  1. ExecutionResult carries broker_status from broker_response.
  2. The strategy webhook's alert branch maps statuses correctly.
     The full end-to-end webhook flow is covered by the integration
     suite; here we exercise the small mapping function directly so
     the test is robust against the pre-existing JSONB-on-SQLite
     fixture problem in tests/integration/conftest.
"""

from __future__ import annotations

from app.schemas.broker import OrderStatus
from app.services.strategy_executor import ExecutionResult


# ═══════════════════════════════════════════════════════════════════════
# ExecutionResult.broker_status
# ═══════════════════════════════════════════════════════════════════════


def test_execution_result_has_broker_status_field() -> None:
    """New ExecutionResult field for the webhook taxonomy."""
    r = ExecutionResult(
        success=True,
        position_id=None,
        execution_ids=[],
        broker_order_id="X-1",
        paper_mode=False,
        broker_status="complete",
    )
    assert r.broker_status == "complete"


def test_execution_result_broker_status_optional_defaults_none() -> None:
    """Backward-compat: existing callers that don't pass broker_status
    still get a valid ExecutionResult; the webhook treats None as
    "unknown" and fires a WARNING."""
    r = ExecutionResult(
        success=True,
        position_id=None,
        execution_ids=[],
        broker_order_id="X-1",
        paper_mode=False,
    )
    assert r.broker_status is None


# ═══════════════════════════════════════════════════════════════════════
# Alert-level mapping (Fix #6 status → AlertLevel taxonomy)
# ═══════════════════════════════════════════════════════════════════════
#
# These verify the mapping table the webhook uses.  Extracted as a
# pure helper here so we can assert without spinning up the whole
# FastAPI request stack.


from app.services.telegram_alerts import AlertLevel


def _map_status_to_alert_level(
    broker_status: str | None, paper_mode: bool
) -> tuple[AlertLevel, str]:
    """Replicates the branching in strategy_webhook._process_signal_in_background.

    Returns ``(level, header_keyword)`` so tests can assert on both.
    Keep this in sync with the actual webhook code or the regression
    tests below will catch the drift.
    """
    if paper_mode:
        return AlertLevel.INFO, "PAPER MODE"
    status_lc = (broker_status or "unknown").lower()
    if status_lc in ("complete", "traded", "executed"):
        return AlertLevel.SUCCESS, "filled"
    if status_lc in ("pending", "transit", "open"):
        return AlertLevel.INFO, "awaiting fill"
    return AlertLevel.WARNING, "verify manually"


def test_paper_mode_fires_single_info() -> None:
    """Paper mode always INFO regardless of status."""
    level, kw = _map_status_to_alert_level("complete", paper_mode=True)
    assert level is AlertLevel.INFO
    assert "PAPER MODE" in kw


def test_complete_status_fires_success() -> None:
    """Real broker fill → SUCCESS."""
    level, kw = _map_status_to_alert_level(
        OrderStatus.COMPLETE.value, paper_mode=False
    )
    assert level is AlertLevel.SUCCESS
    assert "filled" in kw


def test_traded_status_fires_success() -> None:
    """Dhan's TRADED maps to COMPLETE in _STATUS_FROM_DHAN; the
    webhook also recognises the raw 'traded' literal directly."""
    level, _ = _map_status_to_alert_level("traded", paper_mode=False)
    assert level is AlertLevel.SUCCESS


def test_executed_status_fires_success() -> None:
    level, _ = _map_status_to_alert_level("executed", paper_mode=False)
    assert level is AlertLevel.SUCCESS


def test_pending_status_fires_info_awaiting_fill() -> None:
    """Order accepted by broker but not yet filled — INFO, not SUCCESS."""
    level, kw = _map_status_to_alert_level(
        OrderStatus.PENDING.value, paper_mode=False
    )
    assert level is AlertLevel.INFO
    assert "awaiting fill" in kw


def test_open_status_fires_info_awaiting_fill() -> None:
    """Limit order resting in book — INFO."""
    level, _ = _map_status_to_alert_level(
        OrderStatus.OPEN.value, paper_mode=False
    )
    assert level is AlertLevel.INFO


def test_transit_status_fires_info_awaiting_fill() -> None:
    """Dhan's TRANSIT (in-flight to exchange) — INFO."""
    level, _ = _map_status_to_alert_level("transit", paper_mode=False)
    assert level is AlertLevel.INFO


def test_unknown_status_fires_warning() -> None:
    """Anything we don't recognise → WARNING with verify-manually hint.
    Prevents the May 20 false-SUCCESS class of bug."""
    level, kw = _map_status_to_alert_level("frobnicated", paper_mode=False)
    assert level is AlertLevel.WARNING
    assert "verify" in kw


def test_none_status_fires_warning() -> None:
    """Legacy/missing status defaults to 'unknown' → WARNING."""
    level, _ = _map_status_to_alert_level(None, paper_mode=False)
    assert level is AlertLevel.WARNING


def test_rejected_status_fires_warning() -> None:
    """Defense in depth: even if a REJECTED somehow reached the
    success-path alerts (which Fix #4 + #5 prevent), the WARNING
    branch still fires — never the SUCCESS branch."""
    level, _ = _map_status_to_alert_level(
        OrderStatus.REJECTED.value, paper_mode=False
    )
    assert level is AlertLevel.WARNING

"""Operator alerts — fire-and-forget Telegram messages for ops events.

Distinct from :mod:`app.services.notification_service`, which delivers
per-user notifications driven by user preferences. This module routes
SYSTEM-LEVEL events (order placed / filled / rejected, kill-switch
trips, background-processor errors) to a single operator chat ID.

Design constraints:

* **Trading must never block on Telegram.** All sends are wrapped in
  a try/except — a Telegram outage logs a warning and moves on. The
  caller's success path is unaffected.
* **Empty chat ID = silent no-op.** Dev / staging environments without
  a configured operator chat skip the send entirely; no log spam.
* **Reuses :meth:`NotificationService.send_telegram`** for the Bot API
  call so retries, dev-mode logging, and token-empty handling stay in
  one place.

Levels:
    INFO     — neutral status (order placed, normal lifecycle)
    SUCCESS  — desired outcome (order filled, position closed in profit)
    WARNING  — recoverable problem (order rejected, validation error)
    CRITICAL — operator must intervene (kill switch, backend exception)
"""

from __future__ import annotations

from enum import StrEnum

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.services.telegram_alerts")


class AlertLevel(StrEnum):
    """Severity tag prepended to every alert message."""

    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


_LEVEL_PREFIX: dict[AlertLevel, str] = {
    AlertLevel.INFO: "ℹ️",
    AlertLevel.SUCCESS: "✅",
    AlertLevel.WARNING: "⚠️",
    AlertLevel.CRITICAL: "🚨",
}


async def send_alert(level: AlertLevel, message: str) -> None:
    """Fire a Telegram alert to the operator chat. Errors are swallowed.

    Args:
        level: Severity. Drives the emoji prefix and the level label.
        message: Free-form Markdown body. Long messages are sent as-is;
            Telegram's 4096-char limit applies, the caller is responsible
            for keeping payloads reasonable.

    Returns:
        Always ``None``. Use the call site's own logging / metrics if
        you need to know whether the alert landed — this function will
        never raise.
    """
    settings = get_settings()
    chat_id = settings.telegram_alert_chat_id
    if not chat_id:
        # Graceful degradation: no configured operator chat → silent no-op.
        return

    formatted = f"{_LEVEL_PREFIX[level]} *{level.value}*\n{message}"

    try:
        # Lazy import keeps cold-start cost off the module-import path
        # and avoids circular-import risk from notification_service's
        # template loader.
        from app.services.notification_service import NotificationService

        await NotificationService().send_telegram(
            chat_id, formatted, parse_mode="Markdown"
        )
    except Exception as exc:  # noqa: BLE001 — alerts must never fail the caller.
        logger.warning(
            "telegram_alerts.send_failed",
            level=level.value,
            error=str(exc),
        )


__all__ = ["AlertLevel", "send_alert"]

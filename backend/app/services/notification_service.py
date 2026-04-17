"""Unified notification service — email + Telegram through one interface.

All outbound notifications flow through :meth:`NotificationService.send`,
which consults user preferences and dispatches to the appropriate channel(s).
Kill-switch and security events override preferences and fire on ALL channels.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import Environment as AppEnv
from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("app.services.notification")

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "notifications"

# Event types that ALWAYS send on ALL channels regardless of preferences.
_URGENT_EVENTS: frozenset[str] = frozenset(
    {
        "kill_switch_triggered",
        "broker_session_expired",
        "suspicious_activity",
        "login_new_device",
    }
)


class NotificationService:
    """Send notifications via Email, Telegram, or both based on user preferences."""

    def __init__(self) -> None:
        self._jinja = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ── Main entry ─────────────────────────────────────────────────────

    async def send(
        self,
        user_id: UUID,
        event_type: str,
        context: dict[str, Any],
        db: "AsyncSession",
    ) -> dict[str, str]:
        """Look up user prefs and dispatch to appropriate channels.

        Returns ``{"email": "sent"/"skipped"/"failed", "telegram": ...}``.
        """
        from app.db.models.user import User
        from sqlalchemy import select

        stmt = select(User).where(User.id == user_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            logger.warning("notification.user_not_found", user_id=str(user_id))
            return {"email": "skipped", "telegram": "skipped"}

        prefs = user.notification_prefs or {}
        is_urgent = event_type in _URGENT_EVENTS

        # Determine channels
        send_email = is_urgent or prefs.get("email", True)
        send_telegram = is_urgent or (
            prefs.get("telegram", False) and user.telegram_chat_id
        )

        ctx = {**context, "user_name": user.full_name or "Trader", "event_type": event_type}
        result: dict[str, str] = {}

        # Email
        if send_email and user.email:
            subject, html_body, text_body = self._render_email(event_type, ctx)
            ok = await self.send_email(user.email, subject, html_body, text_body)
            result["email"] = "sent" if ok else "failed"
        else:
            result["email"] = "skipped"

        # Telegram
        if send_telegram and user.telegram_chat_id:
            message = self._render_telegram(event_type, ctx)
            ok = await self.send_telegram(user.telegram_chat_id, message)
            result["telegram"] = "sent" if ok else "failed"
        else:
            result["telegram"] = "skipped"

        logger.info(
            "notification.sent",
            user_id=str(user_id),
            event_type=event_type,
            result=result,
        )
        return result

    # ── Email ──────────────────────────────────────────────────────────

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        """Send email via AWS SES (prod) or log (dev). Retry 2x on failure."""
        settings = get_settings()
        if settings.environment in (AppEnv.DEVELOPMENT, AppEnv.TEST):
            logger.info(
                "notification.email_dev",
                to=to_email,
                subject=subject,
            )
            return True

        # Production: AWS SES
        for attempt in range(3):
            try:
                import boto3

                ses = boto3.client(
                    "ses",
                    region_name=settings.aws_ses_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                )
                ses.send_email(
                    Source=settings.from_email,
                    Destination={"ToAddresses": [to_email]},
                    Message={
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {
                            "Html": {"Data": html_body, "Charset": "UTF-8"},
                            "Text": {"Data": text_body, "Charset": "UTF-8"},
                        },
                    },
                )
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "notification.email_failed",
                    to=to_email,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt == 2:
                    return False
        return False

    # ── Telegram ───────────────────────────────────────────────────────

    async def send_telegram(
        self,
        chat_id: str,
        message: str,
        parse_mode: str = "HTML",
    ) -> bool:
        """Send Telegram message via Bot API. Retry 2x on failure."""
        settings = get_settings()
        if not settings.telegram_bot_token:
            logger.info("notification.telegram_disabled")
            return False

        if settings.environment in (AppEnv.DEVELOPMENT, AppEnv.TEST):
            logger.info(
                "notification.telegram_dev",
                chat_id=chat_id,
                message=message[:100],
            )
            return True

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": parse_mode}

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        return True
                    logger.warning(
                        "notification.telegram_error",
                        status=resp.status_code,
                        attempt=attempt + 1,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "notification.telegram_failed",
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt == 2:
                    return False
        return False

    # ── Template rendering ─────────────────────────────────────────────

    def render_template(
        self, template_name: str, context: dict[str, Any]
    ) -> tuple[str, str]:
        """Render a Jinja2 template pair. Returns (html, plaintext)."""
        html = ""
        text = ""
        try:
            html_tpl = self._jinja.get_template(f"email/{template_name}.html")
            html = html_tpl.render(**context)
        except Exception:  # noqa: BLE001
            pass
        try:
            text_tpl = self._jinja.get_template(f"telegram/{template_name}.txt")
            text = text_tpl.render(**context)
        except Exception:  # noqa: BLE001
            pass
        return html, text

    def _render_email(
        self, event_type: str, context: dict[str, Any]
    ) -> tuple[str, str, str]:
        """Return (subject, html, plaintext) for an email event."""
        subjects: dict[str, str] = {
            "kill_switch_triggered": "Trading Bridge - Kill Switch Triggered",
            "order_filled": "Trading Bridge - Order Filled",
            "order_failed": "Trading Bridge - Order Failed",
            "broker_session_expired": "Trading Bridge - Broker Session Expired",
            "daily_summary": "Trading Bridge - Daily Summary",
            "login_new_device": "Trading Bridge - New Login Detected",
            "suspicious_activity": "Trading Bridge - Security Alert",
            "welcome": "Welcome to Trading Bridge!",
            "password_changed": "Trading Bridge - Password Changed",
            "kill_switch_reset": "Trading Bridge - Kill Switch Reset",
            "strategy_signal": "Trading Bridge - Strategy Signal",
            "circuit_breaker_triggered": "Trading Bridge - Circuit Breaker Alert",
        }
        subject = subjects.get(event_type, f"Trading Bridge - {event_type}")
        html, text = self.render_template(event_type, context)
        if not html:
            html = f"<p>{subject}</p><p>{context}</p>"
        if not text:
            text = f"{subject}\n{context}"
        return subject, html, text

    def _render_telegram(self, event_type: str, context: dict[str, Any]) -> str:
        """Return formatted message for Telegram."""
        try:
            tpl = self._jinja.get_template(f"telegram/{event_type}.txt")
            return tpl.render(**context)
        except Exception:  # noqa: BLE001
            return f"{event_type}: {context.get('message', str(context))}"


notification_service = NotificationService()

__all__ = ["NotificationService", "notification_service"]

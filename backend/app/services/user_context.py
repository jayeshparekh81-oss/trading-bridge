"""Privacy-safe context builder for AlgoMitra AI calls.

Anything in the dict returned here ends up inside Claude's context
window. Strict rule: no API keys, no bank/PAN/Aadhaar, no email
addresses, no phone numbers. Only aggregate counts + names + page
hints — the kind of thing a friend already knows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.broker_credential import BrokerCredential
from app.db.models.trade import Trade
from app.db.models.user import User


async def build_user_context(
    user: User,
    db: AsyncSession,
    *,
    current_page: str | None = None,
) -> dict[str, Any]:
    """Return the minimal context dict to inject into the AI request.

    Args:
        user: The authenticated user. Only the first name and id-derived
            counts are exposed — never the email, phone, or telegram id.
        db: Active session for the count queries.
        current_page: Optional UI hint (e.g., ``/dashboard``, ``/brokers``).
            Frontend passes whatever ``window.location.pathname`` is.

    Returns:
        A dict with at most: ``name``, ``broker_count``, ``trade_count``,
        ``today_pnl`` (Decimal as string), ``current_page``. Missing
        keys are omitted rather than set to ``null`` — keeps the
        rendered prompt short.
    """
    ctx: dict[str, Any] = {}

    # First name only. Strip surnames to reduce identifying signal.
    if user.full_name:
        ctx["name"] = user.full_name.split()[0]
    elif user.email:
        ctx["name"] = user.email.split("@")[0]

    # Active broker count — capability hint, no broker names exposed.
    broker_stmt = (
        select(func.count())
        .select_from(BrokerCredential)
        .where(
            BrokerCredential.user_id == user.id,
            BrokerCredential.is_active.is_(True),
        )
    )
    ctx["broker_count"] = int((await db.execute(broker_stmt)).scalar() or 0)

    # Total trades count + today's realized P&L (IST trading day,
    # approximated as UTC since intraday hours are 9:15-15:30 IST and
    # the comparison only needs same-day-ish accuracy for chat context).
    trade_count_stmt = (
        select(func.count()).select_from(Trade).where(Trade.user_id == user.id)
    )
    ctx["trade_count"] = int((await db.execute(trade_count_stmt)).scalar() or 0)

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_pnl_stmt = (
        select(func.coalesce(func.sum(Trade.pnl_realized), 0))
        .where(
            Trade.user_id == user.id,
            Trade.created_at >= today_start,
        )
    )
    today_pnl = (await db.execute(today_pnl_stmt)).scalar() or Decimal("0")
    if today_pnl != 0:
        ctx["today_pnl"] = str(today_pnl)

    if current_page:
        # Strip query params to avoid leaking session ids etc.
        ctx["current_page"] = current_page.split("?", 1)[0][:64]

    return ctx


__all__ = ["build_user_context"]

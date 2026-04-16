"""Kill-switch Pydantic schemas.

One of the three core safety surfaces (along with ``webhook`` and
``broker``). The API contract here is what an operator sees through the
kill-switch router, and what the service layer returns back up to it.

Design rules:
    * Money is ``Decimal``; never ``float``.
    * Every input is ``extra="forbid"`` — we refuse ambiguous keys so a
      typo in the dashboard client can't silently disable the limit.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class KillSwitchState(StrEnum):
    """Binary state of the kill switch for a user."""

    ACTIVE = "ACTIVE"
    TRIPPED = "TRIPPED"


class TripReason(StrEnum):
    """Why the kill switch fired.

    Kept as a small vocabulary so alerts and reports can group by reason
    without string fuzzing.
    """

    DAILY_LOSS_BREACHED = "daily_loss_breached"
    MAX_TRADES_BREACHED = "max_trades_breached"
    CIRCUIT_BREAKER_HALT = "circuit_breaker_halt"
    MANUAL = "manual"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    AUTO_SQUARE_OFF = "auto_square_off"


# ═══════════════════════════════════════════════════════════════════════
# Config (user-configurable thresholds)
# ═══════════════════════════════════════════════════════════════════════


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class KillSwitchConfigCreate(_StrictBase):
    """Request body to create/update the user's thresholds."""

    max_daily_loss_inr: Decimal = Field(
        ..., gt=Decimal("0"), description="Maximum allowed daily loss in INR."
    )
    max_daily_trades: int = Field(
        ..., gt=0, le=10_000, description="Hard cap on orders per day."
    )
    enabled: bool = True
    auto_square_off: bool = True


class KillSwitchConfigResponse(BaseModel):
    """Current thresholds for a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    max_daily_loss_inr: Decimal
    max_daily_trades: int
    enabled: bool
    auto_square_off: bool
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════
# Status (live read from Redis)
# ═══════════════════════════════════════════════════════════════════════


class KillSwitchStatus(BaseModel):
    """Live kill-switch snapshot, built by the service from Redis."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    state: KillSwitchState
    daily_pnl: Decimal
    max_daily_loss_inr: Decimal
    remaining_loss_budget: Decimal
    trades_today: int
    max_daily_trades: int
    remaining_trades: int
    enabled: bool
    tripped_at: datetime | None = None
    trip_reason: TripReason | None = None


class KillSwitchDailySummary(BaseModel):
    """Aggregated day-to-date numbers for the operator dashboard."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    trades_today: int
    daily_pnl: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    remaining_loss_budget: Decimal
    remaining_trades: int


# ═══════════════════════════════════════════════════════════════════════
# Trigger / reset
# ═══════════════════════════════════════════════════════════════════════


class KillSwitchActionLog(BaseModel):
    """One broker's response to a kill-switch fire-out."""

    broker_credential_id: UUID
    broker_name: str
    pending_cancelled: int = 0
    positions_squared_off: int = 0
    error: str | None = None


class KillSwitchResult(BaseModel):
    """Outcome of a ``check_and_trigger`` call."""

    model_config = ConfigDict(extra="forbid")

    triggered: bool
    reason: TripReason | None = None
    daily_pnl: Decimal
    event_id: UUID | None = None
    actions: list[KillSwitchActionLog] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class KillSwitchEventSchema(BaseModel):
    """Read shape for :class:`~app.db.models.kill_switch.KillSwitchEvent`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    triggered_at: datetime
    reason: str
    daily_pnl_at_trigger: Decimal
    positions_squared_off: list[Any]
    reset_at: datetime | None = None
    reset_by: UUID | None = None


class KillSwitchResetRequest(_StrictBase):
    """Manual-reset payload — ``confirmation_token`` is mandatory.

    In Step 5 the token is a random string we round-trip via the UI; the
    2FA variant lands when the auth layer is wired. The field gates a
    destructive operator action behind deliberate intent.
    """

    confirmation_token: str = Field(..., min_length=8, max_length=128)


class KillSwitchTestResult(BaseModel):
    """Dry-run simulation result — nothing hits a broker."""

    would_trigger: bool
    reason: TripReason | None = None
    daily_pnl: Decimal
    max_daily_loss_inr: Decimal


__all__ = [
    "KillSwitchActionLog",
    "KillSwitchConfigCreate",
    "KillSwitchConfigResponse",
    "KillSwitchDailySummary",
    "KillSwitchEventSchema",
    "KillSwitchResetRequest",
    "KillSwitchResult",
    "KillSwitchState",
    "KillSwitchStatus",
    "KillSwitchTestResult",
    "TripReason",
]

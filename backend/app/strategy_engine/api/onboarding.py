"""User onboarding API.

Four endpoints under ``/api/onboarding`` that drive the 5-step
flow's state machine:

    GET  /state         — current onboarding step + computed
                          ``is_new_user`` flag.
    POST /step          — advance to the next step
                          (clamped to [0, 5]).
    POST /preferences   — persist trading goal + experience
                          level into ``notification_prefs``
                          under reserved keys.
    POST /complete      — mark onboarding done (from skip OR
                          step 5 CTA). Sets ``onboarding_step=6``
                          + populates ``onboarding_completed_at``.

The state machine is deliberately one-way (forward-only) at the
HTTP boundary — ``onboarding_step`` only advances. This avoids
the surprise where a partially-onboarded user accidentally
re-triggers the flow by calling step with a lower value. The
DB column itself isn't decreasing-monotone-locked (admin tooling
can reset for QA / debugging), but the public API never moves
backwards.

All four endpoints require an authenticated user; no admin gate
— each user manages their own onboarding state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.db.models.user import User
from app.db.session import get_session

logger = get_logger("app.strategy_engine.api.onboarding")

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


#: ``onboarding_step == 6`` is the terminal state. Everything below
#: it counts as "still onboarding" — the dashboard's auto-redirect
#: reads ``is_new_user`` (computed from this) to decide.
_COMPLETE_STEP = 6

#: Reserved keys inside ``users.notification_prefs`` JSONB where
#: the onboarding preferences live. Picked unique-enough that an
#: accidental notification setting can't collide.
_PREFS_GOAL_KEY = "_onboarding_goal"
_PREFS_EXPERIENCE_KEY = "_onboarding_experience"

#: Allowed enum values for the trading-goal preference. Mirrors
#: the frontend's Goals step copy.
_VALID_GOALS = (
    "build_and_backtest",
    "marketplace_buy",
    "pine_import",
    "explore",
)

#: Allowed enum values for the experience-level preference.
_VALID_EXPERIENCES = ("new", "intermediate", "expert")


# ─── Boundary models ───────────────────────────────────────────────────


class OnboardingState(BaseModel):
    """Current onboarding posture for the calling user."""

    model_config = ConfigDict(from_attributes=True)

    onboarding_step: int = Field(..., ge=0, le=6)
    is_new_user: bool
    onboarding_completed_at: datetime | None = None
    goal: str | None = None
    experience: str | None = None


class StepAdvance(BaseModel):
    """Body for POST /step. ``next_step`` is the *target* step
    the caller wants to land on (1-5). Server clamps + rejects
    moves backwards."""

    model_config = ConfigDict(extra="forbid")

    next_step: int = Field(..., ge=1, le=5)


class PreferencesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: Literal[
        "build_and_backtest", "marketplace_buy", "pine_import", "explore"
    ] | None = None
    experience: Literal["new", "intermediate", "expert"] | None = None


# ─── Helpers ───────────────────────────────────────────────────────────


async def _attached_user(
    db: AsyncSession, current_user: User
) -> User:
    """Fetch the user via this request's session so subsequent
    mutations land on the right Session-attached row.

    The auth dependency loads the user via its own
    ``get_session`` instance — by the time the endpoint runs,
    that instance is closed and ``current_user`` is detached.
    Doing one ``db.get`` round-trip per mutating endpoint is cheap
    + correct."""
    fresh = await db.get(User, current_user.id)
    if fresh is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User no longer exists.",
        )
    return fresh


def _state_from_user(user: User) -> OnboardingState:
    prefs: dict[str, Any] = user.notification_prefs or {}
    goal = prefs.get(_PREFS_GOAL_KEY)
    experience = prefs.get(_PREFS_EXPERIENCE_KEY)
    return OnboardingState(
        onboarding_step=user.onboarding_step,
        is_new_user=user.onboarding_step < _COMPLETE_STEP,
        onboarding_completed_at=user.onboarding_completed_at,
        goal=goal if isinstance(goal, str) else None,
        experience=experience if isinstance(experience, str) else None,
    )


# ─── Endpoints ─────────────────────────────────────────────────────────


@router.get("/state", response_model=OnboardingState)
async def get_onboarding_state(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> OnboardingState:
    """Read-only view of the caller's onboarding state."""
    return _state_from_user(current_user)


@router.post("/step", response_model=OnboardingState)
async def advance_step(
    body: StepAdvance,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingState:
    """Move forward through the flow.

    Forward-only at the HTTP layer — a request whose
    ``next_step`` is less than or equal to the current step is
    rejected with 409. A user who already completed
    (``onboarding_step == 6``) is rejected with 409 too;
    re-onboarding is a deliberate admin action, not a
    misclick-from-the-flow vector.
    """
    user = await _attached_user(db, current_user)
    if user.onboarding_step >= _COMPLETE_STEP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding already complete.",
        )
    if body.next_step <= user.onboarding_step:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot move backwards: current step is "
                f"{user.onboarding_step}, requested {body.next_step}."
            ),
        )
    user.onboarding_step = body.next_step
    await db.commit()
    await db.refresh(user)
    logger.info(
        "onboarding.step_advanced",
        user_id=str(user.id),
        new_step=body.next_step,
    )
    return _state_from_user(user)


@router.post("/preferences", response_model=OnboardingState)
async def save_preferences(
    body: PreferencesPayload,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingState:
    """Persist the user's trading-goal + experience answers into
    ``notification_prefs``. Either field is optional; calling
    twice with different values overwrites the previous answer.

    Defensive — refuses to mutate prefs if onboarding is already
    complete (no use case for changing the goal post-completion;
    user-settings page is the right surface for that).
    """
    user = await _attached_user(db, current_user)
    if user.onboarding_step >= _COMPLETE_STEP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding already complete; preferences are locked.",
        )

    prefs: dict[str, Any] = dict(user.notification_prefs or {})
    if body.goal is not None:
        prefs[_PREFS_GOAL_KEY] = body.goal
    if body.experience is not None:
        prefs[_PREFS_EXPERIENCE_KEY] = body.experience
    user.notification_prefs = prefs
    await db.commit()
    await db.refresh(user)
    logger.info(
        "onboarding.preferences_saved",
        user_id=str(user.id),
        goal=body.goal,
        experience=body.experience,
    )
    return _state_from_user(user)


@router.post("/complete", response_model=OnboardingState)
async def complete_onboarding(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingState:
    """Terminal — flips ``onboarding_step`` to 6 + stamps
    ``onboarding_completed_at = now()``.

    Idempotent — calling on an already-complete user just returns
    the current state without re-stamping the timestamp."""
    user = await _attached_user(db, current_user)
    if user.onboarding_step < _COMPLETE_STEP:
        user.onboarding_step = _COMPLETE_STEP
        user.onboarding_completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(user)
        logger.info(
            "onboarding.completed",
            user_id=str(user.id),
        )
    return _state_from_user(user)


__all__ = ["router"]

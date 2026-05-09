"""User onboarding state — additive columns on ``users``.

Two new columns:

    * ``onboarding_step``         — 0 = not started, 1-5 = active step,
                                    6 = complete. Existing users get
                                    server_default ``6`` so they pass
                                    through the dashboard's auto-
                                    redirect untouched.
    * ``onboarding_completed_at`` — timestamp the user finished or
                                    skipped. NULL while in progress.

Reversible.

Revision ID: 021_user_onboarding
Revises: 020_support_tickets
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_user_onboarding"
down_revision: str | None = "020_support_tickets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ``onboarding_step`` server_default = 6 → existing users are
    # treated as already-onboarded. New signups override with
    # explicit ``onboarding_step=0`` at insert time.
    op.add_column(
        "users",
        sa.Column(
            "onboarding_step",
            sa.Integer(),
            nullable=False,
            server_default="6",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Lock allowed range at the DB layer so a stray ``-1`` /
    # ``999`` from app code can't slip into the column.
    # Bare suffix — the metadata's naming_convention auto-prepends
    # ``ck_users_`` so the final constraint name resolves to
    # ``ck_users_onboarding_step_range``.
    op.create_check_constraint(
        "onboarding_step_range",
        "users",
        "onboarding_step >= 0 AND onboarding_step <= 6",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_onboarding_step_range", "users", type_="check"
    )
    op.drop_column("users", "onboarding_completed_at")
    op.drop_column("users", "onboarding_step")

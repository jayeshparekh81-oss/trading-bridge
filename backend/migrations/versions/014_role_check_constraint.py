"""Phase 2 RBAC — CHECK constraint on ``users.role``.

Phase 1 (Migration 013) added the ``users.role`` text column with a
soft 2-tier vocabulary (``user`` / ``admin``). Phase 2 expands the
locked vocabulary to five values:

    * ``user``        — default. Regular trader.
    * ``pro_user``    — paid tier (advanced indicators, more
                        strategies, priority support).
    * ``creator``     — marketplace publishing rights.
    * ``admin``       — system management.
    * ``super_admin`` — billing + critical infrastructure.

This migration adds a database-level ``CHECK`` constraint enforcing
that ``role`` is always one of the five locked values. A typo in a
production code path (``user.role = "Admin"``, ``user.role = "pro"``)
fails at INSERT/UPDATE time rather than landing as silent garbage
that breaks role checks downstream.

Existing data: every row created before Phase 2 has ``role`` ∈
{``user``, ``admin``} per Migration 013's backfill, both of which
are valid under the new constraint — so the constraint passes
unconditionally on existing rows. No data migration required.

The matching SQLAlchemy ``CheckConstraint`` is also declared in the
:class:`User` model's ``__table_args__`` so the test harness's
``Base.metadata.create_all`` enforces the same rule. Single source
of truth: edit Migration 014 and the model together if the locked
vocabulary ever changes.

Revision ID: 014_role_check_constraint
Revises: 013_users_role
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "014_role_check_constraint"
down_revision: str | None = "013_users_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Locked role vocabulary. Update Migration 014 + the model + the
#: helpers in ``app/auth/roles.py`` together if this set ever changes.
_VALID_ROLES = ("user", "pro_user", "creator", "admin", "super_admin")
#: Constraint *suffix* — ``Base.metadata.naming_convention`` (see
#: ``app/db/base.py``) prepends ``ck_<table_name>_`` so the resolved
#: SQL name is ``ck_users_role_valid``. Same suffix is used by the
#: User model's ``__table_args__`` so both sides resolve to the same
#: full name.
_CONSTRAINT_NAME = "role_valid"


def upgrade() -> None:
    quoted = ", ".join(f"'{role}'" for role in _VALID_ROLES)
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        "users",
        f"role IN ({quoted})",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, "users", type_="check")

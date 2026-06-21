"""``strategy_state_audit`` — DB-level audit trail for strategies.is_paper / is_active.

Foundation for *tracked flips*. The existing ``audit_log`` table does NOT fit:
it is an app-level, HMAC-signed event log keyed by the application ``user_id``
(columns: ``action_type``, ``raw_data`` jsonb, ``signature``, ``ip_address``) —
it has no structured ``field``/``old``/``new`` columns and a DB trigger has no app
``user_id`` or ``signature`` to populate. So this adds a DEDICATED, append-only
table plus a trigger that captures every change to ``strategies.is_paper`` or
``strategies.is_active``.

What it records (one row per changed field):
    strategy_id, strategy_name, field, old_value, new_value,
    db_user (session_user), client_addr (inet_client_addr()), changed_at (now()).

Trigger discipline (mirrors the safety constraints):
    * AFTER UPDATE ON strategies, FOR EACH ROW.
    * Fires ONLY when is_paper OR is_active actually change — a ``WHEN`` clause
      with ``IS DISTINCT FROM`` keeps it OFF the hot path (the executor updates
      ``last_trust_score`` / ``last_scores_at`` constantly; those never fire it).
    * Pure observability: it INSERTs into the audit table and returns NULL. It
      NEVER modifies a strategy row, never touches is_paper/is_active values.

This migration does NOT change any existing strategy row (no BSE/CDSL state touch).

Fully reversible: downgrade drops the trigger, the function, and the table.
Chains off ``032_users_entitlement`` (current head on main / prod).

Revision ID: 033_strategy_state_audit
Revises: 032_users_entitlement
Create Date: 2026-06-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "033_strategy_state_audit"
down_revision: str | None = "032_users_entitlement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "strategy_state_audit"
_FUNC = "fn_audit_strategy_state"
_TRIGGER = "trg_audit_strategy_state"

# AFTER-UPDATE trigger function: one audit row per changed field. session_user =
# the connecting DB role; inet_client_addr() = client IP (NULL over unix socket).
_CREATE_FUNCTION = f"""
CREATE OR REPLACE FUNCTION {_FUNC}() RETURNS trigger AS $$
BEGIN
    IF NEW.is_paper IS DISTINCT FROM OLD.is_paper THEN
        INSERT INTO {_TABLE}
            (strategy_id, strategy_name, field, old_value, new_value, db_user, client_addr)
        VALUES
            (NEW.id, NEW.name, 'is_paper', OLD.is_paper::text, NEW.is_paper::text,
             session_user, inet_client_addr());
    END IF;
    IF NEW.is_active IS DISTINCT FROM OLD.is_active THEN
        INSERT INTO {_TABLE}
            (strategy_id, strategy_name, field, old_value, new_value, db_user, client_addr)
        VALUES
            (NEW.id, NEW.name, 'is_active', OLD.is_active::text, NEW.is_active::text,
             session_user, inet_client_addr());
    END IF;
    RETURN NULL;  -- AFTER trigger: return value is ignored
END;
$$ LANGUAGE plpgsql;
"""

_CREATE_TRIGGER = f"""
CREATE TRIGGER {_TRIGGER}
    AFTER UPDATE ON strategies
    FOR EACH ROW
    WHEN (OLD.is_paper IS DISTINCT FROM NEW.is_paper
          OR OLD.is_active IS DISTINCT FROM NEW.is_active)
    EXECUTE FUNCTION {_FUNC}();
"""


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_name", sa.Text(), nullable=True),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("db_user", sa.Text(), nullable=False),
        sa.Column("client_addr", postgresql.INET(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_strategy_state_audit_strategy_id", _TABLE, ["strategy_id"])
    op.execute(_CREATE_FUNCTION)
    op.execute(_CREATE_TRIGGER)


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER} ON strategies;")
    op.execute(f"DROP FUNCTION IF EXISTS {_FUNC}();")
    op.drop_index("ix_strategy_state_audit_strategy_id", table_name=_TABLE)
    op.drop_table(_TABLE)

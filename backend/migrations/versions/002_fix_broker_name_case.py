"""Fix broker_name case — normalize mixed-case values to lowercase.

Revision ID: 002_fix_broker_name_case
Revises: 001_initial_schema
Create Date: 2026-04-24

Existing rows may have 'Fyers', 'Dhan', etc. (mixed case) which don't
match the BrokerName StrEnum values ('fyers', 'dhan', …). This migration
normalizes all broker_name values to lowercase.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = "002_fix_broker_name_case"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE broker_credentials SET broker_name = LOWER(broker_name)")


def downgrade() -> None:
    # No meaningful downgrade — lowercase is the correct canonical form.
    pass

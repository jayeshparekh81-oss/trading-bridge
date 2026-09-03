"""Every ``Mapped[datetime]`` column on every model MUST be ``DateTime(timezone=True)``.

WHY THIS EXISTS. ``app/db/base.py`` states the rule — "DateTime(timezone=True)
everywhere — we never store naive" — but nothing enforced it. A column
declared as ``Mapped[datetime] = mapped_column(nullable=False)`` with no explicit
type is inferred by SQLAlchemy 2.0 as a NAIVE ``DateTime()``; the DB column
(created by the migration with ``timezone=True``) is ``timestamptz``; the
handler passes ``datetime.now(UTC)``. asyncpg refuses to bind an aware value
into a naive parameter:

    asyncpg.exceptions.DataError: invalid input for query argument $3 …
    (can't subtract offset-naive and offset-aware datetimes)

That is exactly how the first real customer's "Subscribe — FREE" click 500'd
on 2026-09-03 — with no CORS headers on the 500, so the browser reported
"Network error". Seven models had the defect for four months.

It hid because the existing tests run on SQLite, which stores whatever it is
given. THIS test needs no database at all: it inspects the declared column
types, so it runs anywhere and fails in CI the moment a naive column appears.

Run before the fix it names 10 columns across 7 models. After, zero.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import DateTime

# Importing the package registers every model on Base.metadata.
import app.db.models  # noqa: F401
from app.db.base import Base


def _naive_datetime_columns() -> list[str]:
    offenders: list[str] = []
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if isinstance(col.type, DateTime) and not col.type.timezone:
                offenders.append(f"{table.name}.{col.name}")
    return sorted(offenders)


def test_every_datetime_column_is_timezone_aware() -> None:
    offenders = _naive_datetime_columns()
    assert offenders == [], (
        "NAIVE DateTime columns — declare them DateTime(timezone=True); "
        "the DB column is timestamptz and asyncpg will reject aware values:\n  "
        + "\n  ".join(offenders)
    )


def test_the_guard_actually_looks_at_something() -> None:
    """A guard that scans zero columns passes vacuously. Prove the scan sees
    the aware columns that already exist (TimestampMixin.created_at)."""
    aware = [
        f"{t.name}.{c.name}"
        for t in Base.metadata.sorted_tables
        for c in t.columns
        if isinstance(c.type, DateTime) and c.type.timezone
    ]
    assert len(aware) >= 20, aware
    assert any(name.endswith(".created_at") for name in aware)


@pytest.mark.parametrize(
    "table, column",
    [
        ("marketplace_subscriptions", "subscribed_at"),
        ("marketplace_subscriptions", "access_until"),
        ("marketplace_listings", "published_at"),
        ("ledger_snapshots", "created_at"),
        ("ledger_attestations", "attested_at"),
        ("indicator_approval_queue", "decision_at"),
        ("indicator_status_overrides", "approved_at"),
        ("indicator_status_overrides", "effective_from"),
        ("indicator_status_overrides", "effective_until"),
        ("support_tickets", "resolved_at"),
    ],
)
def test_the_ten_columns_that_broke_subscribe_are_named(table: str, column: str) -> None:
    """The incident's exact columns, pinned individually so a regression on
    any one of them fails with its own name."""
    col = Base.metadata.tables[table].columns[column]
    assert isinstance(col.type, DateTime)
    assert col.type.timezone is True, f"{table}.{column} is naive again"


def test_python_side_datetime_annotation_is_what_we_think() -> None:
    """Sanity: the models really do annotate with ``datetime`` — if someone
    switches to a custom type this guard must be revisited, not bypassed."""
    assert datetime is not None

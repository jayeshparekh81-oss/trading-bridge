"""SQLAlchemy 2.0 declarative base + shared mixins.

All ORM models inherit from :class:`Base`. Common columns
(``id``, ``created_at``, ``updated_at``) are composed via mixins so each
model file stays focused on its business fields.

Design notes:
    * ``UUID(as_uuid=True)`` is used for primary keys so values stay typed
      as :class:`uuid.UUID` at the Python boundary — no ad-hoc casting in
      services.
    * ``DateTime(timezone=True)`` everywhere — we never store naive
      timestamps. Defaults use ``func.now()`` which Postgres resolves to
      UTC when ``timezone`` is true.
    * ``Base.metadata.naming_convention`` fixes constraint names so
      Alembic autogenerates deterministic migrations.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: Deterministic constraint naming — required for clean Alembic diffs.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Common declarative base for every ORM model in the project."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """Adds a UUIDv4 primary key column named ``id``."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns, both timezone-aware."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


__all__ = ["Base", "TimestampMixin", "UUIDPrimaryKeyMixin"]

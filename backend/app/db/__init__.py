"""Database layer — SQLAlchemy 2.0 async core.

Sub-modules:
    * :mod:`app.db.base`    — :class:`Base` declarative class + mixins.
    * :mod:`app.db.session` — engine, sessionmaker, FastAPI dependency.
    * :mod:`app.db.models`  — one module per table.
"""

from __future__ import annotations

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.session import (
    dispose_engine,
    get_engine,
    get_session,
    get_sessionmaker,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "dispose_engine",
    "get_engine",
    "get_session",
    "get_sessionmaker",
]

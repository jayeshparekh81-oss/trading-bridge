"""Migration 014 — ``users.role`` CHECK constraint.

Pins both the structural shape (revision graph + upgrade/downgrade
contract) and the runtime enforcement: an ORM insert with an
out-of-vocabulary role string fails with an integrity error rather
than landing as silent garbage.
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models.user import User


def test_users_table_has_role_check_constraint_in_metadata() -> None:
    """The :class:`CheckConstraint` is declared on the User model's
    ``__table_args__`` so ``Base.metadata.create_all`` enforces the
    same rule the migration adds at the DB level."""
    table = Base.metadata.tables["users"]
    constraint_names = {c.name for c in table.constraints if c.name}
    assert "ck_users_role_valid" in constraint_names


def test_migration_014_chains_after_013() -> None:
    module = importlib.import_module(
        "migrations.versions.014_role_check_constraint"
    )
    assert module.revision == "014_role_check_constraint"
    assert module.down_revision == "013_users_role"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_014_upgrade_creates_check_downgrade_drops_it() -> None:
    """Source-string inspection — pin the constraint name + locked
    five-tier vocabulary so a typo in either direction trips here."""
    import inspect

    module = importlib.import_module(
        "migrations.versions.014_role_check_constraint"
    )
    upgrade_src = inspect.getsource(module.upgrade)
    downgrade_src = inspect.getsource(module.downgrade)

    assert "create_check_constraint" in upgrade_src
    assert "drop_constraint" in downgrade_src

    # Locked vocabulary is asserted against the module's own constant
    # rather than re-scraping the SQL — keeps the test stable when
    # the migration's wording is reformatted.
    assert module._VALID_ROLES == (
        "user",
        "pro_user",
        "creator",
        "admin",
        "super_admin",
    )
    # Suffix only — ``Base.metadata.naming_convention`` prepends
    # ``ck_users_`` so the resolved SQL name is ``ck_users_role_valid``.
    assert module._CONSTRAINT_NAME == "role_valid"


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_check_constraint_rejects_invalid_role(
    db: AsyncSession,
) -> None:
    """Direct CHECK enforcement — inserting ``role='Admin'`` (case
    typo) or ``role='unknown'`` raises IntegrityError. Pins the
    runtime safety net the constraint provides."""
    db.add(
        User(
            email="bad-role@x",
            password_hash="p",
            is_active=True,
            role="Admin",  # capital-A typo, not in the locked set
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_check_constraint_accepts_every_locked_role(
    db: AsyncSession,
) -> None:
    """Sweep over the locked five-tier vocabulary — each value is
    accepted by the CHECK constraint."""
    for idx, role in enumerate(
        ("user", "pro_user", "creator", "admin", "super_admin")
    ):
        db.add(
            User(
                email=f"role-sweep-{idx}@x",
                password_hash="p",
                is_active=True,
                role=role,
            )
        )
    # All five inserts flush in a single batch — if any role were
    # rejected by the CHECK, IntegrityError would fire here.
    await db.flush()

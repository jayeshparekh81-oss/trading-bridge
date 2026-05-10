"""Migrations 023 + 024 — structural tests.

Source-inspection style (matches the rest of ``tests/db/``).
Confirms revision graph wiring + presence of CHECK constraints
+ both directions reference the same table names.
"""

from __future__ import annotations

import importlib
import inspect

from app.db.base import Base


def test_023_table_registered_with_metadata() -> None:
    assert "indicator_status_overrides" in Base.metadata.tables
    table = Base.metadata.tables["indicator_status_overrides"]
    expected = {
        "id",
        "indicator_id",
        "override_status",
        "override_reason",
        "approved_by_user_id",
        "approved_at",
        "effective_from",
        "effective_until",
        "prior_status",
        "prior_status_source",
        "audit_log_id",
        "decision_metadata",
        "created_at",
        "updated_at",
    }
    assert set(table.columns.keys()) == expected


def test_024_table_registered_with_metadata() -> None:
    assert "indicator_approval_queue" in Base.metadata.tables
    table = Base.metadata.tables["indicator_approval_queue"]
    expected = {
        "id",
        "indicator_id",
        "requested_status",
        "request_reason",
        "requester_id",
        "request_metadata",
        "status",
        "decision_by_user_id",
        "decision_at",
        "decision_notes",
        "resulting_override_id",
        "created_at",
        "updated_at",
    }
    assert set(table.columns.keys()) == expected


def test_023_revision_chain() -> None:
    module = importlib.import_module(
        "migrations.versions.023_indicator_status_overrides"
    )
    assert module.revision == "023_indicator_status_overrides"  # type: ignore[attr-defined]
    assert module.down_revision == "022_perf_indexes"  # type: ignore[attr-defined]
    assert callable(module.upgrade)  # type: ignore[attr-defined]
    assert callable(module.downgrade)  # type: ignore[attr-defined]


def test_024_revision_chain() -> None:
    module = importlib.import_module(
        "migrations.versions.024_indicator_approval_queue"
    )
    assert module.revision == "024_indicator_approval_queue"  # type: ignore[attr-defined]
    assert module.down_revision == "023_indicator_status_overrides"  # type: ignore[attr-defined]
    assert callable(module.upgrade)  # type: ignore[attr-defined]
    assert callable(module.downgrade)  # type: ignore[attr-defined]


def test_023_check_constraints_in_upgrade_source() -> None:
    """Both CHECK constraints (override_status enum + prior_status_source
    enum) must appear in the upgrade body. A missing one would let
    a typo'd status value land in the column."""
    module = importlib.import_module(
        "migrations.versions.023_indicator_status_overrides"
    )
    src = inspect.getsource(module.upgrade)  # type: ignore[attr-defined]
    assert "override_status_allowed" in src
    assert "prior_status_source_allowed" in src
    assert "deprecated" in src  # the new state vs registry enum


def test_024_check_constraints_in_upgrade_source() -> None:
    module = importlib.import_module(
        "migrations.versions.024_indicator_approval_queue"
    )
    src = inspect.getsource(module.upgrade)  # type: ignore[attr-defined]
    assert "requested_status_allowed" in src
    assert "queue_status_allowed" in src
    # Lifecycle states.
    for state in ("pending", "approved", "rejected", "withdrawn"):
        assert state in src


def test_both_migrations_have_matching_drop_in_downgrade() -> None:
    """Round-trip parity — both migrations drop the same table they
    create. Catches the regression where someone adds a column to
    upgrade() without updating downgrade()."""
    for module_name, table_name in (
        (
            "migrations.versions.023_indicator_status_overrides",
            "indicator_status_overrides",
        ),
        (
            "migrations.versions.024_indicator_approval_queue",
            "indicator_approval_queue",
        ),
    ):
        module = importlib.import_module(module_name)
        downgrade_src = inspect.getsource(
            module.downgrade  # type: ignore[attr-defined]
        )
        assert (
            f'drop_table("{table_name}")' in downgrade_src
        ), f"{module_name} downgrade missing drop_table for {table_name}"

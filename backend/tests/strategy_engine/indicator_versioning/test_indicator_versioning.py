"""Indicator versioning tests.

Pure-function coverage for the in-memory version registry, the
manifest builder, and the seeded v1.0.0 baseline. Each test that
mutates the registry restores it from the seed afterwards so test
order is irrelevant.
"""

from __future__ import annotations

import ast
import threading
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.strategy_engine.indicator_versioning import (
    BacktestVersionManifest,
    IndicatorVersionRecord,
    UnknownIndicatorError,
    capture_manifest,
    get_current_version,
    list_all_versions,
    register_version,
    seed_initial_versions,
)
from app.strategy_engine.indicator_versioning.constants import (
    ENGINE_VERSION,
    INITIAL_FORMULA_VERSION,
    INITIAL_VERSION,
    INITIAL_VERSION_DATE,
)
from app.strategy_engine.indicator_versioning.registry import (
    clear as registry_clear,
)
from app.strategy_engine.indicator_versioning.registry import (
    known_indicators,
)
from app.strategy_engine.indicators import INDICATOR_REGISTRY


@pytest.fixture(autouse=True)
def _restore_registry() -> Generator[None, None, None]:
    """Reset the registry to the freshly-seeded baseline before *and*
    after every test so no test pollutes another."""
    registry_clear()
    seed_initial_versions()
    yield
    registry_clear()
    seed_initial_versions()


# ─── 1. get_current_version returns v1.0.0 for "ema" ──────────────────


def test_get_current_version_returns_v1_for_seeded_indicator() -> None:
    record = get_current_version("ema")
    assert isinstance(record, IndicatorVersionRecord)
    assert record.indicator_id == "ema"
    assert record.version == INITIAL_VERSION == "1.0.0"
    assert record.formula_version == INITIAL_FORMULA_VERSION == "f1"
    assert record.deprecated is False
    assert record.created_at == INITIAL_VERSION_DATE


# ─── 2. get_current_version raises for unknown indicator ──────────────


def test_get_current_version_raises_for_unknown_indicator() -> None:
    with pytest.raises(UnknownIndicatorError, match="no versions registered"):
        get_current_version("not_a_real_indicator")
    with pytest.raises(UnknownIndicatorError):
        list_all_versions("also_not_real")


# ─── 3. register_version adds new version → becomes current ──────────


def test_register_version_promotes_new_record_to_current() -> None:
    new_record = IndicatorVersionRecord(
        indicator_id="ema",
        version="1.1.0",
        formula_version="f2",
        changelog="Switched to Wilder smoothing",
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    register_version(new_record)
    assert get_current_version("ema").version == "1.1.0"
    assert get_current_version("ema").formula_version == "f2"
    # Idempotency — re-registering the same (id, version) is a no-op.
    register_version(new_record)
    assert len(list_all_versions("ema")) == 2


# ─── 4. list_all_versions returns chronological history ───────────────


def test_list_all_versions_returns_history_newest_first() -> None:
    register_version(
        IndicatorVersionRecord(
            indicator_id="ema",
            version="1.1.0",
            formula_version="f2",
            changelog="Bump",
            created_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )
    register_version(
        IndicatorVersionRecord(
            indicator_id="ema",
            version="1.2.0",
            formula_version="f3",
            changelog="Another bump",
            created_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
    )
    history = list_all_versions("ema")
    assert [r.version for r in history] == ["1.2.0", "1.1.0", "1.0.0"]


# ─── 5. capture_manifest creates correct shape ───────────────────────


def test_capture_manifest_returns_well_formed_record() -> None:
    backtest_id = uuid4()
    strategy_id = uuid4()
    before = datetime.now(UTC)
    manifest = capture_manifest(
        backtest_id=backtest_id,
        strategy_id=strategy_id,
        indicators_used=["ema"],
    )
    after = datetime.now(UTC)

    assert isinstance(manifest, BacktestVersionManifest)
    assert manifest.backtest_id == backtest_id
    assert manifest.strategy_id == strategy_id
    assert set(manifest.indicators_used.keys()) == {"ema"}
    assert manifest.indicators_used["ema"].version == "1.0.0"
    assert manifest.engine_version == ENGINE_VERSION
    assert manifest.schema_version == "1"
    assert before <= manifest.captured_at <= after


# ─── 6. capture_manifest with multiple indicators captures all ────────


def test_capture_manifest_handles_multiple_indicators_and_dedupes() -> None:
    manifest = capture_manifest(
        backtest_id=uuid4(),
        strategy_id=uuid4(),
        # Duplicates are intentional — caller may pass per-instance ids
        # that resolve to the same registry id.
        indicators_used=["ema", "rsi", "macd", "ema"],
    )
    assert set(manifest.indicators_used.keys()) == {"ema", "rsi", "macd"}
    for record in manifest.indicators_used.values():
        assert record.version == "1.0.0"
        assert record.deprecated is False


# ─── 7. Pre-populated 105 indicators all at v1.0.0 ───────────────────


def test_seed_populates_every_runtime_indicator_at_v1() -> None:
    seeded = set(known_indicators())
    expected = set(INDICATOR_REGISTRY.keys())
    assert seeded == expected
    assert len(seeded) == 105
    for indicator_id in seeded:
        record = get_current_version(indicator_id)
        assert record.version == "1.0.0"
        assert record.formula_version == "f1"
        assert record.changelog == "Initial release"
        assert record.deprecated is False


# ─── 8. Thread-safety: concurrent register_version calls ──────────────


def test_concurrent_register_version_does_not_corrupt_history() -> None:
    """100 threads each register a unique version on the same
    indicator. The final history must contain every distinct version
    exactly once plus the seeded v1.0.0 baseline."""
    n_threads = 100
    base = datetime(2026, 6, 1, tzinfo=UTC)

    def worker(idx: int) -> None:
        register_version(
            IndicatorVersionRecord(
                indicator_id="ema",
                version=f"2.{idx:03d}.0",
                formula_version="f2",
                changelog=f"Thread {idx}",
                created_at=base + timedelta(seconds=idx),
            )
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    history = list_all_versions("ema")
    versions = {r.version for r in history}
    expected = {"1.0.0"} | {f"2.{i:03d}.0" for i in range(n_threads)}
    assert versions == expected
    # Every record is unique (no duplicates introduced under contention).
    assert len(history) == n_threads + 1


# ─── 9. Determinism: same input → same shape (timestamps differ) ──────


def test_capture_manifest_is_deterministic_in_shape() -> None:
    sid = uuid4()
    a = capture_manifest(backtest_id=uuid4(), strategy_id=sid, indicators_used=["ema", "rsi"])
    b = capture_manifest(backtest_id=uuid4(), strategy_id=sid, indicators_used=["ema", "rsi"])
    # backtest_id + captured_at differ by design; everything else stable.
    assert a.strategy_id == b.strategy_id
    assert a.indicators_used == b.indicators_used
    assert a.schema_version == b.schema_version
    assert a.engine_version == b.engine_version
    assert a.captured_at <= b.captured_at


# ─── 10. AST inspection: no LLM/DB/network imports ───────────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "aiohttp",
    "websocket",
    "websockets",
    "socket",
    "sqlalchemy",
    "alembic",
    "asyncpg",
    "psycopg2",
    "app.db",
    "app.brokers",
    "app.services",
)


def _versioning_python_files() -> list[Path]:
    pkg_root = (
        Path(__file__).resolve().parents[3] / "app" / "strategy_engine" / "indicator_versioning"
    )
    return sorted(p for p in pkg_root.glob("*.py"))


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES)


@pytest.mark.parametrize("source_file", _versioning_python_files())
def test_versioning_module_does_not_import_forbidden_modules(source_file: Path) -> None:
    """Walk every import in every indicator_versioning ``*.py`` and
    assert no LLM SDK, ORM/DB driver, or HTTP/socket library leaks
    in. Phase 1 is intentionally stdlib + Pydantic only."""
    tree = ast.parse(source_file.read_text(), filename=str(source_file))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                offenders.append(f"from {module} import …")
    assert not offenders, f"{source_file.name} pulls in forbidden modules: {offenders}"


# ─── 11. Backtest endpoint includes version_manifest in response ──────


def test_backtest_endpoint_response_model_carries_version_manifest() -> None:
    """The ``BacktestRunResponse`` Pydantic model must declare
    ``version_manifest`` as a non-optional :class:`BacktestVersionManifest`
    so OpenAPI consumers and the frontend type system see the field."""
    from app.strategy_engine.api.backtest import BacktestRunResponse

    fields = BacktestRunResponse.model_fields
    assert "version_manifest" in fields
    field = fields["version_manifest"]
    # ``annotation`` is the resolved type — should be the model class.
    assert field.annotation is BacktestVersionManifest


# ─── 12. Deprecated indicator flagged in manifest ─────────────────────


def test_deprecated_indicator_falls_back_to_latest_non_deprecated() -> None:
    """When a newer version is registered as deprecated, the manifest
    should still pin the current non-deprecated record."""
    register_version(
        IndicatorVersionRecord(
            indicator_id="ema",
            version="1.5.0",
            formula_version="f5",
            changelog="Deprecated experimental fork",
            created_at=datetime(2026, 6, 1, tzinfo=UTC),
            deprecated=True,
        )
    )
    manifest = capture_manifest(
        backtest_id=uuid4(),
        strategy_id=uuid4(),
        indicators_used=["ema"],
    )
    pinned = manifest.indicators_used["ema"]
    assert pinned.version == "1.0.0"
    assert pinned.deprecated is False


def test_only_deprecated_history_still_resolves() -> None:
    """If every version of an indicator is marked deprecated, the
    registry returns the newest of the bunch and surfaces the flag."""
    registry_clear()
    register_version(
        IndicatorVersionRecord(
            indicator_id="custom",
            version="1.0.0",
            formula_version="f1",
            changelog="Initial",
            created_at=datetime(2026, 5, 5, tzinfo=UTC),
            deprecated=True,
        )
    )
    register_version(
        IndicatorVersionRecord(
            indicator_id="custom",
            version="2.0.0",
            formula_version="f2",
            changelog="Reworked",
            created_at=datetime(2026, 6, 5, tzinfo=UTC),
            deprecated=True,
        )
    )
    record = get_current_version("custom")
    assert record.version == "2.0.0"
    assert record.deprecated is True


# ─── 13. Round-trip Pydantic model_dump / model_validate ──────────────


def test_manifest_round_trips_through_pydantic() -> None:
    original = capture_manifest(
        backtest_id=uuid4(),
        strategy_id=uuid4(),
        indicators_used=["ema", "rsi"],
    )
    raw = original.model_dump_json()
    restored = BacktestVersionManifest.model_validate_json(raw)
    assert restored == original
    assert isinstance(restored.backtest_id, UUID)
    assert isinstance(restored.captured_at, datetime)
    assert restored.indicators_used.keys() == original.indicators_used.keys()
    for indicator_id, record in restored.indicators_used.items():
        assert record == original.indicators_used[indicator_id]

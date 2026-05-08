"""Strategy versioning tests.

Phase 1 covers the in-memory + file-based store, the recursive diff,
the Hinglish summary, and the public manager surface. Each test runs
inside an isolated tmp directory by autouse fixture so disk state
never bleeds across tests.
"""

from __future__ import annotations

import ast
import threading
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.strategy_engine.strategy_versioning import (
    StrategyVersion,
    StrategyVersionComparison,
    StrategyVersionDiff,
    StrategyVersionNotFoundError,
    compare_versions,
    create_version,
    get_latest_version,
    get_version,
    list_versions,
    rollback_to_version,
)
from app.strategy_engine.strategy_versioning import store as version_store
from app.strategy_engine.strategy_versioning.constants import (
    CACHE_DIR_NAME,
    INITIAL_VERSION_NUMBER,
    LOCK_TIMEOUT_SECONDS,
    MAX_VERSIONS_KEPT,
)


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path: Path) -> Generator[Path, None, None]:
    """Point the store at a fresh temp directory for each test, then
    reset both the override and the in-memory cache at teardown."""
    version_store.set_base_dir(tmp_path)
    yield tmp_path
    version_store.set_base_dir(None)


def _sample_strategy(stop_loss: float = 2.0) -> dict[str, Any]:
    """Minimal strategy_json shape used across tests. Real production
    payloads carry many more fields — these tests only need a stable,
    diffable subset."""
    return {
        "name": "Test Strategy",
        "stop_loss_percent": stop_loss,
        "target_percent": 4.0,
        "indicators": [
            {"id": "ema", "period": 20},
            {"id": "rsi", "period": 14},
        ],
        "entry_conditions": [{"left": "close", "op": ">", "right": "ema_20"}],
        "exit_conditions": [{"reason": "stop_loss"}],
    }


# ─── 1. create_version creates v1 with correct fields ────────────────


def test_create_version_creates_first_version_with_expected_shape() -> None:
    sid = uuid4()
    uid = uuid4()
    version = create_version(sid, _sample_strategy(), uid, change_summary="Initial draft")

    assert isinstance(version, StrategyVersion)
    assert version.strategy_id == sid
    assert version.created_by == uid
    assert version.version_number == INITIAL_VERSION_NUMBER == 1
    assert version.parent_version_id is None
    assert version.change_summary == "Initial draft"
    assert version.strategy_json["stop_loss_percent"] == 2.0
    assert isinstance(version.version_id, UUID)


# ─── 2. Second create_version on same strategy creates v2 ────────────


def test_second_create_version_increments_to_v2_and_links_parent() -> None:
    sid = uuid4()
    uid = uuid4()
    v1 = create_version(sid, _sample_strategy(), uid)
    v2 = create_version(sid, _sample_strategy(stop_loss=3.0), uid, change_summary="Tighter SL")

    assert v2.version_number == 2
    assert v2.parent_version_id == v1.version_id
    assert v2.strategy_json["stop_loss_percent"] == 3.0


# ─── 3. version_number auto-increments across many edits ─────────────


def test_version_number_monotonically_increments() -> None:
    sid = uuid4()
    uid = uuid4()
    numbers = [
        create_version(sid, _sample_strategy(stop_loss=float(i)), uid).version_number
        for i in range(1, 6)
    ]
    assert numbers == [1, 2, 3, 4, 5]


# ─── 4. parent_version_id forms a single linear chain ────────────────


def test_parent_chain_is_linear_and_complete() -> None:
    sid = uuid4()
    uid = uuid4()
    versions = [create_version(sid, _sample_strategy(stop_loss=float(i)), uid) for i in range(1, 4)]
    assert versions[0].parent_version_id is None
    assert versions[1].parent_version_id == versions[0].version_id
    assert versions[2].parent_version_id == versions[1].version_id


# ─── 5. get_version retrieves a specific version ─────────────────────


def test_get_version_returns_requested_version() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(stop_loss=1.0), uid)
    create_version(sid, _sample_strategy(stop_loss=2.5), uid)

    fetched = get_version(sid, 2)
    assert fetched.version_number == 2
    assert fetched.strategy_json["stop_loss_percent"] == 2.5


def test_get_version_raises_when_missing() -> None:
    with pytest.raises(StrategyVersionNotFoundError):
        get_version(uuid4(), 1)


# ─── 6. list_versions returns chronological order ────────────────────


def test_list_versions_returns_chronological_order() -> None:
    sid = uuid4()
    uid = uuid4()
    for i in range(1, 5):
        create_version(sid, _sample_strategy(stop_loss=float(i)), uid)
    history = list_versions(sid)
    assert [v.version_number for v in history] == [1, 2, 3, 4]
    assert history[0].created_at <= history[-1].created_at


def test_list_versions_returns_empty_for_unknown_strategy() -> None:
    assert list_versions(uuid4()) == []


# ─── 7. get_latest_version returns highest version number ────────────


def test_get_latest_version_returns_highest_numbered() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(stop_loss=1.0), uid)
    create_version(sid, _sample_strategy(stop_loss=2.0), uid)
    latest = get_latest_version(sid)
    assert latest.version_number == 2
    assert latest.strategy_json["stop_loss_percent"] == 2.0


def test_get_latest_version_raises_for_empty_history() -> None:
    with pytest.raises(StrategyVersionNotFoundError):
        get_latest_version(uuid4())


# ─── 8. compare_versions detects added indicator ─────────────────────


def test_compare_detects_added_indicator() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(), uid)
    augmented = _sample_strategy()
    augmented["indicators"].append({"id": "macd", "period": 12})
    create_version(sid, augmented, uid)

    comp = compare_versions(sid, 1, 2)
    assert isinstance(comp, StrategyVersionComparison)
    added = [d for d in comp.diffs if d.change_type == "added"]
    assert any(d.field_path == "indicators[2]" for d in added)


# ─── 9. compare_versions detects modified field ──────────────────────


def test_compare_detects_modified_scalar_field() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(stop_loss=2.0), uid)
    create_version(sid, _sample_strategy(stop_loss=3.5), uid)

    comp = compare_versions(sid, 1, 2)
    sl_diffs = [d for d in comp.diffs if d.field_path == "stop_loss_percent"]
    assert len(sl_diffs) == 1
    diff = sl_diffs[0]
    assert diff.change_type == "modified"
    assert diff.old_value == 2.0
    assert diff.new_value == 3.5


def test_compare_detects_nested_indicator_modification() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(), uid)
    edited = _sample_strategy()
    edited["indicators"][1]["period"] = 21
    create_version(sid, edited, uid)

    comp = compare_versions(sid, 1, 2)
    nested = [d for d in comp.diffs if d.field_path == "indicators[1].period"]
    assert len(nested) == 1
    assert nested[0].change_type == "modified"
    assert nested[0].old_value == 14
    assert nested[0].new_value == 21


# ─── 10. compare_versions detects removed exit rule ──────────────────


def test_compare_detects_removed_exit_rule() -> None:
    sid = uuid4()
    uid = uuid4()
    base = _sample_strategy()
    base["exit_conditions"] = [{"reason": "stop_loss"}, {"reason": "target"}]
    create_version(sid, base, uid)
    trimmed = _sample_strategy()
    trimmed["exit_conditions"] = [{"reason": "stop_loss"}]
    create_version(sid, trimmed, uid)

    comp = compare_versions(sid, 1, 2)
    removed = [d for d in comp.diffs if d.change_type == "removed"]
    assert any("exit_conditions[1]" in d.field_path for d in removed)


# ─── 11. Hinglish summary contains expected keywords ─────────────────


def test_hinglish_summary_mentions_stop_loss_change() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(stop_loss=2.0), uid)
    create_version(sid, _sample_strategy(stop_loss=3.0), uid)

    comp = compare_versions(sid, 1, 2)
    assert "Stop loss" in comp.summary_hinglish
    assert "2" in comp.summary_hinglish and "3" in comp.summary_hinglish


def test_hinglish_summary_mentions_indicator_changes() -> None:
    sid = uuid4()
    uid = uuid4()
    base = _sample_strategy()
    create_version(sid, base, uid)
    augmented = _sample_strategy()
    augmented["indicators"].append({"id": "macd", "period": 12})
    create_version(sid, augmented, uid)

    comp = compare_versions(sid, 1, 2)
    assert "indicator" in comp.summary_hinglish.lower()
    assert "added" in comp.summary_hinglish.lower()


def test_hinglish_summary_handles_no_changes() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(), uid)
    create_version(sid, _sample_strategy(), uid)
    comp = compare_versions(sid, 1, 2)
    assert comp.diffs == []
    assert comp.summary_hinglish  # non-empty by min_length=1 contract


# ─── 12. rollback_to_version creates new version with old content ────


def test_rollback_creates_new_version_with_old_content() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(stop_loss=2.0), uid)
    create_version(sid, _sample_strategy(stop_loss=5.0), uid)
    create_version(sid, _sample_strategy(stop_loss=8.0), uid)

    rolled = rollback_to_version(sid, target_version=1, user_id=uid)
    assert rolled.version_number == 4
    assert rolled.strategy_json["stop_loss_percent"] == 2.0
    assert "Rolled back to v1" in rolled.change_summary


# ─── 13. Rollback preserves history ──────────────────────────────────


def test_rollback_preserves_full_history() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(stop_loss=2.0), uid)
    create_version(sid, _sample_strategy(stop_loss=5.0), uid)
    rollback_to_version(sid, 1, uid)

    history = list_versions(sid)
    assert [v.version_number for v in history] == [1, 2, 3]
    # Original v1 and v2 unchanged.
    assert history[0].strategy_json["stop_loss_percent"] == 2.0
    assert history[1].strategy_json["stop_loss_percent"] == 5.0
    assert history[2].strategy_json["stop_loss_percent"] == 2.0


def test_rollback_to_unknown_version_raises() -> None:
    sid = uuid4()
    uid = uuid4()
    create_version(sid, _sample_strategy(), uid)
    with pytest.raises(StrategyVersionNotFoundError):
        rollback_to_version(sid, 99, uid)


# ─── 14. Persistence: write v1, read after cache-reset simulation ────


def test_persistence_survives_cache_reset(tmp_path: Path) -> None:
    """After writing two versions and clearing the in-memory cache,
    reads must rehydrate from disk and return the same data."""
    sid = uuid4()
    uid = uuid4()
    v1 = create_version(sid, _sample_strategy(stop_loss=1.5), uid)
    v2 = create_version(sid, _sample_strategy(stop_loss=2.5), uid)

    # Simulate process restart: drop in-memory cache, keep base_dir.
    version_store.reset()

    rehydrated = list_versions(sid)
    assert len(rehydrated) == 2
    assert rehydrated[0].version_id == v1.version_id
    assert rehydrated[1].version_id == v2.version_id
    assert rehydrated[1].strategy_json["stop_loss_percent"] == 2.5

    # And the on-disk layout matches the documented contract.
    folder = tmp_path / str(sid)
    assert (folder / "v1.json").exists()
    assert (folder / "v2.json").exists()


# ─── 15. Thread safety: concurrent create_version calls ──────────────


def test_concurrent_create_version_yields_unique_sequential_numbers() -> None:
    sid = uuid4()
    uid = uuid4()
    n_threads = 100
    barrier = threading.Barrier(n_threads)

    def worker(idx: int) -> None:
        barrier.wait()  # release all threads at once for max contention
        create_version(sid, _sample_strategy(stop_loss=float(idx)), uid)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    history = list_versions(sid)
    assert len(history) == n_threads
    numbers = sorted(v.version_number for v in history)
    assert numbers == list(range(1, n_threads + 1))
    # Every version_id is unique under contention.
    assert len({v.version_id for v in history}) == n_threads


# ─── 16. Determinism: same input produces same shape ─────────────────


def test_create_version_shape_is_deterministic_under_same_input() -> None:
    sid_a, sid_b = uuid4(), uuid4()
    uid = uuid4()
    payload = _sample_strategy()
    a = create_version(sid_a, payload, uid, change_summary="x")
    b = create_version(sid_b, payload, uid, change_summary="x")

    # UUIDs and timestamps differ; everything else lines up.
    assert a.version_id != b.version_id
    assert a.created_at <= b.created_at
    assert a.version_number == b.version_number == 1
    assert a.parent_version_id is None and b.parent_version_id is None
    assert a.strategy_json == b.strategy_json
    assert a.change_summary == b.change_summary
    assert a.created_by == b.created_by


# ─── 17. AST inspection: no LLM/DB/network/sqlalchemy imports ────────


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
    "redis",
    "celery",
    "app.db",
    "app.brokers",
    "app.services",
)


def _versioning_python_files() -> list[Path]:
    pkg_root = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "strategy_engine"
        / "strategy_versioning"
    )
    return sorted(p for p in pkg_root.glob("*.py"))


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES)


@pytest.mark.parametrize("source_file", _versioning_python_files())
def test_versioning_module_does_not_import_forbidden_modules(source_file: Path) -> None:
    """Walk every import in every strategy_versioning ``*.py`` and
    assert no LLM SDK, ORM/DB driver, HTTP/socket library, or app
    service layer leaks in. Phase 1 is intentionally stdlib + Pydantic
    only — DB persistence is Phase 3."""
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


# ─── Bonus: round-trip pydantic model_dump_json / model_validate ─────


def test_strategy_version_round_trips_through_pydantic_json() -> None:
    sid = uuid4()
    uid = uuid4()
    original = create_version(sid, _sample_strategy(), uid, change_summary="round trip")
    raw = original.model_dump_json()
    restored = StrategyVersion.model_validate_json(raw)
    assert restored == original


# ─── Bonus: diff record validation rejects unknown change_type ───────


def test_strategy_version_diff_rejects_invalid_change_type() -> None:
    with pytest.raises(ValueError):
        StrategyVersionDiff(
            field_path="x",
            old_value=1,
            new_value=2,
            change_type="bogus",  # type: ignore[arg-type]
        )


# ─── Bonus: deep-copy guarantees isolation from caller mutation ──────


def test_create_version_isolates_from_caller_mutation() -> None:
    sid = uuid4()
    uid = uuid4()
    payload = _sample_strategy(stop_loss=2.0)
    version = create_version(sid, payload, uid)

    payload["stop_loss_percent"] = 99.0
    payload["indicators"].append({"id": "macd", "period": 12})

    fetched = get_version(sid, 1)
    assert fetched.strategy_json["stop_loss_percent"] == 2.0
    assert len(fetched.strategy_json["indicators"]) == 2
    assert version.strategy_json["stop_loss_percent"] == 2.0


# ─── Bonus: constants exposed and sane ───────────────────────────────


def test_constants_have_expected_values() -> None:
    assert CACHE_DIR_NAME == "strategy_versions"
    assert INITIAL_VERSION_NUMBER == 1
    assert MAX_VERSIONS_KEPT >= 1
    assert LOCK_TIMEOUT_SECONDS >= 1

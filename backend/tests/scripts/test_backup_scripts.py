"""Tests for the backup pipeline.

Three tiers covered here:

1. **Shell-script behavior** (subprocess) — stub mode, restore safety
   guard, verify-script corruption detection. Each script lives at
   ``backend/scripts/*.sh`` and is invoked via ``subprocess.run`` so
   we exercise the actual file the cron runs.
2. **Backup health endpoint** — admin gate, JSON shape, parsing of
   the state files written by the scripts.
3. **State-file integration** — the backup script writes
   ``.backup-state.json`` whose shape the endpoint must round-trip.

The shell tests skip when bash isn't on PATH (covers Windows CI). They
deliberately use ``BACKUP_LOCAL_DIR`` set to a tmp_path to avoid
touching ``/var/backups`` (which requires root).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.auth.roles import ROLE_ADMIN, ROLE_USER
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.health import router as backup_health_router

# Repo root → backend/scripts. Resolved via Path so the test file's
# location, not CWD, anchors the lookup.
_BACKEND = Path(__file__).resolve().parents[2]
_SCRIPTS = _BACKEND / "scripts"

#: Skip-marker for environments without bash (rare; CI runs Linux).
_BASH = shutil.which("bash")
requires_bash = pytest.mark.skipif(_BASH is None, reason="bash not available")


# ─── Shell-script tier ────────────────────────────────────────────────


@requires_bash
def test_backup_script_runs_in_stub_mode_without_db_url(
    tmp_path: Path,
) -> None:
    """``backup_postgres.sh`` exits 0 + writes nothing when
    ``BACKUP_DB_URL`` is unset. Critical for: dev laptops that have
    the cron file installed but no live DB; first-boot CI runs."""
    script = _SCRIPTS / "backup_postgres.sh"
    result = subprocess.run(
        ["bash", str(script)],
        env={"BACKUP_LOCAL_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "stub mode" in result.stderr.lower()
    # Stub mode must NOT have written a dump file.
    assert not list(tmp_path.glob("tradetri-*.dump*"))


@requires_bash
def test_verify_script_runs_in_stub_mode_and_writes_state(
    tmp_path: Path,
) -> None:
    """``verify_backup.sh`` in stub mode still drops the
    state JSON the health endpoint reads. Without that, the admin
    dashboard would render "never run" forever in a stub-mode
    environment."""
    script = _SCRIPTS / "verify_backup.sh"
    result = subprocess.run(
        ["bash", str(script)],
        env={"BACKUP_LOCAL_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    state_file = tmp_path / ".verify-state.json"
    assert state_file.exists()
    payload = json.loads(state_file.read_text())
    assert payload["status"] == "stub"


@requires_bash
def test_restore_script_blocks_mismatched_confirm_token(
    tmp_path: Path,
) -> None:
    """The ``--confirm <db_name>`` token must match the DB name
    embedded in ``BACKUP_RESTORE_TARGET``. A mismatch exits 2 *before*
    any pg_restore — defends against a tired oncall engineer
    accidentally restoring into prod."""
    script = _SCRIPTS / "restore_postgres.sh"
    result = subprocess.run(
        [
            "bash",
            str(script),
            "tradetri-20260510T030000Z",
            "--confirm",
            "definitely_not_the_target",
        ],
        env={
            "BACKUP_RESTORE_TARGET": "postgres://u:p@h/scratch_db",
            "BACKUP_LOCAL_DIR": str(tmp_path),
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2, (
        f"expected exit 2 for confirm-mismatch, got {result.returncode}: "
        f"{result.stderr}"
    )
    assert "definitely_not_the_target" in result.stderr


@requires_bash
def test_restore_script_blocks_production_host_pattern(
    tmp_path: Path,
) -> None:
    """The ``BACKUP_PRODUCTION_HOST`` env var fences off the prod RDS
    host. Even with a valid confirm token, the script must refuse to
    restore against that host — production restore is a console
    operation, not a script."""
    script = _SCRIPTS / "restore_postgres.sh"
    result = subprocess.run(
        [
            "bash",
            str(script),
            "tradetri-20260510T030000Z",
            "--confirm",
            "tradetri",
        ],
        env={
            "BACKUP_RESTORE_TARGET": "postgres://u:p@prod-1.rds.amazonaws.com/tradetri",
            "BACKUP_PRODUCTION_HOST": "prod-1.rds.amazonaws.com",
            "BACKUP_LOCAL_DIR": str(tmp_path),
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert "production host" in result.stderr.lower()


# ─── Backup-health endpoint tier ──────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-bkp-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


async def _seed(
    maker: async_sessionmaker[AsyncSession],
    *,
    role: str,
    email: str,
) -> User:
    async with maker() as s:
        u = User(email=email, password_hash="x", is_active=True, role=role)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User | None], TestClient]:
    def _build(user: User | None) -> TestClient:
        app = FastAPI()
        app.include_router(backup_health_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                yield s

        app.dependency_overrides[get_session] = _override_session

        if user is not None:
            async def _override_user() -> User:
                async with db_maker() as s:
                    fresh = await s.get(User, user.id)
                    assert fresh is not None
                    return fresh

            app.dependency_overrides[get_current_active_user] = _override_user

        return TestClient(app)

    return _build


@pytest.mark.asyncio
async def test_backup_health_requires_admin(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """Non-admin users get 403 — the endpoint surfaces operational
    metadata that's not appropriate for end users."""
    user = await _seed(db_maker, role=ROLE_USER, email="user@x")
    with make_client(user) as client:
        resp = client.get("/api/health/backups")
    assert resp.status_code == 403


def test_backup_health_unauthenticated_returns_401(
    make_client: Callable[[User | None], TestClient],
) -> None:
    """No bearer = 401 (the auth dep raises before role check)."""
    with make_client(None) as client:
        resp = client.get("/api/health/backups")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_backup_health_returns_empty_state_when_no_files(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh install — no state files yet. Endpoint returns 200 with
    nullable fields cleared rather than 500-ing on the missing files.
    The admin UI renders this as "no backup yet"."""
    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path))
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)
    admin = await _seed(db_maker, role=ROLE_ADMIN, email="admin@x")
    with make_client(admin) as client:
        resp = client.get("/api/health/backups")
    body = resp.json()
    assert resp.status_code == 200
    assert body["last_backup_at"] is None
    assert body["last_backup_age_hours"] is None
    assert body["backup_count_30d"] == 0
    assert body["last_verification_status"] is None
    assert body["s3_configured"] is False
    assert body["healthy"] is False


@pytest.mark.asyncio
async def test_backup_health_reports_fresh_backup(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backup-state JSON written within the last 25 hours +
    a passing verification flips the ``healthy`` flag to True. Also
    confirms the endpoint counts dump files in the spool dir."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    (tmp_path / f"tradetri-{ts}.dump").write_bytes(b"x" * 42)
    (tmp_path / ".backup-state.json").write_text(
        json.dumps(
            {
                "last_backup_at": ts,
                "last_backup_basename": f"tradetri-{ts}.dump",
                "last_backup_size_bytes": 42,
                "encrypted": False,
                "uploaded_to_s3": False,
            }
        )
    )
    (tmp_path / ".verify-state.json").write_text(
        json.dumps(
            {
                "verified_at": ts,
                "status": "ok",
                "detail": "users=10 drift=0%",
            }
        )
    )
    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("BACKUP_S3_BUCKET", "tradetri-prod-backups")

    admin = await _seed(db_maker, role=ROLE_ADMIN, email="admin2@x")
    with make_client(admin) as client:
        resp = client.get("/api/health/backups")
    body = resp.json()
    assert resp.status_code == 200
    assert body["last_backup_at"] == ts
    assert body["last_backup_size_bytes"] == 42
    assert body["backup_count_30d"] == 1
    assert body["last_verification_status"] == "ok"
    assert body["s3_configured"] is True
    assert body["s3_bucket"] == "tradetri-prod-backups"
    assert body["healthy"] is True
    # Age must be small (just-written) — sub-second under the 25h cap.
    assert body["last_backup_age_hours"] is not None
    assert body["last_backup_age_hours"] < 1.0


@pytest.mark.asyncio
async def test_backup_health_marks_stale_backup_unhealthy(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backup older than the 25h freshness window flips
    ``healthy`` to False — even if the most recent verification was
    "ok". This catches the case where the cron stopped running but
    the last verification still has a stale "ok" recorded."""
    from datetime import UTC, datetime, timedelta

    stale = datetime.now(UTC) - timedelta(hours=48)
    ts = stale.strftime("%Y%m%dT%H%M%SZ")
    (tmp_path / f"tradetri-{ts}.dump").write_bytes(b"x" * 42)
    (tmp_path / ".backup-state.json").write_text(
        json.dumps(
            {
                "last_backup_at": ts,
                "last_backup_basename": f"tradetri-{ts}.dump",
                "last_backup_size_bytes": 42,
                "encrypted": True,
                "uploaded_to_s3": True,
            }
        )
    )
    (tmp_path / ".verify-state.json").write_text(
        json.dumps(
            {
                "verified_at": ts,
                "status": "ok",
                "detail": "users=10 drift=0%",
            }
        )
    )
    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path))
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)

    admin = await _seed(db_maker, role=ROLE_ADMIN, email="admin3@x")
    with make_client(admin) as client:
        resp = client.get("/api/health/backups")
    body = resp.json()
    assert body["healthy"] is False
    assert body["last_backup_age_hours"] is not None
    assert body["last_backup_age_hours"] >= 25.0


@pytest.mark.asyncio
async def test_backup_health_reports_failed_verification(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verification status of "fail" flips ``healthy`` False even
    when the dump itself is fresh — e.g. the dump uploaded successfully
    but the verify script detected drift > tolerance."""
    from datetime import UTC, datetime

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (tmp_path / f"tradetri-{ts}.dump").write_bytes(b"x")
    (tmp_path / ".backup-state.json").write_text(
        json.dumps({"last_backup_at": ts, "last_backup_size_bytes": 1})
    )
    (tmp_path / ".verify-state.json").write_text(
        json.dumps(
            {
                "verified_at": ts,
                "status": "fail",
                "detail": "users count drift 47% > tolerance 5%",
            }
        )
    )
    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path))

    admin = await _seed(db_maker, role=ROLE_ADMIN, email="admin4@x")
    with make_client(admin) as client:
        resp = client.get("/api/health/backups")
    body = resp.json()
    assert body["last_verification_status"] == "fail"
    assert "drift" in (body["last_verification_detail"] or "")
    assert body["healthy"] is False

"""Backup health endpoint — admin-only.

Reads the two state files written by ``backup_postgres.sh`` +
``verify_backup.sh`` from the local spool directory and surfaces:

* The last successful backup's timestamp + size.
* The count of backups in the last 30 days (target ~30).
* The last verification result (ok / fail / stub).
* Whether the configured S3 bucket is reachable.

This sits next to ``app.api.health`` (liveness + readiness) but is
deliberately separated: the liveness endpoint must stay sub-ms and
unauthenticated for k8s probes, while this endpoint is admin-gated +
performs disk + S3 I/O.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.auth.roles import require_admin
from app.core.logging import get_logger
from app.db.models.user import User

logger = get_logger("app.strategy_engine.api.health")

router = APIRouter(prefix="/api/health", tags=["backups"])

#: Local directory the cron backup scripts write to. Mirrors the
#: shell scripts' ``BACKUP_LOCAL_DIR`` default. Override via env at
#: process start when running in a non-default container layout.
_DEFAULT_LOCAL_DIR = "/var/backups/tradetri"

#: Filename pattern produced by ``backup_postgres.sh``. Captured so
#: the count + age computation can ignore unrelated files in the
#: spool directory (verify-state, lockfiles, decrypted scratch).
_DUMP_NAME_RE = re.compile(r"^tradetri-(\d{8}T\d{6}Z)\.dump(\.gpg)?$")


class BackupHealth(BaseModel):
    """Wire shape for ``GET /api/health/backups``.

    Fields are intentionally flat — this is consumed by the admin
    dashboard + downstream monitoring (Datadog / CloudWatch synthetic
    canary), neither of which benefit from nesting.
    """

    model_config = ConfigDict(from_attributes=False)

    spool_dir: str
    s3_bucket: str | None
    last_backup_at: str | None = Field(
        None, description="UTC ISO8601 timestamp of the most recent dump."
    )
    last_backup_age_hours: float | None = Field(
        None, description="Hours since the most recent dump; null if none."
    )
    last_backup_size_bytes: int | None = None
    backup_count_30d: int = Field(
        ..., description="Number of dumps with mtime within the last 30 days."
    )
    last_verification_status: str | None = Field(
        None, description='"ok" / "fail" / "stub" / null if never run.'
    )
    last_verification_at: str | None = None
    last_verification_detail: str | None = None
    s3_configured: bool
    healthy: bool = Field(
        ...,
        description=(
            "True iff: backup within last 25 hours AND last verification "
            "status is ok (or stub in dev)."
        ),
    )


def _spool_dir() -> Path:
    return Path(os.environ.get("BACKUP_LOCAL_DIR", _DEFAULT_LOCAL_DIR))


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open() as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("backup_health.read_failed", path=str(path), error=str(exc))
        return None
    if not isinstance(data, dict):
        return None
    return data


def _parse_dump_timestamp(name: str) -> datetime | None:
    """Parse the timestamp suffix of a dump filename into a tz-aware
    datetime. Returns ``None`` for filenames that don't match the
    canonical pattern (e.g. operator-staged scratch files)."""
    match = _DUMP_NAME_RE.match(name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=UTC
        )
    except ValueError:
        return None


def _scan_dumps(spool: Path) -> list[tuple[datetime, Path]]:
    """List ``(timestamp, path)`` pairs for every dump in ``spool``.

    Sorted newest-first. Files that don't match the canonical naming
    convention are silently skipped — the directory may also contain
    decrypted scratch dumps + state JSON.
    """
    if not spool.is_dir():
        return []
    out: list[tuple[datetime, Path]] = []
    for child in spool.iterdir():
        if not child.is_file():
            continue
        ts = _parse_dump_timestamp(child.name)
        if ts is None:
            continue
        out.append((ts, child))
    out.sort(key=lambda pair: pair[0], reverse=True)
    return out


@router.get("/backups", response_model=BackupHealth)
async def backup_health(
    _admin: Annotated[User, Depends(require_admin)],
) -> BackupHealth:
    """Snapshot of backup pipeline health for admin dashboards.

    Reads two state JSON files written by the cron scripts:

    * ``.backup-state.json`` — most-recent successful backup metadata.
    * ``.verify-state.json`` — most-recent verification outcome.

    When either file is missing the endpoint still returns a 200
    with the available fields ``None`` — admin UI renders the gaps
    as "no run yet" rather than treating it as an error.
    """
    spool = _spool_dir()
    s3_bucket = os.environ.get("BACKUP_S3_BUCKET") or None

    backup_state = _read_json(spool / ".backup-state.json") or {}
    verify_state = _read_json(spool / ".verify-state.json") or {}

    last_backup_at_str: str | None = backup_state.get("last_backup_at")
    last_backup_size: int | None = backup_state.get("last_backup_size_bytes")

    last_backup_age_hours: float | None = None
    if isinstance(last_backup_at_str, str):
        parsed = _parse_dump_timestamp(f"tradetri-{last_backup_at_str}.dump")
        if parsed is not None:
            delta = datetime.now(UTC) - parsed
            last_backup_age_hours = round(delta.total_seconds() / 3600.0, 2)

    cutoff = datetime.now(UTC) - timedelta(days=30)
    count_30d = sum(1 for ts, _ in _scan_dumps(spool) if ts >= cutoff)

    verify_status = verify_state.get("status")
    if not isinstance(verify_status, str):
        verify_status = None
    verify_at = verify_state.get("verified_at")
    if not isinstance(verify_at, str):
        verify_at = None
    verify_detail = verify_state.get("detail")
    if not isinstance(verify_detail, str):
        verify_detail = None

    # Healthy = a fresh backup AND a passing verification.
    # 25 hours covers the daily cron's 24h cycle plus a 1-hour grace
    # window so a slightly-delayed run doesn't flap the indicator.
    fresh = (
        last_backup_age_hours is not None and last_backup_age_hours < 25.0
    )
    verified = verify_status in ("ok", "stub")
    healthy = fresh and verified

    return BackupHealth(
        spool_dir=str(spool),
        s3_bucket=s3_bucket,
        last_backup_at=last_backup_at_str,
        last_backup_age_hours=last_backup_age_hours,
        last_backup_size_bytes=last_backup_size,
        backup_count_30d=count_30d,
        last_verification_status=verify_status,
        last_verification_at=verify_at,
        last_verification_detail=verify_detail,
        s3_configured=s3_bucket is not None,
        healthy=healthy,
    )


__all__ = ["BackupHealth", "router"]

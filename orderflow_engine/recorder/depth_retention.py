"""Depth-subtree retention (Module R1) — shorter local window than R0.

R0 owns the day-folder lifecycle (keeps 10 days of ``data/{date}/`` and deletes
the whole folder once verified + S3-backed-up). Depth data is far larger per day,
and S3 is our durable copy (R0's recursive backup uploads ``data/{date}/depth/``
automatically), so locally we keep only a short REPLAY-CONVENIENCE buffer.

This sweep deletes the ``depth/`` SUBTREE of days older than ``keep_days`` while
leaving the rest of the day folder (R0's ticks/events) intact — it never touches
a day's non-depth data and never deletes a whole day. Same safety guard as R0:

    delete(data/{date}/depth)  iff  depth/report.json exists (depth verified)
        AND  (s3 disabled  OR  data/{date}/backup.json shows a successful upload)

so depth is never removed locally until it is durably in S3.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import date
from pathlib import Path

from recorder.retention import _backup_ok, _parse_day

log = logging.getLogger("recorder.depth_retention")


def _delete_reason(day_dir: Path, s3_enabled: bool) -> str | None:
    """None if the day's depth/ is safe to delete, else a reason to keep it."""
    depth_dir = day_dir / "depth"
    if not (depth_dir / "report.json").exists():
        return "no depth/report.json (unverified)"
    if s3_enabled and not _backup_ok(day_dir):
        return "awaiting successful S3 backup"
    return None


def depth_retention_sweep(data_dir: Path, *, today: date, keep_days: int = 5,
                          s3_enabled: bool = False, dry_run: bool = False) -> dict:
    data_dir = Path(data_dir)
    result: dict = {"today": today.isoformat(), "keep_days": keep_days,
                    "kept": [], "deleted": [], "skipped": []}
    if not data_dir.exists():
        result["error"] = f"{data_dir} does not exist"
        return result

    # Only days that actually have a depth/ subtree are candidates.
    days = sorted((p for p in data_dir.iterdir()
                   if p.is_dir() and _parse_day(p.name) is not None
                   and (p / "depth").is_dir()),
                  key=lambda p: p.name, reverse=True)
    keep, candidates = days[:keep_days], days[keep_days:]
    result["kept"] = [p.name for p in keep]

    for day_dir in candidates:
        reason = _delete_reason(day_dir, s3_enabled)
        if reason is not None:
            result["skipped"].append({"date": day_dir.name, "reason": reason})
            log.info("depth retention: keeping %s/depth — %s", day_dir.name, reason)
            continue
        if dry_run:
            result["deleted"].append(day_dir.name)
            continue
        try:
            shutil.rmtree(day_dir / "depth")
            result["deleted"].append(day_dir.name)
            _log_event(data_dir, {"kind": "DEPTH_RETENTION_DELETE",
                                  "date": day_dir.name, "today": today.isoformat()})
            log.info("depth retention: DELETED %s/depth (older than %d days, "
                     "verified+backed-up)", day_dir.name, keep_days)
        except OSError as exc:
            result["skipped"].append({"date": day_dir.name,
                                      "reason": f"rmtree failed: {exc}"})
            log.error("depth retention: failed to delete %s/depth: %s", day_dir.name, exc)

    return result


def _log_event(data_dir: Path, event: dict) -> None:
    try:
        with (data_dir / "depth_retention.jsonl").open("a") as fh:
            fh.write(json.dumps(event, default=str) + "\n")
    except OSError:
        log.warning("could not append depth-retention event %s", event)

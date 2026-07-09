"""Local retention sweep — bound disk use without ever dropping unbacked data.

Runs nightly (16:05 IST, after verify + backup). Keeps the newest
``retention_days`` daily folders; older folders are deleted **only if it is safe**:

    delete(day)  iff  report.json exists
                 AND  (s3 backup disabled  OR  backup.json shows a successful upload)

So a day is never removed locally until it has been consolidated/verified and
(when S3 is on) durably backed up. Every deletion is logged as an event to
``<data_dir>/retention.jsonl`` and the recorder log. Pure + injectable
(``today``, ``now_iso``) for deterministic tests; ``dry_run`` plans without
touching disk.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import date
from pathlib import Path

log = logging.getLogger("recorder.retention")


def _parse_day(name: str) -> date | None:
    try:
        return date.fromisoformat(name)
    except ValueError:
        return None


def _backup_ok(day_dir: Path) -> bool:
    p = day_dir / "backup.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return False
    return bool(data.get("success"))


def _delete_reason(day_dir: Path, s3_enabled: bool) -> str | None:
    """Return None if the day is safe to delete, else a human reason to keep it."""
    if not (day_dir / "report.json").exists():
        return "no report.json (unverified)"
    if s3_enabled and not _backup_ok(day_dir):
        return "awaiting successful S3 backup"
    return None


def retention_sweep(data_dir: Path, *, today: date, retention_days: int = 10,
                    s3_enabled: bool = False, dry_run: bool = False) -> dict:
    data_dir = Path(data_dir)
    result: dict = {"today": today.isoformat(), "retention_days": retention_days,
                    "kept": [], "deleted": [], "skipped": []}
    if not data_dir.exists():
        result["error"] = f"{data_dir} does not exist"
        return result

    days = sorted((p for p in data_dir.iterdir()
                   if p.is_dir() and _parse_day(p.name) is not None),
                  key=lambda p: p.name, reverse=True)
    # Newest retention_days folders are always kept.
    keep, candidates = days[:retention_days], days[retention_days:]
    result["kept"] = [p.name for p in keep]

    for day_dir in candidates:
        reason = _delete_reason(day_dir, s3_enabled)
        if reason is not None:
            result["skipped"].append({"date": day_dir.name, "reason": reason})
            log.info("retention: keeping %s — %s", day_dir.name, reason)
            continue
        if dry_run:
            result["deleted"].append(day_dir.name)
            continue
        try:
            shutil.rmtree(day_dir)
            result["deleted"].append(day_dir.name)
            _log_event(data_dir, {"kind": "RETENTION_DELETE", "date": day_dir.name,
                                  "today": today.isoformat()})
            log.info("retention: DELETED %s (older than %d days, verified+backed-up)",
                     day_dir.name, retention_days)
        except OSError as exc:
            result["skipped"].append({"date": day_dir.name, "reason": f"rmtree failed: {exc}"})
            log.error("retention: failed to delete %s: %s", day_dir.name, exc)

    return result


def _log_event(data_dir: Path, event: dict) -> None:
    """Append a retention event to <data_dir>/retention.jsonl (durable audit)."""
    try:
        line = json.dumps(event, default=str)
        with (data_dir / "retention.jsonl").open("a") as fh:
            fh.write(line + "\n")
    except OSError:
        log.warning("could not append retention event %s", event)


def main(argv: list[str]) -> int:
    import yaml
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    here = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((here / "config.yaml").read_text())
    ret = cfg.get("retention", {})
    data_dir = here / cfg["storage"]["data_dir"]
    s3_enabled = bool(cfg.get("s3_backup", {}).get("enabled", False))
    from datetime import datetime
    from zoneinfo import ZoneInfo
    dry = "--dry-run" in argv
    result = retention_sweep(
        data_dir, today=datetime.now(ZoneInfo("Asia/Kolkata")).date(),
        retention_days=int(ret.get("retention_days", 10)),
        s3_enabled=s3_enabled, dry_run=dry)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))

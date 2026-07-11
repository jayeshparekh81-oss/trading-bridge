"""Daily S3 backup of a recorded session — the durable, server-independent copy.

After a session is consolidated + verified (15:40 IST), the whole
``data/{date}/`` folder is uploaded to a config-driven S3 bucket. The LOCAL copy
is always kept; S3 is the durable source of truth so recorded data survives an
EC2/AZ failure.

Design:
  * per-file upload with exponential-backoff retry
  * upload-success verification: HEAD each object and compare ContentLength to
    the local file size (a mismatch is treated as a failed upload and retried)
  * a `backup.json` audit is written locally and uploaded as the final marker
  * boto3 uses its default credential chain (EC2 instance role or AWS_* env)
  * a backup FAILURE never raises to the caller — the daemon must keep recording;
    the failure is logged + recorded in backup.json for follow-up

The S3 client and sleep are injectable for tests (no network).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("recorder.s3_backup")


@dataclass
class FileUpload:
    rel: str
    key: str
    size: int
    ok: bool
    retries: int


@dataclass
class BackupResult:
    date: str
    bucket: str
    prefix: str
    files: list = field(default_factory=list)
    total_bytes: int = 0
    ok_count: int = 0
    fail_count: int = 0
    success: bool = False
    skipped: bool = False
    detail: str = ""


class S3Backup:
    def __init__(self, cfg: dict, *, client=None,
                 sleep: Callable[[float], None] = time.sleep):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.bucket = str(cfg.get("bucket", "") or "")
        self.prefix = str(cfg.get("prefix", "") or "").strip("/")
        self.region = cfg.get("region")
        self.retries = max(1, int(cfg.get("retries", 5)))
        self.backoff_base = float(cfg.get("backoff_base_s", 1.0))
        self.max_backoff = float(cfg.get("max_backoff_s", 30.0))
        self.verify = bool(cfg.get("verify", True))
        self._client = client
        self._sleep = sleep

    # -- client --------------------------------------------------------------
    def _get_client(self):
        if self._client is None:
            import boto3  # imported lazily so tests/no-backup runs don't need it
            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def _key(self, date_name: str, rel: str) -> str:
        return "/".join(p for p in (self.prefix, date_name, rel) if p)

    # -- upload --------------------------------------------------------------
    def _upload_one(self, local: Path, key: str) -> tuple[bool, int]:
        """Upload a single file with retry + size verification. Returns (ok, attempts)."""
        size = local.stat().st_size
        client = self._get_client()
        last = None
        for attempt in range(1, self.retries + 1):
            try:
                client.upload_file(str(local), self.bucket, key)
                if self.verify:
                    head = client.head_object(Bucket=self.bucket, Key=key)
                    remote = head.get("ContentLength")
                    if remote != size:
                        raise IOError(f"size mismatch remote={remote} local={size}")
                return True, attempt
            except Exception as exc:  # noqa: BLE001
                last = exc
                if attempt < self.retries:
                    delay = min(self.backoff_base * (2 ** (attempt - 1)), self.max_backoff)
                    log.warning("s3 upload %s attempt %d/%d failed: %s; retry in %.0fs",
                                key, attempt, self.retries, exc, delay)
                    self._sleep(delay)
        log.error("s3 upload FAILED for %s after %d attempts: %s", key, self.retries, last)
        return False, self.retries

    def backup_day(self, day_dir: Path, files: Optional[list[Path]] = None) -> BackupResult:
        """Upload every file under ``day_dir`` (or the given subset). Never raises."""
        day_dir = Path(day_dir)
        res = BackupResult(date=day_dir.name, bucket=self.bucket, prefix=self.prefix)
        if not self.enabled:
            res.skipped = True
            res.success = True
            res.detail = "backup disabled"
            log.info("s3 backup disabled; keeping local copy only (%s)", day_dir.name)
            return res
        if not self.bucket:
            res.detail = "no bucket configured"
            log.error("s3 backup enabled but no bucket configured — data NOT backed up")
            return res
        try:
            if files is None:
                # Exclude any tape-engine analysis outputs (R3): they are DERIVED
                # and reproducible from the raw data via replay — the raw is the
                # asset, analysis is cattle, so it must never be uploaded. (Today
                # analysis/ lives beside data/, not under it; this guard is
                # belt-and-suspenders in case that ever changes.)
                files = sorted(
                    p for p in day_dir.rglob("*")
                    if p.is_file() and "analysis" not in p.relative_to(day_dir).parts)
            for f in files:
                rel = f.relative_to(day_dir).as_posix()
                key = self._key(day_dir.name, rel)
                ok, retries = self._upload_one(f, key)
                res.files.append(FileUpload(rel, key, f.stat().st_size, ok, retries))
                res.total_bytes += f.stat().st_size
                res.ok_count += ok
                res.fail_count += not ok
            res.success = res.fail_count == 0
            res.detail = (f"uploaded {res.ok_count}/{len(res.files)} files "
                          f"({res.total_bytes} bytes) to s3://{self.bucket}/"
                          f"{self._key(day_dir.name, '')}")
            (log.info if res.success else log.error)("s3 backup %s: %s",
                                                     "OK" if res.success else "INCOMPLETE",
                                                     res.detail)
        except Exception as exc:  # noqa: BLE001 - backup must never crash the daemon
            res.detail = f"backup error: {exc}"
            log.exception("s3 backup crashed for %s (data safe locally)", day_dir.name)
        return res

    def write_audit(self, day_dir: Path, result: BackupResult) -> Path:
        out = Path(day_dir) / "backup.json"
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(result), indent=2, default=str))
        tmp.replace(out)
        return out

    def upload_marker(self, day_dir: Path, path: Path) -> bool:
        """Upload a single already-written file (e.g. backup.json) as a marker."""
        if not self.enabled or not self.bucket:
            return False
        rel = Path(path).relative_to(day_dir).as_posix()
        ok, _ = self._upload_one(Path(path), self._key(Path(day_dir).name, rel))
        return ok


def main(argv: list[str]) -> int:
    """CLI: re-run a day's backup on demand. Reads config.yaml for the s3 block."""
    import yaml

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    here = Path(__file__).resolve().parent.parent
    if len(argv) < 2:
        print("usage: python -m recorder.s3_backup <data/YYYY-MM-DD>")
        return 2
    day_dir = Path(argv[1])
    cfg = yaml.safe_load((here / "config.yaml").read_text())
    s3 = S3Backup(cfg.get("s3_backup", {}))
    result = s3.backup_day(day_dir)
    s3.write_audit(day_dir, result)
    s3.upload_marker(day_dir, day_dir / "backup.json")
    print(json.dumps(asdict(result), indent=2, default=str))
    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))

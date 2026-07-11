"""S3 backup tests with a fake client (no network): success, retry, verify, disabled."""

from __future__ import annotations

from pathlib import Path

import pytest

from recorder.s3_backup import S3Backup


class FakeS3:
    """Minimal in-memory S3 stand-in. `fail_first` fails N times per key before
    succeeding; `bad_size` reports a wrong ContentLength to trip verification."""

    def __init__(self, fail_first: int = 0, bad_size: bool = False):
        self.objects: dict[str, int] = {}
        self.fail_first = fail_first
        self.bad_size = bad_size
        self._attempts: dict[str, int] = {}
        self.put_calls = 0

    def upload_file(self, local, bucket, key):
        self._attempts[key] = self._attempts.get(key, 0) + 1
        if self._attempts[key] <= self.fail_first:
            raise ConnectionError("simulated network error")
        self.put_calls += 1
        self.objects[key] = Path(local).stat().st_size

    def head_object(self, Bucket, Key):
        size = self.objects[Key]
        return {"ContentLength": (size + 1) if self.bad_size else size}


def _make_day(tmp_path) -> Path:
    day = tmp_path / "data" / "2026-07-08"
    day.mkdir(parents=True)
    (day / "NIFTY_FUT_61093.parquet").write_bytes(b"x" * 500)
    (day / "events.parquet").write_bytes(b"y" * 100)
    (day / "manifest.json").write_text('{"instruments": []}')
    (day / "report.json").write_text('{"overall": "PASS"}')
    return day


def _cfg(**over):
    base = {"enabled": True, "bucket": "test-bucket", "prefix": "orderflow/r0",
            "region": "ap-south-1", "retries": 4, "backoff_base_s": 1.0, "verify": True}
    base.update(over)
    return base


def test_analysis_outputs_are_excluded(tmp_path):
    """Derived tape-engine analysis must never be swept into the S3 upload (R3)."""
    day = _make_day(tmp_path)
    (day / "analysis").mkdir()
    (day / "analysis" / "NIFTY_FUT_61093.bars.parquet").write_bytes(b"z" * 200)
    fake = FakeS3()
    s3 = S3Backup(_cfg(), client=fake, sleep=lambda *_: None)
    res = s3.backup_day(day)
    assert res.success
    assert not any("analysis" in k for k in fake.objects)          # nothing uploaded
    assert all("analysis" not in f.rel for f in res.files)         # not even listed
    assert any(k.endswith("NIFTY_FUT_61093.parquet") for k in fake.objects)  # raw uploaded


def test_backup_uploads_all_files_with_correct_keys(tmp_path):
    day = _make_day(tmp_path)
    fake = FakeS3()
    s3 = S3Backup(_cfg(), client=fake, sleep=lambda *_: None)
    res = s3.backup_day(day)
    assert res.success is True
    assert res.ok_count == 4 and res.fail_count == 0
    assert "orderflow/r0/2026-07-08/NIFTY_FUT_61093.parquet" in fake.objects
    assert "orderflow/r0/2026-07-08/manifest.json" in fake.objects
    assert res.total_bytes == 500 + 100 + len('{"instruments": []}') + len('{"overall": "PASS"}')


def test_retry_then_succeed(tmp_path):
    day = _make_day(tmp_path)
    fake = FakeS3(fail_first=2)  # first 2 attempts per key fail
    s3 = S3Backup(_cfg(retries=5), client=fake, sleep=lambda *_: None)
    res = s3.backup_day(day)
    assert res.success is True
    # each file needed 3 attempts (2 fail + 1 ok)
    assert all(f.retries == 3 for f in res.files)


def test_verify_size_mismatch_fails(tmp_path):
    day = _make_day(tmp_path)
    fake = FakeS3(bad_size=True)
    s3 = S3Backup(_cfg(retries=3), client=fake, sleep=lambda *_: None)
    res = s3.backup_day(day)
    assert res.success is False
    assert res.fail_count == 4  # every file fails verification


def test_retry_exhausted_marks_failure_but_does_not_raise(tmp_path):
    day = _make_day(tmp_path)
    fake = FakeS3(fail_first=99)  # always fails
    s3 = S3Backup(_cfg(retries=3), client=fake, sleep=lambda *_: None)
    res = s3.backup_day(day)  # must not raise
    assert res.success is False
    assert res.ok_count == 0


def test_disabled_is_noop_and_never_touches_client(tmp_path):
    day = _make_day(tmp_path)
    fake = FakeS3()
    s3 = S3Backup(_cfg(enabled=False), client=fake, sleep=lambda *_: None)
    res = s3.backup_day(day)
    assert res.skipped is True and res.success is True
    assert fake.put_calls == 0


def test_enabled_without_bucket_is_failure_not_crash(tmp_path):
    day = _make_day(tmp_path)
    s3 = S3Backup(_cfg(bucket=""), client=FakeS3(), sleep=lambda *_: None)
    res = s3.backup_day(day)
    assert res.success is False and "bucket" in res.detail


def test_audit_written_and_marker_upload(tmp_path):
    day = _make_day(tmp_path)
    fake = FakeS3()
    s3 = S3Backup(_cfg(), client=fake, sleep=lambda *_: None)
    res = s3.backup_day(day)
    audit = s3.write_audit(day, res)
    assert audit.exists()
    assert s3.upload_marker(day, audit) is True
    assert "orderflow/r0/2026-07-08/backup.json" in fake.objects


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

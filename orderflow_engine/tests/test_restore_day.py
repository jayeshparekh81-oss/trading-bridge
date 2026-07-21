"""M1 restore_day tests — mocked S3, deterministic. Add-only, checksum refusal,
disk-guard refusal, today/live-dir refusal, parts exclusion, cleanup."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from scripts.restore_day import (cleanup_day, plan_keys, restore_day, verify_file)

DAY = "2026-07-14"
ROOT = f"orderflow/r0/{DAY}/"


class FakeS3:
    def __init__(self, files: dict[str, bytes], corrupt: set[str] = ()):
        self.files = files
        self.corrupt = set(corrupt)

    def list_objects_v2(self, **kw):
        out = [{"Key": k, "Size": len(v),
                "ETag": '"%s"' % hashlib.md5(v).hexdigest()}
               for k, v in sorted(self.files.items())]
        return {"Contents": out, "IsTruncated": False}

    def download_file(self, bucket, key, dest):
        data = self.files[key]
        if key in self.corrupt:
            data = data + b"XX"                              # wrong bytes on the wire
        Path(dest).write_bytes(data)


def _s3():
    return FakeS3({
        f"{ROOT}NIFTY_FUT_61093.parquet": b"T" * 100,
        f"{ROOT}manifest.json": b"{}",
        f"{ROOT}backup.json": json.dumps({"files": [
            {"rel": "NIFTY_FUT_61093.parquet", "size": 100},
            {"rel": "depth/NIFTY_FUT_61093.parquet", "size": 50}]}).encode(),
        f"{ROOT}depth/NIFTY_FUT_61093.parquet": b"D" * 50,
        f"{ROOT}depth/NIFTY_FUT_61093/parts/000001.parquet": b"P" * 10,   # EXCLUDED (parts)
        f"{ROOT}corrupt/OLD.parquet.tmp": b"C" * 5,          # EXCLUDED (subdir, not needed)
    })


def test_plan_excludes_parts_subtrees():
    objs = _s3().list_objects_v2()["Contents"]
    plan = plan_keys(objs, DAY)
    rels = {p["rel"] for p in plan}
    assert "depth/NIFTY_FUT_61093.parquet" in rels           # top-level depth kept
    assert not any("parts" in r for r in rels)               # parts excluded
    assert "NIFTY_FUT_61093.parquet" in rels


def test_restore_add_only_and_verified(tmp_path):
    dest = tmp_path / "restore"
    rep = restore_day(DAY, dest_root=dest, client=_s3(), today=date(2026, 7, 22),
                      free_fn=lambda p: 100 * 1024 ** 3)
    assert rep["ok"] and rep["downloaded"] == rep["to_download"]
    assert rep["excluded_parts_objects"] == 2                # parts + corrupt/ subdirs
    f = dest / "data" / DAY / "NIFTY_FUT_61093.parquet"
    assert f.read_bytes() == b"T" * 100
    # ADD-ONLY: mutate the local file; re-run must SKIP it, never overwrite
    f.write_bytes(b"LOCAL")
    rep2 = restore_day(DAY, dest_root=dest, client=_s3(), today=date(2026, 7, 22),
                       free_fn=lambda p: 100 * 1024 ** 3)
    assert "NIFTY_FUT_61093.parquet" in rep2["skipped_existing"]
    assert f.read_bytes() == b"LOCAL"                        # untouched


def test_checksum_mismatch_refused(tmp_path):
    s3 = _s3()
    s3.corrupt.add(f"{ROOT}NIFTY_FUT_61093.parquet")
    rep = restore_day(DAY, dest_root=tmp_path / "r", client=s3, today=date(2026, 7, 22),
                      free_fn=lambda p: 100 * 1024 ** 3)
    assert rep["ok"] is False and rep["verify_failed"]
    assert "size" in rep["verify_failed"][0]["reason"]
    assert not (tmp_path / "r" / "data" / DAY / "NIFTY_FUT_61093.parquet").exists()


def test_disk_guard_refusal(tmp_path):
    rep = restore_day(DAY, dest_root=tmp_path / "r", client=_s3(), today=date(2026, 7, 22),
                      free_fn=lambda p: 1 * 1024 ** 3)       # 1 GB free < need + 10G margin
    assert "disk guard" in rep["refused"]


def test_today_refused(tmp_path):
    rep = restore_day("2026-07-22", dest_root=tmp_path / "r", client=_s3(),
                      today=date(2026, 7, 22))
    assert "TODAY" in rep["refused"]


def test_verify_file_paths(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"abc")
    md5 = hashlib.md5(b"abc").hexdigest()
    assert verify_file(p, 3, md5, 3) is None
    assert "ContentLength" in verify_file(p, 4, md5, None)
    assert "backup.json" in verify_file(p, 3, md5, 99)
    assert "md5" in verify_file(p, 3, "deadbeef", 3)
    assert verify_file(p, 3, "multi-part-etag", 3) is None   # multipart etag: size-only


def test_cleanup(tmp_path):
    dest = tmp_path / "r"
    d = dest / "data" / DAY
    d.mkdir(parents=True)
    (d / "x").write_bytes(b"1")
    assert "removed" in cleanup_day(DAY, dest_root=dest)
    assert not d.exists()
    assert "nothing" in cleanup_day(DAY, dest_root=dest)

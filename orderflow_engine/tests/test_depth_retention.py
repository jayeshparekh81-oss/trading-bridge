"""Tests for depth-subtree retention (Module R1)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from recorder.depth_retention import depth_retention_sweep


def _make_day(root: Path, day: str, *, depth=True, depth_report=True,
              backup_ok=True, root_files=True) -> Path:
    d = root / day
    d.mkdir(parents=True, exist_ok=True)
    if root_files:
        (d / "NIFTY_FUT_1.parquet").write_bytes(b"r0-tick-data")   # R0's own data
        (d / "report.json").write_text(json.dumps({"status": "PASS"}))
    if backup_ok:
        (d / "backup.json").write_text(json.dumps({"success": True}))
    if depth:
        dp = d / "depth"
        dp.mkdir(exist_ok=True)
        (dp / "NIFTY_FUT_1.parquet").write_bytes(b"depth-data")
        if depth_report:
            (dp / "report.json").write_text(json.dumps({"status": "PASS"}))
    return d


def test_keeps_newest_and_deletes_old_depth_subtree(tmp_path):
    for day in ["2026-07-01", "2026-07-02", "2026-07-03",
                "2026-07-04", "2026-07-05", "2026-07-06", "2026-07-07"]:
        _make_day(tmp_path, day)
    res = depth_retention_sweep(tmp_path, today=date(2026, 7, 7),
                                keep_days=5, s3_enabled=True)
    assert set(res["kept"]) == {"2026-07-03", "2026-07-04", "2026-07-05",
                                "2026-07-06", "2026-07-07"}
    assert set(res["deleted"]) == {"2026-07-01", "2026-07-02"}


def test_deletes_only_depth_leaves_day_and_r0_intact(tmp_path):
    for day in ["2026-07-01", "2026-07-02", "2026-07-03",
                "2026-07-04", "2026-07-05", "2026-07-06"]:
        _make_day(tmp_path, day)
    depth_retention_sweep(tmp_path, today=date(2026, 7, 6), keep_days=5, s3_enabled=True)
    old = tmp_path / "2026-07-01"
    assert not (old / "depth").exists()             # depth pruned
    assert old.exists()                             # day folder survives
    assert (old / "NIFTY_FUT_1.parquet").exists()   # R0 data untouched
    assert (old / "report.json").exists()


def test_keeps_when_not_backed_up(tmp_path):
    for day in ["2026-07-01", "2026-07-02", "2026-07-03",
                "2026-07-04", "2026-07-05", "2026-07-06"]:
        _make_day(tmp_path, day)
    # oldest lacks a successful backup -> must be kept while S3 is on
    (tmp_path / "2026-07-01" / "backup.json").write_text(json.dumps({"success": False}))
    res = depth_retention_sweep(tmp_path, today=date(2026, 7, 6), keep_days=5, s3_enabled=True)
    assert "2026-07-01" not in res["deleted"]
    assert (tmp_path / "2026-07-01" / "depth").exists()
    assert any(s["date"] == "2026-07-01" for s in res["skipped"])


def test_keeps_when_depth_unverified(tmp_path):
    for day in ["2026-07-01", "2026-07-02", "2026-07-03",
                "2026-07-04", "2026-07-05", "2026-07-06"]:
        _make_day(tmp_path, day, depth_report=(day != "2026-07-01"))
    res = depth_retention_sweep(tmp_path, today=date(2026, 7, 6), keep_days=5, s3_enabled=True)
    assert "2026-07-01" not in res["deleted"]


def test_s3_disabled_deletes_on_report_only(tmp_path):
    for day in ["2026-07-01", "2026-07-02", "2026-07-03",
                "2026-07-04", "2026-07-05", "2026-07-06"]:
        _make_day(tmp_path, day, backup_ok=False)   # no backup.json at all
    res = depth_retention_sweep(tmp_path, today=date(2026, 7, 6), keep_days=5, s3_enabled=False)
    assert "2026-07-01" in res["deleted"]


def test_days_without_depth_are_ignored(tmp_path):
    _make_day(tmp_path, "2026-07-05")               # has depth
    _make_day(tmp_path, "2026-07-01", depth=False)  # R0-only day, no depth subtree
    res = depth_retention_sweep(tmp_path, today=date(2026, 7, 5), keep_days=1, s3_enabled=True)
    # only depth-bearing days are candidates; the R0-only day is never touched
    assert res["kept"] == ["2026-07-05"]
    assert res["deleted"] == []

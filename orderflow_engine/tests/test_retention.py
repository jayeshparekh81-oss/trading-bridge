"""Retention tests: keep newest N, delete older ONLY IF verified (+backed up)."""

from __future__ import annotations

import json
from datetime import date

from recorder.retention import retention_sweep


def _mkday(data_dir, name, *, report=True, backup_success=None):
    d = data_dir / name
    d.mkdir(parents=True)
    if report:
        (d / "report.json").write_text(json.dumps({"status": "PASS"}))
    if backup_success is not None:
        (d / "backup.json").write_text(json.dumps({"success": backup_success}))
    return d


def test_keeps_newest_n_regardless(tmp_path):
    for i in range(12):
        _mkday(tmp_path, f"2026-06-{i+1:02d}")
    res = retention_sweep(tmp_path, today=date(2026, 6, 30), retention_days=10,
                          s3_enabled=False, dry_run=True)
    assert len(res["kept"]) == 10
    # the 2 oldest are deletion candidates
    assert set(res["deleted"]) == {"2026-06-01", "2026-06-02"}


def test_old_day_without_report_is_skipped(tmp_path):
    for i in range(10):
        _mkday(tmp_path, f"2026-06-{i+3:02d}")           # 10 recent (kept)
    _mkday(tmp_path, "2026-06-01", report=False)          # old, unverified -> skip
    _mkday(tmp_path, "2026-06-02", report=True)           # old, verified -> delete
    res = retention_sweep(tmp_path, today=date(2026, 6, 30), retention_days=10,
                          s3_enabled=False)
    assert "2026-06-02" in res["deleted"]
    assert not (tmp_path / "2026-06-02").exists()
    assert {"date": "2026-06-01", "reason": "no report.json (unverified)"} in res["skipped"]
    assert (tmp_path / "2026-06-01").exists()             # kept on disk


def test_s3_enabled_requires_successful_backup(tmp_path):
    for i in range(10):
        _mkday(tmp_path, f"2026-06-{i+4:02d}")
    _mkday(tmp_path, "2026-06-01", report=True, backup_success=True)   # ok -> delete
    _mkday(tmp_path, "2026-06-02", report=True, backup_success=False)  # failed -> keep
    _mkday(tmp_path, "2026-06-03", report=True)                        # no backup.json -> keep
    res = retention_sweep(tmp_path, today=date(2026, 6, 30), retention_days=10,
                          s3_enabled=True)
    assert res["deleted"] == ["2026-06-01"]
    reasons = {s["date"]: s["reason"] for s in res["skipped"]}
    assert reasons["2026-06-02"] == "awaiting successful S3 backup"
    assert reasons["2026-06-03"] == "awaiting successful S3 backup"


def test_deletion_logged_as_event(tmp_path):
    for i in range(10):
        _mkday(tmp_path, f"2026-06-{i+3:02d}")
    _mkday(tmp_path, "2026-06-01", report=True)
    retention_sweep(tmp_path, today=date(2026, 6, 30), retention_days=10,
                    s3_enabled=False)
    jl = tmp_path / "retention.jsonl"
    assert jl.exists()
    events = [json.loads(l) for l in jl.read_text().splitlines()]
    assert any(e["kind"] == "RETENTION_DELETE" and e["date"] == "2026-06-01"
               for e in events)


def test_nothing_deleted_when_within_retention(tmp_path):
    for i in range(5):
        _mkday(tmp_path, f"2026-06-{i+1:02d}")
    res = retention_sweep(tmp_path, today=date(2026, 6, 30), retention_days=10,
                          s3_enabled=False)
    assert res["deleted"] == []
    assert len(res["kept"]) == 5

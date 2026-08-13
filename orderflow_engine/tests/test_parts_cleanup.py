"""Parts cleanup — deletes real data, so every keep-gate is locked (2026-07-16).

failed backup -> kept; verify PARTIAL -> kept; instrument has problems -> kept; S3 HEAD
fails -> kept; all-clean -> eligible; dry-run deletes nothing; --apply actually deletes.
"""

from __future__ import annotations

import json
from pathlib import Path

from recorder.parts_cleanup import PartsCleanup

CFG = {"bucket": "b", "prefix": "orderflow/r0", "region": "ap-south-1"}


class FakeS3:
    """head_object returns the size for known keys; raises (404) otherwise."""
    def __init__(self, sizes: dict, mismatch: bool = False):
        self.sizes = sizes
        self.mismatch = mismatch

    def head_object(self, Bucket, Key):
        if Key not in self.sizes:
            raise KeyError("404")
        sz = self.sizes[Key]
        return {"ContentLength": sz + 1 if self.mismatch else sz}


def _day(tmp_path, *, status="PASS", backup_success=True, inst_problems=None,
         day_problems=None, final_rows=100):
    day = tmp_path / "2026-07-15"
    (day / "parts" / "NIFTY_FUT_61093").mkdir(parents=True)
    (day / "parts" / "NIFTY_FUT_61093" / "part-0001.parquet").write_bytes(b"x" * 5000)
    final = day / "NIFTY_FUT_61093.parquet"
    final.write_bytes(b"F" * 900)
    (day / "report.json").write_text(json.dumps({
        "status": status,
        "problems": day_problems or [],
        "instruments": [{"file": "NIFTY_FUT_61093.parquet", "rows": final_rows,
                         "problems": inst_problems or []}],
    }))
    (day / "backup.json").write_text(json.dumps({"success": backup_success}))
    return day, final


def _s3_for(final: Path):
    key = "orderflow/r0/2026-07-15/NIFTY_FUT_61093.parquet"
    return FakeS3({key: final.stat().st_size})


# ---- keep cases ------------------------------------------------------------------

def test_failed_backup_keeps_parts(tmp_path):
    day, final = _day(tmp_path, backup_success=False)
    p = PartsCleanup(CFG, client=_s3_for(final)).plan(day)
    assert p["eligible"] == []
    assert p["kept"][0]["reason"] == "backup.json not success:true"


def test_partial_verify_keeps_parts(tmp_path):
    day, final = _day(tmp_path, status="PARTIAL")
    p = PartsCleanup(CFG, client=_s3_for(final)).plan(day)
    assert p["eligible"] == [] and "not PASS" in p["kept"][0]["reason"]


def test_instrument_problem_keeps_parts(tmp_path):
    day, final = _day(tmp_path, inst_problems=["volume RESET"])
    p = PartsCleanup(CFG, client=_s3_for(final)).plan(day)
    assert p["eligible"] == [] and "problems" in p["kept"][0]["reason"]


def test_named_in_day_problems_keeps_parts(tmp_path):
    # PASS status but the instrument is named in a day-level problem -> keep (belt+suspenders)
    day, final = _day(tmp_path, day_problems=["liquid feed gap on NIFTY_FUT_61093"])
    p = PartsCleanup(CFG, client=_s3_for(final)).plan(day)
    assert p["eligible"] == [] and "day-level problems" in p["kept"][0]["reason"]


def test_s3_head_fails_keeps_parts(tmp_path):
    day, final = _day(tmp_path)
    p = PartsCleanup(CFG, client=FakeS3({})).plan(day)          # object not in S3
    assert p["eligible"] == [] and "S3 HEAD" in p["kept"][0]["reason"]


def test_s3_size_mismatch_keeps_parts(tmp_path):
    day, final = _day(tmp_path)
    key = "orderflow/r0/2026-07-15/NIFTY_FUT_61093.parquet"
    p = PartsCleanup(CFG, client=FakeS3({key: final.stat().st_size}, mismatch=True)).plan(day)
    assert p["eligible"] == [] and "S3 HEAD" in p["kept"][0]["reason"]


def test_missing_final_keeps_parts(tmp_path):
    day, final = _day(tmp_path)
    final.unlink()                                              # final gone
    p = PartsCleanup(CFG, client=FakeS3({})).plan(day)
    assert p["eligible"] == [] and p["kept"][0]["reason"] == "final missing on disk"


# ---- eligible + apply ------------------------------------------------------------

def test_all_clean_is_eligible(tmp_path):
    day, final = _day(tmp_path)
    p = PartsCleanup(CFG, client=_s3_for(final)).plan(day)
    assert len(p["eligible"]) == 1 and p["kept"] == []
    assert p["eligible"][0]["base"] == "NIFTY_FUT_61093"
    assert p["free_bytes"] == 5000


def test_dry_run_deletes_nothing(tmp_path):
    day, final = _day(tmp_path)
    pc = PartsCleanup(CFG, client=_s3_for(final))
    res = pc.run(day, apply=False)
    assert res["applied"] is False
    assert (day / "parts" / "NIFTY_FUT_61093").exists()        # still there


def test_apply_deletes_only_eligible(tmp_path):
    day, final = _day(tmp_path)
    pc = PartsCleanup(CFG, client=_s3_for(final))
    res = pc.run(day, apply=True)
    assert res["applied"] is True
    assert not (day / "parts" / "NIFTY_FUT_61093").exists()     # deleted
    assert not (day / "parts").exists()                         # empty parent removed
    assert final.exists()                                       # final untouched


def test_apply_keeps_when_gate_fails(tmp_path):
    day, final = _day(tmp_path, backup_success=False)
    pc = PartsCleanup(CFG, client=_s3_for(final))
    pc.run(day, apply=True)
    assert (day / "parts" / "NIFTY_FUT_61093").exists()         # NOT deleted (backup failed)

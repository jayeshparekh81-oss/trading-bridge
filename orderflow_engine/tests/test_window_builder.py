"""Window-builder tests (i)-(v) — every I/O seam injected, no S3/disk/replay.

(i)   all-local frozen list -> all ok, correct manifest
(ii)  a 0-candidate day -> empty-ok, KEPT (not dropped, not failed)
(iii) a restore-needed day -> restore called, alternate root recorded, cleanup called after
(iv)  a restore FAILURE -> failed with reason, excluded, run continues (no crash)
(v)   refuses to run with no explicit day-list
"""

from __future__ import annotations

from datetime import date

import pytest

from research.window_builder import (
    AssessResult, DEGRADED, EMPTY_OK, FAILED, LocalProbe, OK, build_window,
)

INSTS = ("NIFTY_FUT", "BANKNIFTY_FUT")


def _probe(present_complete: dict):
    """present_complete: day -> (present, complete, reason)."""
    def fn(day, data_root):
        pr, co, rs = present_complete.get(day, (False, False, "not local"))
        return LocalProbe(present=pr, complete=co, reason=rs)
    return fn


def _assess(counts: dict):
    """counts: day -> int|None candidate count."""
    def fn(day, root, instruments):
        c = counts.get(day, 0)
        return AssessResult(candidates=c, per_instrument={} if c is None else {"NIFTY_FUT": c})
    return fn


# ---------- (i) all local -> all ok ----------
def test_i_all_local_ok():
    days = ["2026-07-20", "2026-07-21"]
    man = build_window(
        days, instruments=INSTS, today=date(2026, 7, 22),
        probe_fn=_probe({d: (True, True, "span 100%") for d in days}),
        assess_fn=_assess({"2026-07-20": 310, "2026-07-21": 246}),
        restore_fn=lambda d, r: (_ for _ in ()).throw(AssertionError("restore must not be called")),
        cleanup_fn=lambda d, r: (_ for _ in ()).throw(AssertionError("cleanup must not be called")))
    assert man["ready"] == days and not man["excluded"]
    assert man["counts"][OK] == 2
    e = {x["day"]: x for x in man["days"]}
    assert e["2026-07-20"]["source"] == "local" and e["2026-07-20"]["status"] == OK
    assert e["2026-07-20"]["candidates"] == 310
    assert e["2026-07-21"]["candidates"] == 246


# ---------- (ii) 0-candidate day -> empty-ok, kept, NOT failed ----------
def test_ii_empty_ok_kept_not_dropped():
    days = ["2026-07-14", "2026-07-15"]
    man = build_window(
        days, instruments=INSTS, today=date(2026, 7, 22),
        probe_fn=_probe({d: (True, True, "") for d in days}),
        assess_fn=_assess({"2026-07-14": 0, "2026-07-15": 280}))
    e = {x["day"]: x for x in man["days"]}
    assert e["2026-07-14"]["status"] == EMPTY_OK          # distinct from failed
    assert e["2026-07-14"]["candidates"] == 0
    assert e["2026-07-14"]["status"] != FAILED
    assert len(man["days"]) == 2                          # nothing dropped
    assert "2026-07-14" in man["ready"]                  # empty-ok is consumable
    assert man["counts"][EMPTY_OK] == 1 and man["counts"][OK] == 1
    assert not man["excluded"]


# ---------- (iii) restore-needed -> restore + alternate root + cleanup after ----------
def test_iii_restore_flow_records_root_and_cleans():
    calls = {"restore": [], "cleanup": [], "order": []}

    def restore_fn(day, restore_root):
        calls["restore"].append(day); calls["order"].append(("restore", day))
        return {"ok": True, "dest": f"{restore_root}/data/{day}"}

    def cleanup_fn(day, restore_root):
        calls["cleanup"].append(day); calls["order"].append(("cleanup", day))
        return "removed"

    def assess_fn(day, root, instruments):
        calls["order"].append(("assess", day))
        return AssessResult(candidates=99, per_instrument={"NIFTY_FUT": 99})

    man = build_window(
        ["2026-07-13"], instruments=INSTS, today=date(2026, 7, 22),
        restore_root="/tmp/x/restore",
        probe_fn=_probe({"2026-07-13": (False, False, "S3-only")}),
        restore_fn=restore_fn, cleanup_fn=cleanup_fn, assess_fn=assess_fn)
    e = man["days"][0]
    assert e["source"] == "restored" and e["status"] == OK and e["candidates"] == 99
    assert e["root"] == "/tmp/x/restore"                 # alternate root recorded
    assert "re-restore to evaluate" in e["note"]
    assert calls["restore"] == ["2026-07-13"] and calls["cleanup"] == ["2026-07-13"]
    # INLINE ordering: restore -> assess -> cleanup (cleanup AFTER assess, before any next)
    assert calls["order"] == [("restore", "2026-07-13"), ("assess", "2026-07-13"),
                              ("cleanup", "2026-07-13")]


# ---------- (iv) restore FAILURE -> failed+reason, excluded, run continues ----------
def test_iv_restore_failure_excluded_run_continues():
    def restore_fn(day, restore_root):
        if day == "2026-07-10":
            return {"refused": "REFUSED: no S3 objects under orderflow/r0/2026-07-10/"}
        return {"ok": True}

    days = ["2026-07-10", "2026-07-13"]                   # first fails, second must still process
    man = build_window(
        days, instruments=INSTS, today=date(2026, 7, 22),
        probe_fn=_probe({d: (False, False, "S3-only") for d in days}),
        restore_fn=restore_fn, cleanup_fn=lambda d, r: "removed",
        assess_fn=_assess({"2026-07-13": 250}))
    e = {x["day"]: x for x in man["days"]}
    assert e["2026-07-10"]["status"] == FAILED
    assert "no S3 objects" in e["2026-07-10"]["note"]     # reason preserved
    assert e["2026-07-13"]["status"] == OK                # run CONTINUED past the failure
    assert len(man["days"]) == 2                          # nothing dropped
    assert {x["day"] for x in man["excluded"]} == {"2026-07-10"}
    assert man["ready"] == ["2026-07-13"]
    # a restore that RAISES also becomes failed, not a crash
    man2 = build_window(
        ["2026-07-09"], instruments=INSTS, today=date(2026, 7, 22),
        probe_fn=_probe({"2026-07-09": (False, False, "S3-only")}),
        restore_fn=lambda d, r: (_ for _ in ()).throw(RuntimeError("boto3 down")))
    assert man2["days"][0]["status"] == FAILED and "boto3 down" in man2["days"][0]["note"]


# ---------- partial/stale local day -> degraded, excluded, not silently used ----------
def test_partial_local_degraded_excluded():
    man = build_window(
        ["2026-07-22"], instruments=INSTS, today=date(2026, 7, 23),
        probe_fn=_probe({"2026-07-22": (True, False, "partial session: span 20% < 50% floor")}),
        assess_fn=lambda d, r, i: (_ for _ in ()).throw(AssertionError("must not assess a partial day")))
    e = man["days"][0]
    assert e["status"] == DEGRADED and "partial session" in e["note"]
    assert e["day"] in {x["day"] for x in man["excluded"]}
    assert man["ready"] == []


# ---------- un-assessable (restored raw-only, no signals.parquet) -> degraded ----------
def test_unassessable_candidates_none_degraded():
    man = build_window(
        ["2026-07-13"], instruments=INSTS, today=date(2026, 7, 22),
        probe_fn=_probe({"2026-07-13": (False, False, "S3-only")}),
        restore_fn=lambda d, r: {"ok": True}, cleanup_fn=lambda d, r: "removed",
        assess_fn=lambda d, r, i: AssessResult(candidates=None, note="no signals.parquet"))
    e = man["days"][0]
    assert e["status"] == DEGRADED and "no signals.parquet" in e["note"]


# ---------- (v) refuses with no explicit day-list ----------
def test_v_refuses_without_explicit_list():
    with pytest.raises(ValueError, match="explicit frozen day-list"):
        build_window([])
    with pytest.raises(ValueError):
        build_window(["", "  "])                          # blank entries are not a list
    with pytest.raises(ValueError):
        build_window(None)                                # type: ignore[arg-type]


# ---------- the REAL default probe: completeness from report.json coverage ----------
def _make_day(root, day, *, expected=23280.0, observed=None, with_report=True):
    import json
    dd = root / "data" / day
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "manifest.json").write_text(json.dumps({"instruments": []}))
    if with_report:
        cov = {"expected_session_s": expected}
        if observed is not None:
            cov["observed_span_s"] = observed
        (dd / "report.json").write_text(json.dumps({"coverage": cov}))
    return dd


def test_default_probe_completeness(tmp_path):
    from research.window_builder import _default_probe
    TODAY = date(2026, 7, 23)
    _make_day(tmp_path, "2026-07-21", observed=23368.6)   # 100% span
    _make_day(tmp_path, "2026-07-22", observed=22189.8)   # 95% span (post-rollback full day)
    _make_day(tmp_path, "2026-07-19", observed=4600.0)    # ~20% span -> partial
    _make_day(tmp_path, "2026-07-18", with_report=False)  # no report -> not finalized
    _make_day(tmp_path, "2026-07-23", observed=23000.0)   # TODAY -> still recording

    def probe(day):
        return _default_probe(day, tmp_path, today=TODAY, min_coverage_frac=0.5)

    assert probe("2026-07-21").complete is True
    assert probe("2026-07-22").complete is True            # 95% clears the 50% floor
    p19 = probe("2026-07-19"); assert p19.present and not p19.complete and "partial" in p19.reason
    p18 = probe("2026-07-18"); assert p18.present and not p18.complete and "not finalized" in p18.reason
    p23 = probe("2026-07-23"); assert p23.present and not p23.complete and "TODAY" in p23.reason
    p00 = probe("2026-07-01"); assert p00.present is False  # no dir at all

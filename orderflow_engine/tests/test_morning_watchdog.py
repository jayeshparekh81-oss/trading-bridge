"""Morning-watchdog check functions — mocked docker/fs, deterministic."""

from __future__ import annotations

import time

from scripts.morning_watchdog import (build_message, check_bse_fut, check_containers,
                                      check_errors, check_resolve_log, check_ticks, run)

GOOD_INSPECT = "/orderflow_recorder running 0\n/orderflow_depth_recorder running 0\n"
GOOD_LOG = ("resolved BSE stock future -> 61134 (BSE-Jul2026-FUT, expiry 2026-07-28)\n"
            "resolved BSE stock option chain -> expiry 2026-07-28, 44 strikes\n"
            "universe capacity: 26 core + up to 452 option strikes = 478 (limit 15000)\n"
            "idle (verify); sleeping\n")


def test_containers_up_and_restart_counts():
    ok, det = check_containers(sh=lambda c: GOOD_INSPECT)
    assert ok and "running 0" in det
    ok2, _ = check_containers(sh=lambda c: "/orderflow_recorder running 3\n"
                                           "/orderflow_depth_recorder running 0\n")
    assert not ok2                                            # restart-loop caught
    ok3, det3 = check_containers(sh=lambda c: "__ERR__ TimeoutExpired")
    assert not ok3 and "failed" in det3                       # docker down != green


def test_resolve_log_checks():
    ok, det = check_resolve_log(sh=lambda c: GOOD_LOG)
    assert ok and "478" in det and "fut=Y opt=Y" in det
    missing = GOOD_LOG.replace("resolved BSE stock option chain -> expiry 2026-07-28, 44 strikes\n", "")
    ok2, det2 = check_resolve_log(sh=lambda c: missing)
    assert not ok2 and "opt=N" in det2
    bad = GOOD_LOG + "ERROR recorder.main no stock future for BSE: resolve failed\n"
    assert not check_resolve_log(sh=lambda c: bad)[0]


def test_tick_and_bse_file_checks(tmp_path):
    day = "2026-07-22"
    dd = tmp_path / "data" / day
    dd.mkdir(parents=True)
    now = time.time()
    for n in ("NIFTY_FUT_61093.parquet.tmp", "BANKNIFTY_FUT_61088.parquet.tmp"):
        (dd / n).write_bytes(b"x" * 100)
    ok, det = check_ticks(root=tmp_path, day=day, now=now)
    assert ok and "100B" in det
    # stale file -> not fresh -> fail
    ok2, det2 = check_ticks(root=tmp_path, day=day, now=now + 600)
    assert not ok2
    # BSE fut: missing -> fail; present+bytes -> pass
    assert check_bse_fut(root=tmp_path, day=day)[0] is False
    (dd / "BSE_FUT_61134.parquet.tmp").write_bytes(b"y" * 10)
    ok3, det3 = check_bse_fut(root=tmp_path, day=day)
    assert ok3 and "10B" in det3


def test_error_grep_and_messages():
    assert check_errors(sh=lambda c: "INFO fine\nINFO also fine\n")[0] is True
    assert check_errors(sh=lambda c: "Traceback (most recent call last):\n")[0] is False
    green = build_message([("containers", True, "ok"), ("resolve", True, "universe 478"),
                           ("ticks", True, "ok"), ("bse_fut", True, "ok"),
                           ("log_errors", True, "ok")])
    assert green.startswith("✅ BSE DAY-1 ALL GREEN") and "478" in green
    red = build_message([("containers", True, "ok"), ("resolve", False, "opt=N"),
                         ("ticks", False, "NO file"), ("bse_fut", True, "ok"),
                         ("log_errors", True, "ok")])
    assert red.startswith("🔴 PROBLEM: resolve") and "pre-bse" in red and "+1 more" in red


def test_run_test_mode_message(monkeypatch):
    import scripts.morning_watchdog as mw
    monkeypatch.setattr(mw, "check_containers", lambda sh=None: (True, "ok"))
    msg = mw.run(test_mode=True)
    assert msg.startswith("🌙 TEST / pre-market") and "09:05" in msg

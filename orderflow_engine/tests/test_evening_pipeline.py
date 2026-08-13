"""Auto-evening pipeline + Daily Pulse (2026-07-16).

The pipeline must be un-killable-by-failure w.r.t. recording, hard-timeout a hang,
and the Pulse must format correctly + send as an OPS channel independent of signal
alerts. These lock those guarantees.
"""

from __future__ import annotations

import sys

import recorder.evening_pipeline as EP
from alerts.config import AlertsConfig
from alerts.pulse import format_pulse, send_pulse


# ---- pipeline: failure is recorded, never raised; continues best-effort ----------

def test_step_failure_recorded_and_pipeline_continues(tmp_path, monkeypatch):
    py = sys.executable
    monkeypatch.setattr(EP, "_steps", lambda d, c: [
        ("boom", [py, "-c", "import sys; sys.exit(3)"]),      # fails
        ("fine", [py, "-c", "pass"]),                         # runs anyway
    ])
    st = EP.run_pipeline("2026-07-16", {"total_timeout_s": 30, "step_timeout_s": 10},
                         root=tmp_path)
    by = {s["name"]: s for s in st["steps"]}
    assert by["boom"]["status"] == "failed" and by["boom"]["rc"] == 3
    assert by["fine"]["status"] == "ok"                      # continued after the failure
    assert st["overall"] == "failed"                          # surfaced, not hidden
    assert (tmp_path / "analysis" / "2026-07-16" / "pipeline_status.json").exists()


def test_timeout_kills_step_cleanly(tmp_path, monkeypatch):
    py = sys.executable
    monkeypatch.setattr(EP, "_steps", lambda d, c: [
        ("hang", [py, "-c", "import time; time.sleep(30)"]),
    ])
    st = EP.run_pipeline("2026-07-16", {"total_timeout_s": 20, "step_timeout_s": 1},
                         root=tmp_path)
    assert st["steps"][0]["status"] == "timeout"              # killed at step_timeout, not hung
    assert st["overall"] == "timeout"
    assert st["seconds"] < 10                                 # returned promptly (step_timeout=1s)


def test_budget_exhaustion_skips_remaining(tmp_path, monkeypatch):
    py = sys.executable
    monkeypatch.setattr(EP, "_steps", lambda d, c: [
        ("slow", [py, "-c", "import time; time.sleep(2)"]),   # consumes the budget
        ("never", [py, "-c", "pass"]),
    ])
    st = EP.run_pipeline("2026-07-16", {"total_timeout_s": 6, "step_timeout_s": 10},
                         root=tmp_path)
    names = {s["name"]: s["status"] for s in st["steps"]}
    assert names["slow"] == "ok"                             # ran within budget
    assert names["never"] == "skipped_budget"                # budget exhausted -> not launched


# ---- kill-switch + default date (the pipeline runs in its OWN container now) ------

def test_disabled_pipeline_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(EP, "_load_cfg", lambda root: {"enabled": False})

    def fail(*a, **k):
        raise AssertionError("run_pipeline must not run when disabled")
    monkeypatch.setattr(EP, "run_pipeline", fail)
    assert EP.main(["prog", "--date", "2026-07-16", "--root", str(tmp_path)]) == 0


def test_date_defaults_to_today_ist(monkeypatch):
    captured = {}
    monkeypatch.setattr(EP, "_load_cfg", lambda root: {"enabled": True})

    def fake_run(d, c, r):
        captured["date"] = d
        return {"overall": "completed"}
    monkeypatch.setattr(EP, "run_pipeline", fake_run)
    EP.main(["prog", "--root", "/tmp"])                      # no --date -> today IST
    assert captured["date"] == EP._today_ist()


# ---- Pulse: golden format + send-independent-of-signal-alerts --------------------

GOLDEN_DATA = {
    "date": "2026-07-16", "verdict": "PASS", "coverage_pct": 100.4,
    "spot_vix_ok": True, "depth_status": "PASS", "s3_verified": True,
    "disk_free_gb": 71.2, "g0": 2, "candidates": 280, "top_score": 46.4, "fired": 0,
    "pipeline": "completed", "pipeline_steps": [{"name": "tape.run", "status": "ok"}],
}


def test_pulse_golden_format():
    msg = format_pulse(GOLDEN_DATA)
    assert msg == (
        "<b>🩺 Orderflow Pulse — 2026-07-16</b>\n"
        "recording: ✅ <b>PASS</b>  coverage 100.4%\n"
        "spot/VIX ✅   depth ✅   S3 ✅\n"
        "disk free: 71.2 GB\n"
        "G0: day <b>2/5</b>\n"
        "signals: candidates 280   top 46.4   fired 0\n"
        "pipeline: ✅ completed"
    )


def test_pulse_shows_failure_and_partial():
    d = dict(GOLDEN_DATA, verdict="PARTIAL", spot_vix_ok=False, s3_verified=False,
             pipeline="failed", pipeline_steps=[{"name": "chain.run", "status": "timeout"}])
    msg = format_pulse(d)
    assert "🟡 <b>PARTIAL</b>" in msg
    assert "spot/VIX ❌" in msg and "S3 ❌" in msg
    assert "pipeline: ❌ failed  (failed: chain.run)" in msg


class _FakeTransport:
    def __init__(self):
        self.sent = []

    def send(self, text, parse_mode="HTML"):
        self.sent.append(text)
        return True


def test_pulse_sends_when_signal_alerts_off(tmp_path):
    # signal alerts OFF, pulse ON -> the Pulse still sends (it's an ops channel)
    cfg = AlertsConfig({"alerts": {"enabled": False, "pulse_enabled": True}})
    tr = _FakeTransport()
    assert send_pulse("2026-07-16", tmp_path, {"overall": "completed"}, cfg, transport=tr) is True
    assert len(tr.sent) == 1 and "Orderflow Pulse" in tr.sent[0]


def test_pulse_skipped_when_knob_off(tmp_path):
    cfg = AlertsConfig({"alerts": {"enabled": True, "pulse_enabled": False}})
    tr = _FakeTransport()
    assert send_pulse("2026-07-16", tmp_path, {"overall": "completed"}, cfg, transport=tr) is False
    assert tr.sent == []                                      # never sent

"""CLI dry-run, --send gating, daily-summary (Module R7). No network."""

from __future__ import annotations

import json
from pathlib import Path

from alerts import run as R
from tests.alerts.fixtures import sample_row, write_signals_parquet


def _setup(tmp_path):
    out = tmp_path / "analysis" / "2026-07-13"
    write_signals_parquet(out, [
        sample_row(),                                          # fired long, score 35
        # 20s later (> min_gap 10s) so both are sent in the dry-run, not dedup-blocked
        sample_row(side="short", fired=False, gate_reason="cooldown", score=12.0,
                   ts_ns=sample_row()["ts_ns"] + 20 * 10**9),
    ])
    return out


def test_dry_run_writes_file(tmp_path):
    out = _setup(tmp_path)
    rc = R.main(["alerts.run", "--date", "2026-07-13", "--data-dir",
                 str(tmp_path / "data"), "--dry-run", "--min-score", "0"])
    assert rc == 0
    dry = (out / "alerts_dryrun.txt").read_text()
    assert "NIFTY_FUT" in dry and "LONG" in dry
    assert "SHORT" in dry                                      # min-score 0 pulls the non-fired one


def test_min_score_filters(tmp_path):
    out = _setup(tmp_path)
    R.main(["alerts.run", "--date", "2026-07-13", "--data-dir", str(tmp_path / "data"),
            "--dry-run", "--min-score", "30"])
    dry = (out / "alerts_dryrun.txt").read_text()
    assert "LONG" in dry and "SHORT" not in dry               # score-12 short excluded


def test_send_without_credentials_exits_cleanly(tmp_path, monkeypatch, capsys):
    _setup(tmp_path)
    monkeypatch.delenv("ORDERFLOW_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ORDERFLOW_TELEGRAM_CHAT_ID", raising=False)
    rc = R.main(["alerts.run", "--date", "2026-07-13", "--data-dir",
                 str(tmp_path / "data"), "--send"])
    assert rc == 0                                            # clean exit
    out = capsys.readouterr().out
    assert "enabled=false" in out or "refusing" in out       # inert: nothing sent


def test_no_signals_file_returns_2(tmp_path):
    rc = R.main(["alerts.run", "--date", "2026-07-13", "--data-dir", str(tmp_path / "data"),
                 "--dry-run"])
    assert rc == 2


def test_daily_summary_dry_run(tmp_path):
    out = _setup(tmp_path)
    (out / "signals_summary.json").write_text(json.dumps({
        "date": "2026-07-13", "counts": {"candidates": 2, "fired": 1},
        "net_simulated_r": 0.0, "gate_rejects": {"cooldown": 1}}))
    rc = R.main(["alerts.run", "--date", "2026-07-13", "--data-dir", str(tmp_path / "data"),
                 "--dry-run", "--daily-summary", "--top", "5"])
    assert rc == 0
    dry = (out / "alerts_dryrun.txt").read_text()
    assert "2026-07-13" in dry and "candidates: 2" in dry and "top 5 by score" in dry

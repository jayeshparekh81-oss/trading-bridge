"""Daily Pulse — one ops/health message after the evening pipeline (Module R7).

This is NOT a signal alert. It reports SESSION HEALTH (recording verdict, coverage,
spot/VIX/depth ok, S3 verified, disk, G0 counter, candidates/top-score/fired, pipeline
status) so the founder reads one message instead of hunting through logs. It sends even
when ``alerts.enabled`` (signal alerts) is false, gated on its own ``alerts.pulse_enabled``
knob. fire_threshold is never touched. Reuses the R7 TelegramTransport/DryRunTransport.

collect_pulse_data() is read-only and DEFENSIVE — every source is optional; a missing file
becomes an "?" in the message, never an exception (the Pulse must survive a broken pipeline,
that's the whole point). format_pulse() is pure (golden-testable).
"""

from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from alerts.format import esc
from alerts.transport import DryRunTransport, TelegramTransport

HERE = Path(__file__).resolve().parent.parent
G0_START = date(2026, 7, 15)          # G0 Day-1 — the first clean session (see TAPE_NOTES)
G0_TARGET = 5
SPOT_VIX = ["NIFTY_SPOT", "BANKNIFTY_SPOT", "INDIA_VIX"]


def _load_json(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:  # noqa: BLE001
        return None


_HOLIDAYS: Optional[frozenset] = None


def _holidays() -> frozenset:
    """NSE holiday set, loaded once from the same holidays.yaml the recorder skips on."""
    global _HOLIDAYS
    if _HOLIDAYS is None:
        from recorder.scheduler import load_holidays
        _HOLIDAYS = load_holidays(HERE / "holidays.yaml")
    return _HOLIDAYS


def _no_session(rep: dict) -> bool:
    """A day the market was CLOSED (a holiday — listed or NSE-unscheduled) or produced no
    data at all: the recorder connected but coverage is ~0. This is NOT a dirty session,
    so it must NOT reset the streak. (A real dirty day — e.g. the 07-13 disk crash at 84%
    coverage — has real coverage and correctly still resets.)"""
    cov = (rep.get("coverage") or {}).get("coverage_pct")
    return cov is not None and cov < 5.0


def _g0_counter(root: Path, up_to: date) -> int:
    """Consecutive clean-PASS sessions from G0_START..up_to. SKIPPED (streak unchanged):
    weekends, LISTED holidays, not-run days (no report), and NO-SESSION days (recorder
    connected on a closed weekday → ~0% coverage — the unlisted/unscheduled-holiday hole).
    A real PARTIAL/FAIL session resets. Read-only."""
    streak, d = 0, G0_START
    hols = _holidays()
    while d <= up_to:
        if d not in hols:                                 # listed holiday -> skip entirely
            rep = _load_json(root / "data" / d.isoformat() / "report.json")
            if rep is not None and not _no_session(rep):  # a REAL session ran this day
                streak = streak + 1 if rep.get("status") == "PASS" else 0
        d += timedelta(days=1)
    return streak


def collect_pulse_data(date_str: str, root: Path, pipeline_status: Optional[dict] = None) -> dict:
    """Gather everything the Pulse reports. Read-only; missing sources -> None."""
    ddir = root / "data" / date_str
    adir = root / "analysis" / date_str
    rep = _load_json(ddir / "report.json") or {}
    backup = _load_json(ddir / "backup.json") or {}
    depth_rep = _load_json(ddir / "depth" / "report.json") or {}
    sig = _load_json(adir / "signals_summary.json") or {}

    # spot/VIX rows ok = every spot/VIX instrument recorded > 0 rows
    rows_by_sym = {}
    for inst in rep.get("instruments", []):
        stem = str(inst.get("file", "")).replace(".parquet", "")
        sym = "_".join(stem.split("_")[:-1])
        rows_by_sym[sym] = inst.get("rows", 0)
    spot_ok = all(rows_by_sym.get(s, 0) > 0 for s in SPOT_VIX) if rows_by_sym else None

    try:
        free_gb = round(shutil.disk_usage(str(root)).free / 1e9, 1)
    except Exception:  # noqa: BLE001
        free_gb = None

    cov = rep.get("coverage", {}) or {}
    counts = sig.get("counts", {}) or {}
    # top score: the summary carries counts + fires, not the max candidate score —
    # read it from the score column of signals.parquet (cheap, one column, defensive).
    top_score = None
    sp = adir / "signals.parquet"
    if sp.exists():
        try:
            import pyarrow.parquet as pq
            scores = pq.read_table(str(sp), columns=["score"]).column("score").to_pylist()
            top_score = max(scores) if scores else None
        except Exception:  # noqa: BLE001
            top_score = None

    return {
        "date": date_str,
        "verdict": rep.get("status"),
        "coverage_pct": cov.get("coverage_pct"),
        "spot_vix_ok": spot_ok,
        "depth_status": depth_rep.get("status"),
        "s3_verified": (backup.get("success") is True) if backup else None,
        "disk_free_gb": free_gb,
        "g0": _g0_counter(root, date.fromisoformat(date_str)),
        "candidates": counts.get("candidates"),
        "top_score": round(top_score, 1) if top_score is not None else None,
        "fired": counts.get("fired"),
        "pipeline": (pipeline_status or {}).get("overall", "unknown"),
        "pipeline_steps": (pipeline_status or {}).get("steps", []),
    }


def _mark(ok: Optional[bool]) -> str:
    return "✅" if ok is True else ("❌" if ok is False else "❔")


def format_pulse(d: dict) -> str:
    """Pure formatter -> Telegram HTML. Golden-tested."""
    v = d.get("verdict")
    vmark = {"PASS": "✅", "PARTIAL": "🟡", "FAIL": "❌"}.get(v, "❔")
    cov = d.get("coverage_pct")
    g0 = d.get("g0")
    pipe = d.get("pipeline", "unknown")
    pmark = {"completed": "✅", "failed": "❌", "timeout": "⏱️", "skipped": "⏭️"}.get(pipe, "❔")
    failed = [s.get("name") for s in d.get("pipeline_steps", []) if s.get("status") != "ok"]
    lines = [
        f"<b>🩺 Orderflow Pulse — {esc(str(d.get('date', '?')))}</b>",
        f"recording: {vmark} <b>{esc(str(v or '?'))}</b>"
        f"{f'  coverage {cov}%' if cov is not None else ''}",
        f"spot/VIX {_mark(d.get('spot_vix_ok'))}   "
        f"depth {_mark(d.get('depth_status') == 'PASS') if d.get('depth_status') else '❔'}   "
        f"S3 {_mark(d.get('s3_verified'))}",
        f"disk free: {d.get('disk_free_gb', '?')} GB",
        f"G0: day <b>{g0 if g0 is not None else '?'}/{G0_TARGET}</b>",
        f"signals: candidates {d.get('candidates', '?')}   "
        f"top {d.get('top_score', '?')}   fired {d.get('fired', '?')}",
        f"pipeline: {pmark} {esc(pipe)}"
        + (f"  (failed: {esc(', '.join(failed))})" if failed else ""),
    ]
    return "\n".join(lines)


def send_pulse(date_str: str, root: Path, pipeline_status: Optional[dict], cfg,
               transport=None) -> bool:
    """Build + send the Pulse. Gated on cfg.pulse_enabled (NOT cfg.enabled — the Pulse
    is a health message, not a signal). Returns False (no send) when disabled or when
    Telegram creds are absent. Never raises."""
    if not cfg.pulse_enabled:
        return False
    data = collect_pulse_data(date_str, root, pipeline_status)
    text = format_pulse(data)
    if transport is None:
        transport = (DryRunTransport(root / "analysis" / date_str / "pulse_dryrun.txt")
                     if cfg.transport == "dryrun" else TelegramTransport(cfg))
    try:
        return bool(transport.send(text))
    except Exception:  # noqa: BLE001 — a failed Pulse must never crash the pipeline
        return False

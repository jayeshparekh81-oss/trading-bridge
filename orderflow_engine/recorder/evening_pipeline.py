"""Auto-evening analysis pipeline (Module R7 ops).

After the EOD consolidate+verify+S3 (~15:40), the recorder launches this DETACHED so
the day's full analysis X-ray is on disk (~16:40) instead of the founder waiting ~55min
for it later. It runs the chain — levels.daily(NIFTY,BANKNIFTY) -> tape.run -> levels.run
--daily-cache -> chain.run --index NIFTY -> signals.run -> alerts.run --dry-run
--daily-summary — then sends the Daily Pulse.

SAFETY (it must NEVER endanger recording):
  * runs as a DETACHED subprocess of the recorder (separate process group) — it does not
    touch the recorder's asyncio loop or state;
  * runs only in the idle window (15:45–09:05 next day), never during recording;
  * HARD total budget + per-step timeout (SIGKILL) so a hang can't survive into the next
    session; a step failure is RECORDED and the pipeline continues best-effort;
  * self-caps address space via RLIMIT_AS (mem_cap_mb); the container cgroup mem_limit is
    the RSS backstop;
  * every failure is visible in pipeline_status.json + the Pulse, and CANNOT affect the
    recorder (fire-and-forget launch, caught at the call site).

Run standalone: python -m recorder.evening_pipeline --date YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent.parent      # orderflow_engine/
DAILY_CACHE_DEFAULT = str(Path.home() / "oe_hist")


def _steps(date_str: str, cache: str) -> list[tuple[str, list[str]]]:
    d = date.fromisoformat(date_str)
    frm = (d - timedelta(days=60)).isoformat()
    py = [sys.executable, "-m"]
    return [
        ("levels.daily.NIFTY", py + ["levels.daily", "--symbol", "NIFTY",
                                     "--from", frm, "--to", date_str, "--cache", cache]),
        ("levels.daily.BANKNIFTY", py + ["levels.daily", "--symbol", "BANKNIFTY",
                                         "--from", frm, "--to", date_str, "--cache", cache]),
        ("tape.run", py + ["tape.run", "--date", date_str]),
        ("levels.run", py + ["levels.run", "--date", date_str, "--daily-cache", cache]),
        ("chain.run", py + ["chain.run", "--date", date_str, "--index", "NIFTY"]),
        ("signals.run", py + ["signals.run", "--date", date_str]),
        ("alerts.run", py + ["alerts.run", "--date", date_str, "--dry-run", "--daily-summary"]),
    ]


def _today_ist() -> str:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()


def run_pipeline(date_str: str, cfg: dict, root: Path = HERE, log=None) -> dict:
    """Run the chain best-effort under a total budget. Returns a status dict.
    Never raises — every step failure is captured."""
    cache = cfg.get("daily_cache") or DAILY_CACHE_DEFAULT
    total_budget = float(cfg.get("total_timeout_s", 5400))    # 90 min (>~55min runtime)
    step_to = float(cfg.get("step_timeout_s", 2400))          # 40 min/step
    logdir = root / "analysis" / date_str
    logdir.mkdir(parents=True, exist_ok=True)
    logf = log or (logdir / "evening_pipeline.log").open("a")
    started = time.monotonic()

    def emit(msg: str) -> None:
        logf.write(msg + "\n")
        logf.flush()

    emit(f"=== evening pipeline {date_str} start (budget {total_budget:.0f}s) ===")
    steps_status = []
    for name, argv in _steps(date_str, cache):
        elapsed = time.monotonic() - started
        remaining = total_budget - elapsed
        if remaining <= 5:
            emit(f"[{name}] SKIPPED — total budget exhausted ({elapsed:.0f}s)")
            steps_status.append({"name": name, "status": "skipped_budget"})
            continue
        to = min(step_to, remaining)
        emit(f"[{name}] start (timeout {to:.0f}s, {remaining:.0f}s budget left)")
        t0 = time.monotonic()
        try:
            r = subprocess.run(argv, cwd=str(root), stdout=logf, stderr=subprocess.STDOUT,
                               timeout=to)
            dt = time.monotonic() - t0
            st = "ok" if r.returncode == 0 else "failed"
            emit(f"[{name}] {st} rc={r.returncode} ({dt:.0f}s)")
            steps_status.append({"name": name, "status": st, "rc": r.returncode,
                                 "seconds": round(dt, 1)})
        except subprocess.TimeoutExpired:
            dt = time.monotonic() - t0
            emit(f"[{name}] TIMEOUT after {dt:.0f}s — killed")
            steps_status.append({"name": name, "status": "timeout", "seconds": round(dt, 1)})
        except Exception as exc:  # noqa: BLE001
            emit(f"[{name}] ERROR {type(exc).__name__}: {exc}")
            steps_status.append({"name": name, "status": "error", "error": type(exc).__name__})

    any_bad = any(s["status"] != "ok" for s in steps_status)
    overall = ("timeout" if any(s["status"] == "timeout" for s in steps_status)
               else ("failed" if any_bad else "completed"))
    total_s = round(time.monotonic() - started, 1)
    status = {"date": date_str, "overall": overall, "seconds": total_s, "steps": steps_status}
    (logdir / "pipeline_status.json").write_text(json.dumps(status, indent=2))
    emit(f"=== pipeline {overall} in {total_s:.0f}s ===")
    if log is None:
        logf.close()
    return status


def _load_cfg(root: Path) -> dict:
    import yaml
    p = root / "config.yaml"
    d = yaml.safe_load(p.read_text()) if p.exists() else {}
    return (d or {}).get("evening_pipeline", {}) or {}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="recorder.evening_pipeline")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today IST)")
    ap.add_argument("--root", default=str(HERE))
    args = ap.parse_args(argv[1:])
    root = Path(args.root)
    date_str = args.date or _today_ist()
    cfg = _load_cfg(root)
    if not cfg.get("enabled", True):
        print("evening_pipeline.enabled=false — skipping")
        return 0
    status = run_pipeline(date_str, cfg, root)
    # Pulse — send even if the pipeline failed (that's exactly when it matters)
    try:
        from alerts.config import load_alerts_config
        from alerts.pulse import send_pulse
        send_pulse(date_str, root, status, load_alerts_config())
    except Exception:  # noqa: BLE001
        pass
    return 0 if status["overall"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

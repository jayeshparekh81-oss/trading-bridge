"""MORNING WATCHDOG v2 (2026-07-23) — DISK-TRUTH recurring health check.

Codifies the manual disk-truth checklist. VERDICTS come from disk + docker STATE only; any
docker-log read is SUPPLEMENTARY context and captures stderr (2>&1) — the v1 lesson (v1 grepped
stdout while the recorder logs to stderr, went blind, and false-alarmed a healthy BSE session).

STRICTLY READ-ONLY w.r.t. data/: it reads file SIZES and manifest.json only, never writes there.
Every side effect (docker, telegram, clock, sleep, filesystem sizes) is an injectable seam so
the whole verdict tree is unit-testable without docker, network, or a real 45s wait.

Verdict logic (verbatim from the runbook):
  * GREEN  = all pass -> one-line Telegram.
  * YELLOW = BSE-only anomaly with core (NIFTY/BANKNIFTY) healthy -> "NOT an emergency, no
             rollback; capture logs, diagnose at leisure".
  * RED    = core not flowing OR crash-loop -> "genuine rollback trigger, see OPS_NOTES
             2-MINUTE ROLLBACK (STEP-0 log dump first)".
  * HOLIDAY (per holidays.yaml) = one-line "holiday, no session" (quiet).
Reuses the Daily-Pulse Telegram transport (alerts/transport.py) and load_holidays
(recorder/scheduler.py) — nothing rebuilt.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent.parent          # orderflow_engine/
IST = timezone(timedelta(hours=5, minutes=30))
CORE = ("NIFTY_FUT", "BANKNIFTY_FUT")
BSE_FUT_ID = 61134
RECORDER, DEPTH = "orderflow_recorder", "orderflow_depth_recorder"
LATEST_IMAGE = "orderflow-recorder:latest"
MARKET_OPEN, MARKET_CLOSE = time(9, 15), time(15, 30)
GROWTH_WAIT_S = 45


# ---------------------------- injectable seams --------------------------------
def _sh(cmd: list[str]) -> str:
    """Run a command, MERGING stderr into stdout (the v1 fix — docker/python log to stderr)."""
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=30)
        return r.stdout
    except Exception as exc:                            # noqa: BLE001 — report, never raise
        return f"__ERR__ {type(exc).__name__}"


def _now() -> datetime:
    return datetime.now(IST)


def _newest_size(day_dir: Path, prefix: str) -> Optional[int]:
    """Size of the newest .tmp/.parquet file for ``prefix`` (READ-ONLY: stat only)."""
    files = [f for f in day_dir.glob(f"{prefix}_*") if f.suffix in (".tmp", ".parquet")]
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime).stat().st_size


# ---------------------------- market calendar ---------------------------------
def is_market_hours(now: datetime, holidays: frozenset) -> bool:
    return (now.weekday() < 5 and now.date() not in holidays
            and MARKET_OPEN <= now.timetz().replace(tzinfo=None) <= MARKET_CLOSE)


def is_trading_day(now: datetime, holidays: frozenset) -> bool:
    return now.weekday() < 5 and now.date() not in holidays


# ---------------------------- checks (disk/docker truth) ----------------------
def check_containers(sh: Callable = _sh) -> dict:
    """Both recorders running, restarts=0, on the CURRENT :latest image (not a hardcoded hash)."""
    out = sh(["docker", "inspect", RECORDER, DEPTH,
              "--format", "{{.Name}} {{.State.Status}} {{.RestartCount}} {{.Image}}"])
    latest = sh(["docker", "inspect", LATEST_IMAGE, "--format", "{{.Id}}"]).strip()
    if "__ERR__" in out:
        return {"ok": False, "running": False, "restarts_ok": False, "image_ok": False,
                "detail": f"docker inspect failed: {out.strip()}"}
    rows = [l.split() for l in out.strip().splitlines() if l.strip()]
    running = len(rows) == 2 and all(len(r) >= 4 and r[1] == "running" for r in rows)
    restarts_ok = len(rows) == 2 and all(len(r) >= 4 and r[2] == "0" for r in rows)
    image_ok = bool(latest) and "__ERR__" not in latest and \
        all(len(r) >= 4 and r[3] == latest for r in rows)
    detail = "; ".join(f"{r[0]} {r[1]} restarts={r[2]}" for r in rows) or "no containers"
    return {"ok": running and restarts_ok and image_ok, "running": running,
            "restarts_ok": restarts_ok, "image_ok": image_ok, "detail": detail}


def check_manifest(root: Path, day: str) -> dict:
    """Today's manifest: BSE_FUT present, BSE options>=35, universe 480-520, core present."""
    import json
    p = root / "data" / day / "manifest.json"
    if not p.exists():
        return {"ok": False, "core_ok": False, "bse_ok": False, "detail": "no manifest.json"}
    try:
        ins = json.loads(p.read_text()).get("instruments", [])
    except Exception:                                   # noqa: BLE001
        return {"ok": False, "core_ok": False, "bse_ok": False, "detail": "manifest unreadable"}
    syms = {e.get("symbol"): e for e in ins}
    total = len(ins)
    core_present = all(c in syms for c in CORE)
    bse_fut = syms.get("BSE_FUT", {}).get("security_id") == BSE_FUT_ID
    bse_opts = sum(1 for s in syms if s.startswith("BSE_") and ("_CE_" in s or "_PE_" in s))
    # Universe band 470-520 (founder-confirmed 2026-07-23; healthy days measure ~477-505 —
    # the ATM-window arming varies the total, 480 would false-RED a healthy day).
    # SEVERITY SPLIT (founder refinement): universe-out-of-band alone is CHAIN-SIDE
    # degradation (record-only impact) -> YELLOW; only core-missing is RED-class.
    universe_ok = 470 <= total <= 520
    bse_ok = bse_fut and bse_opts >= 35
    return {"ok": core_present and universe_ok and bse_ok, "core_ok": core_present,
            "universe_ok": universe_ok, "bse_ok": bse_ok,
            "detail": f"universe {total}, BSE_FUT={'Y' if bse_fut else 'N'}, "
                      f"BSE opts {bse_opts}, core={'Y' if core_present else 'N'}"}


def sample_growth(root: Path, day: str, prefixes, *, market_open: bool,
                  sleep_fn: Callable = None, size_fn: Callable = _newest_size) -> dict:
    """Two size samples GROWTH_WAIT_S apart; each prefix -> grew? Outside market hours we
    report presence/size only (grew=None) and never sleep."""
    day_dir = root / "data" / day
    s1 = {p: size_fn(day_dir, p) for p in prefixes}
    if not market_open:
        return {p: {"grew": None, "size": s1[p], "present": s1[p] is not None} for p in prefixes}
    (sleep_fn or __import__("time").sleep)(GROWTH_WAIT_S)
    s2 = {p: size_fn(day_dir, p) for p in prefixes}
    out = {}
    for p in prefixes:
        a, b = s1[p], s2[p]
        grew = (a is not None and b is not None and b > a)
        out[p] = {"grew": grew, "s1": a, "s2": b, "present": a is not None}
    return out


def check_depth(root: Path, day: str, *, market_open: bool, sh: Callable = _sh,
                sleep_fn: Callable = None) -> dict:
    """Depth journals to depth/parts/<inst>/part-*.parquet during the session; the top-level
    depth/*.parquet is the EOD consolidation. Count part-files, resample for growth."""
    parts = root / "data" / day / "depth" / "parts"
    def count() -> int:
        return sum(1 for _ in parts.glob("*/*.parquet")) if parts.exists() else 0
    n1 = count()
    dirs = sum(1 for _ in parts.iterdir()) if parts.exists() else 0
    if not market_open:
        return {"ok": n1 > 0, "grew": None, "part_files": n1, "inst_dirs": dirs}
    (sleep_fn or __import__("time").sleep)(GROWTH_WAIT_S)
    n2 = count()
    return {"ok": n2 > n1, "grew": n2 > n1, "part_files": n2, "inst_dirs": dirs}


# ---------------------------- verdict -----------------------------------------
def classify(containers: dict, manifest: dict, growth: dict, depth: dict,
             *, market_open: bool) -> tuple[str, str]:
    """Return (verdict, telegram message). Disk/docker STATE only — never log-grep."""
    crash_loop = not containers["running"] or not containers["restarts_ok"]
    core_grow_bad = market_open and any(not growth.get(c, {}).get("grew", False) for c in CORE)
    core_missing = not manifest["core_ok"]              # NIFTY/BANKNIFTY absent from manifest
    # RED: crash-loop / containers down-or-restarting, or core not present / not flowing.
    # (Universe-out-of-band alone is NOT RED — founder refinement 2026-07-23: chain-side
    # degradation with core healthy is record-only impact -> YELLOW below.)
    if crash_loop or core_grow_bad or core_missing:
        why = []
        if crash_loop:
            why.append(f"crash-loop/down ({containers['detail']})")
        if core_missing:
            why.append(f"core missing from manifest ({manifest['detail']})")
        if core_grow_bad:
            bad = [c for c in CORE if not growth.get(c, {}).get("grew", False)]
            why.append(f"core not flowing: {', '.join(bad)}")
        return "RED", ("🔴 RED: " + "; ".join(why) +
                       " — GENUINE ROLLBACK TRIGGER, see OPS_NOTES 2-MINUTE ROLLBACK "
                       "(STEP-0 log dump FIRST).")
    # YELLOW: chain-side-only anomaly with core healthy (BSE issue OR universe out of band)
    bse_grow_bad = market_open and not growth.get("BSE_FUT", {}).get("grew", False)
    universe_bad = not manifest.get("universe_ok", True)
    if not manifest["bse_ok"] or bse_grow_bad or universe_bad:
        det = manifest["detail"] + ("; BSE_FUT not growing" if bse_grow_bad else "") + \
            ("; universe out of 470-520 band" if universe_bad else "")
        return "YELLOW", ("🟡 YELLOW: chain-side anomaly, core healthy (" + det +
                          "). NOT an emergency, no rollback; capture logs "
                          "(docker logs <c> 2>&1 > file), diagnose at leisure.")
    # GREEN — "flowing" is only claimed in market hours (growth verified); off-hours the
    # recorder is idle, so we report STATE only, never a flow claim.
    depth_note = f"depth {depth.get('part_files', 0)} parts" + ("↑" if depth.get("grew") else "")
    flow = "core+BSE flowing" if market_open else "state healthy (off-hours, idle — no growth check)"
    return "GREEN", (f"🟢 GREEN: {manifest['detail']}; {flow}; {depth_note}; restarts=0")


def run(root: Path = HERE, *, now: Optional[datetime] = None, sh: Callable = _sh,
        holidays: Optional[frozenset] = None, sleep_fn: Callable = None,
        size_fn: Callable = _newest_size) -> tuple[str, str]:
    now = now or _now()
    if holidays is None:
        from recorder.scheduler import load_holidays
        holidays = load_holidays(root / "holidays.yaml")
    day = now.date().isoformat()
    if not is_trading_day(now, holidays):
        return "HOLIDAY", f"🗓 holiday/weekend, no session ({day})"
    mkt = is_market_hours(now, holidays)
    containers = check_containers(sh)
    manifest = check_manifest(root, day)
    growth = sample_growth(root, day, list(CORE) + ["BSE_FUT"], market_open=mkt,
                           sleep_fn=sleep_fn, size_fn=size_fn)
    depth = check_depth(root, day, market_open=mkt, sh=sh, sleep_fn=sleep_fn)
    return classify(containers, manifest, growth, depth, market_open=mkt)


# ---------------------------- CLI ---------------------------------------------
def main(argv: list[str]) -> int:
    import os
    verdict, msg = run()
    print(f"{verdict}: {msg}")
    if "--dry-run" in argv:                             # print only, no send
        return 0
    env = HERE / ".env"                                 # cron has no compose env injection
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    sys.path.insert(0, str(HERE))
    from alerts.config import load_alerts_config
    from alerts.transport import TelegramTransport
    sent = TelegramTransport(load_alerts_config()).send(msg)
    print(f"telegram sent={sent}")
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

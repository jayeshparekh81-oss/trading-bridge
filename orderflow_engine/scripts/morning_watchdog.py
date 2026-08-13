"""ONE-TIME morning watchdog (2026-07-22, BSE day-1) — ALERT-ONLY, read-only.

Checks (never acts): (a) both recorder containers Up with 0 restarts; (b) today's
resolve log — armed universe count, BSE FUTSTK + OPTSTK resolved, zero resolve errors;
(c) NIFTY/BANKNIFTY fut tick files exist, >0 bytes, fresh mtime; (d) BSE_FUT file
>0 bytes; (e) error/traceback grep in today's recorder logs.

Sends ONE Telegram via the SAME transport the Daily Pulse uses
(alerts/transport.py:41 TelegramTransport, env ORDERFLOW_TELEGRAM_BOT_TOKEN/CHAT_ID —
namespaced, never the live bot). NEVER takes any action; rollback is a HUMAN decision
(OPS_NOTES pre-bse block).

Scheduling: a DATE-GUARDED cron line (host clock is UTC; 09:20 IST = 03:50 UTC —
same TZ convention as the 15:50-IST/10:20-UTC evening-pipeline line). `at` was
rejected because atd is not installed on this host; the inline `date +%F` guard makes
the line one-shot even if it lingers. Removal noted in OPS_NOTES.

FAIL-SAFE (in OPS_NOTES): NO message by 09:25 == the watchdog itself failed — treat
as unknown state and run the Wednesday checklist by hand.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent      # orderflow_engine/
TARGET_DAY = "2026-07-22"
FRESH_S = 180                                       # tick file must be < 3 min old


def _sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except Exception as exc:                       # noqa: BLE001 — report, never raise
        return f"__ERR__ {type(exc).__name__}"


# ---------------------------- pure checks (runner injectable for tests) --------------
def check_containers(sh=_sh) -> tuple[bool, str]:
    out = sh(["docker", "inspect", "orderflow_recorder", "orderflow_depth_recorder",
              "--format", "{{.Name}} {{.State.Status}} {{.RestartCount}}"])
    if "__ERR__" in out:
        return False, f"docker inspect failed: {out}"
    lines = [l for l in out.strip().splitlines() if l]
    ok = len(lines) == 2 and all(" running 0" in l for l in lines)
    return ok, "; ".join(lines) or "no containers found"


def check_resolve_log(sh=_sh) -> tuple[bool, str]:
    log = sh(["docker", "logs", "orderflow_recorder", "--since", "8h"])
    if "__ERR__" in log:
        return False, "docker logs failed"
    fut = "resolved BSE stock future" in log
    opt = "resolved BSE stock option chain" in log
    errs = sum(1 for l in log.splitlines()
               if ("resolve" in l.lower() and ("error" in l.lower() or "no stock" in l.lower())))
    cap = next((l.split("universe capacity: ")[1].split(" (")[0]
                for l in log.splitlines() if "universe capacity:" in l), "?")
    ok = fut and opt and errs == 0
    return ok, f"universe {cap}; BSE fut={'Y' if fut else 'N'} opt={'Y' if opt else 'N'} resolve_errs={errs}"


def _file_ok(day_dir: Path, prefix: str, *, fresh_s: int = FRESH_S,
             now: float | None = None) -> tuple[bool, str]:
    files = sorted(day_dir.glob(f"{prefix}_*"))
    files = [f for f in files if f.suffix in (".tmp", ".parquet")]
    if not files:
        return False, f"{prefix}: NO file"
    f = files[-1]
    size = f.stat().st_size
    age = (now if now is not None else time.time()) - f.stat().st_mtime
    ok = size > 0 and age < fresh_s
    return ok, f"{prefix}: {size}B age={int(age)}s"


def check_ticks(root: Path = HERE, day: str = TARGET_DAY, now: float | None = None,
                fresh_s: int = FRESH_S) -> tuple[bool, str]:
    dd = root / "data" / day
    if not dd.exists():
        return False, f"data/{day} missing"
    n_ok, n_msg = _file_ok(dd, "NIFTY_FUT", fresh_s=fresh_s, now=now)
    b_ok, b_msg = _file_ok(dd, "BANKNIFTY_FUT", fresh_s=fresh_s, now=now)
    return n_ok and b_ok, f"{n_msg}; {b_msg}"


def check_bse_fut(root: Path = HERE, day: str = TARGET_DAY) -> tuple[bool, str]:
    dd = root / "data" / day
    files = [f for f in dd.glob("BSE_FUT_*") if f.suffix in (".tmp", ".parquet")] \
        if dd.exists() else []
    if not files:
        return False, "BSE_FUT: NO file"
    size = files[-1].stat().st_size
    return size > 0, f"BSE_FUT: {size}B"


def check_errors(sh=_sh) -> tuple[bool, str]:
    log = sh(["docker", "logs", "orderflow_recorder", "--since", "8h"])
    bad = [l for l in log.splitlines()
           if any(k in l.lower() for k in ("traceback", "exception", " error"))]
    return len(bad) == 0, f"log errors={len(bad)}" + (f" e.g. {bad[0][:90]}" if bad else "")


def build_message(results: list[tuple[str, bool, str]]) -> str:
    failed = [(n, d) for n, ok, d in results if not ok]
    if not failed:
        det = next((d for n, _, d in results if n == "resolve"), "")
        return f"✅ BSE DAY-1 ALL GREEN — {det}, ticks flowing"
    n, d = failed[0]
    return (f"🔴 PROBLEM: {n} — {d} — rollback: OPS_NOTES pre-bse block "
            f"(+{len(failed) - 1} more fail)" if len(failed) > 1 else
            f"🔴 PROBLEM: {n} — {d} — rollback: OPS_NOTES pre-bse block")


def run(test_mode: bool = False) -> str:
    if test_mode:                                   # tonight's end-to-end pipe proof
        ok, det = check_containers()
        nxt = "next connect 09:05" if ok else det
        return f"🌙 TEST / pre-market: {'containers Up, ' + nxt if ok else '🔴 ' + det}"
    results = [("containers", *check_containers()),
               ("resolve", *check_resolve_log()),
               ("ticks", *check_ticks()),
               ("bse_fut", *check_bse_fut()),
               ("log_errors", *check_errors())]
    return build_message(results)


def main(argv: list[str]) -> int:
    test_mode = "--test" in argv
    # load ORDERFLOW_TELEGRAM_* from .env (cron has no docker-compose env injection)
    import os
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    msg = run(test_mode=test_mode)
    print(msg)
    sys.path.insert(0, str(HERE))
    from alerts.config import load_alerts_config
    from alerts.transport import TelegramTransport
    sent = TelegramTransport(load_alerts_config()).send(msg)
    print(f"telegram sent={sent}")
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

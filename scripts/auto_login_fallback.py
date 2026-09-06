#!/usr/bin/env python3
"""scripts/auto_login_fallback.py — the 08:35 IST second chance at the daily Dhan token.

WHY. auto_login.py runs 03:00 UTC (08:30 IST) and already retries a bad TOTP three times across
slot boundaries — a path that has recovered every Invalid-TOTP it has seen (7, 12, 14, 18 Aug;
the 14th and 18th needed the third attempt). What it does NOT have is a second CHANCE: when all
three attempts fail, the next scheduled mint is tomorrow, and the 09:15 open arrives with no
token. This script is that second chance, 40 minutes before the open.

IT DOES NOT RE-IMPLEMENT THE LOGIN. It decides only WHETHER to run the proven one, then runs it
as a subprocess exactly as cron does. auto_login.py is a live-money credential path and is not
edited here; a fallback that forked its logic would be a second, less-tested minting path.

THE GUARD IS THE WHOLE POINT — a needless re-mint is not free. save_credential() deactivates the
active row and inserts a new one, and with CRED_RELINK_ENABLED=false the strategies keep pointing
at the old id and lean on the executor's runtime fallback. So this runs on exactly one condition:
no ACTIVE Dhan credential was created today. Anything else — including not being able to find out
— means DO NOTHING. Fail-closed here means "do not churn a token that is probably fine", and if
the DB cannot be read then re-minting could not have saved us anyway: auto_login needs the same
DB to store what it mints.

Writes nothing but its own log lines. Never prints a token, a PIN, or a TOTP.
"""

import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path("/home/ubuntu/trading-bridge")
AUTO_LOGIN = ROOT / "scripts" / "auto_login.py"
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env", override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("auto_login_fallback")

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID")


def minted_today() -> bool | None:
    """True / False / None = could not find out. The third answer is a real answer here."""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    except Exception as e:                       # noqa: BLE001
        log.error(f"  ✗ DB unreachable ({type(e).__name__}: {e}) — cannot tell whether a token "
                  f"exists; NOT re-minting (auto_login would need this same DB to save one)")
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT created_at FROM broker_credentials
                WHERE lower(broker_name)='dhan' AND user_id=%s AND is_active=true
                ORDER BY created_at DESC LIMIT 1
            """, (DEFAULT_USER_ID,))
            row = cur.fetchone()
    except Exception as e:                       # noqa: BLE001
        log.error(f"  ✗ credential query failed ({type(e).__name__}: {e}) — NOT re-minting")
        return None
    finally:
        conn.close()

    if not row or not row[0]:
        log.warning("  ⚠️ no ACTIVE Dhan credential row at all")
        return False
    created = row[0]
    created_ist = created.astimezone(IST) if created.tzinfo else created
    today = datetime.now(IST).date()
    ok = created_ist.date() == today
    log.info(f"  {'✓' if ok else '✗'} newest active Dhan credential created "
             f"{created_ist.isoformat()} ({'today' if ok else 'NOT today'})")
    return ok


def auto_login_already_running() -> bool:
    """True if the 08:30 run is somehow still going — never mint concurrently with it.

    The pattern is anchored on 'auto_login.py' precisely so THIS script's own command line
    ('auto_login_fallback.py') cannot match it. Self-matching pgrep has bitten this project
    before; the worst outcome here would be two logins racing to rewrite the same credential row.
    """
    try:
        out = subprocess.run(["pgrep", "-af", r"auto_login\.py"], capture_output=True,
                             text=True, timeout=10).stdout
    except Exception as e:                       # noqa: BLE001
        log.warning(f"  ⚠️ could not check for a running auto_login ({type(e).__name__}) — "
                    f"assuming none")
        return False
    hits = [ln for ln in out.splitlines()
            if re.search(r"auto_login\.py(\s|$)", ln) and "fallback" not in ln]
    if hits:
        log.warning(f"  ⚠️ auto_login.py is STILL RUNNING ({len(hits)} process) — standing down")
    return bool(hits)


def main() -> int:
    log.info("=" * 60)
    log.info(f"🔁 auto-login FALLBACK | {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")

    if not DEFAULT_USER_ID:
        log.error("❌ DEFAULT_USER_ID not set — cannot check credential state; standing down")
        return 1

    have = minted_today()
    if have is True:
        log.info("✅ token already minted today — nothing to do (no re-mint, no churn)")
        log.info("=" * 60)
        return 0
    if have is None:
        log.error("⛔ credential state UNKNOWN — standing down without minting")
        log.info("=" * 60)
        return 1
    if auto_login_already_running():
        log.info("=" * 60)
        return 0

    log.warning("⚠️ NO token minted today — running the 08:30 login path again NOW")
    try:
        r = subprocess.run([sys.executable, str(AUTO_LOGIN)], timeout=600)
        rc = r.returncode
    except Exception as e:                       # noqa: BLE001
        log.error(f"❌ fallback invocation failed ({type(e).__name__}: {e})")
        log.info("=" * 60)
        return 1

    log.info(f"{'✅' if rc == 0 else '❌'} fallback auto_login exited rc={rc}"
             f"{'' if rc == 0 else ' — its own Telegram alert has already fired; MANUAL LOGIN '
                                   'NEEDED BEFORE 09:15'}")
    log.info("=" * 60)
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
TRADETRI Auto-Login v4 — FINAL
==============================
- Dhan: TOTP-based daily auto-login (official API)
- Fyers: refresh-token-based daily renewal (official v3 endpoint)
  Falls back to "needs manual re-auth" message when refresh token expires (~30 days)

Run via cron at 8:30 IST (Mon-Fri):
    30 8 * * 1-5 /usr/bin/python3 /home/ubuntu/trading-bridge/scripts/auto_login.py
"""

import os
import sys
import time
import hashlib
import logging
import requests
import pyotp
import psycopg2
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet


# ============================================================
# CONFIG
# ============================================================

ROOT_ENV = Path("/home/ubuntu/trading-bridge/.env")
BACKEND_ENV = Path("/home/ubuntu/trading-bridge/backend/.env")
load_dotenv(ROOT_ENV)
load_dotenv(BACKEND_ENV, override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("auto_login")

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID")

# Feature flag — gates the new atomic relink path (snapshot active cred ids
# → deactivate → INSERT → repoint strategies.broker_credential_id). When
# false, fall back to the legacy "deactivate-then-INSERT, no relink" flow
# and rely on strategy_executor._load_credential's runtime fallback.
CRED_RELINK_ENABLED = os.getenv("CRED_RELINK_ENABLED", "false").strip().lower() == "true"

_FERNET_KEY = os.getenv("ENCRYPTION_KEY")
if not _FERNET_KEY:
    raise RuntimeError("ENCRYPTION_KEY not found in env (check backend/.env)")
_cipher = Fernet(_FERNET_KEY.encode("utf-8"))


def encrypt(plaintext: str) -> str:
    return _cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    return _cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


# ============================================================
# DHAN AUTO-LOGIN (TOTP-based)
# ============================================================

# Module-level so main()'s Telegram failure-alert can reference the same
# value used inside dhan_login() — no drift if the count is ever changed.
DHAN_MAX_ATTEMPTS = 3
_TELEGRAM_TIMEOUT_SEC = 5  # short — alert is best-effort, never fatal


def _send_failure_alert(message: str) -> None:
    """Best-effort Telegram alert when Dhan auto-login fails after all
    retries. Reads TELEGRAM_BOT_TOKEN + TELEGRAM_ALERT_CHAT_ID from the
    same env source dhan_login() uses (backend/.env via dotenv at module
    import). Missing config → log + no-op. Any send error is swallowed so
    the underlying sys.exit(1) on the auth failure is never masked.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_ALERT_CHAT_ID")
    if not bot_token or not chat_id:
        log.warning(
            "  ⚠️ Telegram alert skipped — "
            "TELEGRAM_BOT_TOKEN or TELEGRAM_ALERT_CHAT_ID missing from env"
        )
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=_TELEGRAM_TIMEOUT_SEC,
        )
        if resp.status_code == 200:
            log.info("  ✓ Telegram failure alert sent")
        else:
            log.warning(
                f"  ⚠️ Telegram alert returned http={resp.status_code}: "
                f"{resp.text[:200]}"
            )
    except Exception as e:
        log.warning(
            f"  ⚠️ Telegram alert send failed (non-fatal): "
            f"{type(e).__name__}: {e}"
        )


def dhan_login() -> dict:
    client_id = os.getenv("DHAN_CLIENT_ID")
    pin = os.getenv("DHAN_PIN")
    totp_secret = os.getenv("DHAN_TOTP_SECRET")

    missing = [k for k, v in {
        "DHAN_CLIENT_ID": client_id,
        "DHAN_PIN": pin,
        "DHAN_TOTP_SECRET": totp_secret,
    }.items() if not v]
    if missing:
        raise ValueError(f"Missing Dhan env vars: {missing}")

    log.info("🔐 Dhan: starting auto-login")

    # DHAN_MAX_ATTEMPTS is module-level so main()'s failure-alert can
    # reference the same value without drift. See header.
    BOUNDARY_GUARD_SEC = 8  # if <8s left in slot, roll into next slot first
    NON_TOTP_SIGNALS = ("too many", "rate limit", "rs-0060", "locked", "blocked")
    last_error: str | None = None

    for attempt in range(1, DHAN_MAX_ATTEMPTS + 1):
        # Proactive slot-boundary avoidance: never mint a TOTP that's about
        # to expire mid-request.
        seconds_left = 30 - (time.time() % 30)
        if seconds_left < BOUNDARY_GUARD_SEC:
            log.info(
                f"  ⏳ TOTP slot edge ({seconds_left:.1f}s left); "
                f"sleeping {seconds_left + 0.5:.1f}s into fresh slot"
            )
            time.sleep(seconds_left + 0.5)

        t_gen = time.time()
        totp = pyotp.TOTP(totp_secret).now()
        slot_pos = int(t_gen) % 30
        log.info(
            f"  ✓ TOTP generated (attempt {attempt}/{DHAN_MAX_ATTEMPTS}, "
            f"slot+{slot_pos}s)"
        )

        try:
            r = requests.post(
                "https://auth.dhan.co/app/generateAccessToken",
                params={"dhanClientId": client_id, "pin": pin, "totp": totp},
                # (connect, read) split — fail fast if Dhan's auth server
                # hangs instead of blocking the whole cron run.
                timeout=(10, 20),
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = (
                f"Dhan auth transport error "
                f"(attempt {attempt}/{DHAN_MAX_ATTEMPTS}, slot+{slot_pos}s): "
                f"{type(e).__name__}: {e}"
            )
            log.error(f"  ✗ {last_error}")
            if attempt == DHAN_MAX_ATTEMPTS:
                break
            log.info("  ⏳ sleeping 31s before retry (transient transport failure)")
            time.sleep(31)
            continue

        r.raise_for_status()
        data = r.json()
        access_token = (
            data.get("accessToken")
            or data.get("access_token")
            or data.get("token")
        )
        if access_token:
            log.info("  ✓ access_token obtained")
            return {
                "access_token": access_token,
                "refresh_token": None,
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=23, minutes=30),
                "client_id": client_id,
                "api_key": client_id,
                "api_secret": pin,
                "totp_secret": totp_secret,
            }

        # No access_token — full telemetry so the NEXT failure tells us
        # *why* (slot-boundary vs Dhan-side reject vs lockout).
        last_error = (
            f"Dhan response missing token "
            f"(attempt {attempt}/{DHAN_MAX_ATTEMPTS}, http={r.status_code}, "
            f"slot+{slot_pos}s): {r.text}"
        )
        log.error(f"  ✗ {last_error}")

        # Retry-eligible iff body says "totp" AND no rate-limit/lockout
        # signal. Rate-limit MUST NOT retry even though its message contains
        # "TOTP" — retrying compounds the lockout on the live account.
        body_lower = r.text.lower()
        is_bad_totp = "totp" in body_lower and not any(
            s in body_lower for s in NON_TOTP_SIGNALS
        )
        if not is_bad_totp:
            log.error(
                "  ⛔ Non-transient failure (rate-limit / credential / other) "
                "— aborting without retry"
            )
            raise RuntimeError(last_error)

        if attempt == DHAN_MAX_ATTEMPTS:
            break

        log.info("  ⏳ sleeping 31s to cross TOTP slot boundary before retry")
        time.sleep(31)

    raise RuntimeError(last_error or "Dhan login failed (no response captured)")


# ============================================================
# FYERS REFRESH-TOKEN RENEWAL (no daily login needed!)
# ============================================================

def fyers_refresh() -> dict:
    """
    Use the saved refresh_token to get a fresh access_token.
    Refresh tokens are valid ~30 days; when they expire, manual re-auth needed.
    """
    log.info("🔐 Fyers: refreshing via refresh_token")

    app_id = os.getenv("FYERS_APP_ID")
    secret_id = os.getenv("FYERS_SECRET_ID")
    pin = os.getenv("FYERS_PIN")

    # Fetch saved refresh_token from DB
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT refresh_token_enc FROM broker_credentials
                WHERE broker_name='FYERS' AND user_id=%s AND is_active=true
                ORDER BY created_at DESC LIMIT 1
            """, (DEFAULT_USER_ID,))
            row = cur.fetchone()
            if not row or not row[0]:
                raise RuntimeError(
                    "No refresh_token in DB. Run manual auth flow:\n"
                    "  python3 scripts/fyers_manual_auth.py"
                )
            refresh_token = decrypt(row[0])
    finally:
        conn.close()
    log.info("  ✓ refresh_token loaded from DB")

    # Call Fyers v3 refresh endpoint
    app_id_hash = hashlib.sha256(f"{app_id}:{secret_id}".encode()).hexdigest()
    r = requests.post(
        "https://api-t1.fyers.in/api/v3/validate-refresh-token",
        json={
            "grant_type": "refresh_token",
            "appIdHash": app_id_hash,
            "refresh_token": refresh_token,
            "pin": pin,
        },
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(
            f"Refresh failed (status {r.status_code}): {r.text}\n"
            "Refresh token may have expired (30 days). "
            "Run manual auth: python3 scripts/fyers_manual_auth.py"
        )

    data = r.json()
    access_token = data.get("access_token")
    new_refresh = data.get("refresh_token") or refresh_token  # keep old if not rotated
    if not access_token:
        raise RuntimeError(f"Refresh response missing token: {r.text}")
    log.info("  ✓ access_token refreshed")

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=23, minutes=30),
        "client_id": os.getenv("FYERS_USER_ID"),
        "api_key": app_id,
        "api_secret": secret_id,
        "totp_secret": os.getenv("FYERS_TOTP_SECRET"),
    }


# ============================================================
# DB SAVE
# ============================================================

def save_credential(broker: str, creds: dict):
    """Atomically deactivate old + insert new encrypted row."""
    enc_client_id = encrypt(creds["client_id"])
    enc_api_key = encrypt(creds["api_key"])
    enc_api_secret = encrypt(creds["api_secret"])
    enc_access_token = encrypt(creds["access_token"])
    enc_refresh_token = encrypt(creds["refresh_token"]) if creds.get("refresh_token") else None
    enc_totp = encrypt(creds["totp_secret"]) if creds.get("totp_secret") else None

    conn = get_db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if CRED_RELINK_ENABLED:
                    # New atomic relink path — snapshot, deactivate, INSERT, repoint
                    cur.execute("""
                        SELECT id FROM broker_credentials
                        WHERE broker_name=%s AND user_id=%s AND is_active=true
                    """, (broker, DEFAULT_USER_ID))
                    old_ids = [row[0] for row in cur.fetchall()]

                    if old_ids:
                        cur.execute("""
                            UPDATE broker_credentials SET is_active=false
                            WHERE id = ANY(%s)
                        """, (old_ids,))
                    deactivated = len(old_ids)

                    cur.execute("""
                        INSERT INTO broker_credentials (
                            id, user_id, broker_name,
                            client_id_enc, api_key_enc, api_secret_enc,
                            access_token_enc, refresh_token_enc, totp_secret_enc,
                            token_expires_at, is_active, created_at
                        ) VALUES (
                            gen_random_uuid(), %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, true, NOW()
                        ) RETURNING id
                    """, (
                        DEFAULT_USER_ID, broker,
                        enc_client_id, enc_api_key, enc_api_secret,
                        enc_access_token, enc_refresh_token, enc_totp,
                        creds["expires_at"],
                    ))
                    new_id = cur.fetchone()[0]

                    relinked = 0
                    if old_ids:
                        cur.execute("""
                            UPDATE strategies SET broker_credential_id=%s
                            WHERE user_id=%s AND broker_credential_id = ANY(%s)
                        """, (new_id, DEFAULT_USER_ID, old_ids))
                        relinked = cur.rowcount

                    log.info(f"  💾 {broker}: deactivated {deactivated} old, "
                             f"relinked {relinked} strategies, new_cred_id={new_id} "
                             f"expires={creds['expires_at'].isoformat()} [relink=ON]")
                else:
                    # Legacy path — kept verbatim for tonight's safe rollout.
                    cur.execute("""
                        UPDATE broker_credentials SET is_active=false
                        WHERE broker_name=%s AND user_id=%s AND is_active=true
                    """, (broker, DEFAULT_USER_ID))
                    deactivated = cur.rowcount

                    cur.execute("""
                        INSERT INTO broker_credentials (
                            id, user_id, broker_name,
                            client_id_enc, api_key_enc, api_secret_enc,
                            access_token_enc, refresh_token_enc, totp_secret_enc,
                            token_expires_at, is_active, created_at
                        ) VALUES (
                            gen_random_uuid(), %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, true, NOW()
                        )
                    """, (
                        DEFAULT_USER_ID, broker,
                        enc_client_id, enc_api_key, enc_api_secret,
                        enc_access_token, enc_refresh_token, enc_totp,
                        creds["expires_at"],
                    ))
                    log.info(f"  💾 {broker}: deactivated {deactivated} old, "
                             f"new token expires {creds['expires_at'].isoformat()} [relink=OFF]")
    finally:
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    log.info("=" * 60)
    log.info(f"🚀 TRADETRI Auto-Login | {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
    log.info("=" * 60)

    if not DEFAULT_USER_ID:
        log.error("❌ DEFAULT_USER_ID not set in .env")
        sys.exit(1)

    results = {}

    # ---- DHAN ----
    try:
        creds = dhan_login()
        save_credential("dhan", creds)
        results["DHAN"] = "✅ OK"
    except Exception as e:
        log.error(f"❌ DHAN failed: {e}")
        results["DHAN"] = f"❌ {type(e).__name__}: {str(e)[:100]}"
        # Total-failure Telegram alert — fires only when ALL retries are
        # exhausted (RuntimeError out of dhan_login) or save_credential
        # blows up. We need to know BEFORE 09:15 open; log lines alone
        # won't surface in time. Non-fatal — never blocks sys.exit(1).
        _send_failure_alert(
            f"⚠️ TRADETRI: Dhan auto-login FAILED after "
            f"{DHAN_MAX_ATTEMPTS} attempts at "
            f"{datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}. "
            f"Token NOT minted — manual login needed before 09:15 open. "
            f"Last error: {str(e)[:300]}"
        )

    # ---- FYERS (manual daily auth — SEBI Apr 2026 compliance) ----
    # Refresh token API disabled by Fyers per SEBI algo framework.
    # User must manually login daily via TRADETRI dashboard.
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXTRACT(EPOCH FROM (token_expires_at - NOW()))/3600
                FROM broker_credentials
                WHERE broker_name='FYERS' AND user_id=%s AND is_active=true
            """, (DEFAULT_USER_ID,))
            row = cur.fetchone()
        conn.close()
        if row and row[0] and row[0] > 0.5:
            results["FYERS"] = f"⏸️  MANUAL (token valid {row[0]:.1f}h)"
        else:
            results["FYERS"] = "⚠️  MANUAL LOGIN REQUIRED"
    except Exception as e:
        results["FYERS"] = f"⚠️  CHECK FAILED: {e}"

    log.info("=" * 60)
    log.info("📊 SUMMARY:")
    for broker, status in results.items():
        log.info(f"   {broker}: {status}")
    log.info("=" * 60)

    failed = [b for b, s in results.items() if s.startswith("❌")]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

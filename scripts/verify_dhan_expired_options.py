#!/usr/bin/env python3
"""Settle ONE question: does Dhan's Expired Options Data API return real
BSE Ltd ATM option bars at 15-minute granularity?

Runs INSIDE the backend container (it needs ENCRYPTION_KEY + DATABASE_URL).
Read-only: it places no order and writes nothing. It decrypts the active
Dhan credential in-process and NEVER prints it.

    docker cp scripts/verify_dhan_expired_options.py trading_bridge_backend:/tmp/v.py
    docker exec trading_bridge_backend python /tmp/v.py

THE POINT OF THIS SCRIPT IS THE CLASSIFICATION. A run that cannot tell
"token expired" from "authorised but no data" tells us nothing, so every
exit path below names exactly which of these happened:

    exit 0  ROWS RETURNED          -> the finding we want
    exit 3  AUTHORISED, NO DATA    -> ALSO a real finding
    exit 2  TOKEN EXPIRED/INVALID  -> NOT a data finding, retry Monday
    exit 4  PARAMETERS REJECTED    -> names the offending parameter
    exit 5  SUBSCRIPTION REQUIRED  -> Data API not active on the account
    exit 6  RATE LIMITED
    exit 7  UNKNOWN / transport

Dhan mints a day-token; auto_login refreshes it weekdays 03:00 UTC
(08:30 IST). Outside that window the token is dead and only exit 2 is
possible -- which is why the expiry is checked BEFORE spending a call.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

ENDPOINT = "https://api.dhan.co/v2/charts/rollingoption"

# BSE Ltd. securityId is the UNDERLYING's id, not the option contract's --
# that is the whole reason this endpoint sidesteps Dhan's recycling of
# expired option security ids.
DEFAULT_SECURITY_ID = "19585"
DEFAULT_FROM = "2025-06-02"
DEFAULT_TO = "2025-06-05"


def _rule(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def _verdict(tag: str, code: int, *lines: str) -> int:
    print(f"\n{'*' * 68}")
    print(f"*** VERDICT: {tag}")
    for ln in lines:
        print(f"***   {ln}")
    print(f"{'*' * 68}")
    return code


def load_credential() -> tuple[str, str, datetime | None]:
    """Return (access_token, client_id, token_expires_at). Never logs them."""
    import psycopg2
    from cryptography.fernet import Fernet

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT access_token_enc, client_id_enc, token_expires_at, created_at
              FROM broker_credentials
             WHERE is_active AND lower(broker_name) LIKE '%%dhan%%'
             ORDER BY created_at DESC
             LIMIT 1
            """
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit(_verdict("NO ACTIVE DHAN CREDENTIAL", 7,
                                  "broker_credentials has no active dhan row."))
    tok_enc, cid_enc, expires_at, created_at = row

    key = os.environ["ENCRYPTION_KEY"]
    f = Fernet(key.encode() if isinstance(key, str) else key)

    def dec(v):
        if v is None:
            return ""
        return f.decrypt(v.encode() if isinstance(v, str) else v).decode()

    token, client_id = dec(tok_enc), dec(cid_enc)
    print(f"  credential created  : {created_at}")
    print(f"  token_expires_at    : {expires_at}")
    print(f"  access token        : decrypted OK, {len(token)} chars (NOT printed)")
    print(f"  client id           : decrypted OK, {len(client_id)} chars (NOT printed)")
    return token, client_id, expires_at


def post(token: str, client_id: str, body: dict, timeout: int = 45):
    import requests

    r = requests.post(
        ENDPOINT,
        json=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "access-token": token,
            "client-id": client_id,
        },
        timeout=timeout,
    )
    try:
        return r.status_code, r.json(), r.text
    except ValueError:
        return r.status_code, None, r.text


def rows_from(payload) -> list[dict]:
    """Dhan charts return PARALLEL COLUMN ARRAYS; tolerate row-dicts too."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("data"), (list, dict)):
        payload = payload["data"]
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
    cols = {k: v for k, v in payload.items() if isinstance(v, list)}
    if not cols:
        return []
    n = min(len(v) for v in cols.values())
    return [{k: v[i] for k, v in cols.items()} for i in range(n)]


def classify(status: int, payload, text: str, label: str) -> int | None:
    """Return an exit code for a terminal outcome, or None to keep going."""
    blob = (text or "").lower()
    err_code = err_msg = ""
    if isinstance(payload, dict):
        err_code = str(payload.get("errorCode") or "")
        err_msg = str(payload.get("errorMessage") or "")

    # ORDER MATTERS. A subscription gate can arrive as 403, which the token
    # branch would otherwise swallow -- and then we would retry every Monday
    # forever instead of learning we simply have not paid. Specific error
    # codes are therefore matched BEFORE the generic status buckets.
    if "subscri" in blob or err_code in ("DH-906", "DH-907"):
        return _verdict("DATA API SUBSCRIPTION REQUIRED", 5,
                        f"HTTP {status} {err_code} {err_msg}".strip(),
                        "DhanHQ Data API is Rs 499 + tax/month, or free if the",
                        "account executed 25 trades in the last 30 days.",
                        "This is a BILLING gate, not a data finding, and not a",
                        "token problem -- re-running on Monday will not help.")

    if status == 429 or err_code == "DH-904" or ("rate" in blob and "limit" in blob):
        return _verdict("RATE LIMITED -- inconclusive", 6,
                        f"HTTP {status} {err_code} {err_msg}".strip(),
                        "Wait and re-run; this is not a data finding.")

    if status in (401, 403) or err_code == "DH-901" or "invalid or expired" in blob:
        return _verdict(
            "TOKEN EXPIRED OR INVALID -- NOT A DATA FINDING", 2,
            f"HTTP {status} {err_code} {err_msg}".strip(),
            "This says NOTHING about whether the data exists.",
            "Dhan day-tokens die overnight; auto_login mints a fresh one",
            "weekdays at 03:00 UTC / 08:30 IST. Re-run after that.",
        )

    if status == 400:
        print(f"  [{label}] PARAMETER REJECTED -> {err_code} {err_msg}")
        return None  # caller may try another parameter combination

    if status != 200:
        return _verdict("UNKNOWN RESPONSE", 7,
                        f"HTTP {status}", (text or "")[:400])

    rows = rows_from(payload)
    if not rows:
        return _verdict(
            "AUTHORISED BUT NO DATA RETURNED -- THIS *IS* A FINDING", 3,
            f"HTTP 200, empty payload for {label}.",
            "Auth succeeded and parameters were accepted, yet Dhan holds",
            "no rows for this symbol/period. Treat as: BSE Ltd expired",
            "option history NOT available at this granularity.",
            f"raw: {(text or '')[:220]}",
        )

    _rule(f"ROWS RETURNED -- {len(rows)} rows for {label}")
    keys = list(rows[0].keys())
    print(f"  fields: {keys}")
    for i, r in enumerate(rows[:5]):
        ts = r.get("timestamp") or r.get("time") or r.get("start_Time")
        human = ""
        if isinstance(ts, (int, float)):
            try:
                human = datetime.fromtimestamp(ts, timezone.utc).astimezone().isoformat()
            except Exception:
                human = ""
        print(f"    [{i}] {human}  " + "  ".join(f"{k}={r.get(k)}" for k in keys[:9]))
    return _verdict(
        "REAL BSE LTD ATM OPTION BARS AT 15-MINUTE GRANULARITY", 0,
        f"{len(rows)} rows for {label}.",
        "Dhan's Expired Options Data API DOES serve this. The option leg",
        "can be extended from 28 recorded days toward the full history.",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--security-id", default=DEFAULT_SECURITY_ID)
    ap.add_argument("--from-date", default=DEFAULT_FROM)
    ap.add_argument("--to-date", default=DEFAULT_TO)
    ap.add_argument("--interval", type=int, default=15)
    ap.add_argument("--option-type", default="CALL", choices=["CALL", "PUT"])
    ap.add_argument("--strike", default="ATM")
    ap.add_argument("--force", action="store_true",
                    help="call even when token_expires_at is already past")
    args = ap.parse_args()

    _rule("DHAN EXPIRED OPTIONS DATA -- BSE Ltd ATM 15-minute verification")
    print(f"  endpoint : POST {ENDPOINT}")
    print(f"  asking   : BSE Ltd underlying {args.security_id}, OPTSTK, MONTH,")
    print(f"             {args.strike} {args.option_type}, interval {args.interval}m,")
    print(f"             {args.from_date} -> {args.to_date} (toDate non-inclusive)")
    print(f"  now (UTC): {datetime.now(timezone.utc).isoformat()}")

    _rule("1. CREDENTIAL")
    token, client_id, expires_at = load_credential()
    if not token:
        return _verdict("NO TOKEN ON THE ACTIVE CREDENTIAL", 2,
                        "access_token_enc decrypted to an empty string.")

    if expires_at is not None:
        now = datetime.now(expires_at.tzinfo or timezone.utc)
        if expires_at <= now and not args.force:
            age = now - expires_at
            return _verdict(
                "TOKEN ALREADY EXPIRED -- NOT CALLING, NOT A DATA FINDING", 2,
                f"token_expires_at {expires_at} is {age} in the past.",
                "Refusing to spend an API call that can only return DH-901.",
                "Re-run on a WEEKDAY after 08:30 IST, once auto_login has",
                "minted a fresh token. Use --force to call anyway.",
            )
        print(f"  token valid for     : {expires_at - now}")

    body = {
        "exchangeSegment": "NSE_FNO",
        "instrument": "OPTSTK",
        "securityId": str(args.security_id),
        "interval": args.interval,
        "expiryFlag": "MONTH",
        "strike": args.strike,
        "drvOptionType": args.option_type,
        "requiredData": ["open", "high", "low", "close", "volume", "oi", "iv", "spot"],
        "fromDate": args.from_date,
        "toDate": args.to_date,
    }

    # expiryCode is documented as required but its allowed values are not
    # published, so try the plausible ones and report each rejection.
    _rule("2. REQUEST")
    print("  body (expiryCode filled per attempt):")
    print("   ", json.dumps(body, separators=(",", ":")))

    last = None
    for attempt, code in enumerate((0, 1, 2, 3), start=1):
        b = dict(body, expiryCode=code)
        label = f"expiryCode={code}"
        print(f"\n  -- attempt {attempt}: {label}")
        try:
            status, payload, text = post(token, client_id, b)
        except Exception as exc:  # transport
            print(f"     transport error: {type(exc).__name__}: {exc}")
            last = ("transport", str(exc))
            continue
        print(f"     HTTP {status}  {len(text or '')} bytes")
        outcome = classify(status, payload, text, label)
        if outcome is not None:
            return outcome
        last = (status, text)

    return _verdict(
        "ALL expiryCode VALUES REJECTED AS PARAMETERS", 4,
        "Auth was fine; Dhan refused every expiryCode 0-3.",
        f"last response: {str(last[1])[:300] if last else 'n/a'}",
        "Next step: read expiryCode's allowed values from the instrument",
        "list (SEM_EXPIRY_CODE in the Dhan scrip master) and pass it via",
        "--security-id / a code edit, rather than guessing.",
    )


if __name__ == "__main__":
    sys.exit(main())

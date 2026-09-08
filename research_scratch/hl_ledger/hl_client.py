"""hl_client.py — the ONLY network surface for the HL-LEDGER run.

SAFETY, enforced in code rather than by convention:
  * exactly one URL constant, https://api.hyperliquid.xyz/info
  * POST only, unauthenticated, Content-Type: application/json
  * there is no function here that can reach /exchange, and no signing code
  * no credential is read, stored, or accepted anywhere

THROTTLE (CP1.6, declared before any bulk pull):
  * serial only, no concurrency
  * SLEEP_S fixed sleep between every call
  * exponential backoff on HTTP 429, MAX_RETRIES attempts, then give up and log
  * HARD_CAP total requests for the entire run; on reaching it every further
    call raises RequestCapReached, which stops the train rather than raising it
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

INFO_URL = "https://api.hyperliquid.xyz/info"
SLEEP_S = 0.6
MAX_RETRIES = 5
HARD_CAP = 2000

_STATE = {"requests": 0, "non200": []}


class RequestCapReached(RuntimeError):
    pass


def stats() -> dict:
    return {"requests_used": _STATE["requests"], "hard_cap": HARD_CAP,
            "non200": list(_STATE["non200"])}


def post(body: dict, *, tag: str = "") -> tuple[int, object, int]:
    """POST one /info request. Returns (status, parsed_or_text, byte_len)."""
    if _STATE["requests"] >= HARD_CAP:
        raise RequestCapReached(
            f"declared cap {HARD_CAP} reached; stopping per CP1.6 (never raise it)")
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        _STATE["requests"] += 1
        r = requests.post(INFO_URL, json=body,
                          headers={"Content-Type": "application/json"}, timeout=30)
        time.sleep(SLEEP_S)
        if r.status_code == 429:
            _STATE["non200"].append({"tag": tag, "status": 429, "attempt": attempt,
                                     "body_type": body.get("type")})
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code != 200:
            _STATE["non200"].append({"tag": tag, "status": r.status_code,
                                     "body_type": body.get("type"),
                                     "text": r.text[:300]})
            return r.status_code, r.text, len(r.content)
        try:
            return r.status_code, r.json(), len(r.content)
        except ValueError:
            return r.status_code, r.text, len(r.content)
    _STATE["non200"].append({"tag": tag, "status": "429-exhausted",
                             "body_type": body.get("type")})
    return 429, None, 0


def save(obj, path: str | Path) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(obj, indent=2)
    p.write_text(txt, encoding="utf-8")
    return len(txt.encode("utf-8"))

"""hl_client.py — the ONLY network surface for the HL-LEDGER run.

SAFETY, enforced in code rather than by convention (AMENDMENT 1):
  * every request URL must have host == hyperliquid.xyz or end with
    ".hyperliquid.xyz"; anything else raises ForbiddenHost
  * any URL whose path contains "exchange" raises ForbiddenPath, on any host
  * read-only verbs only: POST to /info (the documented read API) and GET
  * no credential is read, stored, sent, or accepted anywhere; no signing code

THROTTLE (CP1.6, declared before any bulk pull):
  * serial only, no concurrency
  * SLEEP_S fixed sleep between every call
  * exponential backoff on HTTP 429, MAX_RETRIES attempts, then log and give up
  * HARD_CAP total requests for the entire run, PERSISTED TO DISK so the cap
    holds across separate processes and across a resumed run. On reaching it
    every further call raises RequestCapReached, which stops the train rather
    than raising the cap.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

INFO_URL = "https://api.hyperliquid.xyz/info"
ALLOWED_DOMAIN_SUFFIX = "hyperliquid.xyz"
SLEEP_S = 0.6
MAX_RETRIES = 5
HARD_CAP = 2000

_HERE = Path(__file__).resolve().parent
COUNTER_PATH = _HERE / "receipts" / "request_counter.json"


class RequestCapReached(RuntimeError):
    pass


class ForbiddenHost(RuntimeError):
    pass


class ForbiddenPath(RuntimeError):
    pass


def _assert_allowed(url: str) -> None:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if not (host == ALLOWED_DOMAIN_SUFFIX or host.endswith("." + ALLOWED_DOMAIN_SUFFIX)):
        raise ForbiddenHost(f"host {host!r} is outside {ALLOWED_DOMAIN_SUFFIX}")
    if "exchange" in (p.path or "").lower():
        raise ForbiddenPath(f"path {p.path!r} contains 'exchange' - refused on every host")


def _load() -> dict:
    if COUNTER_PATH.exists():
        try:
            return json.loads(COUNTER_PATH.read_text())
        except ValueError:
            pass
    return {"requests": 0, "non200": []}


def _store(st: dict) -> None:
    COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    COUNTER_PATH.write_text(json.dumps(st, indent=2), encoding="utf-8")


def _bump(tag: str = "") -> int:
    st = _load()
    if st["requests"] >= HARD_CAP:
        raise RequestCapReached(
            f"declared cap {HARD_CAP} reached (used {st['requests']}); "
            "stopping per CP1.6 - never raise it")
    st["requests"] += 1
    _store(st)
    return st["requests"]


def _log_non200(entry: dict) -> None:
    st = _load()
    st["non200"].append(entry)
    _store(st)


def stats() -> dict:
    st = _load()
    return {"requests_used": st["requests"], "hard_cap": HARD_CAP,
            "remaining": HARD_CAP - st["requests"], "non200_count": len(st["non200"]),
            "non200": st["non200"]}


def backfill(n: int) -> int:
    """One-time reconciliation of requests spent before the counter was persisted."""
    st = _load()
    st["requests"] = max(st["requests"], n)
    st.setdefault("backfilled_to", n)
    _store(st)
    return st["requests"]


def post(body: dict, *, tag: str = "", url: str = INFO_URL):
    """POST one read-only /info request. Returns (status, parsed_or_text, byte_len)."""
    _assert_allowed(url)
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        _bump(tag)
        r = requests.post(url, json=body,
                          headers={"Content-Type": "application/json"}, timeout=30)
        time.sleep(SLEEP_S)
        if r.status_code == 429:
            _log_non200({"tag": tag, "status": 429, "attempt": attempt,
                         "body_type": body.get("type")})
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code != 200:
            _log_non200({"tag": tag, "status": r.status_code,
                         "body_type": body.get("type"), "text": r.text[:300]})
            return r.status_code, r.text, len(r.content)
        try:
            return r.status_code, r.json(), len(r.content)
        except ValueError:
            return r.status_code, r.text, len(r.content)
    _log_non200({"tag": tag, "status": "429-exhausted", "body_type": body.get("type")})
    return 429, None, 0


def get(url: str, *, tag: str = ""):
    """GET one read-only first-party URL. Returns (status, parsed_or_text, byte_len)."""
    _assert_allowed(url)
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        _bump(tag)
        r = requests.get(url, timeout=30)
        time.sleep(SLEEP_S)
        if r.status_code == 429:
            _log_non200({"tag": tag, "status": 429, "attempt": attempt, "url": url})
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code != 200:
            _log_non200({"tag": tag, "status": r.status_code, "url": url,
                         "text": r.text[:300]})
            return r.status_code, r.text, len(r.content)
        try:
            return r.status_code, r.json(), len(r.content)
        except ValueError:
            return r.status_code, r.text, len(r.content)
    _log_non200({"tag": tag, "status": "429-exhausted", "url": url})
    return 429, None, 0


def save(obj, path: str | Path) -> int:
    p = Path(path)
    if not p.is_absolute():
        p = _HERE / p
    p.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(obj, indent=2)
    p.write_text(txt, encoding="utf-8")
    return len(txt.encode("utf-8"))

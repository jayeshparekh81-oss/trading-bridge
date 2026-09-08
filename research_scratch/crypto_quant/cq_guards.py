"""cq_guards.py — every hard boundary for the crypto quant lab, enforced in code.

Part D of BLUEPRINT_v3 (head 1e7ac830, sha256 7a67d68f...):
  * network: Binance PUBLIC market data only, GET, unauthenticated
      - allowed hosts: data.binance.vision, api.binance.com
      - refused: any other host, any signed/account/order path, any api key
  * disk: a declared raw-download ceiling, enforced before every write
  * requests: a declared cap, PERSISTED to disk so it survives processes
  * A3: sealed out-of-sample split, quarantined in code, single-use

Nothing here can place an order. There is no signing code and no credential
path anywhere in this module or the programme.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

HERE = Path(__file__).resolve().parent
STATE = HERE / "receipts"

ALLOWED_HOSTS = {"data.binance.vision", "api.binance.com"}

# Any path fragment that would mean account access, signing, or trading.
FORBIDDEN_PATH_TOKENS = (
    "order", "account", "userdata", "listenkey", "withdraw", "transfer",
    "position", "leverage", "margin", "apikey", "signature",
)
FORBIDDEN_QUERY_TOKENS = ("signature", "apikey", "api_key", "timestamp&recvwindow")

DISK_CEILING_BYTES = 20 * 1024**3          # founder decision 1: 20 GiB hard stop
FREE_FLOOR_FRACTION = 0.10                 # never take free space below 10 pct
REQUEST_CAP = 4000
SLEEP_S = 0.25
MAX_RETRIES = 5


class ForbiddenHost(RuntimeError):
    pass


class ForbiddenPath(RuntimeError):
    pass


class RequestCapReached(RuntimeError):
    pass


class DiskCeilingReached(RuntimeError):
    pass


class SealedDataAccess(RuntimeError):
    """A3: raised when a discovery-stage process reaches for the sealed set."""


# ─────────────────────────────────────────────────────────── network guard
def assert_allowed(url: str) -> None:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ForbiddenHost(f"host {host!r} is not in {sorted(ALLOWED_HOSTS)}")
    if p.scheme != "https":
        raise ForbiddenHost(f"scheme {p.scheme!r} refused; https only")
    low = (p.path or "").lower()
    for tok in FORBIDDEN_PATH_TOKENS:
        if tok in low:
            raise ForbiddenPath(f"path {p.path!r} contains {tok!r} - refused on every host")
    q = (p.query or "").lower()
    for tok in FORBIDDEN_QUERY_TOKENS:
        if tok in q:
            raise ForbiddenPath(f"query contains {tok!r} - this run is unauthenticated only")


# ─────────────────────────────────────────────────── persisted request cap
def _counter_path() -> Path:
    STATE.mkdir(parents=True, exist_ok=True)
    return STATE / "request_counter.json"


def _load() -> dict:
    p = _counter_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except ValueError:
            pass
    return {"requests": 0, "bytes_downloaded": 0, "non200": []}


def _store(st: dict) -> None:
    _counter_path().write_text(json.dumps(st, indent=2), encoding="utf-8")


def stats() -> dict:
    st = _load()
    return {"requests_used": st["requests"], "request_cap": REQUEST_CAP,
            "requests_remaining": REQUEST_CAP - st["requests"],
            "bytes_downloaded": st["bytes_downloaded"],
            "disk_ceiling_bytes": DISK_CEILING_BYTES,
            "bytes_remaining": DISK_CEILING_BYTES - st["bytes_downloaded"],
            "non200": st["non200"]}


def free_bytes(path: str | Path = "/") -> tuple[int, int]:
    import shutil
    u = shutil.disk_usage(str(path))
    return u.free, u.total


def assert_disk_ok(incoming: int, path: str | Path = "/") -> None:
    st = _load()
    if st["bytes_downloaded"] + incoming > DISK_CEILING_BYTES:
        raise DiskCeilingReached(
            f"declared ceiling {DISK_CEILING_BYTES/1024**3:.2f} GiB would be exceeded "
            f"(used {st['bytes_downloaded']/1024**3:.2f} GiB, incoming "
            f"{incoming/1024**3:.4f} GiB). STOP - do not raise it, do not delete.")
    free, total = free_bytes(path)
    if (free - incoming) / total < FREE_FLOOR_FRACTION:
        raise DiskCeilingReached(
            f"pull would take free space to {(free-incoming)/total*100:.2f} pct, "
            f"below the {FREE_FLOOR_FRACTION*100:.0f} pct floor. STOP - do not delete.")


def _bump(n_bytes: int = 0) -> None:
    st = _load()
    if st["requests"] >= REQUEST_CAP:
        raise RequestCapReached(f"declared cap {REQUEST_CAP} reached; STOP, never raise it")
    st["requests"] += 1
    st["bytes_downloaded"] += n_bytes
    _store(st)


def note_non200(entry: dict) -> None:
    st = _load()
    st["non200"].append(entry)
    _store(st)


def get(url: str, *, tag: str = "", stream_to: Path | None = None,
        expected_bytes: int | None = None):
    """The ONLY network call in this programme. GET, unauthenticated, read-only."""
    assert_allowed(url)
    if expected_bytes:
        assert_disk_ok(expected_bytes)
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        _bump(0)
        r = requests.get(url, timeout=60, stream=stream_to is not None)
        if r.status_code == 429:
            note_non200({"tag": tag, "status": 429, "attempt": attempt, "url": url})
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code != 200:
            note_non200({"tag": tag, "status": r.status_code, "url": url})
            time.sleep(SLEEP_S)
            return r.status_code, None, 0
        if stream_to is not None:
            stream_to.parent.mkdir(parents=True, exist_ok=True)
            n = 0
            with open(stream_to, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    n += len(chunk)
                    assert_disk_ok(0)
                    fh.write(chunk)
            st = _load()
            st["bytes_downloaded"] += n
            _store(st)
            time.sleep(SLEEP_S)
            return 200, stream_to, n
        body = r.content
        st = _load()
        st["bytes_downloaded"] += len(body)
        _store(st)
        time.sleep(SLEEP_S)
        try:
            return 200, r.json(), len(body)
        except ValueError:
            return 200, body, len(body)
    note_non200({"tag": tag, "status": "429-exhausted", "url": url})
    return 429, None, 0


# ───────────────────────────────────────────── A3 sealed split, single use
class SealedSplit:
    """Chronological split. The confirmation half RAISES for discovery-stage code.

    Unlock is single-use per BLUEPRINT_v3 [v3-3]: one unlock confirms one
    pre-registered batch, then the seal is spent and recorded as such.
    """

    def __init__(self, split_ts_ms: int, ledger: Path | None = None):
        self.split_ts_ms = int(split_ts_ms)
        self.ledger = Path(ledger) if ledger else (STATE / "seal_ledger.json")
        self._unlocked = False

    def _state(self) -> dict:
        if self.ledger.exists():
            return json.loads(self.ledger.read_text())
        return {"unlocks": []}

    def spent(self) -> bool:
        return any(u["split_ts_ms"] == self.split_ts_ms for u in self._state()["unlocks"])

    def discovery(self, rows, ts_key="time"):
        return [r for r in rows if int(r[ts_key]) < self.split_ts_ms]

    def confirmation(self, rows, ts_key="time"):
        if not self._unlocked:
            raise SealedDataAccess(
                "A3 VIOLATION: discovery-stage code requested the sealed confirmation "
                "set. Unlock it explicitly, once, with a pre-registered batch.")
        return [r for r in rows if int(r[ts_key]) >= self.split_ts_ms]

    def unlock(self, batch_id: str, prereg_sha256: str):
        if self.spent():
            raise SealedDataAccess(
                f"A3 [v3-3] VIOLATION: this seal (split {self.split_ts_ms}) is SPENT. "
                "Cut a new seal from data that did not exist at the previous unlock.")
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        st = self._state()
        st["unlocks"].append({"split_ts_ms": self.split_ts_ms, "batch_id": batch_id,
                              "prereg_sha256": prereg_sha256,
                              "unlocked_at": int(time.time() * 1000)})
        self.ledger.write_text(json.dumps(st, indent=2), encoding="utf-8")
        self._unlocked = True
        return self

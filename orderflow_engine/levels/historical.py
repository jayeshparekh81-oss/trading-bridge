"""Minimal VENDORED Dhan v2 historical OHLCV client (Module R4).

Adapts the approach of the backend's dhan_historical.py WITHOUT importing it (that
client is async + coupled to app.core/app.schemas/redis/per-user; orderflow_engine
stays self-contained). Mirrors the same Dhan v2 REST contract but is sync,
stdlib-only (urllib — same idiom as recorder.scrip_master), and ADDS the ≤90-day
(intraday) / ≤5-year (daily) pagination the backend deferred. Scope is deliberately
narrow: fetch + paginate + atomic parquet cache. The backend/pine_replica code is
neither imported nor modified.

  POST https://api.dhan.co/v2/charts/{historical|intraday}
  headers: client-id, access-token, Content-Type: application/json
  payload: {securityId, exchangeSegment, instrument, fromDate, toDate, [interval]}
  response (columnar): {open:[], high:[], low:[], close:[], volume:[], timestamp:[epoch_s]}
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from levels.ohlcv import Bar, bars_to_table, load_ohlcv
from recorder.writer import _atomic_write_table

log = logging.getLogger("levels.historical")

DHAN_BASE = "https://api.dhan.co/v2"
INTRADAY_PATH = "/charts/intraday"
HISTORICAL_PATH = "/charts/historical"
MAX_INTRADAY_DAYS = 90
MAX_DAILY_DAYS = 365 * 5
# intraday interval codes; '1d' routes to the daily endpoint (no interval field)
_TF_INTERVAL = {"1m": "1", "5m": "5", "15m": "15", "1h": "60"}


def _default_post(url: str, payload: dict, headers: dict, timeout: float = 30.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_columnar(body: dict) -> list[Bar]:
    o = body.get("open") or []
    h = body.get("high") or []
    lo = body.get("low") or []
    c = body.get("close") or []
    v = body.get("volume") or []
    ts = body.get("timestamp") or body.get("start_Time") or []
    n = min(len(o), len(h), len(lo), len(c), len(v), len(ts))
    out: list[Bar] = []
    for i in range(n):
        try:
            out.append(Bar(int(ts[i]), float(o[i]), float(h[i]), float(lo[i]),
                           float(c[i]), int(v[i])))
        except (TypeError, ValueError):
            continue   # skip a bad row, keep the rest
    return out


def _chunks(frm: date, to: date, max_days: int) -> list[tuple[date, date]]:
    out = []
    cur = frm
    while cur <= to:
        end = min(cur + timedelta(days=max_days - 1), to)
        out.append((cur, end))
        cur = end + timedelta(days=1)
    return out


class DhanHistorical:
    def __init__(self, client_id: str, access_token: str, cache_dir: Path,
                 *, http_post: Callable = _default_post, base_url: str = DHAN_BASE):
        self.client_id = client_id
        self.access_token = access_token
        self.cache_dir = Path(cache_dir)
        self._post = http_post
        self.base_url = base_url

    @classmethod
    def from_creds(cls, cache_dir: Path, **kw) -> "DhanHistorical":
        """Build using the recorder's read-only daily-minted token."""
        from recorder.creds import get_dhan_credentials
        creds = get_dhan_credentials(broker_name="dhan")
        return cls(creds.client_id, creds.access_token, cache_dir, **kw)

    def _headers(self) -> dict:
        return {"client-id": self.client_id, "access-token": self.access_token,
                "Content-Type": "application/json", "Accept": "application/json"}

    def _cache_path(self, security_id, segment, tf, frm: date, to: date) -> Path:
        return self.cache_dir / f"{segment}_{security_id}_{tf}_{frm}_{to}.parquet"

    def fetch(self, security_id, exchange_segment: str, instrument: str,
              frm: date, to: date, timeframe: str = "1d", *, use_cache: bool = True) -> list[Bar]:
        daily = timeframe == "1d"
        path = HISTORICAL_PATH if daily else INTRADAY_PATH
        max_days = MAX_DAILY_DAYS if daily else MAX_INTRADAY_DAYS
        fmt = "%Y-%m-%d" if daily else "%Y-%m-%d %H:%M:%S"

        merged: dict[int, Bar] = {}
        for cfrm, cto in _chunks(frm, to, max_days):
            cache = self._cache_path(security_id, exchange_segment, timeframe, cfrm, cto)
            if use_cache and cache.exists():
                bars = load_ohlcv(cache)
            else:
                payload = {
                    "securityId": str(security_id),
                    "exchangeSegment": exchange_segment,
                    "instrument": instrument,
                    "fromDate": cfrm.strftime(fmt),
                    "toDate": cto.strftime(fmt),
                }
                if not daily:
                    payload["interval"] = _TF_INTERVAL.get(timeframe, "1")
                body = self._post(self.base_url + path, payload, self._headers())
                bars = parse_columnar(body)
                if use_cache and bars:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    _atomic_write_table(bars_to_table(bars), cache)
            for b in bars:
                merged[b.ts] = b          # dedupe overlapping chunk boundaries by ts
        return [merged[k] for k in sorted(merged)]

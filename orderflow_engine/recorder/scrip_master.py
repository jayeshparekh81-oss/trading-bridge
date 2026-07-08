"""Standalone Dhan scrip-master fetch + instrument resolution.

Does NOT import the main app's scrip-master warm-loop (isolation rule). Fetches
the compact CSV, caches it locally with a dated filename, refreshes at startup
if stale (>20h), and resolves:
  * NIFTY current/nearest-non-expired FUTIDX future -> security_id
  * verifies index security_ids (NIFTY 50 = 13, INDIA VIX = 21) against the CSV

CSV columns (compact api-scrip-master.csv):
  SEM_EXM_EXCH_ID, SEM_SEGMENT, SEM_SMST_SECURITY_ID, SEM_INSTRUMENT_NAME,
  SEM_EXPIRY_CODE, SEM_TRADING_SYMBOL, SEM_LOT_UNITS, SEM_CUSTOM_SYMBOL,
  SEM_EXPIRY_DATE, SEM_STRIKE_PRICE, SEM_OPTION_TYPE, SEM_TICK_SIZE,
  SEM_EXPIRY_FLAG, SEM_EXCH_INSTRUMENT_TYPE, SEM_SERIES, SM_SYMBOL_NAME
"""

from __future__ import annotations

import csv
import logging
import os
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("recorder.scrip_master")

DEFAULT_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
DEFAULT_STALE_HOURS = 20

# Index (IDX_I) instruments we record — verified against the live CSV.
KNOWN_INDEX_IDS = {13: "NIFTY 50", 21: "INDIA VIX"}


@dataclass
class Instrument:
    symbol: str            # short name used in filenames, e.g. "NIFTY_FUT"
    exchange_segment: str  # feed segment string, e.g. "NSE_FNO" / "IDX_I"
    security_id: int
    trading_symbol: str = ""
    expiry: Optional[date] = None
    lot_size: Optional[float] = None
    kind: str = ""         # "spot" | "future" | "option" | "" — for gap/verify policy


@dataclass
class OptionChain:
    underlying: str
    expiry: date
    segment: str           # feed segment for these options (NSE_FNO / BSE_FNO)
    strikes: dict          # strike(float) -> {"CE": security_id, "PE": security_id}


# --------------------------------------------------------------------------
# Parsing (pure)
# --------------------------------------------------------------------------
def load_rows(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def _parse_expiry(raw: str) -> Optional[date]:
    raw = (raw or "").strip()
    if not raw:
        return None
    # e.g. "2026-08-25 14:30:00" or "2026-08-25"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.split(".")[0], fmt).date()
        except ValueError:
            continue
    return None


def _underlying(trading_symbol: str) -> str:
    # "NIFTY-Aug2026-FUT" -> "NIFTY"; "BANKNIFTY-Aug2026-FUT" -> "BANKNIFTY"
    return (trading_symbol or "").split("-", 1)[0].strip().upper()


def resolve_future(rows: list[dict], ref_date: date, *, underlying: str = "NIFTY",
                   instrument_name: str = "FUTIDX", exch: str = "NSE",
                   segment: str = "NSE_FNO", symbol: str = "NIFTY_FUT") -> Instrument:
    """Nearest non-expired future for ``underlying``.

    "Non-expired" = expiry date >= ``ref_date`` (in exchange TZ). On expiry day
    the still-valid contract is selected; the day after, it rolls to the next.
    Raises LookupError if none found.
    """
    candidates = []
    for r in rows:
        if r.get("SEM_EXM_EXCH_ID", "").strip() != exch:
            continue
        if r.get("SEM_INSTRUMENT_NAME", "").strip() != instrument_name:
            continue
        if _underlying(r.get("SEM_TRADING_SYMBOL", "")) != underlying.upper():
            continue
        exp = _parse_expiry(r.get("SEM_EXPIRY_DATE", ""))
        if exp is None or exp < ref_date:
            continue
        candidates.append((exp, r))
    if not candidates:
        raise LookupError(
            f"no non-expired {underlying} {instrument_name} future on/after {ref_date}"
        )
    candidates.sort(key=lambda t: t[0])
    exp, row = candidates[0]
    try:
        lot = float(row.get("SEM_LOT_UNITS") or 0) or None
    except ValueError:
        lot = None
    return Instrument(
        symbol=symbol, exchange_segment=segment,
        security_id=int(row["SEM_SMST_SECURITY_ID"]),
        trading_symbol=row.get("SEM_TRADING_SYMBOL", "").strip(),
        expiry=exp, lot_size=lot, kind="future",
    )


def resolve_option_chain(rows: list[dict], ref_date: date, *, underlying: str,
                         exch: str = "NSE", segment: str = "NSE_FNO",
                         instrument_name: str = "OPTIDX") -> OptionChain:
    """Build the option chain for the nearest non-expired expiry of ``underlying``.

    "Nearest non-expired" = smallest expiry date >= ``ref_date`` — this is the
    current weekly for indices that have weeklies (NIFTY, SENSEX) and the current
    monthly for the rest (BANKNIFTY/FINNIFTY/MIDCPNIFTY). Raises LookupError if
    no options are found. Rolls the day AFTER expiry, consistent with futures.
    """
    underlying = underlying.upper()
    # 1) find the nearest expiry
    expiries = set()
    for r in rows:
        if r.get("SEM_INSTRUMENT_NAME", "").strip() != instrument_name:
            continue
        if r.get("SEM_EXM_EXCH_ID", "").strip() != exch:
            continue
        if _underlying(r.get("SEM_TRADING_SYMBOL", "")) != underlying:
            continue
        exp = _parse_expiry(r.get("SEM_EXPIRY_DATE", ""))
        if exp is not None and exp >= ref_date:
            expiries.add(exp)
    if not expiries:
        raise LookupError(f"no non-expired {underlying} options on/after {ref_date}")
    expiry = min(expiries)

    # 2) collect strikes for that expiry
    strikes: dict = {}
    for r in rows:
        if r.get("SEM_INSTRUMENT_NAME", "").strip() != instrument_name:
            continue
        if r.get("SEM_EXM_EXCH_ID", "").strip() != exch:
            continue
        if _underlying(r.get("SEM_TRADING_SYMBOL", "")) != underlying:
            continue
        if _parse_expiry(r.get("SEM_EXPIRY_DATE", "")) != expiry:
            continue
        opt_type = (r.get("SEM_OPTION_TYPE", "") or "").strip().upper()
        if opt_type not in ("CE", "PE"):
            continue
        try:
            strike = float(r.get("SEM_STRIKE_PRICE") or 0)
            sid = int(r["SEM_SMST_SECURITY_ID"])
        except (ValueError, KeyError):
            continue
        strikes.setdefault(strike, {})[opt_type] = sid
    if not strikes:
        raise LookupError(f"no strikes for {underlying} expiry {expiry}")
    return OptionChain(underlying=underlying, expiry=expiry, segment=segment, strikes=strikes)


def select_atm_window(chain: OptionChain, spot: float, window: int = 5) -> list[Instrument]:
    """Return the CE/PE instruments for ATM +/- ``window`` strikes around ``spot``.

    ATM = the listed strike nearest ``spot`` (uses the actual listed strike grid,
    so no hard-coded strike intervals). At most (2*window+1)*2 instruments.
    """
    strike_grid = sorted(chain.strikes)
    if not strike_grid:
        return []
    nearest_i = min(range(len(strike_grid)), key=lambda i: abs(strike_grid[i] - spot))
    lo = max(0, nearest_i - window)
    hi = min(len(strike_grid), nearest_i + window + 1)
    out: list[Instrument] = []
    for strike in strike_grid[lo:hi]:
        label = int(strike) if float(strike).is_integer() else strike
        for opt_type in ("CE", "PE"):
            sid = chain.strikes[strike].get(opt_type)
            if sid is None:
                continue
            out.append(Instrument(
                symbol=f"{chain.underlying}_{opt_type}_{label}",
                exchange_segment=chain.segment, security_id=sid,
                expiry=chain.expiry, kind="option",
                trading_symbol=f"{chain.underlying}-{chain.expiry}-{label}-{opt_type}",
            ))
    return out


def verify_index(rows: list[dict], security_id: int, symbol: str,
                 segment: str = "IDX_I", exch: str = "NSE") -> Instrument:
    """Confirm an index security_id exists in the CSV (SEM_SEGMENT == 'I').

    Raises LookupError if the id isn't present as an NSE index, guarding against
    a silently-changed id feeding garbage into the recorder.
    """
    for r in rows:
        if r.get("SEM_SEGMENT", "").strip() != "I":
            continue
        if r.get("SEM_EXM_EXCH_ID", "").strip() != exch:
            continue
        try:
            sid = int(r["SEM_SMST_SECURITY_ID"])
        except (KeyError, ValueError):
            continue
        if sid == security_id:
            log.info("verified index %s = %s (%s)", security_id,
                     r.get("SEM_TRADING_SYMBOL"), r.get("SEM_CUSTOM_SYMBOL"))
            return Instrument(symbol=symbol, exchange_segment=segment,
                              security_id=security_id, kind="spot",
                              trading_symbol=r.get("SEM_TRADING_SYMBOL", "").strip())
    raise LookupError(f"index security_id {security_id} ({symbol}) not found in scrip master")


# --------------------------------------------------------------------------
# Fetch + cache (IO)
# --------------------------------------------------------------------------
def _download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
    os.replace(str(tmp), str(dest))


def fetch_scrip_master(cache_dir: str | Path, *, url: str = DEFAULT_URL,
                       today: Optional[date] = None, now_ts: Optional[float] = None,
                       stale_hours: int = DEFAULT_STALE_HOURS,
                       downloader: Callable[[str, Path], None] = _download) -> Path:
    """Return a path to a fresh-enough scrip master CSV, downloading if needed.

    Caches as ``api-scrip-master-{YYYY-MM-DD}.csv``. Reuses the newest cached
    file if its age < ``stale_hours``; otherwise downloads today's file.
    ``today``/``now_ts``/``downloader`` are injectable for tests.
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    if today is None:
        today = datetime.now().date()  # noqa: DTZ005 - caller injects in prod
    if now_ts is None:
        now_ts = datetime.now().timestamp()  # noqa: DTZ005

    existing = sorted(cache.glob("api-scrip-master-*.csv"))
    if existing:
        newest = existing[-1]
        age_h = (now_ts - newest.stat().st_mtime) / 3600.0
        if age_h < stale_hours:
            log.info("using cached scrip master %s (age %.1fh)", newest.name, age_h)
            return newest
        log.info("cached scrip master %s stale (age %.1fh), refreshing", newest.name, age_h)

    dest = cache / f"api-scrip-master-{today.isoformat()}.csv"
    log.info("downloading scrip master -> %s", dest.name)
    downloader(url, dest)
    return dest

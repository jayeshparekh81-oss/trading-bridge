#!/usr/bin/env python3
"""One-time Dhan v2 historical data acquisition for the trend-engine backtest.

Pulls N years (default 5) of **5-minute OHLCV** for NIFTY and BANKNIFTY
**index spot** from Dhan's v2 Historical Data API and writes
``data/<SYMBOL>.parquet`` (+ a ``.csv`` copy) for the backtest harness to read.

Standalone mini-module — no strategy logic, no app imports, no order paths.
It only reads market data. Depends on ``requests`` + ``pandas`` (+ ``pyarrow``
for parquet).

────────────────────────────────────────────────────────────────────────────
CREDENTIALS (environment ONLY — never hardcoded, never committed)
────────────────────────────────────────────────────────────────────────────
    DHAN_ACCESS_TOKEN   Dhan v2 access token   (sent as the ``access-token`` header)
    DHAN_CLIENT_ID      Dhan client id         (sent as the ``client-id``  header)

A gitignored ``.env`` next to this file is auto-loaded if present. Real
environment variables always win over ``.env`` values. See ``.env.example``.

────────────────────────────────────────────────────────────────────────────
DHAN v2 API FACTS baked in here
────────────────────────────────────────────────────────────────────────────
  * Endpoint:  POST https://api.dhan.co/v2/charts/intraday
  * Body:      securityId, exchangeSegment, instrument, interval, fromDate, toDate
  * Auth:      client-id + access-token headers
  * fromDate/toDate for /charts/intraday use IST wall-clock "YYYY-MM-DD HH:MM:SS"
  * Intraday history is available up to ~5 years, but only ~90 days per request
    → we paginate in 90-day windows and stitch + de-duplicate.
  * Rate limit ~5 req/sec per token → we sleep between calls and back off on 429.
  * Response is column-oriented:
        {"open":[...], "high":[...], "low":[...], "close":[...],
         "volume":[...], "timestamp":[<epoch_seconds>, ...]}
    (sometimes nested under a "data" key). ``timestamp`` is epoch seconds
    interpreted as UTC; we convert to tz-aware Asia/Kolkata.

securityId / exchangeSegment are NOT hardcoded: they are resolved at runtime
from Dhan's public scrip-master CSV and printed for eyeball verification. (The
numeric ids are reused across segments — e.g. id 13 is NIFTY in the INDEX
segment but ABB in the NSE equity segment — so we filter to INDEX rows first,
then match the trading symbol.)

────────────────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────────────────
    python trend_engine/fetch_dhan_history.py                 # NIFTY + BANKNIFTY, 5y
    python trend_engine/fetch_dhan_history.py --years 5
    python trend_engine/fetch_dhan_history.py --symbols NIFTY
    python trend_engine/fetch_dhan_history.py --out some/dir
    python trend_engine/fetch_dhan_history.py --dry-run       # resolve + plan, NO auth

Exit codes:  0 ok · 2 missing creds · 3 resolution failure · 1 fetch/other failure
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

# ── Constants ──────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "data"

DHAN_BASE_URL = "https://api.dhan.co/v2"
INTRADAY_PATH = "/charts/intraday"
SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"

IST = ZoneInfo("Asia/Kolkata")
INTERVAL = "5"  # 5-minute candles
WINDOW_DAYS = 90  # Dhan intraday cap per request

# Gentle-on-the-API pacing (Dhan allows ~5 req/s; we stay well under).
SLEEP_BETWEEN_WINDOWS_S = 0.7
HTTP_TIMEOUT_S = 30.0
MAX_RETRIES = 5
RETRY_BASE_DELAY_S = 1.0
RETRY_MAX_DELAY_S = 30.0

# Regular NSE session (IST). Index bars are stamped at bar-open; the last
# 5-min bar of the day opens at 15:25 and covers 15:25–15:30.
SESSION_OPEN = (9, 15)
SESSION_LAST_BAR_OPEN = (15, 25)
BARS_PER_FULL_SESSION = 75  # 09:15 … 15:25 inclusive, 5-min grid

# Symbols we know how to fetch. exchange_segment/instrument are Dhan's INDEX
# conventions; known_security_id is only a cross-check against the resolver.
TARGETS: dict[str, dict] = {
    "NIFTY": {
        "match_symbols": {"NIFTY", "NIFTY 50", "NIFTY50"},
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "known_security_id": "13",
    },
    "BANKNIFTY": {
        "match_symbols": {"BANKNIFTY", "NIFTY BANK", "BANK NIFTY", "NIFTYBANK"},
        "exchange_segment": "IDX_I",
        "instrument": "INDEX",
        "known_security_id": "25",
    },
}


@dataclass
class Resolved:
    symbol: str
    security_id: str
    exchange_segment: str
    instrument: str
    source_trading_symbol: str
    source_name: str


# ── .env loader (zero-dependency; real env wins) ───────────────────────────


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:  # real env takes precedence
            os.environ[key] = val


# ── Scrip-master resolution ────────────────────────────────────────────────


def _download_scrip_master() -> pd.DataFrame:
    print(f"[resolve] downloading scrip master: {SCRIP_MASTER_URL}")
    resp = requests.get(SCRIP_MASTER_URL, timeout=HTTP_TIMEOUT_S)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), low_memory=False)
    print(f"[resolve] scrip master rows: {len(df):,}")
    return df


def resolve_symbols(symbols: list[str], df: pd.DataFrame | None = None) -> dict[str, Resolved]:
    """Resolve securityId + exchangeSegment for each requested index symbol.

    Filters to INDEX rows first (numeric ids are reused across segments),
    then matches the trading symbol / display name. Prints every resolution
    so it can be verified by eye, and warns on any drift from the known id.
    """
    if df is None:
        df = _download_scrip_master()

    # Normalise the columns we depend on; be tolerant of missing ones.
    def col(name: str) -> pd.Series:
        return df[name].astype(str).str.strip() if name in df.columns else pd.Series([""] * len(df))

    instrument_type = col("SEM_EXCH_INSTRUMENT_TYPE").str.upper()
    instrument_name = col("SEM_INSTRUMENT_NAME").str.upper()
    is_index = (instrument_type == "INDEX") | (instrument_name == "INDEX")
    idx_df = df[is_index].copy()
    print(f"[resolve] INDEX rows in scrip master: {len(idx_df):,}")

    trading_sym = col("SEM_TRADING_SYMBOL").str.upper()[is_index]
    sm_name = col("SM_SYMBOL_NAME").str.upper()[is_index]
    custom = col("SEM_CUSTOM_SYMBOL").str.upper()[is_index]
    sec_id = col("SEM_SMST_SECURITY_ID")[is_index]
    exch = col("SEM_EXM_EXCH_ID").str.upper()[is_index]

    out: dict[str, Resolved] = {}
    for symbol in symbols:
        spec = TARGETS[symbol]
        wanted = {w.upper() for w in spec["match_symbols"]}
        mask = trading_sym.isin(wanted) | sm_name.isin(wanted) | custom.isin(wanted)
        # Prefer NSE listing when the same index is present on multiple exchanges.
        candidates = idx_df[mask]
        if len(candidates) > 1 and (exch[mask] == "NSE").any():
            candidates = candidates[exch[mask] == "NSE"]

        if candidates.empty:
            raise LookupError(
                f"could not resolve {symbol} in scrip-master INDEX rows "
                f"(looked for trading/display symbol in {sorted(wanted)})"
            )

        row = candidates.iloc[0]
        resolved = Resolved(
            symbol=symbol,
            security_id=str(row["SEM_SMST_SECURITY_ID"]).strip(),
            exchange_segment=spec["exchange_segment"],
            instrument=spec["instrument"],
            source_trading_symbol=str(row.get("SEM_TRADING_SYMBOL", "")).strip(),
            source_name=str(row.get("SM_SYMBOL_NAME", "")).strip(),
        )
        out[symbol] = resolved

        known = spec["known_security_id"]
        flag = "OK" if resolved.security_id == known else f"⚠ DRIFT (expected {known})"
        print(
            f"[resolve] {symbol:<10} securityId={resolved.security_id:<6} "
            f"segment={resolved.exchange_segment:<6} instrument={resolved.instrument:<6} "
            f"tradingSymbol={resolved.source_trading_symbol!r} name={resolved.source_name!r}  [{flag}]"
        )
        if len(candidates) > 1:
            print(
                f"[resolve]   note: {len(candidates)} INDEX rows matched {symbol}; "
                f"picked securityId={resolved.security_id}. Verify above."
            )
    return out


# ── Fetch ──────────────────────────────────────────────────────────────────


def _windows(start: datetime, end: datetime):
    cursor = start
    while cursor < end:
        win_end = min(cursor + timedelta(days=WINDOW_DAYS), end)
        yield cursor, win_end
        cursor = win_end


def _parse_response(body: dict) -> pd.DataFrame:
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    ts = data.get("timestamp") or data.get("start_Time") or []
    if not ts:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(pd.Series(ts, dtype="int64"), unit="s", utc=True),
            "open": data.get("open", []),
            "high": data.get("high", []),
            "low": data.get("low", []),
            "close": data.get("close", []),
            "volume": data.get("volume", []),
        }
    )
    frame["timestamp"] = frame["timestamp"].dt.tz_convert(IST)
    return frame


def _post_window(
    session: requests.Session,
    headers: dict,
    r: Resolved,
    win_start: datetime,
    win_end: datetime,
) -> pd.DataFrame:
    payload = {
        "securityId": r.security_id,
        "exchangeSegment": r.exchange_segment,
        "instrument": r.instrument,
        "interval": INTERVAL,
        "fromDate": win_start.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "toDate": win_end.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
    }
    url = DHAN_BASE_URL + INTRADAY_PATH
    delay = RETRY_BASE_DELAY_S
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.post(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT_S)
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            print(f"           transport error ({exc.__class__.__name__}); retry {attempt}/{MAX_RETRIES} in {delay:.1f}s")
            time.sleep(delay)
            delay = min(delay * 2, RETRY_MAX_DELAY_S)
            continue

        if resp.status_code == 200:
            return _parse_response(resp.json())

        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Dhan {resp.status_code} after {MAX_RETRIES} tries: {resp.text[:300]}")
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if (retry_after or "").replace(".", "", 1).isdigit() else delay
            print(f"           HTTP {resp.status_code}; retry {attempt}/{MAX_RETRIES} in {wait:.1f}s")
            time.sleep(wait)
            delay = min(delay * 2, RETRY_MAX_DELAY_S)
            continue

        if resp.status_code == 401:
            raise RuntimeError("Dhan 401 Unauthorized — check DHAN_ACCESS_TOKEN / DHAN_CLIENT_ID.")
        # 400 etc. — most often an empty/holiday window; surface + treat as empty.
        raise RuntimeError(f"Dhan HTTP {resp.status_code}: {resp.text[:300]}")

    return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])


def fetch_5min(
    session: requests.Session,
    headers: dict,
    r: Resolved,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    wins = list(_windows(start, end))
    for i, (ws, we) in enumerate(wins, 1):
        label = f"{ws.astimezone(IST).date()} → {we.astimezone(IST).date()}"
        try:
            frame = _post_window(session, headers, r, ws, we)
        except RuntimeError as exc:
            # Empty/holiday window or a per-window failure: log + continue.
            print(f"  [{r.symbol}] window {i}/{len(wins)} {label}: skipped ({exc})")
            time.sleep(SLEEP_BETWEEN_WINDOWS_S)
            continue
        print(f"  [{r.symbol}] window {i}/{len(wins)} {label}: {len(frame):,} bars")
        if not frame.empty:
            frames.append(frame)
        time.sleep(SLEEP_BETWEEN_WINDOWS_S)

    if not frames:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    out = pd.concat(frames, ignore_index=True)
    out = (
        out.drop_duplicates(subset="timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    for c in ("open", "high", "low", "close"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype("int64")
    return out


# ── Validation / quality report ────────────────────────────────────────────


def quality_report(symbol: str, df: pd.DataFrame) -> None:
    print(f"\n──── DATA QUALITY · {symbol} ────")
    if df.empty:
        print("  NO BARS RETURNED — nothing to report.")
        return

    ts = df["timestamp"]
    print(f"  total bars      : {len(df):,}")
    print(f"  date range      : {ts.min()}  →  {ts.max()}")

    dates = ts.dt.normalize().dt.date
    trading_days = sorted(set(dates))
    print(f"  trading days    : {len(trading_days)}")

    # Weekdays in range with zero bars — candidate missing sessions. NOT
    # authoritative (exchange holidays land here too), so it's labelled as such.
    all_weekdays = pd.bdate_range(ts.min().normalize(), ts.max().normalize()).date
    present = set(trading_days)
    missing_weekdays = [d for d in all_weekdays if d not in present]
    print(f"  weekdays w/o data (holidays + gaps): {len(missing_weekdays)}")
    if missing_weekdays:
        preview = ", ".join(str(d) for d in missing_weekdays[:8])
        more = "" if len(missing_weekdays) <= 8 else f"  (+{len(missing_weekdays) - 8} more)"
        print(f"      e.g. {preview}{more}")

    # Intraday gaps > 1 bar within the 09:15–15:30 session.
    open_t = pd.Timestamp("09:15").time()
    last_open_t = pd.Timestamp(f"{SESSION_LAST_BAR_OPEN[0]}:{SESSION_LAST_BAR_OPEN[1]}").time()
    in_session = df[(ts.dt.time >= open_t) & (ts.dt.time <= last_open_t)]
    gap_events = 0
    missing_bars = 0
    short_sessions = 0
    for _, day_df in in_session.groupby(in_session["timestamp"].dt.date):
        day_ts = day_df["timestamp"].sort_values()
        deltas = day_ts.diff().dropna()
        big = deltas[deltas > pd.Timedelta(minutes=5)]
        gap_events += len(big)
        missing_bars += int(sum((d / pd.Timedelta(minutes=5)) - 1 for d in big))
        if len(day_ts) < BARS_PER_FULL_SESSION:
            short_sessions += 1
    print(f"  intraday gaps   : {gap_events} gap(s) > 1 bar, ~{missing_bars} missing bar(s) inside session")
    print(f"  short sessions  : {short_sessions} day(s) with < {BARS_PER_FULL_SESSION} in-session bars")

    zero_vol = int((df["volume"] == 0).sum())
    print(f"  zero-volume bars: {zero_vol:,} of {len(df):,}")
    if zero_vol == len(df):
        print("      (index spot has no traded volume — all-zero is expected here, not a hole)")


# ── Save ───────────────────────────────────────────────────────────────────


def save(symbol: str, df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pq = out_dir / f"{symbol}.parquet"
    csv = out_dir / f"{symbol}.csv"
    df.to_parquet(pq, index=False)
    df.to_csv(csv, index=False)
    print(f"  saved: {pq}  ({pq.stat().st_size / 1_048_576:.2f} MiB)")
    print(f"  saved: {csv} ({csv.stat().st_size / 1_048_576:.2f} MiB)")


# ── main ───────────────────────────────────────────────────────────────────


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch 5-min OHLCV for NIFTY/BANKNIFTY from Dhan v2.")
    p.add_argument("--symbols", nargs="+", default=list(TARGETS), choices=list(TARGETS))
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--dry-run", action="store_true", help="resolve symbols + print window plan, no auth/fetch")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    load_dotenv(HERE / ".env")

    end = datetime.now(UTC).replace(microsecond=0)
    start = end - timedelta(days=365 * args.years)
    print(f"range: {start.astimezone(IST).date()} → {end.astimezone(IST).date()}  ({args.years}y)  interval={INTERVAL}m")
    print(f"symbols: {', '.join(args.symbols)}   out: {args.out}\n")

    try:
        resolved = resolve_symbols(args.symbols)
    except Exception as exc:  # noqa: BLE001 — top-level guard, message is enough
        print(f"ERROR: symbol resolution failed: {exc}", file=sys.stderr)
        return 3

    if args.dry_run:
        print("\n[dry-run] window plan per symbol:")
        wins = list(_windows(start, end))
        for ws, we in wins:
            print(f"    {ws.astimezone(IST).date()} → {we.astimezone(IST).date()}")
        print(f"[dry-run] {len(wins)} windows/symbol · {len(args.symbols)} symbol(s) "
              f"= {len(wins) * len(args.symbols)} requests. No auth used, nothing fetched.")
        return 0

    client_id = os.environ.get("DHAN_CLIENT_ID")
    access_token = os.environ.get("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token:
        print(
            "ERROR: DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN must be set (env or "
            "trend_engine/.env). See trend_engine/.env.example.",
            file=sys.stderr,
        )
        return 2

    headers = {
        "client-id": client_id,
        "access-token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    rc = 0
    with requests.Session() as session:
        for symbol in args.symbols:
            r = resolved[symbol]
            print(f"\n==== FETCH {symbol} (securityId={r.security_id}) ====")
            try:
                df = fetch_5min(session, headers, r, start, end)
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR: fetch failed for {symbol}: {exc}", file=sys.stderr)
                rc = 1
                continue
            quality_report(symbol, df)
            if not df.empty:
                save(symbol, df, args.out)
            else:
                print(f"  {symbol}: empty — not written.")
                rc = 1

    print("\nDone.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

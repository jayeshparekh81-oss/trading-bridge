# trend_engine — historical data acquisition

One-time script to build the 5-minute OHLCV dataset the trend-engine backtest
harness reads. Pulls 5 years of **NIFTY** and **BANKNIFTY** index spot from
Dhan's v2 Historical Data API and writes `data/<SYMBOL>.parquet` (+ `.csv`).

Standalone: `requests` + `pandas` + `pyarrow`. No app imports, no strategy
logic, no order paths — read-only market data.

## Run

```bash
# 1. put creds in a gitignored .env (never committed)
cp trend_engine/.env.example trend_engine/.env
#    edit trend_engine/.env → DHAN_ACCESS_TOKEN, DHAN_CLIENT_ID

# 2. verify resolution + window plan without touching auth
python trend_engine/fetch_dhan_history.py --dry-run

# 3. real pull (5 years, both symbols)
python trend_engine/fetch_dhan_history.py
```

Options: `--symbols NIFTY`, `--years 5`, `--out some/dir`.

## What it does

- Resolves `securityId` / `exchangeSegment` from Dhan's public scrip-master CSV
  (does **not** hardcode numeric ids — they're reused across segments) and
  prints each resolution for eyeball verification, cross-checked against the
  known ids (NIFTY=13, BANKNIFTY=25 in the `IDX_I` INDEX segment).
- Paginates in 90-day windows (Dhan's per-request cap), sleeps between calls,
  backs off on 429/5xx, stitches + de-duplicates into one tz-aware
  (Asia/Kolkata) DataFrame.
- Prints a per-symbol data-quality report: total bars, date range, weekdays
  with no data, intraday gaps > 1 bar in-session, zero-volume bars.

> Index spot legitimately has **zero traded volume** — an all-zero `volume`
> column is expected, not a data hole.

## Output

`data/` holds the generated `.parquet` / `.csv` artifacts and is gitignored —
regenerate by re-running the script; don't commit the datasets.

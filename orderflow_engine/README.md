# orderflow_engine — Module R0: Tick Recorder

A **pure, read-only** data recorder for the Dhan v2 Live Market Feed. It connects
in **FULL packet mode**, parses the binary stream itself, and archives every tick
to daily parquet files with gap auditing and a session verification report.

> **It places NO orders and has NO trading capability.** It holds a Data-API
> token only, used read-only. It is fully isolated under `orderflow_engine/` and
> imports **nothing** from the main trading app.

---

## Why

An orderflow strategy can only be backtested by replaying our own recorded ticks.
Every market day not recorded is lost forever — so R0 is built to be boringly
reliable: atomic writes, part-file fallback, auto-reconnect, gap detection, and a
PASS/FAIL verification at end of day.

## What it records (config-driven in `config.yaml`)

Full capture from day 1 across **all major F&O indices** — 121 instruments:

| per index (×5) | how resolved |
|---|---|
| spot index | verified security_id vs scrip master |
| near-month future | nearest non-expired FUTIDX, daily lookup |
| ATM±5 CE/PE option strikes | nearest weekly/monthly expiry; ATM anchored to the **live spot at open** |

Indices: **NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY** (NSE) and **SENSEX** (BSE),
plus **INDIA VIX**. Verified security_ids: NIFTY=13, BANKNIFTY=25, FINNIFTY=27,
MIDCPNIFTY=442, SENSEX=51 (BSE), VIX=21.

- **Expiries:** NIFTY & SENSEX have **weekly** options; BANKNIFTY/FINNIFTY/
  MIDCPNIFTY are **monthly**. The recorder auto-picks the nearest non-expired
  expiry per index and rolls the day after expiry.
- **ATM±5:** strikes are the 11 listed strikes nearest the spot (strike interval
  auto-detected from the grid, not hard-coded) × CE/PE = 22 options per index.
  ATM is **fixed at open and held all day** (no intraday re-centering) for clean,
  continuous per-strike series. We record **ATM±5 only, never full chains**.
- **ATM discovery is feed-first:** core instruments (spots + futures) stream from
  connect; once the live spot ticks at open, options are ATM-anchored and
  subscribed dynamically. The Option-Chain REST API is **not** used, so its
  1-req/3s limit does not apply.

Plus **NSE cash equities (record-only)** — top NIFTY heavyweights (HDFCBANK,
RELIANCE, ICICIBANK, INFY, TCS, ITC, LT, BHARTIARTL), extra BANKNIFTY
constituents (SBIN, AXISBANK, KOTAKBANK), and three strategy stocks (BSE,
ANGELONE, CDSL). security_ids are resolved from the scrip master **by symbol**
(never hard-coded, so they can't drift), overlaps across lists are auto-deduped,
and each is `gap_check: false` by default (recorded fully but not gating
PASS/FAIL). **Recording a symbol's feed is pure observation** — the recorder
places no orders and touches no strategy code, so it does not interact with any
live strategy running on these symbols elsewhere.

Total universe ≈ **135 instruments** (25 core + up to 110 option strikes) — well
within Dhan's 5×5000 limit; a startup capacity guard refuses to run if a config
change ever exceeds `connections.max × 5000`.

Add/adjust instruments or the ATM window by editing `config.yaml` — **no code
change** required.

## Connections (Dhan limit: 5)

121 instruments fit comfortably (limit is 5000/connection), but they are spread
across `connections.max` websocket connections (default 3, hard-capped at 5) for
resilience — one connection dropping doesn't stop the others. Core instruments
stream on connection 0; each index's option group is assigned to a connection.
Each subscribe message respects the 100-instruments/message cap.

## Gap detection & verification scope

The >3s gap watchdog and session PASS/FAIL apply to **core** instruments only
(spots + futures, which trade continuously). Options and VIX are fully recorded
but **gap-exempt** — a deep-OTM strike can legitimately be silent for minutes, so
counting that as a gap would make verification meaningless. A `manifest.json`
written per day records each instrument's `kind`/`gap_check` so `verify_session`
knows which files must have data (core) and which may be empty (options/VIX).

## Storage layout

```
data/{YYYY-MM-DD}/
    NIFTY_SPOT_13.parquet          # one row per persisted packet (schema in recorder/schema.py)
    NIFTY_FUT_<secid>.parquet
    NIFTY_CE_24800_<secid>.parquet # ATM±5 option strikes, per index
    NIFTY_PE_24800_<secid>.parquet
    ... (BANKNIFTY / FINNIFTY / MIDCPNIFTY / SENSEX spot+fut+options, INDIA_VIX)
    events.parquet                 # reconnects, gaps, subscribe acks, status, disconnects
    manifest.json                  # instruments recorded + kind/gap_check (drives verification)
    report.json                    # verification result
```

Writes are **atomic** (`*.tmp` → `os.replace`, with `fsync`). The daily file only
appears on a clean flush/close, so a mid-flush kill never leaves a corrupt final
file. On any writer error an instrument falls back to self-contained
`parts/<name>/part-NNNN.parquet` files, consolidated at end of day.

## Durable S3 backup (server-independent)

After each session is consolidated + verified (15:40 IST), the whole
`data/{date}/` folder is uploaded to a config-driven S3 bucket, so recorded data
survives an EC2/AZ failure. **The local copy is always kept** — S3 is the durable
source of truth, not a replacement.

- Per-file upload with exponential-backoff **retry** and **upload-success
  verification** (HEAD each object, compare size; mismatch → retry).
- A `backup.json` audit (per-file keys, bytes, retries, success) is written
  locally and uploaded as the final marker.
- A backup failure is logged + recorded in `backup.json` and **never stops the
  recorder** — recording always takes priority.
- Configure under `s3_backup:` in `config.yaml` (`enabled`, `bucket`, `prefix`,
  `region`, `retries`, `verify`). `enabled: false` by default — flip it on once
  the bucket + AWS credentials are in place.
- Credentials use **boto3's default chain** (EC2 instance role preferred, or
  `AWS_*` env vars). No AWS secrets are stored in this repo.
- Re-run a day's backup on demand: `make backup-day DAY=2026-07-09`.

## Credentials — reused, never re-minted

The daily Dhan token is minted by the existing `scripts/auto_login.py` cron
(03:00 UTC) and stored **encrypted in the Postgres `broker_credentials` table**.
This recorder reads the active row and Fernet-decrypts it **read-only**, exactly
as the app does — **no new login/TOTP flow, no new secrets**. It needs, from the
shared repo `.env` files:

- `DATABASE_URL` and `ENCRYPTION_KEY` (from `backend/.env`)
- `DEFAULT_USER_ID` (from root `.env`)

These are injected via `env_file` in `docker-compose.yml`.

---

## Local test run (no Docker)

```bash
cd orderflow_engine
make venv        # create .venv, install pinned deps
make test        # run the unit suite
```

## First-run checklist (Docker)

1. **Confirm DB reachability.** The container must resolve `DATABASE_URL`. Pick
   one option in `docker-compose.yml` (see **Deploy** below) before `up`.
2. `make build`
3. `make up`  → `make logs`. Off-hours you should see a clear idle line:
   `idle (wait); sleeping ...s until next check`.
4. During market hours you should see `resolved NIFTY_FUT -> security_id=…`,
   `SUBSCRIBE 3 instruments`, then packet flow.
5. After 15:40 IST, `data/<today>/report.json` should show `PASS`.

## Tomorrow-morning runbook

```bash
cd orderflow_engine
make up                 # if not already running (restart: unless-stopped keeps it up)
make logs               # watch. At ~09:05 IST: connect; ~09:07: recording

# ~09:15 sanity check — parquet files should be growing:
ls -la data/$(date +%F)/
```

At ~15:40 IST it disconnects, consolidates, and verifies automatically. To verify
on demand:

```bash
make verify                     # today, inside the container
make verify-day DAY=2026-07-09  # a specific day, on the host (needs .venv)
```

`verify_session.py` reports per-instrument packet counts, coverage %, gap
seconds (PASS if 0 gaps > 3s), and NIFTY-future volume monotonicity, with an
overall **PASS/FAIL** banner.

## Deploy — DB reachability (choose one)

The recorder runs as its **own** compose project (`orderflow`), separate from the
main stack. It only needs to reach Postgres read-only:

- **Option 1** — `DATABASE_URL` points to `localhost`/host port → set
  `network_mode: "host"` on the `recorder` service.
- **Option 2** — Postgres is a service on the main app's compose network → attach
  the recorder to that external network (`networks:` block in the compose file).

Both options are stubbed with comments in `docker-compose.yml`.

**For S3 backup**, the container also needs AWS credentials: attach the EC2
instance role to the container (host networking inherits it) or pass `AWS_*` env
vars via `env_file`. Leave `s3_backup.enabled: false` until the bucket + creds
are confirmed.

## Holidays

`holidays.yaml` lists NSE trading holidays to skip. **Verify festival dates
against the official NSE circular** before relying on it — it is safe to
under-list (recorder just connects on a closed day and records nothing) but
dangerous to list a real trading day (a session would be skipped). Weekends are
skipped automatically.

## Isolation guarantees

- Everything lives under `orderflow_engine/`.
- Zero imports from, and zero edits to: `server_final30mar.py`,
  strategy_executor, direct_exit, webhooks, kill_switch, `dhan.py`/`fyers.py`,
  Celery tasks, Alembic migrations, or the main `docker-compose.yml`.
- No order-placement code path exists in this process.

## Module map

| file                     | responsibility                                        |
|--------------------------|-------------------------------------------------------|
| `recorder/parser.py`     | little-endian binary packet parser + frame splitter   |
| `recorder/schema.py`     | pyarrow tick/event schemas                            |
| `recorder/writer.py`     | buffered atomic parquet writer + part-file fallback   |
| `recorder/feed.py`       | websocket client, subscribe, reconnect/backoff        |
| `recorder/watchdog.py`   | per-instrument heartbeat gap detection                |
| `recorder/scrip_master.py`| standalone scrip fetch + expiry/index resolution     |
| `recorder/scheduler.py`  | IST session windows, weekday/holiday gating           |
| `recorder/creds.py`      | read-only DB token load + Fernet decrypt              |
| `recorder/s3_backup.py`  | durable daily S3 upload (retry + verify + audit)      |
| `recorder/main.py`       | daemon orchestration + clean shutdown                 |
| `verify_session.py`      | end-of-day verification report                        |

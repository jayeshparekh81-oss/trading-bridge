# Chart-module patch instructions

This document lists every cross-cutting edit the chart-module work
deferred to `feat/charting-module` could **not** make itself, because
the `feat/charting-module` branch is being developed in parallel with
strategy-engine work in another Claude Code session and edits to shared
files would create merge conflicts.

Apply these patches manually after both branches have been reviewed
and you're ready to land them.

---

## 🟥 Required for the chart module to function

### 1. Register the chart router in `main.py`

Add the import + `include_router` call alongside the existing routers
in `backend/app/main.py`:

```python
# Near the other `from app.api.<router> import router as <name>_router` lines:
from app.api.chart import router as chart_router

# Near the other `app.include_router(...)` calls inside the function
# that wires routers (line ~224 in the current main.py):
app.include_router(chart_router)
```

A single router serves BOTH the HTTP endpoints (`/api/chart/history`,
`/api/chart/ws-token`) and the WebSocket endpoint
(`/ws/chart/{symbol}/{timeframe}`). Only one `include_router` call is
required.

### 2. Confirm `websockets` is available at runtime

The chart module's `dhan_websocket.py` does
`from websockets.asyncio.client import connect as ws_connect`. This
is part of the `websockets>=13.0` package.

**Check first:**

```bash
poetry run python -c "from websockets.asyncio.client import connect; print('OK')"
```

If that succeeds, **no action needed** — `uvicorn[standard]>=0.32.0`
(already pinned in `pyproject.toml`) pulls `websockets` transitively
and current versions ship the `asyncio.client` submodule.

If it fails with `ImportError`:

```bash
poetry add 'websockets>=13.0'
```

Pinning explicitly is also fine as a defensive measure — uvicorn's
pin to websockets may drift in the future and you want a known good
version locked in. Recommended:

```bash
poetry add 'websockets>=13.0,<15.0'
```

### 3. Verify Dhan v2 endpoint shapes before deploy

The chart code was built against Dhan's published v2 spec as of
2026-05-11 but I had no live Dhan access to verify. Sanity-check the
following against the current Dhan swagger / docs before pushing to
prod:

#### 3a. Historical OHLC endpoints — `dhan_historical.py`

Constants under "Endpoint paths" in `backend/app/brokers/dhan_historical.py`:

```python
_DHAN_BASE_URL = "https://api.dhan.co/v2"
_INTRADAY_PATH = "/charts/intraday"     # for 1m, 5m, 15m, 1h
_HISTORICAL_PATH = "/charts/historical" # for 1d (no interval field)
```

And the interval mapping:

```python
_TIMEFRAME_TO_DHAN = {
    Timeframe.ONE_MIN: "1",
    Timeframe.FIVE_MIN: "5",
    Timeframe.FIFTEEN_MIN: "15",
    Timeframe.ONE_HOUR: "60",
    Timeframe.ONE_DAY: "D",
}
```

If Dhan has unified onto a single endpoint or renamed the interval
strings, edit `_INTRADAY_PATH` / `_HISTORICAL_PATH` / `_TIMEFRAME_TO_DHAN`
in `dhan_historical.py` and re-run the unit tests.

Also verify the request payload shape — currently:

```json
{
  "securityId": "11536",
  "exchangeSegment": "NSE_EQ",
  "instrument": "EQUITY",
  "fromDate": "2024-01-01 09:15:00",
  "toDate": "2024-01-01 15:30:00",
  "interval": "5"
}
```

`fromDate` / `toDate` are formatted as IST local time strings (UTC+5:30).
If Dhan now wants ISO-8601 or epoch seconds, update the format strings
in `DhanHistoricalClient.get_historical_ohlc()`.

#### 3b. WebSocket binary protocol — `dhan_websocket.py`

The binary frame layout in `_decode_binary_frame()` matches Dhan v2's
published spec:

- Header (16 bytes): `<BHBI...` — response_code (uint8), message_length
  (uint16 LE), exchange_segment (uint8), security_id (uint32 LE), then
  8 bytes reserved.
- Ticker payload (code 4, 8 bytes): `<fI` — LTP (float32 LE), LTT
  (uint32 LE epoch seconds).
- Quote payload (code 7, 42 bytes): `<fHIfIIIffff` — LTP, LTQ (uint16),
  LTT, ATP, Volume, TotalSellQty, TotalBuyQty, Open, Close, High, Low.

If Dhan has shipped a v3 binary protocol or changed any field width,
update the `struct.unpack_from(...)` calls in `_decode_binary_frame()`
and the constants `_RC_TICKER`, `_RC_QUOTE`, `_RC_DISCONNECT`.

#### 3c. WebSocket URL auth scheme

Currently:

```
wss://api-feed.dhan.co?version=2&token={ACCESS_TOKEN}&clientId={CLIENT_ID}&authType=2
```

`authType=2` corresponds to Dhan v2's TOTP/2FA mode. If your account
uses a different auth flow, edit the URL construction in
`DhanWebSocketAdapter._open_connection()`.

#### 3d. SUBSCRIBE message format

```json
{
  "RequestCode": 17,
  "InstrumentCount": 1,
  "InstrumentList": [{"ExchangeSegment": "NSE_EQ", "SecurityId": "11536"}]
}
```

RequestCode 17 = Quote subscription (default), 15 = Ticker, 16 =
Unsubscribe. Update the constants if Dhan has rotated these.

---

## 🟨 Recommended but not blocking

### 4. Move `DHAN_WS_URL` to typed settings

Currently in `backend/app/brokers/dhan_websocket.py`:

```python
DHAN_WS_URL: str = os.environ.get("DHAN_WS_URL", "wss://api-feed.dhan.co")
```

This was inlined to avoid editing `core/config.py`. After the strategy
branch merges, fold it into `Settings`:

```python
# In backend/app/core/config.py, in the "─── Dhan ───" block:
dhan_ws_url: str = Field(
    default="wss://api-feed.dhan.co",
    description="Dhan v2 market-data WebSocket endpoint for live ticks.",
)
```

Then in `dhan_websocket.py`, replace the env-var lookup with:

```python
from app.core.config import get_settings
DHAN_WS_URL = get_settings().dhan_ws_url
```

### 5. Consolidate typed errors into a shared module

`backend/app/brokers/dhan_historical.py` defines its own
`BrokerAuthError`, `BrokerRateLimitError`, `BrokerUpstreamError`, and
`BrokerInvalidParamsError` rather than importing from
`app.core.exceptions`. Names intentionally mirror the global hierarchy
so consolidation is a mechanical rename.

Recommended target: a new file `backend/app/brokers/errors.py` that
re-exports the shared hierarchy. Then:

```python
# In dhan_historical.py:
from app.brokers.errors import (
    BrokerAuthError,
    BrokerInvalidParamsError,
    BrokerRateLimitError,
    BrokerUpstreamError,
)
```

…and delete the inline class definitions. The chart route in
`api/chart.py` imports from `app.brokers.dhan_historical` today; that
import path stays valid after the consolidation if you re-export the
names from `dhan_historical` too.

### 6. Extract a `SymbolResolver` service

`backend/app/api/chart.py` currently instantiates a transient
`DhanBroker` just to call `get_security_id`. This is the only point
where chart code touches the existing Dhan REST adapter and the
weakest link in the new-files-only isolation.

Recommended: create `backend/app/services/symbol_resolver.py` with one
class that owns the scrip-master cache (shared with the order flow)
and a single `async resolve(symbol, exchange) → (security_id, segment,
instrument)` method. Both `chart.py` and `services/order_service.py`
can depend on it; `DhanBroker` keeps its scrip master internal but is
no longer the public API for symbol resolution.

### 7. Merge `DhanHistoricalClient` into `DhanBroker`

`brokers/dhan_historical.py` duplicates a small amount of HTTP plumbing
(httpx pool setup, auth headers, retry semantics) from
`brokers/dhan.py`. After the strategy branch merges, add a single
`get_historical_ohlc` method to `DhanBroker` reusing its existing
`_call` retry path, then delete `dhan_historical.py` and switch
`api/chart.py` to use `DhanBroker.get_historical_ohlc` directly.

The duplicate-now-merge-later strategy was deliberate: isolation >
DRY when the blast radius matters (parallel branches).

---

## 🟦 Phase 2 enhancements

These are not required for the May 18 launch but are flagged in
inline comments throughout the chart module:

### 8. Server-side downsampling for 3m / 30m timeframes

`Timeframe.THREE_MIN` and `Timeframe.THIRTY_MIN` are present in the
schema but rejected by `DhanHistoricalClient` because Dhan's intraday
endpoint accepts only `{1, 5, 15, 25, 60}`-minute intervals natively.

Phase 2: when a user requests 3m, fetch 1m bars and roll up server-side
into 3-bar groups; for 30m, fetch 15m and roll up into 2-bar groups.

Test cases to write:
- DST transition (skipped hour, doubled hour) — should produce one
  bar per output interval, no duplicates.
- Holiday gap (e.g. weekend) — bars must not span the gap.
- Partial trailing bar (window ends mid-bucket) — emit closed bars
  only, or include a marker.

### 9. Server-side chunking for >90d intraday / >5y daily

`DhanHistoricalClient` currently raises `BrokerInvalidParamsError`
when the date range exceeds Dhan's per-request maximum. Phase 2:
split the range into Dhan-sized chunks, fetch each, splice the
candles, and return the unified list. Watch for duplicate bars at
chunk boundaries.

### 10. Add `aud="ws"` claim to chart WS tokens

`GET /api/chart/ws-token` currently uses `create_session_token` with
the standard claim set (`sub`, `fp`, `iat`, `exp`, `jti`). A future
enhancement should add `aud="ws"` to the JWT payload and have
`validate_session_token` (or a new `validate_ws_token` helper) enforce
the audience claim. This tightens the security model — a stolen
ws-token would not be valid for the regular API surface and vice
versa.

Implementation sketch:
- Extend `create_session_token` to accept an optional `audience:
  str | None` kwarg, set `payload["aud"] = audience` if non-None.
- Add `validate_session_token(... expected_audience: str | None = None)`,
  reject if `claims.get("aud") != expected_audience`.
- Switch `get_chart_ws_token` to pass `audience="ws"`; switch the WS
  handler to pass `expected_audience="ws"`.

### 11. Auto-detect Dhan `instrument` field

`api/chart.py._SEGMENT_TO_INSTRUMENT` is a simplification — F&O symbols
get mapped to `"FUTIDX"` unconditionally. In reality Dhan distinguishes:

- `FUTIDX` — index futures (NIFTY, BANKNIFTY)
- `FUTSTK` — stock futures (RELIANCE-FUT)
- `OPTIDX` — index options
- `OPTSTK` — stock options

Phase 2 should parse the symbol (`NIFTY` vs `RELIANCE`, presence of
strike+CE/PE) and pick the right `instrument`. The historical endpoint
will return 400 today if you ask for a stock-options chart, because
we'd be sending `"FUTIDX"` for what is actually `"OPTSTK"`.

### 12. WebSocket back-pressure

Redis pub/sub is fire-and-forget: a slow WebSocket consumer drops
messages when the Redis server's `client-output-buffer-limit` is hit.
For v1 this is acceptable (chart is best-effort). Phase 2 should
either:

- Switch the live channels to Redis Streams (`XADD` / `XREAD`) so each
  WS consumer has its own cursor, OR
- Add a per-connection asyncio queue in the WS handler with bounded
  size and drop-oldest semantics.

---

## Manual verification checklist before deploy

After applying patches 1–3 above, run:

```bash
cd backend
poetry run pytest tests/test_candle_schemas.py \
                  tests/test_chart_redis.py \
                  tests/test_dhan_historical.py \
                  tests/test_dhan_websocket.py \
                  tests/test_chart_api.py \
                  --cov=app/schemas/candle \
                  --cov=app/services/chart_redis \
                  --cov=app/brokers/dhan_historical \
                  --cov=app/brokers/dhan_websocket \
                  --cov=app/api/chart \
                  --cov-report=term-missing
```

Coverage gate: **96% per module** (non-negotiable per project standard).

Smoke test in dev:

1. `GET /api/chart/ws-token` with a valid session JWT → returns a
   `{token, expires_in: 900}` payload.
2. `GET /api/chart/history?symbol=NIFTY&exchange=NSE&timeframe=5m
   &from=...&to=...` first call → `cached: false`; immediate repeat →
   `cached: true`.
3. Open `ws://localhost:8000/ws/chart/NIFTY/5m?token=<from step 1>`,
   verify heartbeat frames arrive every 15s, then trigger a tick
   publish (via a test script publishing to
   `chart:candles:NIFTY:5m`) and confirm the browser receives the
   envelope.

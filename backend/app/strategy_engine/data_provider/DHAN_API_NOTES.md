# Dhan Historical Data API — Phase A Discovery Notes

Distilled from the official DhanHQ v2 documentation (May 2026) for use
by the Phase B `data_provider` adapter. Sources are listed at the
bottom of this file. Update only when the published API changes.

## Existing in-repo state

- **Adapter file**: `backend/app/brokers/dhan.py` (`DhanBroker` class).
- **Historical method**: **does not exist**. `DhanBroker` exposes order
  placement, positions, kill-switch helpers, and a scrip-master cache
  (`_SCRIP_MASTER`) — no historical-candle path. Phase B must build a
  new client rather than extend the broker.
- **Auth header style**: `access-token: <JWT>` (lowercase, hyphenated).
  The existing client also sends `Content-Type: application/json` and
  `Accept: application/json`.
- **Base URL config**: `settings.dhan_api_base_url` defaults to
  `https://api.dhan.co/v2` (see `app/core/config.py`).
- **Rate-limit handling pattern**: `app/brokers/dhan.py:863-870` —
  `429` responses raise `BrokerRateLimitError` with a parsed
  `Retry-After` header. Phase B will mirror this.
- **Tenacity retry pattern**: existing adapter uses `AsyncRetrying`
  with `stop_after_attempt(3)` and `wait_exponential(multiplier=0.1,
  min=0.1, max=0.4)`. Those tiny waits suit order flow; the data
  provider needs longer backoff because the rate limit is per-second.

## Endpoints

| Purpose | Method | URL |
|---------|--------|-----|
| Daily candles | `POST` | `https://api.dhan.co/v2/charts/historical` |
| Intraday candles | `POST` | `https://api.dhan.co/v2/charts/intraday` |

The Phase B fetcher routes to *daily* when the requested timeframe is
`"1d"`, otherwise to *intraday*.

## Request body

Common fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `securityId` | string | yes | Numeric scrip id (NOT symbol). |
| `exchangeSegment` | enum | yes | See [Enums](#enums). |
| `instrument` | enum | yes | See [Enums](#enums). |
| `expiryCode` | int | no | Derivatives only. |
| `oi` | bool | no | Include open-interest column. |
| `fromDate` | string | yes | Daily: `"YYYY-MM-DD"`. Intraday: `"YYYY-MM-DD HH:MM:SS"`. |
| `toDate` | string | yes | Same format as `fromDate`. **Non-inclusive.** |

Intraday-only:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `interval` | int | yes | One of `1`, `5`, `15`, `25`, `60` (minutes). |

The Phase B request model exposes `Literal["1m","5m","15m","1h","1d"]`
and maps internally:

| Public timeframe | Endpoint | Body field |
|------------------|----------|------------|
| `"1m"` | `/charts/intraday` | `interval=1` |
| `"5m"` | `/charts/intraday` | `interval=5` |
| `"15m"` | `/charts/intraday` | `interval=15` |
| `"1h"` | `/charts/intraday` | `interval=60` |
| `"1d"` | `/charts/historical` | (no `interval`) |

`25m` is supported by Dhan but intentionally not exposed — keeping the
public timeframe enum aligned with what the strategy engine already
documents.

## Response body

```json
{
  "open":          [float, ...],
  "high":          [float, ...],
  "low":           [float, ...],
  "close":         [float, ...],
  "volume":        [int, ...],
  "timestamp":     [int, ...],
  "open_interest": [int, ...]
}
```

- `timestamp` is **Unix epoch seconds**. Timezone is not documented;
  Phase B treats them as UTC and converts to `datetime` with
  `tzinfo=UTC` when constructing each `Candle`.
- All arrays are the same length. Phase B asserts this on parse.
- `open_interest` is omitted unless the request set `oi=true`.

## Error response

```json
{
  "errorType":    "...",
  "errorCode":    "...",
  "errorMessage": "..."
}
```

Phase B treats any non-2xx status as a fetch failure, surfaces
`errorMessage` in the raised exception, and retries only on `429` and
5xx.

## Constraints

| Constraint | Value |
|------------|-------|
| Max date range per intraday request | 90 days |
| Intraday history depth | last 5 years |
| Daily history depth | from instrument inception |
| Supported intraday intervals | `1`, `5`, `15`, `25`, `60` minutes |

The Phase B fetcher rejects intraday requests spanning more than
90 days. Splitting into multiple requests with stitching is a future
enhancement — not part of Phase B.

## Rate limits

Source: [Dhan support article on data API limits](https://dhan.co/support/platforms/dhanhq-api/what-are-the-api-rate-limits-for-dhan/).

| Limit | Value |
|-------|-------|
| Per second | **5 requests** (data APIs, including historical) |
| Per minute / hourly | none beyond the per-second cap |
| Per day | 100 000 requests |

429 fires when the per-second cap is exceeded. The body may include a
`Retry-After` header in seconds — when present, Phase B uses it
directly as the next backoff delay; otherwise it uses an exponential
schedule starting at `INITIAL_BACKOFF_SECONDS = 2` (doubled each
attempt, capped at 3 attempts total).

## Enums

### `exchangeSegment`

| Value | Use |
|-------|-----|
| `IDX_I` | Indices (NIFTY, BANKNIFTY spot quote) |
| `NSE_EQ` | NSE equity cash |
| `NSE_FNO` | NSE F&O (index + stock options/futures) |
| `NSE_CURRENCY` | NSE currency derivatives |
| `BSE_EQ` | BSE equity cash |
| `BSE_FNO` | BSE F&O |
| `BSE_CURRENCY` | BSE currency derivatives |
| `MCX_COMM` | MCX commodities |

### `instrument`

| Value | Description |
|-------|-------------|
| `INDEX` | Index spot (NIFTY, BANKNIFTY, etc.) |
| `EQUITY` | Cash equity |
| `FUTIDX` | Index futures |
| `OPTIDX` | Index options |
| `FUTSTK` | Stock futures |
| `OPTSTK` | Stock options |
| `FUTCOM` | Commodity futures |
| `OPTFUT` | Options on futures |
| `FUTCUR` | Currency futures |
| `OPTCUR` | Currency options |

### `productType` (not used by historical endpoints; here for completeness)

`CNC`, `INTRADAY`, `MARGIN`.

## Symbol → securityId resolution

The historical endpoints key on numeric `securityId`, not symbol
strings. Real production ships a scrip-master CSV that maps every
tradeable symbol — `_SCRIP_MASTER` in `app/brokers/dhan.py` already
handles that for live order flow.

Phase B keeps the data provider self-contained (no broker
dependency, no DB lookup in tests) by:

1. Bundling a small `KNOWN_SYMBOLS` dict in
   `data_provider/constants.py` for the canonical Indian instruments
   the platform supports (NIFTY, BANKNIFTY, FINNIFTY index spot;
   RELIANCE / TCS / INFY equity).
2. Accepting an optional `security_id` / `exchange_segment` /
   `instrument` override on `HistoricalDataRequest` so callers with
   their own scrip-master access can bypass the dict.

Symbols passed as `"NIFTY 50"`, `"Bank Nifty"`, `"  RELIANCE  "` etc.
are normalised by upper-casing, collapsing whitespace, and consulting
a small alias map (`NIFTY 50 → NIFTY`, `BANK NIFTY → BANKNIFTY`).

## Sources

- [Historical Data — DhanHQ v2 (official docs)](https://dhanhq.co/docs/v2/historical-data/)
- [Dhan support — API rate limits](https://dhan.co/support/platforms/dhanhq-api/what-are-the-api-rate-limits-for-dhan/)
- [Dhan support — historical-data timeframes](https://dhan.co/support/platforms/dhanhq-api/what-timeframe-data-is-available-through-dhan-s-historical-data-apis/)
- [DhanHQ v2 introduction (error format, base URL)](https://dhanhq.co/docs/v2/)
- [DhanHQ v2 annexure (enum values)](https://dhanhq.co/docs/v2/annexure/)

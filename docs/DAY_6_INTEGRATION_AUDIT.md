# Day 6 — Real Dhan-Fetch Integration · Pre-task Audit

**Branch**: `feat/backtest-engine-day-6` (cut from `origin/feat/backtest-engine-day-5`)
**Date**: 2026-05-18
**Scope**: Document the contract between `backtest_extension/celery_tasks.py` and `strategy_engine/data_provider` before replacing the synthetic-candle stub.

---

## 1. `fetch_historical_candles` — public contract

**Module**: `app/strategy_engine/data_provider/fetcher.py`
**Re-exported from**: `app.strategy_engine.data_provider` (`__init__.py`)

### Signature

```python
def fetch_historical_candles(
    request: HistoricalDataRequest,
    use_cache: bool = True,
    *,
    access_token: str | None = None,
    base_url: str = DHAN_API_BASE_URL,
    http_post: HttpPost = httpx.post,
    sleep_fn: SleepFn = time.sleep,
    now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> HistoricalDataResponse
```

- All test seams (`access_token`, `http_post`, `sleep_fn`, `now_fn`, `base_url`) are keyword-only — tests can inject mocks without touching module globals or patching `httpx`.
- `use_cache=False` bypasses the on-disk cache (useful in tests; production code uses the default).

### `HistoricalDataRequest` (frozen, `extra="forbid"`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `symbol` | `str` (1-64) | yes | Resolved through `KNOWN_SYMBOLS` (NIFTY, BANKNIFTY, FINNIFTY, RELIANCE, TCS, INFY out of the box). Whitespace-normalised + alias-mapped. |
| `timeframe` | `Literal["1m","5m","15m","1h","1d"]` | yes | Strict literal — string from API must be one of these or pydantic raises. |
| `from_date` | `datetime` | yes | Must be < `to_date`. UTC-aware per `DHAN_API_NOTES.md`. |
| `to_date` | `datetime` | yes | Intraday: `to_date − from_date ≤ 90 days` (model validator). |
| `security_id` | `str \| None` | no | Override for symbols outside `KNOWN_SYMBOLS`. |
| `exchange_segment` | `str \| None` | no | Same. |
| `instrument` | `str \| None` | no | Same. |

### `HistoricalDataResponse` (frozen, `extra="forbid"`)

| Field | Type | Notes |
|---|---|---|
| `candles` | `list[Candle]` | Already sorted ascending by timestamp (parser walks indices 0…n). |
| `request` | `HistoricalDataRequest` | Echo of the request for audit. |
| `fetched_at` | `datetime` | UTC by default. |
| `cache_hit` | `bool` | True when served from disk cache. |
| `quality_warnings` | `list[str]` | Phase-11 messages. **An empty candle stream produces** `["Empty candle stream returned by Dhan."]` and `candles=[]` — it does **not** raise. |

---

## 2. Engine-expected candle format

**Module**: `app/strategy_engine/backtest/normalizer.py`

Engine consumes `list[Candle]` directly via `BacktestInput.candles`. The `Candle` class used by the engine is the **same** `app.strategy_engine.schema.ohlcv.Candle` returned by the data provider. **No conversion needed.**

Normalizer (`normalize_candles`) requires:
1. Non-empty
2. ≥ 2 candles (`MIN_CANDLES_FOR_SIMULATION`)
3. tz-aware timestamps (data provider produces UTC-aware via `datetime.fromtimestamp(ts, tz=UTC)`)
4. No duplicate timestamps
5. Sorted ascending (data provider already returns sorted)

Conditions 3–5 are guaranteed by `parse_candles`. Conditions 1–2 are application-level errors and must be surfaced as `FAILED` with `error_json` in our task.

---

## 3. Required mappings

### 3a. `request_payload` → `HistoricalDataRequest`

`request_payload` in `backtest_runs.request_payload` is written by `api.py:239` as `BacktestEnqueueRequest.model_dump(mode="json", exclude_none=True)`. Therefore the following fields are present:

| `request_payload` key | Source / default | Notes |
|---|---|---|
| `symbol` | `BacktestEnqueueRequest.symbol` (default `"NIFTY"`) | Pass through to `HistoricalDataRequest.symbol`. |
| `timeframe` | `BacktestEnqueueRequest.timeframe` (default `"5m"`) | API stores as plain `str`; provider needs `Literal["1m","5m","15m","1h","1d"]`. Pydantic will raise `ValidationError` on mismatch — desirable, surface as `FAILED`. |
| `start` | `BacktestEnqueueRequest.start` (Optional) | Serialised as ISO 8601 by `mode="json"`. **May be absent** (excluded when None). Default: now − 60 days. |
| `end` | `BacktestEnqueueRequest.end` (Optional) | Same. Default: now. |
| `initial_capital` / `quantity` / `cost_settings` / `ambiguity_mode` | Used by engine path — not by fetcher. |

**Defaulting responsibility**: per `schemas.py:78` docstring (`"final defaulting logic ships Day 6 of the Week 2 sprint"`), Day 6 owns translating absent `start`/`end` into a concrete window (now − 60 days, now).

**ISO string → datetime**: payload values for `start`/`end` are ISO strings (because of `mode="json"`); the new helper must parse them back to tz-aware `datetime` before constructing `HistoricalDataRequest`.

### 3b. `HistoricalDataResponse` → engine candles

```python
response = fetch_historical_candles(request, ...)
candles: list[Candle] = list(response.candles)   # direct pass-through
```

This is the **entirety** of the response-side mapping. The current `_build_synthetic_candles_payload` returns `list[Candle]` — drop-in replacement.

`response.quality_warnings` is informational; **not blocking**. Day 6 surfaces them in structured logs only. Persisting them into the metrics row is out of scope (no schema change).

---

## 4. Known error modes from the provider

| Trigger | Exception | Surfaced as | Notes |
|---|---|---|---|
| Symbol not in `KNOWN_SYMBOLS` and no overrides on request | `ValueError` (from `_resolve_symbol`) | `FAILED` w/ `error_json.type="ValueError"`, message includes the normalised symbol | Maps to "invalid symbol" |
| Invalid timeframe (not in Literal set) | `pydantic.ValidationError` at `HistoricalDataRequest` construction | `FAILED` w/ ValidationError details | Validated at boundary |
| `from_date >= to_date` | `pydantic.ValidationError` (model validator) | `FAILED` | Validated at boundary |
| Intraday request > 90 days | `pydantic.ValidationError` (model validator) | `FAILED` | Dhan constraint |
| HTTP 429 / 5xx with retries exhausted | `DhanFetchError(status_code=429/5xx)` | `FAILED` w/ `fetch_failed: <message>` | **Underlying client already retries up to `MAX_RETRY_ATTEMPTS=3` with `Retry-After` honour + exponential backoff starting at 2 s.** No additional Celery-level retry needed. |
| Network/connection error after retries | `DhanFetchError(original_error=<httpx exc>)` | `FAILED` w/ `fetch_failed` | |
| 4xx non-retryable (auth, invalid securityId, bad request) | `DhanFetchError(status_code=<4xx>, error_code=<dhan>)` | `FAILED` w/ message + status | No retry by design |
| Malformed response (missing column / mismatched lengths) | `DhanFetchError` | `FAILED` w/ `fetch_failed` | |
| Empty candle stream | **No exception** — returns `HistoricalDataResponse(candles=[], quality_warnings=["Empty candle stream..."])` | Application-level check → `FAILED` w/ `no_data_available` | Must be enforced in `_fetch_real_candles` (or just before constructing `BacktestInput` because normalizer would raise `NormalizerError` anyway). |
| 1-candle stream | No exception — returns 1 Candle | `FAILED` via `NormalizerError` (≥2 required) | Caught by existing top-level except → FAILED. |

---

## 5. Discrepancy / flag for founder review

**Spec says**: "Rate limit → backoff + retry once, then FAILED."

**Reality**: `dhan_client.fetch_from_dhan` already implements **3-attempt** retry on 429/5xx with `Retry-After` header support + exponential backoff (`INITIAL_BACKOFF_SECONDS=2`). Adding a second retry layer in the Celery task would double-retry (3 × 2 = 6 attempts worst case), which:

1. Wastes Dhan quota.
2. Extends the Celery task wall time well past sensible limits.
3. Violates the "reuse EXISTING patterns from data_provider for error handling" constraint.

**Proposed interpretation**: Treat "Rate limit retry success" and "Rate limit retry exhaustion" as the **provider-internal** retries. The Celery task just calls the fetcher once; success → SUCCEEDED, `DhanFetchError(status_code=429)` → FAILED with `fetch_failed: rate_limit_exhausted`. Tests use a mocked `http_post` that returns 429 on the first call(s) and 200 later (success) or always 429 (exhaustion).

**If founder wants a Celery-level retry-once on top**, that's a separate change to the task body (and the spec needs to clarify whether it gates on the provider's exhaustion, which is the only signal we can read).

---

## 6. Implementation plan (pending founder approval)

### File 1: `backend/app/backtest_extension/celery_tasks.py`

- **Add** `_fetch_real_candles(payload: dict) -> list[Candle]`:
  - Read `payload["symbol"]`, `payload["timeframe"]`.
  - Read `payload.get("start")` / `payload.get("end")` (ISO strings or absent) — default to `now − 60d` / `now` (UTC-aware).
  - Build `HistoricalDataRequest` — any pydantic ValidationError bubbles up unchanged.
  - Call `fetch_historical_candles(request)` — pass production defaults (real httpx, real time.sleep, real token).
  - Check `response.candles` non-empty → raise dedicated `NoDataError` (small subclass of `RuntimeError`) with message `"no_data_available"` when empty.
  - Log `quality_warnings` count via structured log (do not raise on warnings).
  - Return `list(response.candles)`.
- **Replace** call site at line 245 (`candles = _build_synthetic_candles_payload(payload)`) with `candles = _fetch_real_candles(payload)`.
- **Keep** `_build_synthetic_candles_payload` as deprecated helper for backward compat with Day-4 engine integration tests (do not delete on this branch — separate cleanup PR). Mark with a one-line deprecation comment.
- **Error-handling additions** inside the existing top-level `except Exception` block — none needed structurally; `_build_error_payload` already captures `type` + `message` + `traceback_first_line`. We will, however, **prefix** specific known failure modes for the message so `error_json.message` reads cleanly:
  - `NoDataError` → `"no_data_available"`
  - `DhanFetchError` → `"fetch_failed: <status_code or 'unknown'>: <str(exc)>"`
  - `ValueError` from symbol resolution → `"invalid_symbol: <message>"`
  - `pydantic.ValidationError` from request construction → pydantic's own message (already informative)

### File 2: `backend/tests/backtest_extension/test_day_6_real_fetch.py`

Six+ tests, all using `unittest.mock.patch` on `app.backtest_extension.celery_tasks.fetch_historical_candles` (the symbol imported into the task module) so no Dhan calls fire:

1. **Happy path** — mock returns realistic 250-bar NIFTY 5-minute response → run completes → metrics + trades persisted → `status=SUCCEEDED`.
2. **Empty response** — mock returns `HistoricalDataResponse(candles=[], quality_warnings=[...])` → `FAILED` with `error_json.message="no_data_available"`.
3. **DhanFetchError (non-rate-limit)** — mock raises `DhanFetchError("...", status_code=502)` → `FAILED` with `error_json.message` containing `"fetch_failed"` + `"502"`.
4. **Rate-limit retry success** — mock raises `DhanFetchError(status_code=429)` once then returns a real response on the next call. **Interpretation per Section 5**: this is the provider's internal retry. We will simulate it by mocking `http_post` rather than `fetch_historical_candles` itself, so the real retry path executes. OR, simpler: assert that when fetch_historical_candles returns successfully, the task succeeds (the internal retry is the provider's contract, tested in `tests/strategy_engine/data_provider/`).
5. **Rate-limit retry exhaustion** — mock raises `DhanFetchError(status_code=429)` → task `FAILED` with `"fetch_failed: 429..."`.
6. **Invalid symbol** — mock raises `ValueError("Symbol 'XYZ'... not in the bundled KNOWN_SYMBOLS map.")` → `FAILED` with `error_json.message` containing `"invalid_symbol"`.
7. **(Bonus) Missing start/end defaulting** — payload without `start`/`end` → fetcher receives a request with sane defaults (now-60d, now). Assert via captured `request` argument.

Tests use existing `conftest.py` fixtures for DB setup (`backend/tests/backtest_extension/conftest.py`).

---

## 7. Constraints honoured

- ❌ No edits to `strategy_engine/backtest/*`.
- ❌ No edits to `data_provider/*`.
- ❌ No router registration in `main.py`.
- ✅ Reuse provider's existing retry pattern (don't double-retry).
- ✅ No silent transforms — if provider returns shape X, engine consumes shape X directly (Candle → Candle).

---

## 8. Founder decisions applied

1. **Q1 — Drop Celery-level retry.** Trust provider's internal 3-attempt retry. Test count reduced to **5** (no dedicated rate-limit retry/exhaustion pair — one `fetch_failed` test covers the exhaustion case).
2. **Q2 — Cache-on-failure is a no-op.** Confirmed. Provider only writes cache after a successful fetch; FAILED runs leave the disk cache untouched. No action.
3. **Q3 — Audit Dhan token resolution: DONE (see §9 below).**
4. **Q4 — Keep `_build_synthetic_candles_payload`.** Mark deprecated, test-only docstring + `TODO(day-7-or-later)`.

---

## 9. Dhan access-token resolution — existing patterns audited

### Pattern in production today

Two distinct paths use Dhan tokens; **one** is the correct model for multi-tenant per-user code:

| Caller | Module | Token source | Fits Day-6? |
|---|---|---|---|
| Chart history (`GET /api/chart/history`) | `app/api/chart.py:239` — `_resolve_dhan_credentials(user, db)` | **Per-user `BrokerCredential` row → decrypt `access_token_enc`** | ✅ YES — same shape (per-user, server-side, async-DB-aware) |
| Live order flow | `app/services/order_service.py:210` — `_build_broker_credentials(row, user_id)` | Same per-user `BrokerCredential` row pattern | ✅ YES — same source of truth |
| Legacy strategy-engine preview endpoint | `app/strategy_engine/api/backtest.py:514` | `os.environ.get("DHAN_ACCESS_TOKEN", "")` (global env var) | ❌ NO — single-tenant; not suitable for multi-user backtests |

**Decision**: Day 6 uses the **per-user `BrokerCredential`** pattern — same as `chart.py:_resolve_dhan_credentials` and `order_service._build_broker_credentials`. The Celery task already has `run.user_id`; it opens a DB session and looks up the user's active Dhan credential.

### Resolution helper to add (inside `celery_tasks.py`, NOT a new file)

```python
async def _resolve_dhan_access_token(
    session: AsyncSession, *, user_id: uuid.UUID
) -> str:
    """Return the user's decrypted Dhan access token.

    Mirrors app.api.chart._resolve_dhan_credentials but trimmed to the
    one field the data_provider needs. Raises NoBrokerCredentialError
    when the user has no active Dhan link → caught by the top-level
    except → run lands FAILED with error_json.message='no_broker_credential'.
    """
    stmt = select(BrokerCredential).where(
        BrokerCredential.user_id == user_id,
        BrokerCredential.broker_name == BrokerName.DHAN,
        BrokerCredential.is_active.is_(True),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None or not row.access_token_enc:
        raise NoBrokerCredentialError(
            "no_broker_credential: Dhan link missing or token wiped."
        )
    return decrypt_credential(row.access_token_enc)
```

Plus a small exception class `NoBrokerCredentialError(RuntimeError)` so tests can match it precisely.

### Call-site shape

```python
async with sessionmaker() as session:
    token = await _resolve_dhan_access_token(session, user_id=user_id)
# token captured outside the session because fetch_historical_candles is sync
candles = _fetch_real_candles(payload, access_token=token)
```

`_fetch_real_candles` becomes `(payload: dict, *, access_token: str) -> list[Candle]` and passes `access_token` through to `fetch_historical_candles(...)`.

### Why not the env-var pattern?

- Legacy preview endpoint is single-tenant; the global `DHAN_ACCESS_TOKEN` env var was a stopgap for the era before per-user broker linking shipped.
- Production users hold individual Dhan API tokens — using one env-var would cross-bill all users to one Dhan account (and break under per-second rate-limits).
- The token is short-lived (Dhan rotates daily); `cred_relink_service.py` already handles the refresh path through `BrokerCredential`.

---

## 10. Pre-code safety check — `data_provider` vs `live_orders` isolation

| Check | Result |
|---|---|
| `data_provider/*` imports from `app.brokers` | ❌ none |
| `data_provider/*` imports from `app.strategy_engine.live_orders` | ❌ none |
| `data_provider/*` imports from `app.services.order_service` | ❌ none |
| `live_orders/order_router.py` imports `data_provider` | ❌ none |
| `services/order_service.py` imports `data_provider` | ❌ none |
| `brokers/dhan.py` imports `data_provider` | ❌ none |
| `data_provider` httpx call site | `dhan_client.py` only — pure HTTP, no broker-adapter shared code |

**Conclusion**: `data_provider` is fully isolated from the live-trade path. The Day 6 Celery task touches:
- `BrokerCredential` model (read-only SELECT) — same model live-orders uses, but **separate row + session + read path**. No mutation.
- `decrypt_credential` (pure crypto helper) — stateless.
- `fetch_historical_candles` — confined to `data_provider/`.

**Zero risk** to the live BSE Ltd / Fyers / Dhan order path. Production strategy execution path is untouched.

---

**Audit complete. Proceeding with implementation.**

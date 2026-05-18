# Post-Launch Tech Debt

Issues uncovered during the F&O index Step 1 launch that are intentionally
deferred — none of them affect today's production behaviour, but each is
worth a follow-up before it can bite a future change.

---

## 1. `_resolve_access_token()` references a non-existent Pydantic Settings field

**Location:** `backend/app/strategy_engine/data_provider/fetcher.py:208`

**The bug:**
```python
def _resolve_access_token() -> str:
    settings = get_settings()
    token: Any = getattr(settings, "dhan_access_token", None)
    return str(token) if token else ""
```

`getattr(settings, "dhan_access_token", None)` always returns `None`
because the `Settings` class in `app/core/config.py` does not define a
`dhan_access_token` field. Only `dhan_api_base_url` and
`dhan_scrip_master_url` exist under the `dhan_*` prefix. The fallback
therefore silently returns an empty string for every caller that
relies on it — which is then sent as an empty `Authorization` header
to Dhan, producing `HTTP 401 invalid or expired access token`.

**Today's user impact: zero.**

The only production caller of `fetch_historical_candles(...)` is
`backend/app/strategy_engine/api/backtest.py:514`, which bypasses the
fallback entirely:

```python
token = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()
if not token:
    raise HTTPException(status_code=503, detail="...")
response = fetch_historical_candles(request, access_token=token)
```

`os.environ` is read directly and passed via the explicit
`access_token=` kwarg, so the broken `_resolve_access_token` default
never fires in real traffic.

**Why it's a footgun:**

Any future caller invoking `fetch_historical_candles(req)` *without*
passing `access_token=` — a perfectly reasonable thing to expect from
the function signature — will silently get an empty token, an
unintelligible 401 from Dhan, and a `DhanFetchError` that looks
authentication-related when the root cause is actually that the
fallback never had a real path to discover the token. The function's
own docstring (`fetcher.py:70`) advertises that it reads
`settings.dhan_access_token` if no kwarg is provided — promising
behaviour the code does not deliver.

**Proposed post-launch fix (~30 minutes):**

Two acceptable shapes, pick one:

- **(a) Fail loud** — preferred. Delete the `_resolve_access_token`
  default and make `access_token` a required kwarg on
  `fetch_historical_candles`. Updates the function signature, every
  test call site, and the function docstring. No production caller
  changes (the prod caller already passes the kwarg). Eliminates the
  silent-empty-token failure mode entirely.

- **(b) Add the missing Pydantic field** — `dhan_access_token:
  SecretStr | None = Field(default=None)` on `Settings`, with
  `validation_alias="DHAN_ACCESS_TOKEN"` so it picks up the env var.
  Then `_resolve_access_token` works as advertised. More backwards-
  compatible but keeps the implicit-fallback ergonomics that arguably
  caused the bug in the first place.

Recommend (a). The kwarg is already passed by the only production
caller; the fallback is dead code that misled investigation during the
Step 1 verification.

**Discovered:** 2026-05-11 during F&O index Step 1 verification (commit
`97a96dd`). Took ~15 minutes to identify because the symptom (Dhan 401
for every input including known-good controls) misleadingly pointed at
a stale token. Probing the Pydantic Settings field inventory revealed
the field doesn't exist:

```
Settings has dhan_access_token field: False
all dhan_* fields on Settings: ['dhan_api_base_url', 'dhan_scrip_master_url']
```

**Not in scope for the fix-it-now ticket:** changing the production
call site, restructuring the data_provider module, or unifying the
token-resolution strategy with the broker module's per-user
`broker_credentials` table. Those are separate decisions.

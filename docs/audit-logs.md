# Audit Logs

Backend module for security-critical event recording (commit `d69b1f1`).
Internal developer reference — not user-facing copy.

## Purpose

Tamper-resistant record of every action that has security or
compliance significance: strategy create/update/delete, backtest
runs, AI advisor suggestions, risk-guard blocks, paper trades, live
order attempts, Pine Script imports, and kill-switch events.

The module answers a single question:

> "Who did what, when, and was it allowed?"

The current implementation is an in-memory ring buffer; the public
API is shaped so a future DB-backed store can swap in without
touching call sites. The module is **stdlib-only** by design — no DB
clients, no broker SDKs, no LLM SDKs, no HTTP libraries. The
`test_audit_module_does_not_import_forbidden_modules` test pins that
guarantee.

## Module location

`backend/app/strategy_engine/audit/`

| File | Purpose |
|------|---------|
| `__init__.py` | Public surface: `emit_event`, `query_events`, `clear_audit_log`, `AuditEvent`, `AuditQueryResult`, `EventActor`, `EventSeverity`, `EventType`. |
| `constants.py` | `MAX_EVENTS_IN_MEMORY = 10_000`, `DEFAULT_QUERY_LIMIT = 100`. |
| `models.py` | Frozen Pydantic models — `AuditEvent`, `AuditQueryResult` — plus the `EventType`, `EventSeverity`, `EventActor` literal aliases. |
| `store.py` | Thread-safe `collections.deque(maxlen=MAX_EVENTS_IN_MEMORY)` ring buffer guarded by `threading.Lock`. Exposes `append`, `snapshot`, `size`, `clear`. |
| `emitter.py` | `emit_event` (single write path), `query_events` (single read path), `clear_audit_log`. Holds the auto-severity mapping logic. |
| `loggers.py` | Eight convenience wrappers (`log_strategy_change`, `log_backtest_run`, …) plus the `StrategyChangeType`, `PaperTradeAction`, `KillSwitchAction` literal aliases. |

## Public API

Real signatures from `audit/emitter.py`:

```python
def emit_event(
    event_type: str,
    actor: str,
    summary: str,
    severity: str = "info",
    user_id: UUID | None = None,
    strategy_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent: ...


def query_events(
    user_id: UUID | None = None,
    strategy_id: UUID | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> AuditQueryResult: ...


def clear_audit_log() -> None: ...
```

The emitter is the **only** place `uuid4()` and `datetime.now()` are
read inside the package — the rest of the module is deterministic
and trivially mockable in tests.

### Example — emit + query

```python
from uuid import uuid4
from app.strategy_engine.audit import emit_event, query_events

user_id = uuid4()
strategy_id = uuid4()

emit_event(
    event_type="strategy_updated",
    actor="user",
    summary="User tweaked stop-loss to 1.2 %",
    user_id=user_id,
    strategy_id=strategy_id,
    metadata={"field": "exit.stopLossPercent", "old": 1.0, "new": 1.2},
)

result = query_events(user_id=user_id, severity="info", limit=50)
for ev in result.events:
    print(ev.timestamp, ev.event_type, ev.summary)
```

### Inputs (`emit_event`)

| Parameter | Type | Notes |
|-----------|------|-------|
| `event_type` | `str` | Must be one of the 15 `EventType` literals — invalid values raise `ValueError`. |
| `actor` | `str` | Must be one of the five `EventActor` literals. |
| `summary` | `str` (1-512 chars) | Brief human-readable line; the field is the primary "what happened". |
| `severity` | `str` (default `"info"`) | One of `"info"` / `"warning"` / `"critical"`. Auto-promoted for some event types — see [Severity auto-promotion](#severity-auto-promotion). |
| `user_id` | `UUID \| None` | Nullable so system-level events (kill-switch trips, scheduler jobs) can be recorded without a user. |
| `strategy_id` | `UUID \| None` | Nullable for the same reason. |
| `metadata` | `dict[str, Any] \| None` | Event-specific bag — the emitter never interprets it. Stored as `dict(metadata)` (shallow copy) so caller mutations after the call don't affect the event. |

`emit_event` raises `ValueError` for unknown `event_type`, `actor`,
or (when not auto-promoted) `severity`.

### Inputs (`query_events`)

All filters are AND-combined. `since` / `until` are **inclusive**
bounds (the event must satisfy `since <= timestamp <= until`).
`limit` trims the result to the **most recent** N matches —
`filtered_count` reports the pre-trim total so callers can detect a
truncated window. `query_events` raises `ValueError` for unknown
`event_type`, unknown `severity`, or `limit < 0`.

## Output schema

Field shapes from `audit/models.py`:

### `AuditEvent`

| Field | Type | Notes |
|-------|------|-------|
| `event_id` | `UUID` | Auto-generated via `uuid4()` in `emit_event`. |
| `event_type` | `EventType` | One of the 15 literals — see [Event types](#event-types). |
| `severity` | `Literal["info","warning","critical"]` (`EventSeverity`) | Final, post-auto-promotion value. |
| `user_id` | `UUID \| None` | |
| `strategy_id` | `UUID \| None` | |
| `timestamp` | `datetime` | UTC-aware (`datetime.now(UTC)`). |
| `actor` | `Literal["user","system","ai","broker_guard","kill_switch"]` (`EventActor`) | |
| `summary` | `str` (1-512 chars) | |
| `metadata` | `dict[str, Any]` | Defaults to `{}` if the caller passed `None`. |

`model_config = ConfigDict(frozen=True, extra="forbid")` — once
appended to the buffer, an event is immutable.

### `AuditQueryResult`

| Field | Type | Notes |
|-------|------|-------|
| `events` | `tuple[AuditEvent, ...]` | Most recent matches in chronological (oldest → newest) order. |
| `total_count` | `int` (≥ 0) | Size of the underlying buffer at query time, **before** any filters. |
| `filtered_count` | `int` (≥ 0) | Number of events that matched all filters, **before** the `limit` trim. |

`(filtered_count - len(events))` is the number of events the caller
truncated by passing a low `limit`.

## Event types

The 15 `EventType` literals from `audit/models.py`:

| # | Literal | When emitted |
|---|---------|--------------|
| 1 | `strategy_created` | A user created a strategy. |
| 2 | `strategy_updated` | A user edited an existing strategy. |
| 3 | `strategy_deleted` | A user deleted a strategy. |
| 4 | `backtest_run` | A backtest was executed (success or failure — see metadata). |
| 5 | `ai_suggestion` | The AI advisor produced a suggestion (no user response yet). |
| 6 | `ai_suggestion_accepted` | The user accepted a previously shown AI suggestion. |
| 7 | `ai_suggestion_rejected` | The user rejected a previously shown AI suggestion. Auto-promoted to `warning`. |
| 8 | `risk_block` | The broker / risk guard rejected an action. Auto-promoted to `critical`. |
| 9 | `paper_trade_opened` | A paper-trading position was opened. |
| 10 | `paper_trade_closed` | A paper-trading position was closed. The wrapper sets `severity="warning"` when `pnl < 0`. |
| 11 | `live_order_attempted` | A live order was submitted and allowed. |
| 12 | `live_order_blocked` | A live order was blocked by a guard. Auto-promoted to `critical`. |
| 13 | `pine_import` | A TradingView Pine Script was imported (or import attempted). |
| 14 | `indicator_approved` | An admin approved an indicator. **No convenience wrapper exists today** — emit via `emit_event` directly. |
| 15 | `kill_switch_triggered` | A kill switch fired (or was reset). Auto-promoted to `critical`. |

## Severity auto-promotion

`emit_event` runs every call through `_resolve_severity` before
constructing the `AuditEvent`. The mapping is locked in
`emitter.py`:

```python
_CRITICAL_EVENT_TYPES = frozenset({
    "live_order_blocked",
    "kill_switch_triggered",
    "risk_block",
})

_WARNING_EVENT_TYPES = frozenset({
    "ai_suggestion_rejected",
})

def _resolve_severity(event_type: str, requested: str) -> EventSeverity:
    if event_type in _CRITICAL_EVENT_TYPES:
        return "critical"
    if event_type in _WARNING_EVENT_TYPES:
        return "warning"
    if requested not in _VALID_SEVERITIES:
        raise ValueError(...)
    return requested
```

Resolution order:

1. If `event_type` is in `_CRITICAL_EVENT_TYPES` → `severity =
   "critical"` regardless of what the caller passed. **Critical
   always wins.**
2. Else if `event_type` is in `_WARNING_EVENT_TYPES` → `severity =
   "warning"` regardless of the requested value.
3. Else the caller's `severity` is used (validated against the
   `EventSeverity` literals).

> Note: `paper_trade_closed` is **not** in the auto-promote sets.
> Its severity depends on the trade pnl, which lives outside the
> event-type signal. The decision is made in
> `loggers.log_paper_trade` (warning when `pnl < 0`, info
> otherwise).

## Convenience wrappers (`audit/loggers.py`)

Eight wrappers cover the canonical call sites. Each one funnels
through `emit_event`, so the auto-severity mapping above still
applies — a wrong `severity` argument inside a wrapper cannot
downgrade a critical event.

### `log_strategy_change`

```python
def log_strategy_change(
    strategy_id: UUID,
    user_id: UUID,
    change_type: Literal["created", "updated", "deleted"],
    summary: str,
) -> AuditEvent: ...
```

Emits `strategy_{change_type}` with `actor="user"`,
`severity="info"`, `metadata={"change_type": ...}`.

### `log_backtest_run`

```python
def log_backtest_run(
    strategy_id: UUID,
    user_id: UUID,
    success: bool,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent: ...
```

`event_type="backtest_run"`, `actor="user"`. Severity is `info` on
success, `warning` on failure. The caller's `metadata` is merged in
unchanged alongside `{"success": success}`.

### `log_ai_suggestion`

```python
def log_ai_suggestion(
    strategy_id: UUID,
    user_id: UUID,
    suggestion_type: str,
    accepted: bool | None,
) -> AuditEvent: ...
```

Routes to one of three event types:

| `accepted` | `event_type` | `actor` |
|------------|--------------|---------|
| `None` | `ai_suggestion` | `ai` |
| `True` | `ai_suggestion_accepted` | `user` |
| `False` | `ai_suggestion_rejected` | `user` (auto-promoted to `warning`) |

### `log_risk_block`

```python
def log_risk_block(
    strategy_id: UUID,
    user_id: UUID,
    reason: str,
) -> AuditEvent: ...
```

`event_type="risk_block"`, `actor="broker_guard"`,
`severity="critical"` (auto-enforced),
`metadata={"reason": reason}`.

### `log_pine_import`

```python
def log_pine_import(
    user_id: UUID,
    success: bool,
    license_status: str,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent: ...
```

`event_type="pine_import"`, `actor="user"`, `strategy_id=None`
(imports happen before a strategy id exists). Severity is `info` on
success, `warning` on failure. `license_status` is folded into
`metadata` alongside `success`.

### `log_paper_trade`

```python
def log_paper_trade(
    strategy_id: UUID,
    user_id: UUID,
    action: Literal["open", "close"],
    pnl: float,
) -> AuditEvent: ...
```

`actor="user"`. `action="open"` → `event_type="paper_trade_opened"`,
severity `info`. `action="close"` →
`event_type="paper_trade_closed"`, severity `warning` when `pnl <
0`, otherwise `info`. Metadata always carries `{"action": action,
"pnl": pnl}`.

### `log_live_order_attempt`

```python
def log_live_order_attempt(
    strategy_id: UUID,
    user_id: UUID,
    allowed: bool,
    blocking_reasons: list[str] | None = None,
) -> AuditEvent: ...
```

| `allowed` | `event_type` | `actor` | severity |
|-----------|--------------|---------|----------|
| `True` | `live_order_attempted` | `user` | `info` |
| `False` | `live_order_blocked` | `broker_guard` | `critical` (auto) |

`blocking_reasons` is normalised to a list (empty when `None`) and
stored under `metadata["blocking_reasons"]`.

### `log_kill_switch_event`

```python
def log_kill_switch_event(
    strategy_id: UUID | None,
    user_id: UUID | None,
    action: Literal["triggered", "reset"],
    reason: str,
) -> AuditEvent: ...
```

`actor="kill_switch"`, `severity="critical"` (auto-enforced).

> Caveat: this wrapper always emits **`event_type="kill_switch_triggered"`**
> regardless of whether `action` is `"triggered"` or `"reset"`. The
> `action` value is preserved in `metadata["action"]`. Consumers
> distinguishing between trip and reset must read the metadata, not
> the event type.

## In-memory storage

`audit/store.py` exposes a module-level
`deque(maxlen=MAX_EVENTS_IN_MEMORY)` guarded by a single
`threading.Lock`:

| Constant | Value |
|----------|-------|
| `MAX_EVENTS_IN_MEMORY` | `10_000` |
| `DEFAULT_QUERY_LIMIT` | `100` |

- **Ring buffer** — once the deque is at capacity, the next append
  evicts the oldest event. `test_ring_buffer_caps_and_evicts_oldest`
  pins this behaviour at exactly `MAX_EVENTS_IN_MEMORY + 2` writes.
- **Lock semantics** — the lock is held only for the duration of a
  single `append` / `snapshot` / `clear`, never across user code, so
  contention stays bounded.
- **Read paths** — `query_events` calls `store.snapshot()` (which
  returns a fresh tuple under the lock) and filters in-process. The
  filter loop itself runs lock-free against the snapshot.

## Query filtering

`query_events` filter semantics, in evaluation order:

| Filter | Match condition |
|--------|------------------|
| `user_id` | `event.user_id == user_id` |
| `strategy_id` | `event.strategy_id == strategy_id` |
| `event_type` | `event.event_type == event_type` |
| `severity` | `event.severity == severity` (final post-promotion value) |
| `since` | `event.timestamp >= since` (inclusive) |
| `until` | `event.timestamp <= until` (inclusive) |

All are AND-combined; passing `None` (the default) skips that
filter. After filtering, `limit` trims the **most recent N** matches
(`matched[filtered_count - limit :]`) — so a query for the last 50
events of a busy day returns the latest 50, not the earliest.

`AuditQueryResult.filtered_count` always reflects the
**pre-trim** count, so the caller can detect "the window had more
than `limit` matches and we showed you the most recent N".

## Integration points

### Reads from / depends on

- Pure stdlib (`threading`, `collections.deque`, `datetime`, `uuid`,
  `typing`) plus Pydantic for the boundary models. No app-internal
  dependencies.

### Used by

- **Feature flags** — `app/strategy_engine/feature_flags/manager.py`
  calls `emit_event` directly when a runtime mutation lands on a
  flag in `feature_flags.constants.CRITICAL_FLAGS`
  (`LIVE_TRADING_ENABLED`, `LLM_ADVISOR_ENABLED`,
  `BROKER_GUARD_ENABLED`). Disabling `BROKER_GUARD_ENABLED` is
  routed through `event_type="risk_block"`; every other critical
  flag mutation is recorded as `event_type="kill_switch_triggered"`.
  This is a one-way dependency — the audit module does not import
  feature_flags.
- **TODO**: The Phase 1-9 API endpoints, broker guard, paper-
  trading engine, and Pine importer have **not** been wired to the
  convenience wrappers yet. The wrappers exist; the call sites in
  `app/strategy_engine/api/*.py`, `app/strategy_engine/broker_guard/`,
  `app/strategy_engine/paper_trading/`, and
  `app/strategy_engine/pine_import/` need a follow-up phase to invoke
  them. Treat this section as the integration roadmap, not a
  description of current call traffic.
- **TODO**: There is no admin / frontend surface today. The buffer
  is queryable only from Python.

## Test coverage

`backend/tests/strategy_engine/audit/test_audit.py` — single test
module. **27 tests collected** at the time of writing (the AST-walk
test is parametrised over the six audit `*.py` source files, which
accounts for several of the entries).

Highlights:

| Test | What it pins |
|------|--------------|
| `test_emit_event_creates_event_with_uuid_and_utc_timestamp` | `event_id` is a uuid4, `timestamp` is UTC-aware and lies inside the call window. |
| `test_query_events_returns_all_when_no_filters` | Default-args query returns every buffered event. |
| `test_query_events_filters_by_user_id` / `_by_strategy_id` / `_by_event_type` / `_by_severity` | Each filter reduces the result and `filtered_count` reflects the pre-trim total. |
| `test_query_events_time_range_filtering` | `since` and `until` are inclusive bounds. |
| `test_ring_buffer_caps_and_evicts_oldest` | Writing `MAX_EVENTS_IN_MEMORY + 2` events evicts the two oldest. |
| `test_concurrent_emits_do_not_lose_events` | 20 threads × 5 emits each (100 writes) — every event is preserved with a unique `event_id`. |
| `test_log_risk_block_sets_severity_critical` | The wrapper produces `severity="critical"` and `event_type="risk_block"`. |
| `test_log_pine_import_includes_license_status` | `license_status` is folded into the metadata bag. |
| `test_audit_module_does_not_import_forbidden_modules` | Parametrised AST walk over every `*.py` in the package; rejects `app.services`, `app.brokers`, `app.db`, `sqlalchemy`, `openai`, `anthropic`, `httpx`, `requests` (and any of their submodules). |
| `test_emit_event_is_deterministic_in_shape` | Two calls with identical inputs differ only in `event_id` and `timestamp`; every other field matches byte-for-byte. |
| `test_clear_audit_log_resets_state` | `clear_audit_log()` empties the buffer and `query_events()` reflects the empty state. |
| `test_critical_event_types_force_severity_critical` | Calling `emit_event` with `severity="info"` for `live_order_blocked` / `kill_switch_triggered` still records `severity="critical"`. |
| `test_log_paper_trade_negative_close_is_warning` | Closing with `pnl < 0` records `severity="warning"`; positive / zero pnl stays `info`; opens stay `info`. |
| `test_log_live_order_attempt_blocked_is_critical` | Blocked attempt routes through `live_order_blocked` and is auto-critical. |
| `test_emit_event_rejects_invalid_event_type` / `_invalid_actor` | Both validation gates raise `ValueError`. |
| `test_query_events_rejects_negative_limit` | Negative limits raise `ValueError`. |
| `test_query_events_limit_trims_to_most_recent` | `limit=3` against a 10-event buffer returns the latest three. |

Critical invariants pinned by the suite:

- **Dependency hygiene** — AST inspection forbids DB / broker / LLM /
  HTTP imports across the whole package.
- **Thread safety** — concurrent emits never tear the buffer or
  produce duplicate event ids.
- **Ring buffer cap** — eviction kicks in at exactly the configured
  capacity.
- **Severity auto-promotion** — security-critical event types cannot
  be downgraded by a buggy or malicious caller.
- **Frozen events** — once emitted, an `AuditEvent` cannot be
  mutated.

## Limitations

- **In-memory only.** The buffer is process-local; a restart loses
  every event. No journal, no fsync, no replay.
- **Not multi-process safe.** The `threading.Lock` only guards
  threads inside a single process. Two FastAPI workers each maintain
  their own deque.
- **No SQL queryability.** `query_events` is a Python-side scan —
  fine for ≤ 10 000 events, not a substitute for an indexed store.
- **No retention policy beyond eviction.** Events older than the
  10 000-most-recent are dropped silently. There is no "archived" or
  "expired" state.
- **No persistence layer.** A future phase will swap the in-memory
  store with a DB-backed implementation behind the same public API
  — the call sites in `emitter.py` are intentionally minimal so
  that swap is mechanical.
- **`indicator_approved` has no wrapper.** It is a valid
  `EventType`, but callers must invoke `emit_event` directly until a
  wrapper is added.
- **`log_kill_switch_event` always emits `kill_switch_triggered`**,
  even on `action="reset"`. Consumers that need to distinguish trip
  vs reset must inspect `metadata["action"]`.
- **`metadata` is not validated.** It is a `dict[str, Any]` bag —
  anything JSON-encodable goes in. There is no schema per event
  type.

## Future enhancements

- TODO: PostgreSQL persistence layer behind the existing
  `emit_event` / `query_events` API. The store module already
  isolates the storage concern behind `append` / `snapshot` /
  `clear` / `size`; a DB-backed implementation can swap in without
  touching the emitter.
- TODO: Async / non-blocking event emission. Today `emit_event` is
  fully synchronous and acquires a lock — fine for the current call
  rate, but a high-volume live-trading session would benefit from a
  background flush.
- TODO: Webhook / SIEM export. Configurable downstream sinks
  (Splunk, Datadog, an SQS topic) that receive every event the
  emitter records.
- TODO: User-facing audit log viewer in the admin dashboard. The
  frontend has no rendering surface for `AuditEvent` today.
- TODO: Retention policy with archival. Move events past a
  configurable age out of the hot buffer into cold storage rather
  than dropping them.
- TODO: GDPR-compliant deletion. Today there is no per-user
  delete-events API — required if the store ever holds PII.
- TODO: Schema-per-event-type validation of the `metadata` bag.
  Today the field is free-form `dict[str, Any]`; a future phase
  could attach a Pydantic discriminated union keyed on
  `event_type`.
- TODO: Convenience wrapper for `indicator_approved`. The literal
  exists in `EventType` but no `loggers.py` helper covers it.
- TODO: Wire the existing wrappers into the actual call sites
  (strategy CRUD endpoints, broker guard, paper trading engine,
  Pine importer). The wrappers exist but most production code
  paths still emit nothing.

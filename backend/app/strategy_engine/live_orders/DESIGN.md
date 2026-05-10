# Live Broker Order Wiring — DESIGN (Phase 8B-1 Discovery Output)

Status: DESIGN ONLY. No code changes in this session.
Implementation plan covered in section 9 (Phase 8B-2). Tests in Phase 8B-3.

Locked architectural rules carried into this design:
- Existing `services/dhan_*`, `app/brokers/dhan.py`, and `services/order_service.py` are NOT modified.
- Existing Auto Kill Switch (`services/kill_switch_service.py`, Redis state via `redis_client.get_kill_switch_status`) is read-only from this module.
- AI never participates in any value that affects a live order. The Broker Execution Guard already enforces this; this module only consumes its verdict.
- Default execution mode is paper. Live requires every blocking check to pass.
- 7 completed paper sessions required (`MIN_COMPLETED_SESSIONS = 7` in `paper_trading/engine.py`).

---

## 1. Discovery Findings

### 1.1 Existing broker layer

`app/brokers/base.py::BrokerInterface.place_order(order: OrderRequest) -> OrderResponse`

  Per-user broker instance, constructed from a decrypted `BrokerCredentials`. Subclasses
  implement the abstract method. Two are real: `FyersBroker`, `DhanBroker`. The rest are
  stubs (`stubs.py`). `app/brokers/registry.py::FULLY_IMPLEMENTED = {FYERS, DHAN}`.

`app/brokers/dhan.py::DhanBroker.place_order` (line 435):
  - Inputs: `OrderRequest` (Pydantic) — `symbol`, `exchange`, `side`, `quantity`,
    `order_type`, `product_type`, optional `price`, `trigger_price`, `tag`.
  - Pre-flight inside the broker: `_build_order_payload` resolves `securityId` via the
    Dhan scrip-master, then constructs the wire payload (`dhanClientId`,
    `transactionType`, `exchangeSegment`, `productType`, `orderType`, `validity=DAY`,
    `securityId`, `tradingSymbol`, `quantity`, `disclosedQuantity`, `price`,
    `triggerPrice`, optional `correlationId`).
  - HTTP: `POST /orders` with `access-token` header, retry on transient
    (`BrokerConnectionError`, `BrokerRateLimitError`) up to 3 attempts.
  - Returns: `OrderResponse(broker_order_id, status, message, raw_response)` where
    `status: OrderStatus` is mapped from Dhan's `orderStatus`. See `_STATUS_FROM_DHAN`.
  - Raises typed broker exceptions from `app/core/exceptions`:
    `BrokerAuthError`, `BrokerSessionExpiredError`, `BrokerInsufficientFundsError`,
    `BrokerInvalidSymbolError`, `BrokerOrderRejectedError`, `BrokerRateLimitError`,
    `BrokerConnectionError`, `BrokerOrderError`.

Auth lifecycle (already implemented in Dhan):
  - `DhanBroker.login()` validates the user-pasted access token via `GET /fundlimit`.
  - `DhanBroker.is_session_valid()` consults Redis cache `dhan_session:{user_id}` first,
    falls back to a probe.
  - Tokens stored Fernet-encrypted in `BrokerCredential.access_token_enc`. Decrypt via
    `core.security.decrypt_credential`. `BrokerCredentials` schema lives at
    `app/schemas/broker.py`.

Existing call sites that already place broker orders (NOT to be modified):
  - `app/services/order_service.py::process_webhook_signal` — TradingView webhook path.
    Has session-refresh on `BrokerSessionExpiredError`. Records a `Trade` row. Has NO
    Broker Guard, NO paper-readiness check, NO trust/truth gating.
  - `app/services/strategy_executor.py::place_strategy_orders` — strategy-engine entry
    path. Has a global `paper_mode` flag (`settings.strategy_paper_mode`) and a
    `_live_place_order` helper (`validate_symbol`, funds floor check). Also has NO
    Broker Guard, NO paper-readiness check, NO trust/truth gating.

  Both paths predate the strategy-engine safety stack. The new live-orders module wraps
  a separate, explicit "place a live order from the dashboard" entry point that runs
  the full safety chain. We deliberately leave the webhook / strategy-executor paths
  alone in 8B-2 — wiring those is a follow-up sequencing decision (see §6).

### 1.2 Existing safety layers

`app/strategy_engine/broker_guard/guard.py::evaluate_broker_guard(...)`

  Pure decision function. Frozen `GuardDecision` output. Composes 11 checks:
  - **Blocking** (any `passed=False` → `allowed=False`):
    `stop_loss_present`, `broker_connected`, `kill_switch_inactive`,
    `truth_score >= 55`, `trust_score >= 70`,
    `paper_readiness` (or `user_override_paper`).
  - **Warning**: `truth_risk_level`, `low_trade_count`, `high_drawdown`,
    `paper_override_used`.
  - **Info**: `paper_sessions_recommended` (target 14, see `RECOMMENDED_PAPER_SESSIONS`).

  Thresholds (`broker_guard/constants.py`): `MIN_TRUTH_SCORE_FOR_LIVE = 55`,
  `MIN_TRUST_SCORE_FOR_LIVE = 70`, `HIGH_DRAWDOWN_WARNING = 0.25`,
  `LOW_TRADE_COUNT_WARNING = 30`.

  **Verified: `evaluate_broker_guard` is currently NOT called from any service or
  API.** The only references outside the module itself are tests in
  `tests/strategy_engine/broker_guard/`. This is the integration point Phase 8B-2 wires.

`app/strategy_engine/paper_trading/engine.py`
  - `compute_readiness(strategy, sessions) -> PaperReadinessReport` enforces five gates,
    including `completed_sessions >= MIN_COMPLETED_SESSIONS = 7`, `paper_pnl > 0`,
    `win_rate >= 0.40`, `rule_adherence >= 80%`, stop-loss present.
  - State is held in a module-level `_RECORDS: dict[UUID, _SessionRecord]` — **purely
    in-memory, no DB persistence**. A process restart wipes the counter. This is a
    known constraint Phase 8B-2 must address (see §6 and §8).

`app/services/kill_switch_service.py` + `app/core/redis_client.py`
  - State key: `kill_switch:{user_id}` ∈ {`KILL_SWITCH_ACTIVE`, `KILL_SWITCH_TRIPPED`}.
  - Read API: `redis_client.get_kill_switch_status(user_id)`.
  - The kill-switch service writes the TRIPPED flag *before* firing brokers, so any
    live-order request that arrives mid-trip is correctly rejected.

`app/strategy_engine/feature_flags/`
  - `manager.is_enabled("LIVE_TRADING_ENABLED")`. Default `False`. Sources, in order:
    env override (`TRADETRI_FF_LIVE_TRADING_ENABLED`) > runtime override > registry default.
  - **Per-user feature flagging is NOT supported today.** The flag is global, in-memory.
    Phase 8B-2 needs a per-user gate (see §6).

`app/strategy_engine/audit/loggers.py`
  - `log_live_order_attempt(strategy_id, user_id, allowed, blocking_reasons=[...])`
    already exists. The emitter auto-promotes `live_order_blocked` to `critical`.
  - `log_risk_block(strategy_id, user_id, reason)` available for finer-grained block
    audit when a single check fails for a non-guard reason.
  - Storage today is the in-memory ring buffer at
    `audit/store.py::_events: deque(maxlen=MAX_EVENTS_IN_MEMORY)`. A DB-backed audit
    table (`audit_logs`) exists at `app/db/models/audit_log.py` and is used by the
    kill-switch service. New live-order audit will reuse the same emitter contract;
    the persistent backend swap is tracked separately.

### 1.3 Auth + per-user broker context

`app/api/deps.py::get_current_active_user(request, db) -> User`
  - JWT Bearer in `Authorization` header → `validate_session_token` → `User` row.
  - Per-strategy ownership scope: every strategy endpoint filters by
    `Strategy.user_id == current_user.id` (404 covers both "not found" and "not yours").
  - `BrokerCredential` table is `(user_id, broker_name)` with `is_active` and
    Fernet-encrypted token columns. Decrypt via `core.security.decrypt_credential`.
  - `Strategy.broker_credential_id` FK is the binding the strategy executor already
    uses; live-orders will use the same FK.

### 1.4 Integration points identified

- **Backend**: there is no `/api/orders/live` endpoint today. `app/api/strategy_signals.py`
  is read-only. Webhook path is `/api/webhook` and `/api/strategy_webhook`. New router
  needs to register before any catch-all `/{strategy_id}` route — pattern documented
  in `strategy_engine/api/strategies.py`.
- **Frontend**: strategy detail page is `frontend/src/app/(dashboard)/strategies/[id]/page.tsx`.
  It already renders `TrustScoreBadge` and `VersionHistoryPanel`. There is no "Go Live"
  button anywhere in the codebase (`grep` for "Go Live" / "live trade" returned nothing).
  Backtest sub-page exists at `[id]/backtest/page.tsx` and is the natural home for the
  pre-flight surface.

---

## 2. Proposed Architecture

New module: `backend/app/strategy_engine/live_orders/`

Files:
- `models.py` — Pydantic boundary models (frozen, `extra="forbid"`).
- `safety_chain.py` — composes the safety checks before the Broker Guard, returns the
  first failure or "all green". Reuses existing functions; adds nothing AI-driven.
- `order_router.py` — public entry `place_live_order(...)`. Wraps:
  1. SafetyChain
  2. Broker Execution Guard (`evaluate_broker_guard`)
  3. Audit logging
  4. Existing broker.place_order
- `__init__.py` — re-exports the public boundary.

### 2.1 Public API

```
async def place_live_order(
    *,
    session: AsyncSession,
    user: User,
    strategy_id: UUID,
    side: OrderSide,
    quantity: int,
    order_type: OrderType = OrderType.MARKET,
    price: Decimal | None = None,
    trigger_price: Decimal | None = None,
    product_type: ProductType = ProductType.INTRADAY,
    user_override_paper: bool = False,  # admin-gated; default off
) -> LiveOrderResult
```

Returns a single `LiveOrderResult`. Never raises for *expected* failures (safety
block, guard reject, broker offline) — those are reflected in `success=False` plus
structured detail. Unexpected exceptions (programmer error, DB outage) propagate.

### 2.2 Internal flow (locked sequence)

```
place_live_order(strategy_id, user, signal_type, quantity, price)
 │
 ├─► load Strategy (scoped to user.id) — 404 on cross-user probe
 │
 ├─► SafetyChain.check_all() — first failure short-circuits
 │     1. Auto Kill Switch  → redis_client.get_kill_switch_status(user.id)
 │     2. LIVE_TRADING_ENABLED feature flag for this user
 │     3. Paper sessions complete  → completed >= 7 (per-strategy)
 │     4. Strategy Trust Score >= 70  → from cached/recomputed reliability
 │     5. Strategy Truth Score >= 55  → from cached/recomputed truth report
 │     6. Broker connection healthy  → broker.is_session_valid() + active credential
 │     7. Risk Engine pre-check       → max-daily-trades not at cap, kill-switch
 │                                       config enabled, daily-loss budget remaining
 │
 ├─► Broker Execution Guard (existing evaluate_broker_guard)
 │     Composes blocking + warning + info checks once SafetyChain has cleared the
 │     coarse pre-conditions. The guard is also the only place strategy + reliability
 │     + truth + paper-readiness are fed into the verdict; SafetyChain is the cheap
 │     short-circuit that avoids paying the cost of building those reports when the
 │     trade is going to be blocked anyway.
 │
 ├─► Audit log entry — log_live_order_attempt(allowed=True, ...) PRE-call
 │
 ├─► broker.place_order(OrderRequest(...))   # untouched DhanBroker / FyersBroker
 │     One-shot retry on BrokerSessionExpiredError → broker.login() → retry once
 │     (mirrors order_service.py — proven pattern in production)
 │
 ├─► Audit log entry — POST result (status, broker_order_id, raw_response)
 │
 └─► return LiveOrderResult(success, broker_order_id, ...)

On any safety / guard block:
 ├─► Audit log entry — log_live_order_attempt(allowed=False, blocking_reasons=[...])
 ├─► Audit log entry — log_risk_block(reason) for the most-actionable reason
 └─► return LiveOrderResult(success=False, blocked_by="safety_chain"|"broker_guard", ...)
```

### 2.3 What the module deliberately does NOT do

- Persist `Trade` rows. The existing webhook/executor paths handle that; live-orders
  endpoint will reuse `_record_trade` from `order_service` (no copy-paste). This is a
  Phase 8B-2 implementation detail flagged in §9.
- Compute or recompute strategy values used by the AI (that is still a strategy-engine
  responsibility). The router consumes already-computed scores.
- Modify the existing `DhanBroker.place_order` or its retry / error mapping.
- Touch the kill-switch implementation (read-only via `redis_client`).

---

## 3. Pydantic Models (proposed)

All frozen, `extra="forbid"`, mirrors the strategy-engine convention.

```python
class LiveOrderRequest(BaseModel):
    """Validated body for POST /api/orders/live."""
    strategy_id: UUID
    side: OrderSide                          # BUY | SELL (no EXIT — that path differs)
    quantity: int = Field(..., gt=0)
    order_type: OrderType = OrderType.MARKET
    price: Decimal | None = None
    trigger_price: Decimal | None = None
    product_type: ProductType = ProductType.INTRADAY
    user_override_paper: bool = False        # admin-only; rejected for non-admin


class SafetyCheckResult(BaseModel):
    """Per-check verdict surfaced to the frontend pre-flight panel."""
    check_name: str = Field(..., min_length=1, max_length=64)
    passed: bool
    severity: Literal["blocking", "warning", "info"]
    message: str = Field(..., min_length=1, max_length=512)
    # Hinglish-friendly short reason for the user-facing modal.
    user_reason: str = Field(..., min_length=1, max_length=256)


class LiveOrderResult(BaseModel):
    """Outcome of a place_live_order call.

    success=True  → broker accepted; broker_order_id populated.
    success=False → either safety_chain blocked, guard rejected, or broker rejected.
                    Inspect blocked_by + safety_results / guard_decision for detail.
    """
    success: bool
    broker_order_id: str | None = None
    broker_status: OrderStatus | None = None
    blocked_by: Literal[
        "safety_chain",
        "broker_guard",
        "broker_rejected",
        "broker_offline",
    ] | None = None
    safety_results: tuple[SafetyCheckResult, ...] = ()
    guard_decision: GuardDecision | None = None     # reused from broker_guard.models
    message: str = Field(..., min_length=1, max_length=512)
    audit_event_ids: tuple[UUID, ...] = ()
```

Notes:
- `blocked_by` is a closed Literal so the frontend can render distinct UI per block reason.
- `guard_decision` is the existing frozen `GuardDecision` reused unchanged. The
  frontend already knows how to render warnings + blocking_failures from this shape.
- `audit_event_ids` lets the operator click straight from the order modal to the audit
  trail in admin.

---

## 4. New API Endpoint (proposed)

```
POST /api/orders/live
  Auth:       required (get_current_active_user)
  Body:       LiveOrderRequest
  Response:   LiveOrderResult

  Status codes:
    200   success or expected block (success=False with structured reason).
          Choosing 200-with-detail over 4xx-on-block keeps the frontend's
          mutation handling uniform — every "blocked" path is a normal
          response that renders its own UI; only programmer error / outage
          becomes an HTTP error.
    400   payload validation failure (Pydantic).
    401   missing or invalid Bearer token.
    403   strategy ownership check failed (cross-user probe).
    503   broker offline / session-expired-and-relogin-failed.
```

Hinglish reason rendering: each `SafetyCheckResult.user_reason` carries a short
Hinglish/English-mixed string (e.g. "Auto Kill Switch ON — pehle settle karo.",
"Trust Score 62 hai — minimum 70 chahiye live ke liye."). The blocking_failure
strings on `GuardDecision` are already plain English; we add the Hinglish layer at
the SafetyChain boundary, not inside the Broker Guard (which stays pure).

Router file: `app/api/orders_live.py`. Mounted before any catch-all. The router
imports nothing from `app/services/order_service.py`'s internals — it only reuses
`_record_trade` if Phase 8B-2 decides to persist the resulting trade row (see §9).

---

## 5. Frontend integration points (proposed)

Locations:
- `frontend/src/app/(dashboard)/strategies/[id]/page.tsx` — add "Go Live" button
  beside the existing "View Backtest" affordance. Disabled until pre-flight clears.
- New panel component `frontend/src/components/strategies/live-order-panel.tsx` —
  pre-flight check display + confirmation modal.

UX flow:
1. **Pre-flight check display** — on mount, fetch `GET /api/orders/live/preflight`
   (a new sibling endpoint, dry-run: runs SafetyChain + Broker Guard, no order placed).
   Renders each `SafetyCheckResult` as a row: green tick / red cross / amber warning.
   "Go Live" button is enabled only when every blocking check is `passed=True`.
2. **Order confirmation modal** — on click, surface:
   - Strategy name + version_number
   - Side, quantity, order_type, product_type
   - Estimated slippage / margin if known (Phase 8B-2 may defer)
   - Re-rendered Trust + Truth scores
   - Single "Confirm — place live order" button + Cancel
3. **Order placement progress** — after confirm, optimistic UI: spinner with
   "Placing order…" message. On 200, render the `LiveOrderResult.message` and the
   `broker_order_id`. On 503, render a retry affordance.
4. **Result display** — link to the freshly-created audit events
   (`audit_event_ids`) and to the position page if the broker accepted.

The "Go Live" surface is opt-in: an `EXPERT_MODE_ENABLED` user with a strategy that
already cleared paper-readiness sees the button. Other users see a coaching card
explaining what's needed. (Reuses existing `strategy-coach-card.tsx` shape.)

---

## 6. Migration considerations

- **No new DB tables strictly required for the live-order placement path.** The
  existing `audit_logs` (DB-backed) and Phase 8B-2's optional reuse of `Trade`
  cover the persistence needs.

- **Per-user `LIVE_TRADING_ENABLED` flag (NEW):** the current global feature flag
  is insufficient. Two options on the table for Phase 8B-2:
  - (a) Add `users.live_trading_enabled` boolean column. Cheapest, least flexible.
  - (b) Add a `user_feature_flags(user_id, flag_name, enabled)` table to mirror
    the existing flag registry per-user. More flexible, slightly bigger lift.
  Recommendation: **(a)** for 8B-2 scope; (b) is post-launch when more flags need
  per-user control.

- **Paper sessions persistence (NEW, blocking dependency):** the in-memory `_RECORDS`
  dict means a restart wipes the 7-session counter. Phase 8B-2 must add a
  `paper_sessions(id, user_id, strategy_id, started_at, ended_at, candles_processed,
  trades_summary_json)` table and a `paper_trades(id, paper_session_id, ...)` table,
  then route `start_session` / `end_session` / `process_candle` writes through it.
  This is the single biggest design risk — flagged in §8 and called out in §9 as the
  first 8B-2 deliverable.

- **Latest TruthReport / TrustScore persistence:** today these are computed during a
  backtest API call and held in the response only. Phase 8B-2 needs a deterministic
  source of `latest_truth_score` and `latest_trust_score` per `(strategy_id, version_id)`.
  Recommended: cache the last computed `(truth_score, trust_score, computed_at)` on
  the strategy row (or a small `strategy_scores` side table) at backtest-completion
  time. SafetyChain reads from cache; if absent or stale (> 24h), the chain blocks
  and surfaces "Run a fresh backtest to refresh scores."

---

## 7. Testing strategy

Phase 8B-2 (build module): 20+ unit tests with mocked Dhan calls.
- SafetyChain: one test per check, plus combined "first failure wins" ordering test.
- order_router: success path, broker_session_expired retry path, broker_offline path.
- Audit emission: PRE/POST audit events emitted with correct severity for both
  allow and block branches.
- Pydantic models: serialization round-trip + frozen invariant tests.
- Negative tests: cross-user strategy access (403), missing broker credential, AI
  involvement flag never set on a live request (regression test).

Phase 8B-3 (integration + dry-run):
- Integration: real DB session, mocked broker, full POST /api/orders/live → audit row
  appears → trade row appears.
- Dry-run mode (`preflight=True`): runs SafetyChain + Broker Guard, returns a
  full `LiveOrderResult` minus the broker call. Used by the frontend pre-flight panel.
- Manual staging test before production: see §9.

---

## 8. Risk register

| Risk | Mitigation |
|------|------------|
| Dhan API down mid-order: response timeout, status unknown. | (a) Existing httpx timeout = 30s. (b) Retry in `DhanBroker._call` covers transient. (c) On final timeout, audit event records `broker_offline` with payload; manual reconcile via `get_order_status(broker_order_id)` is the operator's recovery path. (d) `LiveOrderResult.broker_order_id=None` and `blocked_by="broker_offline"` — frontend prompts manual reconcile, never auto-retries the place. |
| Auto Kill Switch trips during order placement. | TRIPPED flag is set BEFORE square-off fires (kill_switch_service.py:291). SafetyChain reads kill_switch state at the start of `place_live_order` AND `evaluate_broker_guard` re-checks it via `auto_kill_switch_active`. Race window is the few ms between guard pass and broker.place_order — acceptable, and the kill-switch service square-off path will reverse any new position immediately. |
| Paper-sessions counter wrong (in-memory loss after restart). | This is a hard dependency on Phase 8B-2 §6. Until paper sessions are DB-persisted, the safety check is unreliable. Mitigation: 8B-2 must ship the DB tables before the live-order endpoint is exposed. The endpoint is feature-flagged off by default. |
| Concurrent order requests from the same user. | Live orders should be idempotent at the broker level (Dhan supports `correlationId` via `OrderRequest.tag`). Phase 8B-2 generates a deterministic correlation ID `live-{strategy_id}-{ts}` and rejects a second request with the same id within 5s using the existing `idempotency_keys` table. Concurrent distinct orders are allowed and pass through SafetyChain independently. |
| Order placed but POST response timeout — is it confirmed? | Same as the first row: caller treats `blocked_by="broker_offline"` as "manual reconcile". Operator re-fetches via `get_order_status`. Never silent-retry. |
| Per-user `LIVE_TRADING_ENABLED` accidentally rolled out globally. | The migration path (§6) explicitly adds a per-user column. The global flag stays in the registry as a kill-everything master switch, but the SafetyChain reads the per-user flag first. Both must be true to allow live. |
| Trust/Truth score cache is stale and the strategy has degraded. | SafetyChain rejects a cached score older than 24h and prompts a fresh backtest. The 24h figure matches the existing Dhan scrip-master TTL — operationally familiar. |
| Audit log buffer overflow (in-memory ring buffer drops oldest events). | The DB-backed `audit_logs` table is already used by kill-switch; live-orders 8B-2 will write to both the in-memory emitter and the DB row in the same transaction. The ring buffer remains for fast reads in the admin UI; the DB is the system of record. |
| Strategy edited mid-flight — version mismatch between displayed pre-flight and placed order. | `LiveOrderRequest` carries `strategy_id` only; SafetyChain reads `Strategy.current_version_number` at place-time. If the version changed since the frontend showed the pre-flight, the order is blocked with "Strategy was edited — refresh and re-confirm" and the user must re-run pre-flight. |

---

## 9. Phase 8B-2 implementation plan (next session)

### 9.1 File-by-file breakdown

| File | Action | Estimate |
|------|--------|---------:|
| `migrations/versions/0XX_paper_sessions.py` | NEW — `paper_sessions` + `paper_trades` tables. Add `users.live_trading_enabled` bool default false. Add `strategies.last_truth_score`, `strategies.last_trust_score`, `strategies.last_scores_at`. | 60 min |
| `app/db/models/paper_session.py` | NEW — ORM mapping for the two tables above. | 20 min |
| `app/strategy_engine/paper_trading/engine.py` | EDIT — replace `_RECORDS` writes with DB writes; keep API surface identical. Tests in `tests/strategy_engine/paper_trading/` continue to pass. | 90 min |
| `app/strategy_engine/live_orders/models.py` | NEW — Pydantic boundary models per §3. | 20 min |
| `app/strategy_engine/live_orders/safety_chain.py` | NEW — composes the 7 checks per §2.2. Pure, except for the kill-switch redis read and DB read for paper-session count. | 60 min |
| `app/strategy_engine/live_orders/order_router.py` | NEW — `place_live_order` orchestrator per §2.2. Reuses `evaluate_broker_guard` and `DhanBroker.place_order` as-is. | 60 min |
| `app/strategy_engine/live_orders/__init__.py` | NEW — public re-exports. | 5 min |
| `app/api/orders_live.py` | NEW — POST `/api/orders/live` and POST `/api/orders/live/preflight`. Uses `get_current_active_user`. | 45 min |
| `app/main.py` | EDIT — register `orders_live_router` BEFORE any catch-all. | 5 min |
| `frontend/src/components/strategies/live-order-panel.tsx` | NEW — pre-flight + confirmation modal per §5. | 90 min |
| `frontend/src/app/(dashboard)/strategies/[id]/page.tsx` | EDIT — wire panel + Go Live button. | 30 min |

Total: ~7 h backend + ~2 h frontend in 8B-2.

### 9.2 Test list (Phase 8B-2 acceptance)

Unit (target: 20+):
1. `place_live_order_success_path_returns_broker_order_id`
2. `place_live_order_blocked_by_kill_switch`
3. `place_live_order_blocked_by_live_trading_flag_off`
4. `place_live_order_blocked_by_paper_sessions_under_seven`
5. `place_live_order_blocked_by_trust_score_below_70`
6. `place_live_order_blocked_by_truth_score_below_55`
7. `place_live_order_blocked_by_broker_session_invalid`
8. `place_live_order_session_expired_relogins_once_then_succeeds`
9. `place_live_order_session_expired_relogin_fails_returns_503`
10. `place_live_order_broker_rejected_returns_structured_failure`
11. `place_live_order_cross_user_strategy_returns_403`
12. `place_live_order_concurrent_same_correlation_id_idempotent`
13. `place_live_order_emits_pre_and_post_audit_events`
14. `place_live_order_blocked_emits_critical_audit_event`
15. `place_live_order_no_ai_calls_made_during_path` (regression)
16. `safety_chain_first_failure_short_circuits` (no extra reads after first fail)
17. `safety_chain_all_pass_returns_empty_blocking_list`
18. `live_order_result_serialization_round_trip`
19. `preflight_endpoint_does_not_call_broker_place_order`
20. `strategy_version_changed_between_preflight_and_place_blocks`
21. `live_trading_enabled_per_user_false_blocks_even_if_global_true`

Integration (8B-3): full POST → DB row → audit row → frontend renders result.

### 9.3 Manual staging plan

1. Deploy 8B-2 to staging with `LIVE_TRADING_ENABLED` global = false.
2. Whitelist one internal user via `users.live_trading_enabled = true`.
3. Connect a real (small-balance) Dhan account.
4. Run a tiny BUY (1 lot of a low-value contract) end to end. Verify audit, trade row,
   broker order status reconciliation.
5. Trigger each block path manually (force kill-switch trip; revoke broker session;
   set trust score to 65 in DB) and confirm SafetyChain rejects with the right
   `blocked_by` value.
6. Smoke-test the frontend pre-flight panel.
7. Sign-off → enable global flag in production for the same whitelisted user only.

---

## Glossary of cited code paths

- `app/brokers/dhan.py:435` — `DhanBroker.place_order`
- `app/brokers/base.py:95` — `BrokerInterface.place_order` abstract
- `app/brokers/registry.py:38` — `FULLY_IMPLEMENTED`
- `app/services/order_service.py:94` — `process_webhook_signal`
- `app/services/strategy_executor.py:102` — `place_strategy_orders`
- `app/services/kill_switch_service.py:258` — `KillSwitchService.check_and_trigger`
- `app/strategy_engine/broker_guard/guard.py:42` — `evaluate_broker_guard`
- `app/strategy_engine/broker_guard/constants.py` — guard thresholds
- `app/strategy_engine/paper_trading/engine.py:58` — `MIN_COMPLETED_SESSIONS = 7`
- `app/strategy_engine/paper_trading/engine.py:246` — `compute_readiness`
- `app/strategy_engine/feature_flags/registry.py:35` — `LIVE_TRADING_ENABLED`
- `app/strategy_engine/audit/loggers.py:187` — `log_live_order_attempt`
- `app/api/deps.py:84` — `get_current_active_user`
- `app/db/models/strategy.py:35` — `Strategy.broker_credential_id`
- `frontend/src/app/(dashboard)/strategies/[id]/page.tsx` — strategy detail page (target for Go Live button)

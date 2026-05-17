# `strategy_json` Dependency Map — Phase A audit

**Branch:** `fix/strategy-detail-clone`
**Date:** 2026-05-17
**Audit scope:** every `strategy_json` reference in `backend/app/`, classified
by whether a null DSL blocks the code path (BLOCKING) or passes through
gracefully (READ-ONLY).

---

## TL;DR

Cloned-from-template strategies write `Strategy.strategy_json = None`
(per `app/templates/clone_service.py:125-133` — DSL hydration deferred
to Phase 7-8). Across the 14 callsites I audited, the impact is:

- **No existing fallback path** lifts `template_origin.config_json` into
  the runtime. Path 2 (auto-hydrate at clone-time) is not partially
  built.
- The live-trading path, the backtest endpoint, and the version history
  pipeline are **fully blocked** by null DSL — each fails CLOSED with a
  user-visible "no DSL — recreate in Phase 5 builder" message.
- The compliance reports fall back to an empty dict so they don't
  crash, but the report content is vacuous (zero indicators evaluated,
  zero rules checked).
- The order executor itself does NOT read strategy_json — but its
  upstream gates (webhook + safety guard) already block null-DSL rows
  before the executor is reached.

**Verdict:** cloned strategies are **functionally inert** today.
Path 1 (UX fix per `PATCH_INSTRUCTIONS_STRATEGY_DETAIL.md`) is the
correct response: surface the template's `config_json` for browsing
and review, while being explicit that live trading + backtesting
unlock with the Phase 5 Strategy Builder.

---

## Callsite-by-callsite

### 1. `app/db/models/strategy.py`

**Role:** column definition only (`strategy_json: Mapped[dict | None]`)
**Classification:** N/A — storage layer
**Null behaviour:** column is nullable; nothing reads here

### 2. `app/services/strategy_executor.py`

**Role:** dispatches an approved `StrategySignal` to the broker.
**Classification:** **READ-ONLY (does NOT consult strategy_json at all)**
**Null behaviour:** unaffected — the executor takes a pre-computed signal
+ Strategy row for credentials/ownership; no DSL evaluation here. Upstream
(webhook + safety guard) decides whether the executor is ever reached.

### 3. `app/strategy_engine/live_orders/order_router.py:397-419`

**Role:** Broker-Execution-Guard subset run on the live-order path —
specifically the stop-loss-present check.
**Classification:** **BLOCKING (fails closed)**
**Null behaviour:**

```py
if not strategy.strategy_json:
    return GuardCheckResult(
        check_name="stop_loss_present",
        passed=False,
        severity="blocking",
        message=(
            "Strategy has no DSL — stop loss verify nahi ho saka. "
            "Phase 5 builder se strategy recreate karo."
        ),
    )
```

Cloned strategies cannot reach the broker. This is desired safety
behaviour — a null-DSL strategy has no defined stop-loss, so live
trading is correctly blocked.

### 4. `app/strategy_engine/api/backtest.py:244-251`

**Role:** the backtest endpoint that powers the Phase D Strategy Tester.
**Classification:** **BLOCKING (HTTP 422)**
**Null behaviour:**

```py
if not strategy_row.strategy_json:
    raise HTTPException(
        status_code=422,
        detail=(
            "Strategy has no DSL configured (legacy row). Recreate it "
            "via the Phase 5 builder to make it backtest-ready."
        ),
    )
```

Cloned strategies cannot be backtested. The frontend's existing
"View Backtest" link gracefully degrades to a disabled CTA (today's
"Backtest unavailable (no DSL)" — replaced by the Phase B patches).

### 5. `app/strategy_engine/api/compliance.py:119, 190, 235`

**Role:** the compliance report endpoints.
**Classification:** **READ-ONLY (fallback to `{}`)**
**Null behaviour:**

```py
strategy_json=row.strategy_json or {},
```

Cloned strategies get a vacuous compliance report — no indicators
detected, no rules applied. Doesn't crash, but the report is
information-free. Acceptable for the Phase 1 launch since the
compliance report panel can render an "Awaiting Strategy Builder
config" state.

### 6. `app/strategy_engine/compliance/aggregate.py:67-100`

**Role:** rolls compliance signals across the user's strategies.
**Classification:** **READ-ONLY (defensive default)**
**Null behaviour:** `json_blob = getattr(row, "strategy_json", None) or {}`.
Same as above — vacuous but non-crashing.

### 7. `app/strategy_engine/compliance/evaluator.py:234, 245, 265, 273`

**Role:** indicator + rule-set extraction for compliance scoring.
**Classification:** **READ-ONLY (`dict.get` semantics)**
**Null behaviour:** with an empty dict input from #5 above, the
`strategy_json.get("indicators")` returns None and the evaluator
short-circuits to "no indicators detected" rather than crashing.

### 8. `app/strategy_engine/api/strategies.py` (CRUD)

**Role:** the GET/POST/PUT/DELETE endpoints for `/api/strategies/{...}`.
**Classification:** **READ-ONLY (pass-through)**
**Null behaviour:** GET returns the column verbatim (None for clones).
POST/PUT require a populated payload from the request body so they
don't apply to the clone path. This is the file Phase B patches.

### 9. `app/strategy_engine/api/schemas.py`

**Role:** Pydantic response model — `StrategyResponse.strategy_json:
dict[str, Any] | None`.
**Classification:** **READ-ONLY (declared nullable)**
**Null behaviour:** explicitly typed nullable. No issues.

### 10. `app/strategy_engine/api/strategy_versions.py`

**Role:** version history endpoints under `/api/strategies/{id}/versions`.
**Classification:** **READ-ONLY but cloned strategies have NO versions**
**Null behaviour:** clone_service does NOT call `create_version()` (compare
with the create-strategy handler at `api/strategies.py:93` which DOES).
So cloned strategies show an empty version list. The
`VersionHistoryPanel` on the detail page degrades cleanly to its empty
state.

### 11. `app/strategy_engine/strategy_versioning/store.py + diff.py + manager.py + models.py`

**Role:** internal version-history machinery.
**Classification:** **READ-ONLY (only reached if a version exists)**
**Null behaviour:** never reached for cloned strategies — no v1 row.

### 12. `app/strategy_engine/api/compare_fix.py`

**Role:** comparison endpoint used by the version-diff modal.
**Classification:** **READ-ONLY (only reached if at least 2 versions exist)**
**Null behaviour:** never reached for cloned strategies.

---

## What this means for cloned-from-template strategies today

| User action | Endpoint hit | Result for clone | Why |
|---|---|---|---|
| Open detail page | `GET /api/strategies/{id}` | renders WRONG legacy warning | bug — Phase B fix |
| Click "View Backtest" | `POST /api/strategies/{id}/backtest` | HTTP 422 "no DSL" | by design |
| Click "Go Live" | webhook + order router | blocked at safety guard | by design |
| Open compliance report | `GET /api/compliance/strategies/{id}` | vacuous empty report | acceptable degraded mode |
| Open version history | `GET /api/strategies/{id}/versions` | empty list | clone_service doesn't seed v1 |
| Edit in builder | `PUT /api/strategies/{id}` | works — accepts new DSL | becomes a normal Phase 5 strategy |

The only WRONG behaviour today is the **detail page's misleading
"pre-Phase-5 legacy" warning** — fixed by Phase B.

---

## Decision: Path 1 vs Path 2

**Path 1** (Phase B/C UX fix): show the template's config_json in the
detail page, set honest "Available with Strategy Builder (Phase 5)"
messaging across the template gallery + clone CTA + detail page. Live
trading + backtesting remain blocked by the existing safety guards
which already give human-readable error messages.

**Path 2** (auto-hydrate at clone time): map `config_json` → `strategy_json`
in `clone_service` so cloned strategies become first-class trading
strategies immediately. Requires defining the bidirectional mapping
between the Phase 1 config_json shape and the Phase 5 StrategyJSON DSL,
which is non-trivial (the formats are NOT isomorphic).

**Choosing Path 1** because:

1. No fallback path exists in the codebase today — Path 2 is fresh
   bidirectional-mapping work that belongs in Phase 7-8 alongside the
   builder's template-import feature.
2. The Phase 1 launch deck positions templates as **"browse + bookmark
   + preview"**, not "instant live trading". Path 1 makes the UI
   match that positioning honestly.
3. The existing safety guards (order router #3, backtest endpoint #4)
   already produce correct human-readable error messages — they're
   "right" for the wrong reason (they think it's a legacy row). The
   message stays correct in spirit; the detail page wrapper just
   needs to acknowledge the new "cloned-but-no-DSL" case.

## Open items handed to Phase B

1. Apply the 3 patches per `PATCH_INSTRUCTIONS_STRATEGY_DETAIL.md`
2. Add the "Available with Strategy Builder" badge per Phase C plan
3. Add tests per Phase D plan
4. NO change to clone_service or any of the BLOCKING callsites (#3, #4) —
   their behaviour is correct, just the detail page's user-facing
   framing needs work

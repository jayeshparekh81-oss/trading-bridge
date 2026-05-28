# Options Support Audit — 2026-05-21

Branch: `main` @ HEAD `3f8dd65` (clean, no uncommitted changes, no stashes)
Scope: `backend/` — read-only inventory. Live BSE LTD futures strategy NOT touched.

---

## Executive Summary

**Overall completion: ~8% (revised from earlier 0% claim)**

The earlier "0% built" estimate was off, but only directionally — there is more scaffolding than expected, but **zero options can actually be traded today**. Every options template in the catalog is explicitly 501-blocked. The execution layer, broker payloads, and scrip-master parser are all options-blind.

- ✅ **Production-ready (options-relevant):**
  - F&O segment routing at broker level (`BFO → BSE_FNO`, `NFO → NSE_FNO`) — `app/brokers/dhan.py:133-134, 358-359`
  - F&O product-type enforcement (NRML/MARGIN, never INTRADAY) — last-chance trap at `app/brokers/dhan.py:991-1003`
  - Templates **catalog** schema with `InstrumentType` enum (CASH/FUTURES/CALL/PUT/MULTI_LEG) — `app/templates/schemas.py:37-42`
  - 63 options templates seeded in catalog (5 CALL + 4 PUT + 54 MULTI_LEG) — `data/strategy_templates_seed.json`

- 🟡 **Skeleton / partial (touched but inert):**
  - `instrument_type` passthrough field on webhook payload (max 32, no enum) — `app/schemas/strategy_webhook.py:123`
  - Pine mapper docstring claims "Phase-1 scope: Future + Options" — `app/services/pine_mapper.py:22` — but no option_type/strike/expiry handling
  - Pack 16 indicators: `atm_strike_distance`, `round_number_attraction`, `expiry_day_volatility_proxy` — all PROXIES over price/range, not real options chain (see `app/strategy_engine/indicators/_pack16_active.py:5-6` "None of those exist yet…")
  - `requires_options_builder=True` on 63 templates → `TemplateNotCloneableError(http_status=501)` — `app/templates/clone_service.py:94-103`

- ❌ **Missing entirely:**
  - No `option_type` / `strike_price` / `expiry_date` field anywhere in `app/` (0 hits, excluding templates `InstrumentType` enum values)
  - No `"CE"` / `"PE"` literals anywhere in `app/`
  - No options migration files (migrations 001–027, none touch options)
  - No `instrument_type` column on `strategies` or `strategy_positions` table
  - No options entries in `OrderRequest` schema (`app/schemas/broker.py:158-186`)
  - No strike-selector / expiry-calculator / options-symbol-builder utility
  - Dhan scrip-master parser drops `SEM_OPTION_TYPE`, `SEM_STRIKE_PRICE`, `SEM_EXPIRY_DATE` columns at parse time (`app/brokers/dhan.py:265-334` extracts only sec_id/symbol/segment/lot_units)
  - No options branches in `strategy_executor.py` (934 lines, 0 hits for option/strike/expiry/premium)
  - No options branches in `direct_exit.py` (621 lines, 0 hits)
  - No options branches in `kill_switch_service.py` (premium-based exit absent)
  - No options-aware Telegram alert templates
  - No options test files in `tests/` (only `test_advisor_optional_inputs.py` which is "optional inputs", not "options")

- 🔍 **Surprise findings:**
  1. The "symbol picker 507 entries" trigger was likely the **scrip-master CSV** loaded at runtime (Dhan publishes thousands of options rows). Code can `lookup(symbol, segment)` and resolve a `securityId`, but cannot reason about strike/expiry. If you hand-construct a symbol like `NIFTY-23MAY26-25000-CE` (assuming Dhan's exact format), the broker call would route correctly — but no upstream code can build that symbol.
  2. 113-template catalog is 56% options templates (63/113) — they appear in `GET /api/templates` and the picker UI, but **every clone attempt returns HTTP 501** with the user-facing message "Options-strategy templates require the options builder which is shipping in Phase 7-8."
  3. Pack 16's "options-aware" indicators (commit `e887cde feat(indicators): Pack 16 - options-aware + Greeks PROXIES`) carry tags=["options"] but their calculations are pure price/range derivatives — `atm_strike_distance` just snaps `close` to the nearest multiple of `strike_step` (default 100). No options chain ingestion.
  4. `MULTI_LEG` exists only as a template instrument_type enum value (54 templates). The codebase's `leg_role` field (in `strategy_executions`) is unrelated — it tags entry/partial/sl execution legs, not multi-leg options structures.
  5. `futures_resolver.py` exists for monthly rollover (`BSE-MAY2026-FUT → BSE-JUN2026-FUT`). **No equivalent options expiry rollover exists.**

---

## Detailed Findings (per area)

### 1. Database & Migrations (~3%)
- `backend/migrations/versions/` — 27 migration files (`001_initial_schema.py` through `027_strategies_is_paper.py`). **None mention options/strike/expiry/CE/PE.**
- `app/db/models/strategy.py:52` — `allowed_symbols` is the only F&O hook (a list); no `instrument_type` column.
- `app/db/models/strategy_position.py:66` — position carries only `symbol: str`; no instrument_type / option_type / strike / expiry / product_type. Product type is resolved per-order at execution, never stored.
- `app/templates/models.py:69` — `instrument_type: Mapped[str]` on `strategy_templates` only (the catalog table, NOT a runtime concept).
- `app/templates/models.py:102-105` — `requires_options_builder: bool` + `legs_count: int | None` columns exist, populated for 63 catalog rows.

### 2. Strategy Execution Layer (0%)
- `app/services/strategy_executor.py` (934 lines) — **zero matches** for option/strike/expiry/premium. The executor treats every symbol as opaque.
- `app/services/pine_mapper.py:22` — docstring claim ("Phase-1 scope: Future + Options") is aspirational only. The actual mapping (`_PINE_TO_NATIVE` at `pine_mapper.py:47-56`) carries ENTRY/PARTIAL/EXIT/SL_HIT × long/short — eight combos, none options-specific. Mapped payload (`pine_mapper.py:134-151`) has no option fields.
- `app/services/direct_exit.py` (621 lines) — zero matches; exit logic identical for futures and (theoretical) options.

### 3. Broker Adapters (~25%)
- `app/brokers/dhan.py:133-134` — `Exchange.NFO → "NSE_FNO"`, `Exchange.BFO → "BSE_FNO"` (segment table).
- `app/brokers/dhan.py:358-359` — `_canonical_segment` alias fallback `NFO/BFO → NSE_FNO/BSE_FNO`.
- `app/brokers/dhan.py:991-1003` — F&O permanent rule trap: rejects INTRADAY for `NSE_FNO`/`BSE_FNO`/`NSE_CURRENCY`/`MCX_COMM`. **Generic enough to route an options symbol if upstream constructs one correctly, but no upstream constructs one.**
- `app/brokers/dhan.py:265-334` (`_ScripMaster._parse`) — **CRITICAL GAP**: parser extracts only `SEM_SMST_SECURITY_ID`, `SEM_TRADING_SYMBOL`, `SEM_INSTRUMENT_NAME`, segment, and `SEM_LOT_UNITS`. **Ignores `SEM_OPTION_TYPE`, `SEM_STRIKE_PRICE`, `SEM_EXPIRY_DATE` columns.** The data is in the CSV but discarded.
- `app/brokers/fyers.py:586` — comment acknowledges "NFO/BFO/MCX/CDS carry the expiry/strike inside the symbol itself" — so Fyers is symbol-as-string too.
- `app/brokers/fyers.py:136-138` — same segment mapping.
- `app/schemas/broker.py:158-186` — `OrderRequest` has no `option_type`, `strike_price`, `expiry`, or `lot_size` field. Symbol-as-string is the contract.

### 4. Symbol & Instrument Master (~10%)
- `app/brokers/dhan.py:218-349` — `_ScripMaster` class: `lookup(symbol, segment) → security_id`, `lot_size(security_id) → int`. Pre-warmed at app startup (`app/main.py:97-107`).
- `app/services/futures_resolver.py:5-17` — month-stamped continuous-future resolver (`BSE-MAY2026-FUT` → active monthly). **No options equivalent.**
- **No strike-selection utility** (ATM/OTM/delta) — searched the entire app/, zero matches.
- **No expiry calculator** (current_week / next_week) — zero matches.
- **No options-symbol builder** (e.g., `(NIFTY, 25000, CE, 23-MAY-2026) → "NIFTY23MAY25000CE"`).
- BSE LTD options specifically: would inherit BFO routing if a properly-formed symbol were supplied, but no code path produces one.

### 5. Webhook & Signal Layer (~5%)
- `app/api/strategy_webhook.py:352-354` — comment acknowledges "every NSE F&O monthly expiry (last Thursday)" — context only, no handler logic.
- `app/schemas/strategy_webhook.py:123` — `instrument_type: str | None = Field(default=None, max_length=32)` — **accepted as opaque passthrough, never validated against an enum, never branched on downstream.** This is the field the founder spotted; it does not do what its name implies.
- `app/schemas/strategy_webhook.py:124-128` — `product_type`, `order_type`, `price`, `signal_id`, `lot_size_hint` — all symbol-agnostic.
- Pine payload validator (`pine_mapper.py:59-65`) only checks `type` has `LONG_/SHORT_` prefix; accepts no option_type field.

### 6. Reconciliation & Kill Switch (0%)
- `app/workers/reconciliation_loop.py:50-67` — `reconcile_once(session)` is symbol-agnostic (filters by `live_trading_enabled` strategies). No options-specific reconciliation.
- `app/services/kill_switch_service.py` — no option / strike / expiry / premium matches. Close logic is generic square-off via broker's `square_off_all`.

### 7. Telegram / Alerts (0%)
- `app/services/telegram_alerts.py` and `app/services/notification_service.py` — no options-aware templates. Alerts emit symbol + side + qty + price. No strike / expiry / premium fields in any template.
- `app/db/models/trade_marker.py:120` — `TradeMarkerType.EXPIRY` enum value exists with comment "option/future expiry close", but no emitter populates it for options today.

### 8. Git History Forensics
- Stash: **empty** (`git stash list` → no entries).
- Options-named branches: `feat/fno-stocks-expansion`, `feat/major-indices-fno-v2`, `feat/drop-nifty-next-50` — all about which **futures contracts** are tradable, not options.
- Options-related commits on `main`:
  - `b1290b2 fix(faq): correct expiry-day-quirks FAQ — weekly options now NIFTY-only` — content/FAQ only
  - `11a2f9d fix(explainers): remove banknifty-weekly-equity — SEBI rationalized to NIFTY-only weekly options` — content only
  - `e887cde feat(indicators): Pack 16 - options-aware + Greeks PROXIES (191 -> 203)` — **the only code-bearing options commit**; adds 3 indicators that proxy options behavior from price data
  - `a4801f4 feat(resolver): date-driven continuous-future resolver for Dhan execution (BSE auto-rollover with 15:30 expiry-day boundary)` — **futures rollover, not options**
- **No pending uncommitted options work anywhere.**

### 9. Test Coverage (0%)
- `tests/strategy_engine/advisor/test_advisor_optional_inputs.py` — false hit; "optional inputs", not "options".
- F&O tests in `tests/test_product_type_fix3.py:101-226` and `tests/test_dhan_broker.py:783` exercise BFO/NSE_FNO routing with **futures symbols only** (`NIFTY25MAY-FUT`, `BSESTOCK-FUT`, `NIFTY25JANFUT`).
- **No `test_options_*.py`** file exists. **No `test_*_option_*.py`** file exists.
- Coverage estimate for options paths: **0%** (no tests target options-specific code because no options-specific code exists).

---

## Realistic Effort Estimate

The blocker is that almost nothing options-specific exists; what exists is misleading scaffolding. The catalog metadata (63 templates) and segment routing are the only real assets. Effort budgets assume one senior engineer:

- **Optimistic (single-leg CE/PE only, no Greeks, no chain):** ~4–5 weeks
  - Scrip-master extension to keep OptionType/Strike/Expiry columns (~3 days)
  - Options-symbol builder + strike/expiry resolvers (~5 days)
  - Webhook + OrderRequest schema additions (`option_type`, `strike`, `expiry`) + executor branches (~5 days)
  - Position/leg model migration + reconciliation update (~4 days)
  - Telegram template variants (~2 days)
  - Tests + 1 paper-trade pilot (~5 days)

- **Pessimistic (multi-leg + Greeks-aware + chain ingestion, matching the 54 MULTI_LEG templates):** ~12–16 weeks
  - All of the above, plus:
  - Multi-leg order orchestration with rollback (legs partial-fill is hard)
  - Options chain ingestion + caching (real-time IV, delta)
  - Margin pre-check per spread (Dhan's bracket margin API)
  - Greeks calculation library + indicator wiring
  - Stress-tested rollover/expiry handling
  - 4-leg condor/strangle backtester wiring

- **Critical-path blockers:**
  1. Scrip-master CSV parser must retain OptionType/Strike/Expiry columns before anything else can be built on top.
  2. `OrderRequest` schema change is invasive — every broker adapter + every test fixture changes.
  3. Position model migration (adding option_type/strike/expiry) must be back-compat with the live BSE LTD futures strategy `89423ecc-c76e-432c-b107-0791508542f0`.

- **Quick wins (1–2 day finishes):**
  1. Validate `instrument_type` webhook field against an enum (CASH/FUTURES/CALL/PUT) — currently it's an unvalidated free-string. (Risk: catches typos before they reach the executor.)
  2. Add a one-line note to `pine_mapper.py:22` clarifying that "Phase-1 scope: Future + Options" is aspirational, not implemented — prevents future readers from being misled.
  3. Surface the 501 message earlier in the picker UI (gate the "Use Template" button), so users don't click through expecting it to work.

- **Ground-up builds needed:**
  1. Options-symbol builder (no precedent in the codebase).
  2. Strike/expiry selector (ATM/OTM/delta-based — needs a chain feed).
  3. Multi-leg order coordinator (no abstraction supports it today).
  4. Greeks / IV calculation layer (Pack 16 proxies are NOT a foundation).
  5. Options-aware Telegram templates.
  6. Options-aware reconciliation (matching legs across broker positions).

---

## Code Gaps Identified

1. **`app/brokers/dhan.py:265-334`** — Scrip-master parser silently drops `SEM_OPTION_TYPE`, `SEM_STRIKE_PRICE`, `SEM_EXPIRY_DATE` columns. **Why it matters:** these are the data anchor for every options feature downstream. Until they are retained, no strike/expiry-aware logic is possible.

2. **`app/schemas/broker.py:158-186`** — `OrderRequest` has no option_type/strike/expiry fields. **Why it matters:** every broker adapter would need to change to receive structured options input rather than a pre-built symbol string. This is the single biggest architectural decision.

3. **`app/schemas/strategy_webhook.py:123`** — `instrument_type` is accepted but never used. **Why it matters:** silently misleading — looks like options support is wired when it is not. Either validate against an enum and branch on it, or remove the field.

4. **`app/services/pine_mapper.py:22`** — Docstring lies. **Why it matters:** new engineers (and the founder) will keep reading this and overestimating options readiness.

5. **`app/db/models/strategy_position.py`** — No instrument_type, no option_type, no strike, no expiry, no leg_index. **Why it matters:** multi-leg positions cannot be represented in the current model; even single-leg options cannot store their defining metadata.

6. **`app/templates/clone_service.py:94-103`** — 63/113 templates blocked behind `HTTP 501`. **Why it matters:** the catalog UX is "look but don't touch" for over half its inventory. Either ship the builder or hide these templates from the picker.

7. **No options test fixtures** anywhere. **Why it matters:** even if the rest were built, there are no canonical CE/PE symbol fixtures, no chain fixtures, no expiry-day fixtures. Test scaffolding from scratch will absorb ~20% of the build effort.

---

## Recommended Next Steps (priority order)

1. **Decide the architectural pattern first** — symbol-as-string (broker-conformant, no structured options field) vs structured option fields (option_type/strike/expiry on OrderRequest, builder constructs symbol). The codebase currently does the first by default; the templates schema implies the second. Pick one and document.
2. **Extend the Dhan scrip-master parser** to retain OptionType/Strike/Expiry columns and expose lookup-by-(underlying, expiry, strike, type). This unblocks every downstream piece. (~3 days, well-scoped.)
3. **Validate `instrument_type` in the webhook** against an enum, even if the executor still rejects options for now. Cheap win that prevents silently-wrong payloads. (~1 day.)
4. **Gate the options templates in the picker UI** — either hide them or label them "Coming Soon — Phase 7-8" before the user clicks. Stops user frustration from the current 501. (~1 day frontend.)
5. **Decide single-leg vs multi-leg as the v1 scope** before any code is written. The 4–5 week vs 12–16 week range is driven entirely by this decision. **Strongly recommend single-leg CE/PE for v1** — the live BSE LTD futures strategy proves the basic pipeline works; single-leg options is the minimum extension. Multi-leg can be Phase 7-8 as currently labeled.
6. **Write the options test fixtures alongside the parser change**, not after. Without them, every subsequent PR will be untestable.

---

## Anomalies / Risk Flags

- **Misleading scaffolding**: `instrument_type` field on the webhook, `Phase-1 scope: Future + Options` docstring on pine_mapper, and Pack 16's "options-aware" tag together create the impression of partial implementation. There is no partial implementation — only naming.
- **Live BSE LTD futures isolation**: the executor's product-type rule (`F&O = NRML, never INTRADAY`, `app/services/strategy_executor.py:597-642`) was hardened by the May 2026 incident series (Bug #3 fixes). Any options work that touches `_resolve_product_type` risks regressing the live strategy. Recommend feature-flagging options paths so the futures path stays untouched.
- **Templates table is committed-but-unusable surface area**: 63 catalog rows that 501 on every clone attempt have been live since `026_add_strategy_templates.py`. This is product debt, not technical debt — it sets a user expectation the product cannot meet.
- **No prior options branch / no stash / no in-progress work**: the founder's recall of "options-related code partially added" is best explained by the templates catalog seed + Pack 16 indicator naming + the webhook `instrument_type` passthrough. There is no orphaned options branch hiding elsewhere; all three are on `main` today and visible in this audit.
- **Scrip-master pre-warm at startup** (`app/main.py:107`) loads the full Dhan CSV including options rows, so the in-memory cache *does* contain options entries — but with strike/expiry/optionType fields discarded, only the symbol-string lookup works. Confirms the "507 F&O entries" finding while clarifying it is data without semantics.

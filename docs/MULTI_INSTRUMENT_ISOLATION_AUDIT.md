# Multi-Instrument Isolation Audit

- **Date:** 2026-06-28
- **Status:** Design-phase reference. Read-only audit — nothing built from this yet.

> **Live BSE / CDSL / ANGELONE FUTURES (`is_paper=false`) must stay byte-for-byte untouched.** This document maps where instrument-type is (and isn't) decided so a future cash/option pipeline can be fully isolated from the live futures execution path.

---

## PART 1 — Audit: where instrument-type is decided

### Headline
There is **no instrument-type column** anywhere. "It's futures" is enforced structurally by the executor passing **`Exchange.NFO` as a constant** at every call site, which then forces NRML. That hardcode is the isolation seam.

### 1. The `Exchange.NFO` hardcode chokepoint
The live path does not *read* instrument type — it *hardcodes* it. Every executor/exit call site passes `exchange=Exchange.NFO`:
- `strategy_executor.py:232` (entry)
- `direct_exit.py:257, 429, 607` (exits)
- Comment at `strategy_executor.py:216-218`: *"pass Exchange.NFO … current TRADETRI is F&O-only; multi-exchange routing is a separate epic."*

Broker layer (`dhan.py`) already has the vocabulary for other instruments — `ProductType{INTRADAY, DELIVERY=CNC, MARGIN, BO, CO}`, `Exchange→segment{NSE_EQ, BSE_EQ, NSE_FNO, BSE_FNO, MCX_COMM, NSE_CURRENCY}` — so cash and options are *representable* at the broker, but never *reached* from the live path.

### 2. `_resolve_product_type` (incl. the dead equity branch)
`strategy_executor.py:682-715`:
```python
_FNO_EXCHANGES = frozenset({Exchange.NFO, Exchange.BFO, Exchange.CDS, Exchange.MCX})
_FORBIDDEN_FNO_PAYLOAD_PRODUCT_TYPES = frozenset({"INTRADAY", "MIS"})

def _resolve_product_type(signal, exchange: Exchange = Exchange.NFO) -> ProductType:
    raw = str((signal.raw_payload or {}).get("product_type") or "").upper()
    is_fno = exchange in _FNO_EXCHANGES
    if is_fno:
        if raw in _FORBIDDEN_FNO_PAYLOAD_PRODUCT_TYPES:
            raise InvalidProductTypeError(...)        # permanent rule 1
        return ProductType.MARGIN                     # F&O → NRML, regardless of payload
    # Equity path — payload wins; default DELIVERY (CNC)
    if not raw:
        return ProductType.DELIVERY
    return _PRODUCT_TYPE_FROM_PAYLOAD.get(raw, ProductType.DELIVERY)
```
- F&O → always MARGIN (NRML); INTRADAY/MIS payload → `InvalidProductTypeError` (permanent rule 1, incident 2026-05-20).
- **The equity branch (`DELIVERY`/`CNC`) already exists but is UNREACHABLE** in the live path — it only fires if a caller passes a non-NFO exchange, and no caller ever does. This is both a footgun (a future caller could silently route equity through the same executor) and a latent capability.
- Defense-in-depth: `dhan.py:1280-1285` also traps INTRADAY for F&O (3-layer enforcement).

### 3. Strategy model / webhook instrument fields
- **`strategy.py` (Strategy model): NO `instrument_type` / `product_type` / `asset_type` / `segment` column.** Only `strategy_json` JSONB (which *can* nest an `"options"` block) + `allowed_symbols`. Instrument type is **implicit-futures**.
- **Webhook payload:** `schemas/strategy_webhook.py:123-124` accepts optional `instrument_type` and `product_type`. `product_type` *is* consumed (by `_resolve_product_type` via `raw_payload`); **`instrument_type` is accepted but NOT consumed by execution routing** (only `pine_mapper.is_options_strategy` reads a forward-compat `getattr(strategy, "instrument_type")` that does not exist as a column yet).
- `templates/` carry an `instrument_type` enum, but as **catalog metadata only** — not wired to execution.

### 4. `futures_resolver` — assumes futures
Futures-specific. Continuous notation (`BSE1!`) → month-stamped `BSE-MAY2026-FUT`; `_CANONICAL_FUT_RE = ^([A-Z][A-Z0-9]*)-[A-Z]{3}\d{4}-FUT$` matches **only `-FUT`**; everything else **passes through unchanged** (`resolve_or_passthrough`). Not instrument-aware — cash symbols would pass through untouched; options use a separate resolver (`pine_mapper`).

### 5. Existing options Phase-2B scaffold (dormant, paper-only)
- `pine_mapper.py`: `resolve_atm_strike`, `resolve_strike`, `resolve_options_expiry`, `resolve_option_type` (CE/PE), and the **instrument decision point** `is_options_strategy(strategy)` (`:469-483`): detection order = explicit `instrument_type` attr → `strategy_json.instrument_type == "options"` → presence of a `strategy_json.options` block.
- `schemas/pine_webhook.py`: `PineAlertPayload.spot_price`, `OptionsConfig`, `StrikeSelection`, the **NRML carry-forward mandate**, `_FORBIDDEN_PRODUCTS = {MIS, INTRADAY}`.
- `indicators/calculations/atm_strike_distance.py`; scrip-master option-triplet parsing in `dhan.py`.
- Options still route via **`Exchange.NFO` / `BFO` → NRML** (inherit the underlying's F&O segment). Roughly half-built; paper-only; not flipped on.

### 6. Cash / equity = NO execution path
There is **no cash execution path**. Only latent pieces exist: the unreachable `DELIVERY`/`CNC` branch in `_resolve_product_type` + broker `NSE_EQ`/`BSE_EQ` segments. A cash pipeline is a ground-up build.

### Isolation summary
The live futures path is well-isolated *by accident of being hardcoded*. Three structural facts protect it: (1) the `Exchange.NFO` constant at the executor call sites; (2) the dead equity branch (reachable only via a non-NFO exchange that nobody passes); (3) no instrument-type decision exists for cash today. The clean design is to branch on instrument-type **above** `place_strategy_orders` and give cash/options their own executor + resolver, leaving the NFO-hardcoded futures call sites and `futures_resolver` byte-for-byte untouched.

---

## DECISIONS & DESIGN (2026-06-28)

- **Status:** Design-phase. Read-only audit. Nothing built.

> **Live BSE/CDSL/ANGELONE FUTURES (`is_paper=false`) must stay byte-for-byte untouched. All real-money multi-instrument work is GATED on SEBI clarity; Stage 1 = paper only.**

### Founder decision
- Support **THREE instrument types for subscribers: Cash / Option / Future.** Founder's call — lets small-capital customers pick affordable instruments and upgrade as confidence grows.

### Instrument reality (effort + risk)
- **FUTURES:** done, live, tested — **DO NOT TOUCH.**
- **OPTIONS:** ~half-built dormant Phase-2B scaffold exists (strike/expiry/CE-PE resolvers, `is_options_strategy`, `pine_webhook` schema), **paper-only**, routes via **NFO → NRML**. Needs completion + paper testing.
- **CASH:** **zero execution path.** Ground-up build required. **HARDEST** — the source strategies short, but a cash short isn't deliverable → **cash = LONG-ONLY** (a different, untested strategy shape).

### Isolation architecture (protects live futures)
- **Branch on instrument-type ABOVE `place_strategy_orders`** — an explicit instrument-router at routing time, **BEFORE** the executor.
- Futures call sites **keep passing the `Exchange.NFO` constant — NEVER parameterized by data.** Cash/options get their **OWN executor entry + resolver.**
- Live futures strategies (no `instrument_type`, no `options` block) **deterministically fall through to the existing NFO path, unchanged.**
- `futures_resolver` left **byte-for-byte untouched**; options use the separate `pine_mapper` strike/expiry resolver; cash needs its own.

### Build order (lowest-risk)
1. **Isolation / instrument-router layer first** — so futures stays 100% separate + provably safe.
2. **Options next** — complete the dormant scaffold; it's partly built and F&O-adjacent.
3. **Cash last** — ground-up, long-only; hardest.
4. **All paper-validated; real-money only post-SEBI.**

### RISK FLAGS (honest record)
- Running cash/option logic on strategies originally calibrated for **FUTURES is UNTESTED** — customer-money risk. Each instrument needs **separate ground-up validation** before ANY real-money use. **NOT** a "drop the same strategy onto cash/option" shortcut.
- **Cash = long-only** loses the strategy's short engine → effectively a **different strategy**; must be tested as such.
- **Options theta-decay** materially changes the drawdown profile (founder-noted) → requires its own backtest/forward-test.
- These are flagged so the decision is **on record as informed.**

### Open design questions
- **Options:** which strike/expiry rule maps a futures-style signal (ATM? OTM? weekly/monthly?) — partly answerable from the existing `pine_mapper` resolvers.
- **Cash:** how is long-only entry/exit defined when the source strategy assumes futures long + short?
- **UX:** customer instrument-choice flow + clear Cash/Option risk warnings at subscribe time.

---

## Key files

- Executor chokepoint: `backend/app/services/strategy_executor.py` (`place_strategy_orders:119`, `Exchange.NFO` call site `:232`, `_resolve_product_type:682-715`, `_FNO_EXCHANGES:662`)
- Exit path: `backend/app/services/direct_exit.py` (`Exchange.NFO` + `_resolve_product_type` at `:257, 429, 607`)
- Broker product/segment maps: `backend/app/brokers/dhan.py` (`_PRODUCT_TO_DHAN:116`, `_EXCHANGE_TO_DHAN_SEGMENT:132`, F&O trap `:1280-1285`)
- Strategy model (no instrument column): `backend/app/db/models/strategy.py` (`strategy_json:89`)
- Webhook payload fields: `backend/app/schemas/strategy_webhook.py:123-124` (`instrument_type`, `product_type`)
- Futures resolver: `backend/app/services/futures_resolver.py` (`_CANONICAL_FUT_RE:102`, `resolve_or_passthrough:211`)
- Options scaffold: `backend/app/services/pine_mapper.py` (`resolve_atm_strike:306`, `resolve_strike:320`, `resolve_options_expiry:363`, `resolve_option_type:419`, `is_options_strategy:469`); `backend/app/schemas/pine_webhook.py` (`OptionsConfig`, `StrikeSelection`, `_FORBIDDEN_PRODUCTS`); `backend/app/strategy_engine/indicators/calculations/atm_strike_distance.py`

---

*Read-only audit + design decisions. Source: code trace of `main` (== `origin/main`) on 2026-06-28. Nothing in this document has been built or deployed. Companion to `docs/FANOUT_ARCHITECTURE_AUDIT.md`.*

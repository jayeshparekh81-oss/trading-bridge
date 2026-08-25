# SIGNAL CONTRACT — what to POST to reuse the existing execution core

**Purpose:** the exact recipe for a non-TradingView caller (e.g. the Python engine) to feed
signals into the live TRADETRI pipeline **without rebuilding anything**. Every claim below is
code-verified on branch `docs/stale-copy-cleanup`, file:line cited. READ-ONLY audit — nothing was
modified.

---

## 1. ENDPOINT

```
POST https://api.tradetri.com/api/webhook/strategy/{webhook_token}
Content-Type: application/json
```
- Route: `backend/app/api/strategy_webhook.py:128-142` (`@router.post("/strategy/{token}")`).
- Mounted: `backend/app/main.py:257` (prefix `/api/webhook`). **This is the live path.**
- The legacy `POST /api/webhook/{token}` (`webhook.py`) is a different, older receiver — mounted
  only when `strategy_paper_mode=False` (`main.py:255`) and it self-503s in paper mode
  (`webhook.py:119-131`). **Do not target it.**
- `{webhook_token}` is a 43-char opaque token that identifies user + strategy (see §5).

---

## 2. PAYLOAD SCHEMA

Two accepted shapes. The server auto-detects **Pine** format by the presence of a `type` field
starting `LONG_`/`SHORT_` (`pine_mapper.py:86-91`); anything else is parsed as **native**.
**Recommendation for the Python engine: send the NATIVE shape** — fewer moving parts, no mapper
translation, and `quantity` is unambiguous.

### 2a. Native shape (canonical) — `schemas/strategy_webhook.py:55-190`

| Field | Type | Req | Notes |
|---|---|---|---|
| `action` | `ENTRY`\|`PARTIAL`\|`EXIT`\|`SL_HIT` (+legacy `BUY`/`SELL`) | **yes** | `strategy_webhook.py:30-45` |
| `symbol` | str 1-64 | **yes** | **uppercased at the boundary** (`:137-146`); must be Dhan's canonical name (§6) |
| `side` | `long`\|`short` | **yes** except when using BUY/SELL alias | required for ENTRY/PARTIAL/EXIT/SL_HIT (`:148-180`) |
| `quantity` | int >0 ≤100000 | **ENTRY only** | interpreted per `quantity_unit` |
| `quantity_unit` | `contracts`\|`lots` | no (default `contracts`) | `lots` ⇒ executor multiplies by resolved lot_size (`strategy_executor.py:489-505`) |
| `close_pct` / `closePct` | float (0,99] | **PARTIAL only** | `close_qty = floor(open_qty × pct/100)` rounded down to lot multiple |
| `price` | number ≥0 | no | paper-mode fill price |
| `order_type` | str | no (default `market`) | |
| `product_type` | str | no | send `MARGIN`/`NRML` for carry-forward; **F&O + INTRADAY is hard-rejected** (`dhan.py:1284-1296`) |
| `instrument_type` | str | no | informational, stored in `raw_payload` |
| `signal_id` | str ≤128 | no | informational |
| `lot_size_hint` | int >0 | no | paper-mode sizing hint (live reads the real lot size from the broker) |
| `timestamp` | str | **strongly recommended** | **load-bearing for the duplicate guard — see §6.2** |
| `indicators` | object | no | opaque; stored for AI validator/audit |
| `score` | float | no | **if present, it is USED as the AI score** (§4.3) |

Unknown fields are dropped (`extra="ignore"`, `:70`).

**ENTRY example (native, what the Python engine should send):**
```json
{
  "action": "ENTRY",
  "side": "long",
  "symbol": "BSE-AUG2026-FUT",
  "quantity": 750,
  "quantity_unit": "contracts",
  "product_type": "MARGIN",
  "order_type": "market",
  "price": 3532.8,
  "score": 72.5,
  "signal_id": "pyengine-2026-08-01T10:15:00+05:30-L1",
  "timestamp": "2026-08-01T10:15:00+05:30"
}
```

**EXIT example** (quantity/close_pct ignored — always closes the full remainder):
```json
{
  "action": "EXIT",
  "side": "long",
  "symbol": "BSE-AUG2026-FUT",
  "price": 3560.0,
  "signal_id": "pyengine-2026-08-01T14:30:00+05:30-X1",
  "timestamp": "2026-08-01T14:30:00+05:30"
}
```
*PARTIAL:* same as EXIT plus `"action": "PARTIAL", "closePct": 50`.

### 2b. Pine v4.8.1 shape (what TradingView sends today) — `pine_mapper.py:1-200`
`{"action": "ENTRY|PARTIAL|EXIT", "type": "LONG_ENTRY|SHORT_ENTRY|LONG_PARTIAL|SHORT_PARTIAL|LONG_EXIT|SHORT_EXIT|LONG_SL|SHORT_SL", "qty": <LOTS>, "closePct": …, "indicators": {…17 keys…}, "score": …, "timestamp": …}`
Mapping table `pine_mapper.py:80-84`; note `("EXIT","LONG_SL") → SL_HIT`. **Pine `qty` is in LOTS**
— the mapper tags `quantity_unit="lots"` (`:181`). Pine may omit `symbol` (falls back to
`strategy.allowed_symbols[0]`, `:243-256`).

**The TV alert template actually in use** (`docs/tradingview_alert_setup.md:40-51`) is the
*native* shape with a hardcoded dated contract and `quantity` in **total contracts**.

---

## 3. AUTH — what is ACTUALLY enforced

**Today the URL token is the only credential required.** `webhook_require_hmac` defaults **False**
(`config.py:367`), and in that branch the handler simply strips any stray `signature` field and
proceeds (`strategy_webhook.py:262-266`).

If `webhook_require_hmac=True` (env-set; prod value UNVERIFIABLE-LOCALLY):
1. **TradingView egress-IP bypass** — requests from the six configured CIDRs
   (`34.212/16, 34.213/16, 35.89/16, 52.32/16, 52.89/16, 54.218/16`, `config.py:345-353`) skip
   HMAC entirely (`strategy_webhook.py:224-233`). *A non-TV caller will NOT match these.*
2. Otherwise **HMAC required**, either:
   - header `X-Signature: <hmac_sha256(raw_body, webhook_hmac_secret)>`, or
   - a `"signature"` field in the JSON body, verified against the canonical re-serialization
     `json.dumps(payload, sort_keys=True, separators=(",",":"))` (`:246-252`).
   - Missing both ⇒ 401 (`:253-259`).

**⚠️ This is the "HMAC gap" — confirmed: with the default config the endpoint is
URL-token-only.** For the Python engine: send the token in the URL; add `X-Signature` **only if**
the flag is on in prod (worth confirming before go-live — see §7).

Other gates every caller must pass (in order, `strategy_webhook.py:159-370`): platform-halt →
token lookup → **rate limit 60/min per user** → JSON parse → HMAC (above) → **Redis idempotency
(60s content-hash)** → kill-switch → user active → max-daily-trades → strategy resolve →
**market-hours 09:15–15:25 IST (403 outside; bypassed ONLY for paper strategies)** → qty ceiling
10 000.

---

## 4. FLOW — payload → Dhan order

1. **Webhook** validates + persists a `StrategySignal` row (`:510-522`), then dispatches to Celery
   (`:658-671` → `tasks/signal_execution.py:814`). *(Note: this path writes `strategy_signals`,
   not `webhook_events`.)*
2. **Celery** `execute_signal_async` on a shared persistent event loop
   (`signal_execution.py:87`, `core/async_bridge.py:96`). Same-fire duplicate guard matches on
   `raw_payload["timestamp"]` over a 24 h lookback (`:149-189`) — see §6.2.
3. **AI validator** (`services/ai_validator.py`): `LONG ≥85 → 4 lots`, `≥51 → 2 lots`, else
   REJECT; `SHORT ≥51` (`:61-63, 331-353`). **Score precedence: an inbound `score` in the payload
   is used as-is; the server's `compute_score` is only a fallback** (`ai_validator.py:411-412`,
   `pine_mapper.py:123-141`). Runs only when `strategy.ai_validation_enabled` (model default
   True). **A signal scoring <51 is rejected before any order.**
4. **Executor** (`services/strategy_executor.py`): `paper_mode = resolve_paper_mode(strategy)`
   (`:158`) — **per-strategy `is_paper` wins; global `strategy_paper_mode` (default True) is the
   fallback** (`paper_mode_resolver.py:34-48`). Requires `strategy.broker_credential_id`
   (`:160-163`). Quantity = `min(AI_reco, strategy.entry_lots) × lot_size` (`:485`); whole-lot and
   even-lot validation; `quantity_unit="lots"` triggers the ×lot_size conversion (`:489-505`).
5. **Order** `_live_place_order` (`:848`): session check → symbol probe → funds floor ×1.10 →
   per-signal broker idempotency claim → `broker.place_order` → Dhan `POST /orders` v2
   (`brokers/dhan.py:620, 1299-1316`). Product type forced **MARGIN/NRML** for F&O; INTRADAY
   raises (`dhan.py:1284-1296`).

**Where the real-order decision is gated:** ① `strategy.is_paper` (per strategy row) ②
`settings.strategy_paper_mode` (global fallback) ③ AI validator ≥ threshold ④ kill-switch /
max-daily-trades / market-hours ⑤ funds check. `execution_mode` is a **marketplace-subscription**
field only — it plays no part in this owner path (and subscriber fan-out is flag-off and
paper-forced anyway).

---

## 5. STRATEGY IDENTITY — how the payload says "which strategy"

**It doesn't. The URL token does.** There is no `strategy_id`/name field in the payload.
`(user_id, webhook_token_id, is_active=True) → exactly one Strategy row`
(`strategy_webhook.py:747-756`). That row carries `broker_credential_id` → the Fernet-encrypted
Dhan credential used for the order.

⇒ **BSE / CDSL / ANGELONE are distinguished purely by which token URL you POST to.** One token =
one strategy = one instrument's plumbing. `symbol` in the payload must agree with that strategy's
instrument; it is not used to select the strategy.

*(For reference: those three are the `s1/s2/s3` showcase codes — `s1=BSE 89423ecc`,
`s2=CDSL 0252e82c`, `s3=ANGELONE`; `showcase_api.py:35-39`.)*

---

## 6. TV-SPECIFIC COUPLING a non-TV caller must satisfy

1. **Symbol must be Dhan-canonical, dated.** `BSE1!` does NOT resolve in Dhan's scrip master
   (`docs/tradingview_alert_setup.md:36-40`). Either send the exact contract
   (`BSE-AUG2026-FUT`) or send a root the resolver knows — `_TV_ROOT_TO_DHAN_ROOT`
   (`services/futures_resolver.py:84-97`) maps `{NSE:BSE, BSE:NSE, BSE, BSE1!}` (and the CDSL /
   ANGELONE equivalents) to the live front month via real `SEM_EXPIRY_DATE`, rolling at 14:30 IST
   on expiry day. **Sending a root is safer than hardcoding a month** — the resolver handles the
   roll. Unknown symbols pass through unchanged (and will fail at the broker).
   **EXIT/PARTIAL are never re-resolved** — they pin to the open position's stored symbol
   (`strategy_webhook.py:399-428`), so the exit symbol you send is effectively advisory.
2. **`timestamp` is load-bearing.** The duplicate guard treats *the same `timestamp` value* as the
   same fire for 24 h (`signal_execution.py:149-189`). Emit a **unique per-fire** timestamp
   (ISO-8601). Reusing one silently suppresses a legitimate later entry; omitting it weakens the
   guard.
3. **60-second content-hash idempotency** (`strategy_webhook.py:270`): two byte-identical bodies
   inside 60 s ⇒ the second is silently absorbed. Vary `signal_id`/`timestamp` for genuine
   repeats.
4. **Market-hours 403** for non-paper strategies outside 09:15–15:25 IST — a live strategy cannot
   be exercised off-hours (`:352-370`).
5. **Rate limit 60/min per user**; `quantity ≤ 10 000`; whole-lot and (for partial-profit
   strategies) **even-lot** sizing or the executor rejects.
6. **Quantity unit**: native default is **contracts**. Send `quantity_unit:"lots"` only if you
   mean lots. Getting this wrong is a silent ×lot_size (e.g. ×375) sizing error.
7. **Score semantics**: if you send `score`, it *bypasses* the server's own scoring and is judged
   against the 51/85 thresholds directly. Omit it to let the server compute one.
8. **No `strategy_id` field** — identity is the token (§5). Sending one is ignored.

---

## 7. UNCERTAIN / TO CONFIRM BEFORE WIRING
- **`webhook_require_hmac` value in prod** — code default False (URL-token-only). If prod sets it
  True, the Python engine must sign (§3) since it won't hit TV's IP allowlist.
  **UNVERIFIABLE-LOCALLY.**
- **`strategy.is_paper` for the target strategy** — decides paper vs real order.
  **UNVERIFIABLE-LOCALLY** (prod DB).
- **The token value itself** — 43-char secret, per strategy; not in the repo.
- `ai_validation_enabled` per strategy row (model default True) — if on, sub-51 scores never
  reach the broker.
- Whether `strategy.entry_lots` (the ceiling) matches the size the engine intends — the executor
  takes `min(AI_reco, entry_lots)`, so a low `entry_lots` silently caps the order.

---

### TL;DR recipe
`POST /api/webhook/strategy/<token>` with a native JSON body: `action`, `side`, `symbol`
(Dhan-canonical or a known root), `quantity` (contracts, ENTRY only), optional
`product_type: "MARGIN"`, `price`, `score`, and a **unique `timestamp`**. Auth = the token in the
URL (add `X-Signature` only if HMAC is enforced in prod). Everything downstream — AI validation,
sizing, NRML enforcement, idempotency, kill-switch, exits, reconciliation — is already built and
runs unchanged.

---

## 8. RUNNING-IMAGE VERIFICATION (2026-08-04) — supersedes the body where they differ

The body above was built from FILE reads on a checkout. This section is the re-verification
against the **running container** (founder order, S4 item 5): exec into
`trading_bridge_backend`, image `421d844b` (built 2026-07-20; container restarted 2026-07-31
17:22 UTC, same image, 0 restarts since). **All 14 cited files are md5-identical inside the
container** to `main@2b909c5`, which is byte-identical to this doc's checkout
(`docs/stale-copy-cleanup`) for every cited file — so every §1–§6 file:line claim was checked
against exactly the deployed bytes. Runtime values were read from the running `get_settings()`.
**RE-VERIFY THIS SECTION AFTER EVERY PLATFORM DEPLOY** — it pins an image, and images get
rebuilt (pine_replica/PREARM_HARDENING.md H6).

**Divergences found (body stands corrected by this list):**

1. **§3 field name wrong.** The TV-IP allowlist setting is `tradingview_trusted_ips`
   (`config.py:345`), not `tradingview_ip_ranges`.
2. **§3 effective CIDRs differ from the cited ones.** The six `/16`s in the body ARE the code
   default in the deployed image, but **prod env overrides them with ten broader blocks**
   (34.208/12, 35.80/12, 44.224/11, 52.24/13, 52.32/11, 52.88/13, 54.184/13, 54.200/13,
   54.212/14, 54.218/15). Dormant today (HMAC off), but §3's description of the HMAC-on branch
   is not what prod would actually do.
3. **§7 open items CLOSED (2026-08-04).** `webhook_require_hmac = False` **confirmed in the
   running container** (env included), no longer "code default, UNVERIFIABLE-LOCALLY".
   URL-token-only is the live auth. `strategy_paper_mode = True` confirmed live, and the
   per-row override was **executed in the deployed environment** (not file-read):
   `resolve_paper_mode(is_paper=False) → False` with the running settings — a signal to
   89423ecc places a **REAL order** (`_live_place_order`, deployed `:225`); the global flag's
   only effects on this path are elsewhere (legacy receiver unmounted, live-orders API
   refused, position poll loop off). Live row pin (read-only DB read):
   `89423ecc: is_paper=f, is_active=t, ai_validation_enabled=t, entry_lots=2` —
   `ai_validation_enabled=TRUE` today, see divergence 4 and PREARM_HARDENING.md H8 (hard
   blocker: must be flipped FALSE before the bridge arms).
4. **§4.4 sizing precedence is incomplete, and it matters for the Python engine.** Deployed
   `_resolve_quantity` (`strategy_executor.py:444-519`): **when `ai_validation_enabled` and the
   validator approves, the payload's `quantity` is IGNORED** — the brain's tier decides
   (`min(AI_reco, entry_lots) × lot_size`, `:485-486`). Sending `quantity: 750` with a score
   that lands ≥85 gets you **4 lots (1500 contracts), not 750**. Only with AI off (or no
   recommendation) does payload quantity win — and an over-ceiling quantity then **RAISES
   loudly** (`:499-513`), it is not silently min-capped; §7's "silently caps" applies to the
   AI branch only. Before S5: pin `ai_validation_enabled` for the target strategy and decide
   score policy accordingly.
5. **§5 parenthetical: s3 is not bound.** Deployed `showcase_api.py:35-39` maps `s3 → None`
   (no live strategy), not ANGELONE.
6. **Citation nits (content correct, pointer off):** the action enum lives in
   `schemas/strategy_webhook.py:30-45` (the table cites the api file); `extra="ignore"` is at
   schemas `:74`, not `:70`.
7. **Verified nuance worth pinning:** the market-hours gate is **hardcoded**
   `_MARKET_CLOSE = time(15, 25)` (`api/strategy_webhook.py:96-97`). A runtime settings pair
   `market_open_time=09:15 / market_close_time=15:30` EXISTS but the webhook gate never reads
   it — do not "verify" the gate against that knob. (This also re-confirms the 15:15-carry
   premise: the gate closes at 15:25, before the 15:15 bar completes at 15:30.)

**Everything else checked exact against the deployed bytes:** route + mounts (§1), the legacy
receiver's conditional mount + self-503, the full §2a schema (incl. `close_pct` (0,99] with the
`closePct` alias, symbol uppercased at schemas `:143-146`), the HMAC block (`:223-264`, both
branches strip a stray `signature`), 60 s content-hash idempotency **before** the business
gates (`:267-275`), the §3 gate order, the 10 000-contract ceiling, StrategySignal persisted at
`:510` (i.e. a 403 leaves NO server-side row — the sender's durable sink is the only trace),
dispatch via `dispatch_signal` (`signal_execution.py:814`), exit/PARTIAL pinning to the stored
position symbol (`:406-424`), every §2b Pine-mapper claim, AI thresholds 51/85 + payload-score
precedence (`ai_validator.py:411-412`), the 24 h same-`timestamp` duplicate guard, the F&O
INTRADAY hard-reject (`dhan.py:1284-1296`) and `POST /orders` v2 (`:620-622`), the
futures-resolver root map, and `paper_mode_resolver` precedence.

# Queue — BSE Futures Symbol-Resolution Fix (scoped plan)

**Status:** PLAN ONLY. No code changed by this doc. Branch `docs/queue-bse-symbol-fix`.

## Root cause (confirmed live 2026-06-01)
Production Pine alerts for the live BSE strategy `89423ecc` carry an **explicit
expired contract** in `raw_payload.symbol` — e.g. `"BSE-MAY2026-FUT"`. The
`futures_resolver` only **rolls continuous aliases** (`BSE1!` / `NSE:BSE` →
front month); it **passes explicit months through unchanged**. The expired
contract is **gone from Dhan's scrip master**, so the order router's
`get_security_id()` raises:

```
resolve_or_passthrough('BSE-MAY2026-FUT') -> 'BSE-MAY2026-FUT'   (no roll)
get_security_id('BSE-MAY2026-FUT')        -> BrokerInvalidSymbolError:
                                             "Symbol 'BSE-MAY2026-FUT' not found in Dhan scrip master"
```

The order **dies at symbol→security_id, before any `POST /orders`**. This is the
real "no execution" cause (same class as the 2026-05-14 `NSE:BSE not found`
failure) — **not** auth, IP, margin, idempotency, or the credential-casing bug.
The rest of the pipeline is healthy: token valid (`/fundlimit` 200), AI approves,
executor builds MARKET / MARGIN(NRML) / 375 when fed a *resolvable* symbol.

## 🔴 Sacred constraints (apply to every phase)
- `futures_resolver.py` feeds the **live order path** — surgical changes only,
  full test suite, founder-gated deploy. Touching it = touching execution.
- **F&O = NRML/MARGIN only.** No change to product-type logic.
- Do **not** modify `strategy_executor`, `direct_exit`, `strategy_webhook`,
  `kill_switch`, broker adapters beyond what each phase scopes.
- No market-hours deploys. Branch only; founder gates each deploy.
- Live strategy `89423ecc` is real money — verify `is_paper` state before any
  test that could place an order.

---

## Phase 1 — Observability FIRST (root cause visibility, zero behaviour change)
**Goal:** make symbol-resolution failures *loud and countable* so this class of
silent failure can never hide for months again. **Lowest risk — no logic change.**

- **Structured warning** at the resolver / router boundary when a symbol fails to
  map to a `security_id`: log `symbol`, `resolved`, `underlying`, `reason`,
  `strategy_id`, `signal_id` at WARNING (not swallowed).
- **Metric/counter** `order.symbol_resolution_failure` (Prometheus) labelled by
  underlying + reason, so a dashboard/alert can fire on the first failure.
- **Telegram operator alert** on resolution failure (the operator-alert path
  already exists) — "signal dropped: `<symbol>` not in scrip master".
- **Signal-status fidelity:** ensure `strategy_signals.status='failed'` +
  `notes` already capture the reason (they do today — verify and surface it in
  the UI / a `/me/signals` view).
- **Backfill check:** a one-off read-only report counting historical
  `status='failed'` signals by reason (we already know: Invalid-IP, symbol).

*Risk: NONE (logging/metrics only). Ship first, independently.*

---

## Phase 2 — Option 1: fix the signal source (root-cause, low-risk)
**Goal:** Pine/TradingView sends the **continuous** alias the resolver already
rolls correctly, so explicit months never reach the backend.

- **Pine alert change (primary):** emit `ticker = "BSE1!"` (or `NSE:BSE`) instead
  of the explicit `BSE-MON2026-FUT`. This is a **signal-source/config change**,
  not backend code — the resolver already maps `BSE1!` → `BSE-JUN2026-FUT`/62395
  (verified). Apply the same to every F&O underlying in use (NIFTY, BANKNIFTY,
  CDSL, etc.).
- **Backend guard (defensive, scoped to webhook validation, NOT the resolver):**
  when an incoming payload symbol is an **explicit dated future that is absent
  from / expired in the scrip master**, reject early with a clear
  `failed` status + the Phase-1 alert, rather than failing deep in the adapter.
  This keeps the failure legible without changing resolution behaviour.
- **Docs:** update the strategy/alert authoring guide — "F&O alerts MUST use the
  continuous alias (`BSE1!` / `NSE:BSE`); never hard-code an expiry month."

*Risk: LOW. The backend change is webhook-side validation only; the resolver is
untouched. The Pine change is external. Ship after Phase 1.*

---

## Phase 3 — Option 2: resolver safety-net (careful, guardrailed)
**Goal:** even if an explicit *expired* month slips through, roll it to the
active front month instead of dying — but with strict guardrails so it never
rolls into the wrong instrument.

**Behaviour:** in `futures_resolver`, when the payload symbol is an explicit
dated future (`<ROOT>-<MON><YYYY>-FUT`) AND that exact contract is **absent from
the scrip master or past its expiry**, roll to the **active front month for the
same root** (the same logic continuous aliases already use).

**🛡️ Guardrails (all must hold, else passthrough + loud WARNING — never guess):**
1. **Same root + same instrument type only** — never cross underlyings; never
   turn a FUT into an option or vice-versa.
2. **Only roll when the explicit contract is genuinely gone/expired** — if the
   exact contract still exists in the scrip master, pass it through unchanged
   (respect an intentional explicit month).
3. **Bounded roll** — only to the *nearest active* contract for that root; never
   skip months or pick an arbitrary far contract.
4. **Loud + attributable** — emit a structured `futures_resolver.explicit_roll`
   WARNING (original, resolved, reason, days_to_expiry) and a metric, so an
   auto-roll is always visible (it's a safety net, not a silent default).
5. **Never roll into a contract whose lot size differs unexpectedly** without
   flagging (BSE lot changed 375→200 across months — a roll must surface the new
   lot so qty math stays correct).
6. **Fail-closed** — any ambiguity (multiple candidates, unparseable month) →
   passthrough + WARNING, never a guess.

**Tests (must accompany):** expired-explicit → rolls to front month; live-explicit
→ unchanged; unknown root → passthrough+warn; cross-type → never; lot-size-change
surfaced. Extend the existing `futures_resolver` test suite (45+ tests) — do not
rebuild it.

*Risk: MEDIUM (touches the live resolver / order path). Ship LAST, founder-gated,
behind the guardrails, with the Phase-1 observability already in place to watch it.*

---

## Rollout order & rationale
1. **Phase 1 (observability)** — ship immediately; zero risk; gives us eyes.
2. **Phase 2 (Option 1)** — fix the source so the bug stops occurring; low risk.
3. **Phase 3 (Option 2)** — guardrailed safety net for anything that still slips;
   highest risk, ships last with observability watching it.

This sequencing means production gets *visibility* and the *root-cause fix* before
any change to the live resolver — and the safety net only lands once we can see
exactly what it does.

## Out of scope (call out, don't silently include)
- Changing AI sizing / `entry_lots` / executor MARKET-forcing (separate concern).
- Options-contract resolution (this plan is futures-symbol only).
- The market-data `/marketfeed/ltp` 401 (separate subscription issue; does not
  block order placement).

## Already done (this session, not part of the queue)
- Cleaned stale `strategy_positions` row `bf70e28c` (closed, BSE-MAY paper entry):
  `remaining_quantity 2 → 0`. Status-guarded single-row fix; no open position
  affected. (The entry-vs-add lookup keys on `status in (open,partial)`, so this
  was cosmetic, but cleared to avoid future confusion.)

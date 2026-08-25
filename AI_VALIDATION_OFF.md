# AI_VALIDATION_OFF — turning the AI validator off, safely (READ-ONLY investigation)

Context: the score-filter study (2026-07-31) showed the robot composite is a **price proxy**
(`corr(score, log price) = +0.907` vs `corr(score, return) = +0.067`), so the absolute `51`
threshold acts as a date filter. Moving to **fixed sizing / no score** means turning
`ai_validation_enabled` OFF per strategy. This document is the map + procedure. **Nothing was
executed** — no code changed, no DB written, no service touched, no EC2 action.

---

## 1. WHERE THE FLAG LIVES

**A per-strategy DB column — not a config setting, not an env var.**

| | |
|---|---|
| Column | `strategies.ai_validation_enabled` — `BOOLEAN NOT NULL`, `server_default TRUE` |
| Migration | `backend/migrations/versions/005_strategy_engine.py:65-73` |
| ORM | `backend/app/db/models/strategy.py:71-73` (`default=True, nullable=False`) |
| Read by | `backend/app/services/ai_validator.py:392` and `backend/app/services/strategy_executor.py:485` |
| Exposed via API | `backend/app/api/users.py:460, 515` (`GET/PUT /api/users/me/strategies…` include the field) |

**Default is TRUE** — every strategy validates by default, including any new one.

**Safe reversible way to set it OFF (per strategy):** it is a single boolean on one row, so the
flip is inherently reversible — flip it back to `TRUE` to restore. Two routes exist (procedure in
§5): the **authenticated API** (`PUT /api/users/me/strategies/{id}`, the audited path) or a
**direct SQL UPDATE** on the one row. No migration, no deploy, no code change is required.

⚠️ Unlike `is_paper`/`is_active`, this column is **not covered by the `strategy_state_audit`
trigger** (migration `033_strategy_state_audit.py` watches `is_paper`/`is_active` only) — so a
direct SQL flip leaves **no audit trail**. Prefer the API route, or record the change manually.

---

## 2. SIZING WHEN AI IS OFF — where the quantity actually comes from

Trace: `strategy_executor.py:485-519` (`_resolve_quantity`). With `ai_validation_enabled=False`
the AI branch is skipped entirely and resolution falls through **in this order**:

1. **`signal.quantity` from the payload — FIRST and authoritative.** (`:498-517`)
   - If `quantity_unit == "lots"`, it is multiplied by `lot_size` first (`:494-497`).
   - If the result exceeds `entry_lots × lot_size`, the executor **raises** (`:502-513`) —
     `entry_lots` is a hard ceiling, never a silent clamp.
2. `recommended_lots` if somehow present (`:515-516`) — not applicable when AI is off.
3. **`ceiling_contracts` = `entry_lots × lot_size`** as the final fallback (`:519`) — i.e. when the
   payload carries **no** quantity, size is the strategy's configured `entry_lots`.

**Confirmed fixed-size source: whatever the payload sends (bounded by `entry_lots`); if the
payload omits quantity, it is exactly `strategy.entry_lots × lot_size`.**
For the bridge as it now stands — which always sends an explicit ENTRY `quantity` in
`quantity_unit: "contracts"` — **the payload value wins**, provided it is ≤ `entry_lots × lot_size`.

Sizing is then still subject to `_validate_quantity` (`:521+`): >0, ≤ ceiling, whole-lot multiple,
and the **even-lot rule** for any strategy with `partial_profit_lots > 0`.

---

## 3. ACCEPT / REJECT WHEN AI IS OFF

**All signals pass the validator — it becomes a stub approval.** `ai_validator.py:392-398`:

```python
if not strategy.ai_validation_enabled:
    bypass_lots = max(0, min(strategy.entry_lots or 0, ENTRY_QTY_MAX))
    return AIDecision(decision=AIDecisionStatus.APPROVED,
                      reasoning="AI validation disabled for this strategy.",
                      confidence=Decimal("1.000"), recommended_lots=bypass_lots)
```
The only rejection gate downstream is `signal_execution.py:404-408` (`if decision is REJECTED →
status="rejected", return`), which can no longer trigger from the validator.

⚠️ **"All signals pass" means the AI gate only.** Every other gate stays fully in force and can
still reject/skip a signal: platform halt, rate limit (60/min), HMAC (if enabled), 60s
idempotency, **kill-switch**, user-active, **max-daily-trades**, **market-hours 09:15–15:25 IST**
(non-paper), symbol resolution, Pydantic validation, the qty ceiling above, funds check, and the
broker's own rejection. Turning AI off removes a *filter*, not the *safety rail*.

Side effect worth noting: `strategy_signals.ai_decision` will read `APPROVED` with reasoning
"AI validation disabled for this strategy." for every entry — useful for confirming the flip took
effect from the data side.

---

## 4. CURRENT is_paper STATE FOR BSE / CDSL / ANGELONE

**UNVERIFIABLE-LOCALLY — I could not and did not read the production database.** No `psql` client
on this machine and no production `DATABASE_URL` available locally; reading prod would also exceed
"read-only, no live actions".

What the **code** implies (not proof of current state):
- Column default is **TRUE (paper)** — `strategy.py:100-105`, `005_strategy_engine.py`.
- Migration `027_strategies_is_paper.py:70-82` set **every** strategy to `is_paper = TRUE`
  **except** the hardcoded founder id `89423ecc-c76e-432c-b107-0791508542f0` → **FALSE (live)**.
  That is the only strategy id hardcoded anywhere in the schema.
- **CDSL (`0252e82c…`) and ANGELONE have no code-level special-casing at all** — their live/paper
  status is pure DB state set after that migration.
- Resolution at runtime: `paper_mode_resolver.py:34-48` — per-strategy `is_paper` wins; the global
  `strategy_paper_mode` (config default **True** = safe) is only the fallback.

**To verify safely (you, on the host — read-only, no writes):**
```sql
SELECT id, name, is_paper, is_active, ai_validation_enabled, entry_lots, partial_profit_lots
FROM strategies
WHERE id::text LIKE '89423ecc%' OR id::text LIKE '0252e82c%'
ORDER BY name;
```
Prior session notes claimed BSE + CDSL are `is_paper=false, is_active=true` — **treat as
doc-claim, confirm with the query above before any flip.**

---

## 5. SAFE FLIP PROCEDURE — DOCUMENTED, NOT EXECUTED

**Restart needed? NO.** The flag is read per-signal from the DB inside the Celery task
(`validate_signal(sig, strategy)` at `signal_execution.py:398`, with the Strategy row loaded that
same request). There is no cached settings object and no module-level constant involved — the next
signal after commit uses the new value. No container restart, no deploy, no migration.

### Pre-flip checks (read-only)
1. Run the SQL in §4 — record **current** `is_paper`, `is_active`, `ai_validation_enabled`,
   `entry_lots`, `partial_profit_lots` for the target strategy. This row *is* your rollback note.
2. Confirm `entry_lots × lot_size` ≥ the quantity the engine/bridge will send, or the executor
   raises (§2). With the bridge's current 2 lots × 200 = 400 contracts, `entry_lots` must be ≥ 2.
3. If `partial_profit_lots > 0`, the lot count must be **even** (2, 4, 6 — not 1/3/5).
4. Prefer flipping **outside market hours** (or with the strategy `is_paper=true` / kill-switch
   tripped) so no in-flight signal straddles the change.

### The flip (choose ONE route)
**Route A — API (preferred: authenticated, audited, no DB access):**
`PUT /api/users/me/strategies/{strategy_id}` with `{"ai_validation_enabled": false}` as the
owning user (`backend/app/api/users.py:460,515`). Verify by re-reading the strategy.

**Route B — direct SQL (single row, explicit, no audit trigger — see §1 warning):**
```sql
-- flip OFF
UPDATE strategies SET ai_validation_enabled = FALSE WHERE id = '<strategy-uuid>';
-- verify
SELECT id, ai_validation_enabled FROM strategies WHERE id = '<strategy-uuid>';
```

### Verify it took effect
Send one signal (paper strategy, or in-hours on the target) and confirm on the row:
`strategy_signals.ai_decision = 'APPROVED'` with
`ai_reasoning = 'AI validation disabled for this strategy.'` (§3), and that the resulting order
quantity equals the payload quantity (§2).

### Revert (immediate, one statement)
```sql
UPDATE strategies SET ai_validation_enabled = TRUE WHERE id = '<strategy-uuid>';
```
or the same API call with `true`. No restart, effective on the next signal.

---

## 6. FLAGS / UNCERTAINTIES
- **UNVERIFIABLE-LOCALLY:** current `is_paper` / `is_active` / `ai_validation_enabled` /
  `entry_lots` values for BSE, CDSL, ANGELONE (prod DB). Everything in §4 is code-implication only.
- **UNVERIFIABLE-LOCALLY:** whether prod runs this exact code — the DNA audit put prod at
  `main@2b909c5 + migration 040` (2026-07-20) while this tree is `docs/stale-copy-cleanup`; the
  files cited here are long-standing, but confirm on the host before acting.
- **No audit trail** on `ai_validation_enabled` changes (trigger covers `is_paper`/`is_active`
  only) — Route A or a manual log entry is the mitigation.
- **Scope reminder:** turning AI off removes the score gate *and* the AI's 2→4 lot upgrade. Sizing
  becomes exactly what the payload says (or `entry_lots`) — which is the intent of the fixed-sizing
  move, but it means **the payload's quantity is now the only thing deciding size**, bounded by
  `entry_lots`. Set `entry_lots` deliberately.

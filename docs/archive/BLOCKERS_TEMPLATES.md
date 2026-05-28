# BLOCKERS — Strategy Template System Phase 1

**Date:** 2026-05-17
**Branch:** `feat/strategy-template-system`
**Status:** Phase 1 build complete (catalog + backend + frontend + seed + tests). No hard blockers. This doc surfaces the few ambiguities I resolved by judgment-call so Jayesh can review + confirm or override.

---

## Resolved-by-judgment-call items (please review)

### 1. Migration directory — actual location

**Spec said**: `backend/alembic/versions/026_add_strategy_templates.py`
**Actual repo layout**: `backend/migrations/versions/` (no `alembic/` subdirectory)
**Resolution**: created the migration at `backend/migrations/versions/026_add_strategy_templates.py`. Latest existing migration was `025_add_trade_markers.py`. Revision header points `down_revision = "025_add_trade_markers"`.

### 2. `backend/app/templates/` already existed (notification templates)

**Spec said**: "Backend: backend/app/templates/ (new module)"
**Actual repo**: `backend/app/templates/notifications/` already exists with `.txt` + `.html` files for Telegram and email notification message templates. ZERO Python files inside, so no file-level collision with the spec's `models.py`/`schemas.py`/etc.
**Resolution**: created the 6 new Python files alongside the existing `notifications/` subdir. The `__init__.py` carries a docstring distinguishing the two purposes.

### 3. 19 categories not explicitly enumerated in spec

**Spec said**: "category (enum: 19 values per catalog)"
**No catalog doc was provided** with the 19 category strings.
**Resolution**: enumerated 19 plausible categories in `seed_strategy_templates.json:_meta.category_canon`. Of those, 13 are actually used by the 113 shipped templates; the remaining 6 (Scalping, Swing, Positional, Index Strategy, Sector Rotation, Pairs/Stat-Arb) are canonical names reserved for Phase 2-3 additions.

Categories used: `Breakout`, `Event-Driven`, `Intraday`, `Mean Reversion`, `Momentum`, `Options Directional`, `Options Income`, `Options Spreads`, `Options Volatility`, `Pattern Recognition`, `Trend Following`, `Volatility`, `Volume Profile`.

If Jayesh's external catalog doc has a different category vocabulary, the seed file is the only place that needs to change (the `category` column is a free-form `VARCHAR(64)`, not an enum at DB level).

### 4. 35 inactive equity + 63 options slugs/names — AI-generated placeholders

**Spec said**: "Full slug list in catalog doc."
**No catalog doc was provided** with the 98 inactive entry names.

**Resolution**: generated 98 industry-standard equity + Indian-derivatives options strategy names. Each entry carries:
- Realistic name (e.g., "Iron Condor — NIFTY Weekly", "Donchian Channel Breakout")
- Plausible category, complexity, risk_level, recommended_capital_inr
- `description_en` flagged with "Coming soon." or "Requires options builder."
- `is_active = false`, `config_json = {}` so no real trading logic is implied
- Sequential `display_order` (200-540 for equity inactive, 1000-1620 for options) keeps them at the bottom of the picker behind the 15 active templates

**Action item for Jayesh**: review the 98 placeholder names against your catalog doc. Renaming a slug is a CSV-style edit to `backend/data/strategy_templates_seed.json` (no migration needed — the seed loader is idempotent and re-keying happens via slug). I'd suggest a quick scan before Phase 2 to lock in the canonical names.

### 5. Strategy creation flow — chose direct ORM, not internal HTTP self-call

**Spec said**: "creates strategy via existing strategy creation flow"
**Possible interpretations**:
- (a) Call `POST /api/users/me/strategies` internally via httpx (would be weird — self-call)
- (b) Mirror the existing flow at the ORM layer (idiomatic FastAPI)

**Resolution**: option (b). `clone_service.clone_template()` directly creates a `Strategy()` ORM row with the same column writes the existing `users.py:520` endpoint uses (name, user_id, max_position_size=0, allowed_symbols=[], is_active=True; webhook_token_id + broker_credential_id deliberately null — user wires those after clone). The created strategy is identical in shape to one created via the existing endpoint, just with a `strategy_template_origin` linking row added.

### 6. Counts of "15 active" vs the spec's "13 active" inconsistency

**Spec said**: "Phase 1: 15 active equity templates" AND later "Local test results: All 113 entries verified in seed (13 active, 98 inactive — confirm count)"
**Resolution**: shipped **15** active per the explicit named list (the 13 looked like a transcription typo). All 15 slugs match the spec's enumeration verbatim.

### 7. `max_open_positions = 1` enforced in validator

**Spec said**: `max_open_positions=1` for each of the 15 active configs.
**Validator behavior**: rejects any value other than exactly 1 in Phase 1. If post-launch you want to allow `max_open_positions > 1` (concurrent positions), the validator change is one line.

---

## What WAS not implemented (intentional, per spec scope)

These are NOT bugs — they're explicit Phase-1 scope exclusions per the spec's "FORBIDDEN" list:

- No backtest engine integration (Week 2 work).
- No chart integration beyond what Phase E markers already do.
- No BACKTEST / PAPER / LIVE mode toggle (Week 3 work).
- No options strategy builder (Phase 7-8 — that's why all 63 options templates carry `requires_options_builder=true` and return 501 on clone).
- No SSH / EC2 / docker — migration is committed but **not applied** to any environment. Jayesh runs `alembic upgrade head` manually as part of the next deploy.
- No `main` merge, no `git push`, no Vercel deploy.

---

## Open follow-ups (Phase 2-3)

1. **Populate the 35 inactive equity configs.** Same shape as the 15 active templates' `config_json`. Roughly ~1 hr per template at thoughtful design speed.
2. **Lock in the canonical inactive-equity slug list** (rename + replay seed loader).
3. **Backfill the 6 unused categories** (Scalping, Swing, Positional, Index Strategy, Sector Rotation, Pairs/Stat-Arb) with at least one template each before launching the full picker UI.
4. **`description_hi` for the 98 inactive entries** — currently empty strings; could be populated post-launch by Lokesh or as part of a translation sprint.
5. **Phase 7-8 options builder** — when that ships, the 63 options templates' `config_json` gets populated and `requires_options_builder` flips to `false` on the rows. No schema migration needed.
6. **Strategy detail page** — clone returns a `strategy_id` and the frontend currently `router.push("/strategies/${strategy_id}")` — that route is presumed to exist (it's the standard strategy detail page). If not, this is a no-op redirect failure.

---

## Verification snapshot

```
Backend tests:   46 passed (validator + seed shape)
TypeScript:      clean on all new + 3 small-edit files
Seed JSON:       113 entries, 0 validation errors, 0 slug duplicates
                 15 active equity (full config_json)
                 35 inactive equity (empty config_json)
                 63 options pending builder (empty config_json)
```

No push, no deploy, no migration applied. Awaiting Jayesh's review.

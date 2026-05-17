# Templates Implementation Roadmap

Phase 1 ships the catalog + clone path. Subsequent phases progressively populate inactive entries and unlock options + backtest integration.

## Phase 1 — Catalog + Clone (this branch)

**Goal**: surface 113 entries on `/strategies/templates`. Clone any of the 15 active templates into a strategy.

**Shipped**:

- ✅ DB migration `026_add_strategy_templates.py` (additive only)
- ✅ Backend module `app/templates/` (6 files: models, schemas, validator, registry, clone_service, api)
- ✅ 4 endpoints: `GET /api/templates`, `GET /api/templates/categories`, `GET /api/templates/{slug}`, `POST /api/templates/{slug}/clone`
- ✅ Frontend route `/strategies/templates` with gallery + filters + detail modal
- ✅ Seed file with 113 entries (15 active + 35 inactive equity + 63 options)
- ✅ Sidebar "Templates" nav item + tour-id
- ✅ `/strategies` page "Browse Templates" CTA
- ✅ 46 backend unit + seed-shape tests passing

**NOT shipped (out of Phase 1 scope)**:

- Migration NOT applied to any environment (`alembic upgrade head` runs at deploy time)
- No branch push / main merge / Vercel deploy

## Phase 2 — Populate inactive equity configs

Fill in `config_json` for the 35 cataloged-but-inactive equity templates. Roughly 1 hr per template at thoughtful design speed × 35 = 35 hrs of focused design work. Suggested batching:

| Batch | Templates | Estimated effort |
|---|---|---|
| Batch A — Trend Following gap-fillers (~10) | Heikin-Ashi, Donchian, Ichimoku, ADX-filter, Triple EMA, PSAR + EMA, Hull MA, ALMA, KAMA, Chandelier Exit | ~10 hrs |
| Batch B — Mean Reversion + Pattern (~12) | Williams %R, Stochastic, Pivot Bounce, Camarilla, Fib Retracement, BB %B, Engulfing, Hammer, Doji, RSI Divergence, MFI, Keltner | ~12 hrs |
| Batch C — Volume + Volatility (~8) | Volume Spike, OBV, CMF, Squeeze Momentum, ATR Trailing, OBV Divergence, MACD Divergence, Renko | ~8 hrs |
| Batch D — Specialty (~5) | Inside Bar, Range Trading, Pivot Reversal, Aroon Crossover, Heikin-Ashi Smooth | ~5 hrs |

Each batch: write the `config_json`, flip `is_active=true`, re-run seed loader, ship.

## Phase 3 — Backfill 6 unused canonical categories

Add at least one Phase-2-config-quality template each for:
- Scalping, Swing, Positional, Index Strategy, Sector Rotation, Pairs/Stat-Arb

~6 templates × ~1 hr = ~6 hrs. Makes the catalog feel complete across all 19 categories.

## Phase 4 — UX polish (post-launch)

- Tour onboarding step pointing at the "Templates" sidebar item (already has `templates-nav` data-attr, just needs a tourStep entry)
- Per-template payoff-shape preview tiles (line for trend-followers, dual-band for mean-revs, etc.)
- "Recently cloned" section above the gallery
- Performance stats per template (when backtest engine ships in Phase 6-7)
- Indian-language toggle (description_hi already in schema; just needs i18n wire-up)

## Phase 5-6 — Backtest engine integration

Pre-req: Phase F Component 4 (backtest engine) ships.
Then: clone-with-backtest-preview — show prospective P&L / win-rate / drawdown before the user clones.
Files touched: extends `app/templates/clone_service.py` to call the backtest engine; new "Backtest preview" tab in `TemplateDetailModal`.

## Phase 7-8 — Options builder

Unblocks the 63 options templates. Once the options builder ships:

1. Populate `config_json` for each of the 63 (leg structures, strike selection rules, expiry filters)
2. Flip `requires_options_builder=false` on rows that the builder can now handle
3. Clone path: `POST /api/templates/{slug}/clone` returns 201 instead of 501 for these slugs

The frontend automatically picks up the state change — `TemplateCard`'s state resolver flips from `options-builder-required` → `active-equity` (or a new `active-options` variant if needed).

## Phase 9+ — Marketplace

- User-submitted templates with approval workflow (mirrors the existing `app.strategy_engine.indicator_admin` queue pattern)
- Per-template performance leaderboard (uses real paper-trade aggregate stats)
- Revenue share on user-template clones (existing `marketplace_ledger` table is ready)

## Migration deploy checklist

When ready to push to prod:

```bash
# 1. Branch merge to main
git push origin feat/strategy-template-system
# Open PR, review, merge to main

# 2. Deploy backend (Docker rebuild + restart)
ssh ubuntu@<EC2_IP>
cd /home/ubuntu/trading-bridge
git pull origin main

# 3. Apply migration
docker compose exec backend alembic upgrade head
# Should output: 025_add_trade_markers -> 026_add_strategy_templates

# 4. Seed the catalog
docker compose exec backend python -m app.templates.scripts.seed_strategy_templates
# (Script not shipped in Phase 1 — Phase 1 ships the registry.load_from_seed_file() helper;
#  Jayesh writes a 1-line wrapper script at deploy time.)

# 5. Rebuild + restart backend container
docker compose build backend
docker compose up -d backend

# 6. Smoke test
curl -H "Authorization: Bearer $TOKEN" https://api.tradetri.com/api/templates
# Expect: {"total": 113, "active_count": 15, "inactive_count": 98, "items": [...]}

# 7. Frontend deploys automatically via Vercel on main push
```

## Rollback

Migration is fully reversible. To revert:

```bash
docker compose exec backend alembic downgrade -1
# Drops strategy_template_origin then strategy_templates
```

No data loss for the rest of the system — both new tables are leaf nodes (no other tables reference them). Cloned strategies remain in the `strategies` table; only the template-origin link is dropped.

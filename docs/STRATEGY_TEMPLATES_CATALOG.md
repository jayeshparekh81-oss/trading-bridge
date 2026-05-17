# Strategy Templates Catalog — Phase 1

The TRADETRI catalog ships **113 strategy templates** organised in three buckets:

| Bucket | Count | State | Customer-visible | Cloneable |
|---|---:|---|---|---|
| Active equity | 15 | Full config_json populated | YES | YES (201 Created) |
| Cataloged equity, coming soon | 35 | Metadata only, `is_active=false` | YES (greyed "Coming Soon" card) | NO (409 Conflict) |
| Options pending builder | 63 | Metadata only, `requires_options_builder=true` | YES (purple "Options Phase 7-8" card) | NO (501 Not Implemented) |

Source of truth: `backend/data/strategy_templates_seed.json` (single file, idempotent loader).

## The 15 active equity templates

| # | Slug | Name | Category | Complexity | Timeframe | Indicators |
|---:|---|---|---|---|---|---|
| 1 | `ema-crossover-9-21` | EMA Crossover 9/21 | Trend Following | beginner | 5m | ema_9, ema_21 |
| 2 | `ema-crossover-20-50` | EMA Crossover 20/50 | Trend Following | beginner | 15m | ema_20, ema_50 |
| 3 | `macd-trend-signal` | MACD Trend with Signal Cross | Momentum | intermediate | 15m | macd_12_26_9 |
| 4 | `supertrend-rider` | Supertrend Rider | Trend Following | beginner | 15m | supertrend_10_3 |
| 5 | `rsi-oversold-bounce` | RSI Oversold Bounce | Mean Reversion | beginner | 15m | rsi_14 |
| 6 | `bb-mean-reversion` | Bollinger Band Mean Reversion | Mean Reversion | intermediate | 15m | bb_20_2 |
| 7 | `bb-squeeze-breakout` | BB Squeeze Breakout | Breakout | advanced | 15m | bb_20_2, atr_14 |
| 8 | `orb-15min` | Opening Range Breakout (15-min) | Breakout | intermediate | 5m | orb_15 |
| 9 | `pdh-pdl-breakout` | Previous Day High/Low Breakout | Breakout | beginner | 15m | pdh, pdl |
| 10 | `vwap-bounce` | VWAP Bounce | Mean Reversion | intermediate | 5m | vwap |
| 11 | `macd-histogram-momentum` | MACD Histogram Momentum | Momentum | intermediate | 15m | macd_12_26_9 |
| 12 | `banknifty-weekly-equity` | Bank Nifty Weekly Expiry (Equity Leg) | Event-Driven | advanced | 5m | banknifty_pdh, india_vix |
| 13 | `premarket-gap` | Pre-Market Gap Strategy | Event-Driven | intermediate | 5m | pre_market_gap_pct |
| 14 | `rsi-macd-confluence` | RSI + MACD Confluence | Momentum | intermediate | 15m | rsi_14, macd_12_26_9 |
| 15 | `bb-rsi-oversold` | BB + RSI Oversold | Mean Reversion | intermediate | 15m | bb_20_2, rsi_14 |

Each carries a fully populated `config_json` with:

```jsonc
{
  "indicators": ["..."],
  "entry_long":  { "condition": "..." },
  "entry_short": { "condition": "..." },  // optional, paired with exit_short
  "exit_long":   { "condition": "..." },
  "exit_short":  { "condition": "..." },
  "stop_loss_pct":     1.5,    // 0.5 ≤ x ≤ 10
  "take_profit_pct":   3.0,    // 0.5 ≤ x ≤ 20
  "position_sizing": { "method": "fixed_amount", "amount_inr": 50000 },
  "max_open_positions": 1,     // Phase 1: exactly 1
  "trading_hours":   { "start": "09:15", "end": "15:15" }
}
```

## Categories (19 canonical, 13 currently used)

`Trend Following`, `Mean Reversion`, `Breakout`, `Momentum`, `Volatility`, `Scalping`*, `Swing`*, `Intraday`, `Positional`*, `Volume Profile`, `Pattern Recognition`, `Event-Driven`, `Options Income`, `Options Directional`, `Options Spreads`, `Options Volatility`, `Index Strategy`*, `Sector Rotation`*, `Pairs / Stat-Arb`*.

(\* = canonical name reserved for Phase 2-3 templates; not yet populated.)

## Tags vocabulary

Per-template free-form `tags` list. Conventions used in seed:

- Complexity hints: `beginner-friendly`, `expert`
- Strategy family: `trend`, `momentum`, `mean-reversion`, `breakout`, `pattern`
- Indicator names: `ema`, `macd`, `rsi`, `bollinger-bands`, `vwap`, `supertrend`
- Style: `intraday`, `swing`, `event-driven`, `gap`, `expiry`
- Options-specific: `options`, `spread`, `iron-condor`, `naked`, `long-vol`, `short-vol`, `weekly`, `monthly`

## Indexing strategy

DB indexes on `category`, `complexity`, `segment`, `instrument_type`, `is_active` — matches the four picker filters + the active/inactive gate. The unique index on `slug` doubles as the lookup path for `GET /api/templates/{slug}` and `POST /api/templates/{slug}/clone`.

## Cloning

Clone semantics, per HTTP status:

| Status | Meaning |
|---|---|
| 201 Created | Strategy materialised. Response: `{strategy_id, strategy_name, template_slug, message}`. Frontend redirects to `/strategies/{strategy_id}`. |
| 404 Not Found | Slug doesn't exist. |
| 409 Conflict | Template is cataloged but `is_active=false` (coming-soon equity). |
| 501 Not Implemented | Template requires the options builder (Phase 7-8). |
| 500 Internal Server Error | Catalog row has malformed `config_json`. Data-integrity issue worth paging on; shouldn't fire because the seed loader validates pre-write. |

The cloned strategy has:
- `name = "<Template name> (from template)"` (or `name_override` from the request body)
- `user_id = <calling user>`
- `is_active = true`
- `webhook_token_id = NULL`, `broker_credential_id = NULL` (user wires these on the strategy detail page after clone)
- A linking row in `strategy_template_origin` recording the template provenance

## Endpoints

All four under `/api/templates`, JWT-auth-required:

```
GET    /api/templates                  filtered list (category, complexity, segment, search, is_active)
GET    /api/templates/categories       counts per category for the picker filter sidebar
GET    /api/templates/{slug}           full detail (incl. config_json)
POST   /api/templates/{slug}/clone     materialise as Strategy (or 409 / 501 per state)
```

## Files

| Path | Purpose |
|---|---|
| `backend/migrations/versions/026_add_strategy_templates.py` | DDL: `strategy_templates` + `strategy_template_origin` tables |
| `backend/app/templates/models.py` | ORM models |
| `backend/app/templates/schemas.py` | Pydantic v2 wire shapes |
| `backend/app/templates/validator.py` | `config_json` validation (active vs inactive) |
| `backend/app/templates/registry.py` | Seed loader + filtered query helpers |
| `backend/app/templates/clone_service.py` | Template → Strategy materialisation |
| `backend/app/templates/api.py` | FastAPI router (4 endpoints) |
| `backend/data/strategy_templates_seed.json` | The 113-entry catalog (single source of truth) |
| `backend/tests/templates/` | Unit + seed-shape tests (46 cases) |
| `frontend/src/lib/strategy-templates/{api,types}.ts` | REST client + TypeScript types |
| `frontend/src/components/strategy-templates/Template{Card,DetailModal,Filters}.tsx` | UI components |
| `frontend/src/app/(dashboard)/strategies/templates/page.tsx` | The /strategies/templates route |

Plus 3 small existing-file additions:
- `backend/app/main.py` — register `strategy_templates_router`
- `frontend/src/components/dashboard/sidebar.tsx` — "Templates" nav item + `templates-nav` tour-id
- `frontend/src/app/(dashboard)/strategies/page.tsx` — "Browse Templates" CTA button

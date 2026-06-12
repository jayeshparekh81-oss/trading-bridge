# POLISH PACK 1 — Review

Branch: `feat/polish-pack-1` (6 commits, branched from main @ `42839bd`).
Verified before every commit: `npm run build` (exit 0), `npm run lint`
(116 problems = baseline), `npx vitest run` (4 failed / 849 passed =
baseline; the 4 are the pre-existing ChartContainer ×3 + TemplateCard ×1
failures, untouched by this pack). Machine check (STEP 0):
`Jayeshs-Mac-mini.local`, repo `/Users/jayeshparekh/projects/trading-bridge`.

---

## Item 1 — Fork page: 4 equal door cards  (`c9a2cc3`)

**What changed:** `/strategies/new` now renders four `Door` cards in the
existing 2-col grid (2×2 ≥640px, stacked below): Marketplace (keeps the
"Recommended for first-timers" badge + emerald accent — only accented
card), Build my own (unchanged), Intermediate ("Pick your own
indicators, with guardrails."), Expert ("Full DSL — bring your own
conditions."). The footer "Already comfortable? …" escape-hatch line is
removed. Links only; `?edit=` handling and routing logic untouched.

**Files:** `frontend/src/app/(dashboard)/strategies/new/page.tsx`

**1-minute test:** Open `/strategies/new`. Count 4 cards, only the
marketplace one glows green. Click each: lands on /marketplace,
/strategies/new/beginner, /intermediate, /expert. Narrow the window —
cards stack. No footer line under the grid.

**Not done & why:** testIds keep the existing `two-door-*` prefix
(`two-door-intermediate`, `two-door-expert`) — renaming the prefix would
churn test hooks for zero user benefit.

## Item 2 — Orphaned mode toggle removed from /strategies  (`4a26a71`)

**Investigation findings:** The pill toggle never filtered the list. It
wrote `tb_strategy_mode`, but every builder overwrites that key on mount
(beginner page.tsx:225, intermediate:176, expert:414), so the toggle had
no lasting cross-surface effect. Its only on-page consumers were (a) the
legacy-strategy banner gate (`mode === "beginner" && !strategy_json`)
and (b) the backtest CTA label ("Run" vs "View Backtest"). The old
`/strategies/new` redirector that used to read the key was replaced by
the M1 fork.

**What changed:** Removed the `ModeSelector` usage, its `mode` state,
and the `mode` prop threading on /strategies. Banner now gates on
`!strategy.strategy_json` alone; backtest label fixed to "Run Backtest".
**Kept:** `mode-selector.tsx` itself — builders, the onboarding modal,
and IndicatorLibrary still import the component/type/storage key (live
function inside builders: indicator clickability + card visibility).

**Files:** `frontend/src/app/(dashboard)/strategies/page.tsx`

**1-minute test:** Open `/strategies` — no Beginner/Intermediate/Expert
pills, no "MOST POPULAR"/"ADVANCED" badges, no "Full DSL" caption.
Cards render; DSL strategies show "Run Backtest". Builders still show
their own mode selector.

## Item 3 — AlgoMitra bubble vs wizard CTAs  (`38ef23e`)

**What changed:** Bottom clearance on the beginner wizard container:
`pb-36` on mobile (launcher sits at `bottom-20` there) and `pb-24` at
`md+` (launcher at `bottom-6`, ~48px tall). The CTA row is the last
element, so at end-of-scroll it now sits above the fixed pill at all
widths. The bubble itself (position, size, z-index) is untouched.

**Files:** `frontend/src/app/(dashboard)/strategies/new/beginner/page.tsx`

**1-minute test:** At ~1140px width open `/strategies/new/beginner`,
scroll to the bottom of any step — Next/Continue sits clearly above the
AlgoMitra pill (verified in-browser at 1043px effective width; gap
visible). Repeat at mobile width.

**Not done & why:** Mid-scroll the pill can still pass over page content
— unavoidable for a viewport-fixed element without redesigning/moving
the bubble, which the item excluded. Intermediate/expert builders and
the /strategies/{id} deploy panel weren't touched (item scoped to the
beginner wizard CTAs).

## Item 4 — Migrate banner on Pine/webhook strategies  (`d2f3b41`)

**Discriminator hunt (negative result):** `/api/strategies` returns only
`id, name, is_active, strategy_json, created_at, updated_at`
(+`template_origin` on detail). `strategy_json` is null for
Pine/webhook-driven, legacy hand-built, AND template-cloned strategies
alike. `webhook_token_id` exists in the DB but is not serialized. So
there is **no reliable frontend-visible discriminator** today.

**What changed (per the fallback instruction):** banner copy softened to
"Is strategy ko Pine/webhook se signals milte hain — builder migration
optional hai." A code comment documents why the copy is neutral.
"Backtest unavailable (no DSL)" label untouched. (Note: with Item 2 the
banner now shows in what used to be non-beginner modes too — the old
visibility was an artifact of the removed toggle.)

**Files:** `frontend/src/app/(dashboard)/strategies/page.tsx`

**1-minute test:** `/strategies` → BSE LTD Futures card shows the new
Hinglish line and the unchanged disabled "Backtest unavailable (no
DSL)" button. DSL-ready cards show no banner.

**Follow-up suggestion (backend, out of scope):** expose
`webhook_token_id` (or an `is_webhook_linked` bool) in
`StrategyResponse` — then the banner can be hidden precisely.

## Item 5 — "upcoming Wednesday builder" placeholders  (`6250db8`)

**What changed:** The indicator-library toast `…— coming Wednesday.` →
`…— available in the new builder.` The other placeholder ("Migrate it
via the upcoming Wednesday builder…") was already replaced wholesale by
Item 4's banner rewrite.

**Files:** `frontend/src/components/strategies/indicator-library.tsx`

**Left alone deliberately:** "Wednesday" mentions in
`lib/indicators/content/vwap.ts` and `macd.ts` (genuine expiry-week
market content) and `lib/marketing/telegram/strategy-of-week.ts`
(weekly cadence label) — not placeholders.

**1-minute test:** `/strategies/indicators` (Indicator Library), click
any clickable indicator card → toast says "available in the new
builder".

## Item 6 — "Templates" → "Strategy Templates"  (`91b07c8`)

**What changed (visible copy only):**
- Sidebar nav label (`sidebar.tsx`)
- "Browse Templates" → "Browse Strategy Templates" (/strategies header)
- Explainer detail page back-links + not-found body, EN and Hinglish
  (`templates/[slug]/page.tsx`)
- Tutorial script references to the renamed button
  (`lib/tutorials/scripts/first-strategy-template.ts`, 4 spots)
- `/strategies/templates` h1 already said "Strategy Templates" — no change.

**Unchanged:** routes (/strategies/templates), component/file names,
TS types, API functions, analytics, all `template-*` test ids.

**Not done & why:** the old builder pages' "Saved Templates" sections
(builder/entry|exit|risk) — those are saved entry/exit/risk *block*
templates, a different concept from the strategy-template catalog;
renaming them "Strategy Templates" would be wrong, not consistent.

**1-minute test:** Sidebar shows "Strategy Templates"; /strategies
header button reads "Browse Strategy Templates"; open any explainer →
back-link reads "Back to Strategy Templates".

---

## Pack-wide notes

- This file is intentionally **uncommitted** (the pack is capped at one
  commit per item, 6 max). Delete or commit it as you prefer.
- Visual verification was done against the live dev server
  (localhost:3000 → prod API), logged in, including the BSE LTD Futures
  card for Item 4 and the 1140px wizard overlap for Item 3.
- No backend, migrations, .env, or sacred-zone files touched anywhere
  in the pack.

# Queue BBB Sprint 9a — Indicator Library Verification badges (frontend)

**Branch:** `feat/frontend-indicator-badges` (off `main@55047df`)
**Date:** 2026-06-02
**Time used:** ~30 min (cap 120 min)
**Verdict:** **PASS.** 4 new files + 1 surgical 5-line edit to the existing Indicator Library card. Build: `npm run build` ✓ (4.0s compile, 5.9s TS, 48/48 pages). Lint: ✓ 0 issues on new files. Zero `any`, zero `@ts-ignore`, zero new dependencies, zero global-token changes.

---

## 1. Headline

| Item | Value |
|---|---|
| Files added | 3 (data JSON mirror + types/loader + badge component) |
| Files modified | 1 (`indicator-library.tsx`, +5 / −1 lines) |
| Sacred-zone touches | 0 |
| New dependencies | 0 |
| New colour tokens | 0 (reuses existing `profit`, `accent-blue`, `amber-500`, `muted-foreground`, `white/[0.0X]`) |
| TypeScript `any` / `@ts-ignore` | 0 |
| Existing components reused | `Badge`, `Tooltip` / `TooltipTrigger` / `TooltipContent` / `TooltipProvider` (from `components/ui/`), Lucide icons (`ShieldCheck`, `Shield`, `ShieldQuestion`, `AlertTriangle` — all already imported elsewhere) |
| `npm run build` | ✓ pass |
| Lint on new files | ✓ pass (eslint exit 0) |

---

## 2. Files added

### 2.1 `frontend/src/data/indicator_library_badges.json` (773 lines, mirror)

Verbatim copy of `docs/indicator_library_badges.json` (Sprint 8c artifact). Lives under `src/data/` for ESM-safe build-time import (same pattern as existing `src/data/glossary.json`). Regen: the founder's badge-generator script in `backend/tests/queue_ww_sprint_8c/generate_badges.py` writes to `docs/`; a follow-up sprint can wire a build-time copy step if the artifact needs to live in two places.

### 2.2 `frontend/src/lib/indicators/verification.ts` (~70 LOC)

Typed loader. Exports:
- `VerificationBadgeKind` — exact union of the 5 badge strings from spec
- `VerificationBadgeEntry` — full row shape (`indicator`, `tier_pine`, `tier_talib`, `divergence_note`, `badge`, `badge_help`)
- `getVerificationBadge(slug) → entry | undefined`
- `allVerificationEntries()` — for tests + future aggregate-count widget

Builds a `Map<slug, entry>` at module load (O(1) lookup; 96 entries, negligible cost). Returns `undefined` for unknown slugs — caller treats as "no badge to render."

### 2.3 `frontend/src/components/indicators/IndicatorVerificationBadge.tsx` (~110 LOC)

The new component. **Distinct from the existing `IndicatorBadge.tsx`** (category pill — Momentum/Trend/Volatility/etc., used widely and untouched). Both can render on the same card.

Props:
- `slug: string` (required)
- `compact?: boolean` (suppresses tooltip — for autosuggest dropdowns per spec §4)
- `className?: string`

Behavior:
- Looks up `slug` → returns `null` if no entry (silent fallback, no error)
- Renders a `<Badge>` pill with icon + label, colour-mapped by badge kind:
  - **Verified** → ShieldCheck, `profit` green
  - **Verified*** → ShieldCheck, `profit` green (asterisk in label)
  - **Best-effort** → Shield, `accent-blue`
  - **Convention varies** → AlertTriangle, `amber-500` family
  - **Under review** → ShieldQuestion, `muted-foreground`
- Wraps the pill in a Tooltip from `@/components/ui/tooltip` (the existing `@base-ui/react/tooltip` wrapper). Tooltip body = badge-kind generic help text (spec §2) + the row's `divergence_note` (when non-empty).
- Each pill has `data-testid="indicator-verification-badge"` + `data-slug` + `data-badge` for E2E tests / Playwright (consistent with existing `data-testid` patterns).

### 2.4 The 5-line edit to `indicator-library.tsx`

In `IndicatorCard`, the existing single-element top-right cluster (`<StatusBadge>`) is wrapped in a `flex flex-col items-end gap-1 shrink-0`, with the new `<IndicatorVerificationBadge slug={indicator.id} />` stacked below `StatusBadge`. Net diff:

```diff
+import { IndicatorVerificationBadge } from "@/components/indicators/IndicatorVerificationBadge";
@@
-        <StatusBadge status={indicator.status} />
+        <div className="flex flex-col items-end gap-1 shrink-0">
+          <StatusBadge status={indicator.status} />
+          <IndicatorVerificationBadge slug={indicator.id} />
+        </div>
```

That's the only edit. The card's overall structure, padding, animations, status/difficulty badges, click behaviour, and mode-gating logic are all unchanged.

---

## 3. Build + lint

```
$ cd frontend && npm run build
✓ Compiled successfully in 4.0s
  Running TypeScript ... Finished TypeScript in 5.9s ...
✓ Generating static pages using 7 workers (48/48) in 294ms
```

48 routes built; `/strategies/indicators` is a static prerendered page in the output. 2 pre-existing warnings about missing `@sentry/nextjs` + `posthog-js` modules — unrelated to this work (they appear on `main@55047df` build too).

```
$ npx eslint src/lib/indicators/verification.ts src/components/indicators/IndicatorVerificationBadge.tsx
$ echo $?
0
```

---

## 4. Screenshot description (CC cannot launch a browser — UI rendering described from code)

On `/strategies/indicators` after build:

- Page heading: "Indicator Library" + BookOpen icon (unchanged).
- Grid of cards: 1 col mobile, 2 cols md, 3 cols lg (unchanged).
- Each card top row, **right side**:
  - **Before this sprint:** single status badge (Active / Experimental / Coming soon).
  - **After this sprint:** vertical stack — status badge on top, verification badge below it, both right-aligned with a 4px gap. Cards for indicators not in the badge artifact (e.g. exotic test slugs) render only the status badge — no empty slot.
- Verification badge visuals on hover/focus open a tooltip popup (`@base-ui/react` portal-rendered) with:
  - Bold heading line = badge label (e.g. "Convention varies")
  - Body = generic help text from spec §2
  - When `divergence_note` is present (the 6 ⚠ Convention-varies indicators, 1 ✅* macd warmup-note, the 11 🛠 Best-effort drift notes, plus a handful of others), a third line below renders the row-specific note in 80% opacity.
- Indicators expected to surface each badge in the visible default-grid (beginner mode hides Experimental + Coming soon, so the badge mix shown depends on mode):
  - **Verified ✅** dominates (75 of 96): `sma`, `ema`, `rsi`, `bollinger_bands`, `atr`, `stochastic`, `donchian_channel`, `ichimoku`, `mfi`, `roc`, `cci`, `obv`, `trix`, `ultimate_oscillator`, etc.
  - **Verified* ✅** (1): `macd_12_26_9` only.
  - **Best-effort 🛠** (11): `adx`, `dema`, `kama`, `tema`, `wma`, `variance`, `supertrend`, `bollinger_bandwidth`, `hammer`, `shooting_star`, `marubozu`, `volume_breakout`, `session_high_breakout`, `session_low_breakout`.
  - **Convention varies ⚠** (6): `aroon`, `aroon_up`, `aroon_down`, `aroon_oscillator`, `chande_momentum`, `chaikin_oscillator`.
  - **Under review 🚧** (3-4): `breadth_thrust`, `advance_decline_proxy`, `trend_age_bars`, plus `vwap` until Sprint 8a's reactivation criterion flips it back.

---

## 5. What this sprint does NOT do

- ❌ Modify any existing component file beyond the 5-line edit to `indicator-library.tsx`.
- ❌ Modify the existing category-badge `IndicatorBadge.tsx` (distinct, widely-used component).
- ❌ Introduce any new colour token, spacing token, or font family.
- ❌ Add any npm dependency (every import resolves to an already-installed package).
- ❌ Modify any sacred-zone file or any backend file.
- ❌ Change the strategy-builder dropdown or strategy detail page — those surfaces are covered by Sprint 9b (tooltips).
- ❌ Push to `main` or create any Vercel deploy.

---

## 6. Founder review checklist for tomorrow

1. **Pull this branch locally:** `git fetch && git checkout feat/frontend-indicator-badges`
2. **Verify build:** `cd frontend && npm run build` (expect ✓ + the same 2 pre-existing sentry/posthog warnings)
3. **Run dev server:** `npm run dev` → open `http://localhost:3000/strategies/indicators`
4. **Switch authoring mode to "expert"** at `/strategies` to surface the maximum indicator set (so the ⚠ and 🚧 variants appear).
5. **Hover any card's verification badge** to confirm tooltip pops with the right text + divergence note.
6. **Pick at least one of each badge kind to spot-check:**
   - Verified: `sma` or `rsi`
   - Verified*: `macd_12_26_9`
   - Best-effort: `adx` or `supertrend`
   - Convention varies: `aroon` or `chaikin_oscillator`
   - Under review: `breadth_thrust` or `vwap` (until 8a is activated)
7. **Confirm card layout** doesn't visually crowd — the right-side stack should fit within the card on mobile/tablet/desktop without overlapping the title.
8. **Approve / request changes** before any merge.

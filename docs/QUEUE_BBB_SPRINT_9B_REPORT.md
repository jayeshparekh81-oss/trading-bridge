# Queue BBB Sprint 9b — Convention tooltips (frontend)

**Branch:** `feat/frontend-convention-tooltips` (off `main@55047df`)
**Date:** 2026-06-02
**Time used:** ~35 min (cap 90 min)
**Verdict:** **PASS.** 3 new files + 3 surgical edits land the 6 convention tooltips on all 3 surfaces from the spec. Build: `npm run build` ✓ (4.3s compile, 48/48 pages). Lint on the new/edited files: ✓ exit 0. Zero new dependencies, zero new colour tokens, zero sacred-zone touches, zero new tooltip-primitive components (uses the existing `@/components/ui/tooltip` wrapper).

---

## 1. Headline

| Item | Value |
|---|---|
| Files added | 3 (data JSON + loader + composable warning helper) |
| Files modified | 3 (Indicator Detail Modal, Intermediate Builder Picker, Strategy Detail Page) |
| Indicators covered | 6 (`aroon`, `aroon_up`, `aroon_down`, `aroon_oscillator`, `chande_momentum`, `chaikin_oscillator`) |
| Surfaces wired | 3 / 3 (detail modal full body, builder dropdown inline ⚠, strategy detail pill list inline ⚠) |
| Sacred-zone touches | 0 |
| New dependencies | 0 (reuses `@base-ui/react/tooltip` via existing `@/components/ui/tooltip`, lucide `AlertTriangle`) |
| New colour tokens | 0 (uses existing `amber-500` / `amber-300` / `amber-200` / `amber-400` family — same palette as Sprint 9a's ⚠ Convention varies badge) |
| TypeScript `any` / `@ts-ignore` | 0 |
| `npm run build` | ✓ pass (4.3s compile, 48/48 pages, same 2 pre-existing sentry/posthog warnings) |
| Lint on new + edited files (excluding pre-existing main-baseline lint error on `IndicatorDetailModal.tsx:41`) | ✓ pass |

---

## 2. Files added

### 2.1 `frontend/src/data/convention_tooltips.json` (~30 lines)

The 6 entries from `docs/CONVENTION_TOOLTIP_FINAL.md`. Each row has:
- `indicator` — slug
- `tooltip_short` — first-sentence chart-hover variant (~15-25 words)
- `tooltip_full` — full 50-80 word body for the detail-modal context

JSON validated with `node -e "JSON.parse(...)"` before commit.

### 2.2 `frontend/src/lib/indicators/convention-tooltips.ts` (~45 LOC)

Typed loader. Exports:
- `ConventionTooltipEntry` (row shape)
- `getConventionTooltip(slug) → entry | undefined`
- `isConventionVaries(slug) → boolean`

Map-backed O(1) lookup. Mirrors the pattern of Sprint 9a's `verification.ts`.

### 2.3 `frontend/src/components/indicators/ConventionWarning.tsx` (~100 LOC)

Composable helper — **not a new tooltip primitive** (uses the existing `@/components/ui/tooltip` `@base-ui/react` wrapper). Three variants per Sprint 8d §2:

| Variant | Renders | Used on |
|---|---|---|
| `inline` (default) | ⚠ AlertTriangle icon + hover Tooltip showing `tooltip_short` | Builder picker dropdown rows; strategy detail page pills |
| `compact` | ⚠ icon only, no Tooltip | Autosuggest contexts (spec §4 "no popover-on-popover") |
| `full` | Inline block with the full 50-80 word `tooltip_full` + "Convention varies" header | Indicator detail modal |

Returns `null` for any slug not in the 6 — callers render it unconditionally. `data-testid` set per variant for E2E selectors.

---

## 3. Files modified (3 surgical edits)

### 3.1 `frontend/src/components/indicators/IndicatorDetailModal.tsx` (+2 lines net)

```diff
+import { ConventionWarning } from "./ConventionWarning";
@@
         {oneLiner}
       </p>
+
+      {/* Convention-varies notice (renders only for the 6 Sprint 8d slugs) */}
+      <ConventionWarning slug={slug} variant="full" className="mb-4" />
```

A new amber-bordered block renders between the one-liner card and the description paragraphs **only when** the modal is open on one of the 6 slugs.

### 3.2 `frontend/src/components/strategies/intermediate-builder/indicator-picker.tsx` (+4 / −1 lines net)

`IndicatorRow` (the dropdown option) gets an inline ⚠ next to the indicator name:

```diff
+import { ConventionWarning } from "@/components/indicators/ConventionWarning";
@@
-        <div className="text-sm font-medium truncate">{indicator.name}</div>
+        <div className="flex items-center gap-1.5">
+          <span className="text-sm font-medium truncate">{indicator.name}</span>
+          <ConventionWarning slug={indicator.id} variant="inline" />
+        </div>
```

Hovering / focusing the ⚠ opens a `tooltip_short` popover. For the 90+ non-convention indicators, `ConventionWarning` returns null and the row renders identically to today.

### 3.3 `frontend/src/app/(dashboard)/strategies/[id]/page.tsx` (+3 / −1 lines net)

The Indicators pill list at the bottom of the strategy header card. Each pill now wraps name + inline ⚠ in a flex container:

```diff
+import { ConventionWarning } from "@/components/indicators/ConventionWarning";
@@
-          <span … className="text-[10px] font-mono px-1.5 py-0.5 rounded …">
-            {name}
-          </span>
+          <span … className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded …">
+            {name}
+            <ConventionWarning slug={name} variant="inline" />
+          </span>
```

(The page renders `indicators.map((name) => ...)` where the array is `config["indicators"]` from the strategy JSON — when slugs match the 6, the ⚠ appears; otherwise rendered nothing.)

---

## 4. Build + lint

```
$ cd frontend && npm run build
✓ Compiled successfully in 4.3s
✓ Generating static pages using 7 workers (48/48) in 300ms
```

```
$ npx eslint src/lib/indicators/convention-tooltips.ts \
             src/components/indicators/ConventionWarning.tsx \
             src/components/strategies/intermediate-builder/indicator-picker.tsx \
             'src/app/(dashboard)/strategies/[id]/page.tsx'
$ echo $?
0
```

**Pre-existing lint error noted, NOT introduced by 9b:** `IndicatorDetailModal.tsx:41` has a `react-hooks/set-state-in-effect` error on the `setLang(readLang())` inside a `useEffect`. Verified via `git stash` that the error exists on `main@55047df` before any 9b edit. The 9b diff against `main` for that file is purely `+1 import line, +3-line JSX block` — none of which touches that effect. Out of scope.

---

## 5. Screenshot description (code-derived; CC cannot render the UI)

### 5.1 Indicator Detail Modal — `/indicators` route, click any of the 6 slugs

- Header (unchanged): name, category badge, complexity tag, language toggle, close button.
- One-liner card (unchanged): the dark-themed rounded card with the registry's one-line summary.
- **NEW for the 6 slugs:** an amber-bordered block immediately below the one-liner:
  ```
  ┌─────────────────────────────────────────────────────────┐
  │ ⚠ CONVENTION VARIES                                      │
  │                                                          │
  │ TRADETRI's Aroon uses the Pine Script convention: when  │
  │ the period's high (or low) is hit on more than one bar, │
  │ the first occurrence wins. TA-Lib uses the last-…       │
  │ (50-80 word body)                                        │
  └─────────────────────────────────────────────────────────┘
  ```
- Description, use-cases, signals, pitfalls, formula, Indian context (unchanged).
- For the other 90 indicators: nothing renders. Modal looks exactly as today.

### 5.2 Intermediate Builder Picker — `/strategies/new/intermediate`

Each indicator row in the catalogue grid:
- Indicator name (unchanged), followed by a small ⚠ amber icon (only for the 6 slugs).
- Hovering / focusing the ⚠ opens an `@base-ui` portal-rendered tooltip with the `tooltip_short` text in a dark popover.

### 5.3 Strategy Detail Page — `/strategies/[id]`

The "Indicators" pill list at the bottom of the strategy header card:
- Each pill (e.g. `aroon · chande_momentum`) renders as today; pills for the 6 convention slugs additionally show a small ⚠ icon to the right of the slug text.
- Hovering opens the same `tooltip_short` popover as the builder picker.

---

## 6. What this sprint does NOT do

- ❌ Build a new tooltip primitive — composes the existing `@/components/ui/tooltip` `@base-ui/react` wrapper.
- ❌ Modify the existing `IndicatorTooltip.tsx` (registry-backed one-liner tooltip — not currently consumed by any component in `src/`).
- ❌ Modify the existing `IndicatorBadge.tsx` (category pill — distinct, widely used).
- ❌ Modify any expert-builder file, beginner-builder file, or backtest-results page (the spec called out 3 surfaces; the expert builder uses a different `indicator-section.tsx` widget and is left for a follow-up if needed).
- ❌ Translate the 6 tooltips into Hindi / Hinglish (CONVENTION_TOOLTIP_FINAL §5 explicitly defers this to a localisation sprint).
- ❌ Modify backend metadata. The 6 slugs and copy come from the markdown spec; the JSON artifact is hand-mirrored.
- ❌ Push to `main` or trigger any Vercel deploy.

---

## 7. Founder review checklist for tomorrow

1. **Pull this branch locally:** `git fetch && git checkout feat/frontend-convention-tooltips`
2. **`cd frontend && npm run build`** — expect ✓ + the 2 pre-existing sentry/posthog warnings.
3. **`npm run dev`** → visit the 3 surfaces:
   - **Detail modal** — `/indicators`, click any of `aroon`, `aroon_up`, `aroon_down`, `aroon_oscillator`, `chande_momentum`, `chaikin_oscillator`. Verify the amber block appears under the one-liner with the right wording. Verify non-convention slugs (e.g. `sma`, `rsi`) render the modal unchanged.
   - **Intermediate builder picker** — `/strategies/new/intermediate`, search for `aroon` or `chande`, confirm a small ⚠ next to the name. Hover → tooltip pops with first-sentence text. For `sma` / `rsi`, no ⚠.
   - **Strategy detail page** — `/strategies/[id]` for a strategy whose config has one of the 6 indicators in `config["indicators"]`. Confirm the pill in the Indicators footer renders the ⚠. (If you don't have such a strategy on hand, the simplest spot-check is to inspect any strategy and add `"aroon"` to its config temporarily in DB, OR test via a strategy template that already references these indicators.)
4. **Voice spot-check** — read the 6 `tooltip_full` strings in `frontend/src/data/convention_tooltips.json`. Confirm Sprint 8d founder-checklist item 3 (chaikin voice asymmetry with the other 5) is either acceptable as-is OR queue a 1-string copy edit before merge.
5. **Approve / request changes** before any merge.

# M4 CONSOLIDATION SPEC — One Adaptive Strategy Wizard

> Read-only analysis of main @ `f62585d` (2026-06-13, overnight). ZERO code written.
> Author: Claude (overnight task). Status: AWAITING FOUNDER REVIEW — nothing here is implemented.

## EXECUTIVE SUMMARY

1. Three builders today: beginner (5-step wizard, 1,718 LOC), intermediate (single-page form, 2,302 LOC), expert (6-tab page, 3,764 LOC + 315 shared robustness-controls) — **≈7,800 LOC** total, zero `dynamic()` splitting, all `"use client"`. (Figures adversarially re-verified via `wc -l`, including the `.ts` modules an earlier glob missed.)
2. The DSL they emit is already a **strict superset chain**: beginner ⊂ intermediate ⊂ expert — same `StrategyJsonPayload` envelope, same `POST /strategies` call; only the `mode` field and which optional blocks are populated differ.
3. Expert's `applyJsonToState()` already hydrates any of the three payloads — the unified wizard can be **one shell over the expert state model with a per-mode capability matrix**.
4. Recommended architecture: **single shell + mode-driven config (Option B)** — routes `/strategies/new/{beginner,intermediate,expert}` become thin wrappers rendering `<UnifiedBuilder mode=…>`; **no redirects, so `?edit={id}` links keep working byte-for-byte**.
5. The 4-door fork page needs **zero changes** — doors already point at the three routes the wrappers will live on.
6. Rollout: default-OFF env flag (`NEXT_PUBLIC_M4_UNIFIED_BUILDER`), old builders untouched and routable until founder flips; new shell built in parallel from copied primitives, dedupe deletion only in the final cleanup module.
7. Six modules: M4a golden-test safety net → M4b shared core (types/validators/serializers) → M4c primitives → M4d shell + expert parity (incl. edit) → M4e intermediate+beginner modes → M4f flip + cleanup. ~33–45h total.
8. Hard requirement honored: edit deep-links (`/strategies/new/expert?edit={id}`, generated at `strategy-actions-menu.tsx:103`) never change shape; M4d carries a dedicated edit-parity test gate.
9. Two corrections to folklore: `<ModeSelector>` has **zero render sites** since Polish Pack 1 (only its storage-key constant is imported), and the "230-indicator catalogue" number is stale marketing copy (fork-page docstring, FAQ, onboarding tour, tutorial scripts) — the registry holds **70 indicators**.
10. 10 product decisions are queued for the founder (§7) — biggest: 3 modes vs 2-modes+advanced-toggle, what "Create New Strategy" defaults to, and whether the `mode` field in saved DSL must stay as-is for the backend.

---

## 1. INVENTORY

### 1.1 Beginner builder

| Aspect | Detail |
|---|---|
| Route | `/strategies/new/beginner` — `src/app/(dashboard)/strategies/new/beginner/page.tsx` (511 LOC, `"use client"`) |
| Entry points | Fork-page Door 2 (`two-door-build`); direct URL; onboarding modal level pick |
| Components | `components/strategies/beginner-builder/`: `step-goal` (97), `step-preset` (250), `step-preview` (197), `step-run` (70), `step-deploy` (163, **M3**), `progress-stepper` (55), `presets.ts` (375 — DSL builder) = 1,207 LOC + 511 page = **1,718 total** |
| Flow | 5 linear steps: ①Goal (intraday/swing/scalping/safe) → ②Setup (preset indicators + period overrides, SL% ∈ {0.5,1,2,3}, Target% ∈ {1,2,3,5}) → ③Preview (read-only rules + name input) → ④Run (saves + backtests) → ⑤Deploy |
| State | `useReducer` — `WizardState { step, goal, name, stopLossPercent, targetPercent, periodOverrides, submitState, created }`. No draft persistence: reload = reset |
| Save | Step 4: `POST /strategies` body `{ strategy_json }` → `{id, name}`; then advances to step 5. Re-submitting after Back creates a NEW strategy (fresh client UUID) |
| Payload | `mode:"beginner"`, `version:1`; entry hardcoded `side:"BUY"`, `operator:"AND"`, indicator-conditions only (per-goal preset, e.g. intraday = EMA-9>EMA-21 AND RSI-14<30); exit = `targetPercent`+`stopLossPercent` only; **no `risk` block**; `execution {mode:"backtest", orderType:"MARKET", productType:"INTRADAY"}` |
| Deploy step (M3) | `step-deploy.tsx` reuses shared `SafetyPreFlightPanel` (`GET /orders/live/preflight?strategy_id=` — 7 checks incl. 7 paper sessions, trust ≥70, truth ≥55), `GoLiveButton` (locked until `all_passed`), `GoLiveModal` (`POST /orders/live`, `dry_run` defaults true, paper mode forces it), `OrderResultCard`. Footer links to `/strategies/{id}/backtest` |
| Backtest | Never calls the backtest endpoint itself; `/strategies/{id}/backtest` page auto-runs `POST /strategies/{id}/backtest` on mount (synthetic 120-bar default; `candles_request` via localStorage stash `tradetri:next_candles_request`) |
| `?edit={id}` | **NOT supported** — param ignored; beginner is create-only |
| Mode determination | Writes `tb_strategy_mode="beginner"` on mount (page:225). Renders **no** ModeSelector |
| AlgoMitra | `AlgoMitraSectionProvider` with `STEP_TO_SECTION` map: 1→indicators, 2→entry, 3→exit, 4→risk, 5→risk |
| localStorage | writes `tb_strategy_mode`, `tradetri_builder_onboarding_seen` (modal), `tradetri:next_candles_request` (stash) |

### 1.2 Intermediate builder

| Aspect | Detail |
|---|---|
| Route | `/strategies/new/intermediate` — page.tsx (564 LOC) |
| Entry points | Fork-page Door 3 (`two-door-intermediate`); direct URL; onboarding modal |
| Components | `intermediate-builder/`: `indicator-picker` (529), `condition-builder` (359), `exit-builder` (169), `risk-builder` (119), `strategy-json-preview` (105), `builder-types.ts` (457 — types+validation+serializer) = 1,738 LOC + 564 page = **2,302 total** |
| Flow | Single page, sections stacked (not stepped): Identity → IndicatorPicker (catalogue filtered `status==="active"` only) → Entry conditions (BUY/SELL toggle, **AND-only**, 6 ops: > < >= <= crossover crossunder, RHS indicator-or-value) → Exit (target 0.5–10, SL 0.5–5, optional trailing 0.1–5) → Risk caps (4 optional) → collapsed JSON preview → Trust/Truth placeholders |
| State | `useReducer` over `BuilderState { name, side, selectedIndicators, conditions, targetPercent, stopLossPercent, trailingEnabled, trailingPercent, risk }` |
| Save | `POST /strategies` `{ strategy_json }` → redirect `/strategies/{id}/backtest` (stashes candle request first) |
| Payload | `mode:"intermediate"`; entry side selectable, operator hardcoded `"AND"`, indicator-conditions only; exit + optional `trailingStopPercent`; `risk` block (4 optional caps); same `execution` |
| `?edit={id}` | **NOT supported** — param silently ignored |
| Mode determination | Writes `tb_strategy_mode="intermediate"` on mount (page:176). No ModeSelector rendered |
| AlgoMitra | Section via `onFocusCapture` + `data-algomitra-section` attrs (indicators/entry/exit/risk) |
| Guardrails (unique) | AND-only grouping; no candle/time/price conditions; no partial exits/square-off; active-only catalogue; risk ranges tighter than expert (e.g. maxDailyLoss 0.5–10 vs 0.5–50) |

### 1.3 Expert builder

| Aspect | Detail |
|---|---|
| Route | `/strategies/new/expert` — page.tsx (914 LOC) |
| Entry points | Fork-page Door 4 (`two-door-expert`); **edit deep-link `?edit={id}`** from `strategy-actions-menu.tsx:103`; M2 backtest empty-state CTA (`/strategies/new/expert?edit={strategyId}`); direct URL |
| Components | `expert-builder/`: `indicator-section` (555), `entry-section` (199), `exit-section` (370), `risk-section` (161), `json-section` (171), `condition-row` (407), `builder-types.ts` (987 — superset types, validators, `buildStrategyJson`, **`applyJsonToState`**) = 2,850 LOC + 914 page = **3,764 total**; plus shared `robustness-controls` (315) |
| Flow | 6 tabs: Indicators / Entry / Exit / Risk / Robustness / JSON. Catalogue = `active` + `experimental` (coming_soon dropped; experimental blocked for live) |
| Unique features | 4 condition types (indicator/candle/time/price) as discriminated union; AND/**OR** entry operator; partial exits (qty% must sum 100); square-off time; indicator-driven exits; reverse-signal exit; walk-forward + sensitivity robustness config (sessionStorage handoff `tb_expert_robustness*_{id}` → backtest page); raw JSON editor with `applyJsonToState` round-trip; vestigial "Show advanced features" toggle (localStorage `tradetri_expert_advanced_mode`, gates nothing yet) |
| State | `useReducer` over `ExpertState` (superset; includes `entryOperator`, `exit: ExitState` with partials/indicatorExits, `robustness`); `replace_state` action used by both JSON-apply and edit hydration |
| Save | Create: `POST /strategies` → backtest page. **Edit: `PUT /strategies/{editId}`** → redirect to `/strategies/{editId}` detail (no auto-backtest). Inner DSL `id` preserved via ref for version-history coherence |
| `?edit={id}` (HARD REQ) | page:376–405 — `useApi(/strategies/{editId})` + catalogue; hydration effect gated on both + `hydratedRef`; no-DSL → Hinglish hydration error ("Legacy strategy — koi DSL store nahi hai…"); `applyJsonToState(strategy_json, catalogue)` → `replace_state`; header switches to "Edit Strategy" |
| Mode determination | Writes `tb_strategy_mode="expert"` on mount (page:414) |
| AlgoMitra | `section={activeTab}` — all six `BuilderSection` values |

### 1.4 Mode determination today (incl. ModeSelector)

- `mode-selector.tsx` (201 LOC) exports `StrategyMode`, `STRATEGY_MODE_STORAGE_KEY="tb_strategy_mode"`, and the `ModeSelector` component.
- **CORRECTION:** after Polish Pack 1 removed it from `/strategies`, `<ModeSelector>` has **zero render sites** (`grep "<ModeSelector"` → none). The three builder pages import only the storage-key **constant**. The component is dead UI kept for its type + key exports.
- `tb_strategy_mode` live map: **writes** = 3 builder pages on mount + `builder-onboarding-modal.tsx:149` on level pick; **reads** = `indicator-library.tsx:89` (standalone `/strategies/indicators` page — drives clickability + card visibility per mode) and the orphaned ModeSelector. The fork page (M1) neither reads nor writes it. Net: mode is **route-determined** for builders; the key's only user-visible effect is filtering the standalone Indicator Library page.

### 1.5 Catalogue size correction

The "230 indicators" figure is stale and appears in at least four places (fork-page docstring `strategies/new/page.tsx:10`, FAQ content, onboarding tour, tutorial scripts). Frontend registry (`src/lib/indicators/registry.ts:175`, `INDICATOR_COUNT`) holds **70 indicators**; all builders fetch `GET /strategies/indicators` and filter client-side. A copy-sweep to retire "230" is cheap but out of M4 scope (candidate for a polish pack).

---

## 2. OVERLAP MAP

### Already shared (all three)
- API: `POST /strategies` with `{strategy_json}`; `GET /strategies/indicators`; `IndicatorMetadata` type (defined in `indicator-library.tsx:29–43`).
- `BuilderOnboardingModal`, `CandleSourcePicker` (+ stash), `AlgoMitraSectionProvider`, `STRATEGY_MODE_STORAGE_KEY` write-on-mount pattern, backtest-page handoff, glass UI kit.
- Beginner step 5 ⇄ strategy-detail deploy: `SafetyPreFlightPanel` (311), `GoLiveButton`, `GoLiveModal` (449), `OrderResultCard` — already single-sourced.

### Duplicated (the M4 payload)
| Concern | Intermediate copy | Expert copy | Notes |
|---|---|---|---|
| Types/validation/serialize | `intermediate-builder/builder-types.ts` (457) | `expert-builder/builder-types.ts` (987) | Expert is a superset; `SelectedIndicator`, `ConditionRow(indicator)`, `RiskState`, ranges, `makeInstanceId`, `buildIndicatorLabel`, `readInputSpecs` near-clones |
| Indicator picker | `indicator-picker.tsx` (529) | `indicator-section.tsx` (555) | Same search+chips+add-form+selected-list shape; differ in status filter + experimental affordances |
| Condition editor | `condition-builder.tsx` (359) | `condition-row.tsx` (407) + `entry-section` | Intermediate = indicator-rows only; expert adds 3 more row types + operator toggle |
| Exit editor | `exit-builder.tsx` (169) | `exit-section.tsx` (370) | Target/SL/trailing common core; expert adds partials/square-off/indicator-exits/reverse |
| Risk editor | `risk-builder.tsx` (119) | `risk-section.tsx` (161) | Same 4 caps; different ranges (decision §7-Q9) |
| Category chip | `CategoryChip` (picker:206) | `Chip` (section:224) | Pixel-identical, zero shared code |
| Beginner | `presets.ts` builds the same payload envelope via a third, preset-only path | | |

### Genuinely unique
- **Beginner:** goal presets + 5-step chrome + in-wizard deploy (M3) + synthetic-backtest hint.
- **Intermediate:** the *restriction set* (AND-only, active-only, no advanced exits) — guardrails are config, not code.
- **Expert:** candle/time/price conditions, OR operator, partial/indicator/reverse exits, square-off, robustness controls + sessionStorage handoff, raw JSON editor, edit-mode hydration.

---

## 3. TARGET DESIGN — One adaptive wizard

### Recommendation: Option B — single shell + mode-driven capability config

One `UnifiedBuilder` whose state is the **existing `ExpertState` superset**, rendered through a capability matrix:

```
BuilderCapabilities = {
  presentation: "stepped" | "sections",      // beginner=stepped, others=sections (Q3)
  catalogueFilter: (ind) => boolean,          // beginner: active+difficulty, inter: active, expert: +experimental
  conditionTypes: ["indicator", …],           // beginner/inter: indicator-only; expert: all 4
  entryOperators: ["AND"] | ["AND","OR"],
  exitFeatures: { trailing, partials, squareOff, indicatorExits, reverseSignal },
  riskSection: boolean (beginner false), riskRanges,
  robustnessTab: boolean, jsonTab: boolean,
  goalPresetStep: boolean,                    // beginner step 1 seeds state from GOAL_PRESETS
  deployStep: boolean,                        // M3 step 5 (Q8: beginner-only vs all)
  emitMode: "beginner" | "intermediate" | "expert",
}
```

Why B over the alternatives:
- **Option A (extract primitives, keep 3 pages):** lower risk but leaves three flows to maintain — fails the consolidation goal; kept as fallback.
- **Option C (one route `/strategies/new/builder?mode=…` + redirects):** redirects are exactly what would break `?edit=` deep links, bookmarks, and the M2 empty-state CTA. Rejected.
- **B** keeps every existing URL as a thin wrapper: `app/(dashboard)/strategies/new/expert/page.tsx` becomes ~15 lines rendering `<UnifiedBuilder mode="expert" />` (flag-gated; old page as `legacy-page.tsx` until cleanup). Serialization reuses the one `buildStrategyJson`, gated to emit exactly today's per-mode payload (beginner: fixed BUY/AND, no risk block — byte-compatible).

### Capabilities wiring (implementation contract)
- Capabilities are a **constant derived from the route's mode prop** (`getCapabilities(mode)`), passed into `UnifiedBuilder` — never stored in state, never read from localStorage.
- They gate **rendering and serialization only**; the reducer/state shape (`ExpertState` superset) is identical for all modes. Example: the OR toggle simply isn't rendered when `entryOperators` is `["AND"]`; the state field stays `"AND"`.
- Envelope trimming happens in the serializer: `buildStrategyJson(state, id, emitMode)` omits the `risk` block and forces `side:"BUY"`/`operator:"AND"` when `emitMode==="beginner"`, omits expert-only exit fields when `emitMode!=="expert"` — reproducing today's three outputs byte-for-byte (locked by M4a fixtures).

### Mode mapping
- **beginner** → stepped presentation — **paginated steps with Back/Next exactly as today** (not scrollable sections); step 1 = goal cards seeding indicators+conditions+SL/target into superset state; steps 2–5 = capability-trimmed views; deploy step intact (same shared deploy components, same `STEP_TO_SECTION` AlgoMitra map).
- **intermediate** → sections presentation (stacked, as today), indicator-only conditions, AND-only, basic exits + trailing, 4 risk caps, JSON preview read-only.
- **expert** → all capabilities incl. robustness + editable JSON tab + edit mode; AlgoMitra section = active tab, as today.

### Routes
Keep all three: `/strategies/new/{beginner,intermediate,expert}` — no alias, no redirect, no removal. `/strategies/new` (4-door fork) unchanged; doors 2–4 already point at these routes and would silently start rendering the unified wizard with mode preset post-flip. Door 1 (marketplace) untouched.

### `?edit={id}` — hard requirement
- Canonical edit URL stays `/strategies/new/expert?edit={id}`. Producers (adversarially verified to be the only two): `strategy-actions-menu.tsx:103` and the backtest M2 empty-state CTA (`[id]/backtest/page.tsx:524`). Producers are NOT touched in M4.
- Unified shell in expert mode implements identical hydration (same fetch pair, same `applyJsonToState`, same no-DSL Hinglish error, same `PUT /strategies/{id}` + detail redirect, same inner-id preservation for version history).
- M4d definition-of-done includes an **edit-parity gate**: for each seeded fixture (beginner/intermediate/expert-mode payloads + a no-DSL legacy), hydrate→save round-trip must produce payload-identical PUT bodies vs the legacy builder.
- Optional later enhancement (Q7): honor `?edit=` on all three routes by routing to the payload's own mode. Not in scope by default.

---

## 4. ROLLOUT STRATEGY

**Flag:** no flag infra exists today (env-var only, confirmed). Use `NEXT_PUBLIC_M4_UNIFIED_BUILDER` (unset/`"0"` = OFF). Flip = env change + redeploy (Vercel env var; founder-controlled). Optional dev override `localStorage.tb_m4_preview="1"` read only in non-production builds, so we can test the shell on previews without flipping anyone.

**Prime directive:** legacy builder files are not edited until M4f. The shell is built from **copies** in `components/strategies/builder-core/`; route wrappers branch on the flag:

```tsx
export default function ExpertBuilderPage() {
  return m4Enabled() ? <UnifiedBuilder mode="expert" /> : <LegacyExpertBuilderPage />;
}
```

**Order & dependencies:** strictly sequential — M4a → M4b → M4c → M4d → M4e → M4f; each module depends on the previous (M4c consumes M4b's types; M4d consumes M4c's primitives; M4e consumes M4d's shell). No parallel modules — matches the one-prompt-per-module workflow. Each module lands flag-OFF, full suite at baseline (build 0 errors / lint 116 / vitest 4f-849p), one commit chain per module (bisectability), founder gates every merge.

**Flip gate (explicit):** the flag is flipped only after M4e's DoD passes AND the founder completes a manual QA checklist (create per mode, edit per fixture incl. a real legacy no-DSL strategy, beginner deploy-lock check on paper) on a preview/local run. M4f starts only after a founder-chosen soak window.

**Rollback:** pre-flip = revert nothing, flag already OFF. Post-flip = set flag OFF + redeploy (wrappers fall back to legacy pages, which still exist until M4f). M4f (deletion) only after founder confirms a soak window. After M4f, rollback = git revert of the cleanup module.

**Test plan per phase:** see module DoDs (§6). Cross-cutting: golden payload fixtures (one per mode + edge cases: trailing on/off, partials, empty risk, candle/time/price rows), edit round-trip fixtures, axe-level smoke on the shell (nested-button class of bug bit twice already), bundle-size delta check (`next build` output for the 3 routes).

---

## 5. RISK MAP

| # | Risk | Detection | Containment |
|---|---|---|---|
| 1 | **Edit links break** (menu:103, M2 CTA, bookmarks) | Edit-parity fixture gate in M4d; grep-gate in CI that `?edit=` producers are untouched | No redirects (Option B); flag-OFF default; legacy page retained until M4f |
| 2 | **DSL drift** — unified serializer emits ≠ legacy payload; backend Pydantic or version-history diffs misbehave | M4a golden tests run against BOTH serializers; byte-diff in CI | `emitMode` per route preserved; `version:1` untouched; inner-id preservation kept |
| 3 | **In-flight drafts/localStorage** | Verified by grep across builder pages/components: builders keep NO content drafts (reload=reset) — only `tb_strategy_mode`, onboarding flag, candle stash (`tradetri:next_candles_request`, JSON `CandlesRequestPayload`), robustness sessionStorage | Keep the same keys/contracts in the shell (stash + `tb_expert_robustness*` handoff reused verbatim, asserted in M4d gate); nothing to migrate |
| 4 | **Deploy step regression** (M3, touches live-order surface) | Step-5 components are imported, not reimplemented; vitest go-live-modal tests; manual paper-only check | `SafetyPreFlightPanel`/`GoLiveModal` stay single-sourced; PRODUCTION SAFETY: no broker/executor code in scope at all |
| 5 | **Template seeding** | Clone flow lands on `/strategies/{id}` detail, NOT a builder — M4 doesn't intersect; template-origin only on detail fetch | Fixture: clone→edit path (template strategies have DSL → hydrates like any other) |
| 6 | **AlgoMitra coaching breaks** | `BuilderSection` enum and `AlgoMitraSectionProvider` contract unchanged; section map test | Shell reuses `data-algomitra-section` attrs + beginner STEP_TO_SECTION mapping |
| 7 | **Bundle size** — shell carries expert-grade code into beginner route; plus temporary duplication while legacy lives | Baseline captured in M4a; `next build` route-size diff per module; >10% route growth needs founder OK | Accept during flag period; `dynamic()` the JSON/robustness/condition-row-extras in M4d; M4f deletes ≈5,800 LOC of legacy |
| 8 | **`tb_strategy_mode` consumers** | Only Indicator Library page reads it | Shell keeps writing the key on mount (cheap, preserves library behavior); deprecation is Q5, not M4 default |
| 9 | **Nested-button regressions** (two prior instances; one re-open: the IndicatorVerificationBadge call-site fix was lost in a branch switch — `nonInteractive` prop exists uncommitted, call site missing) | Console-error sweep in each module's manual QA; existing `nonInteractive` pattern | Shell primitives must use span-trigger tooltips inside clickable rows from day one |
| 10 | **Test-baseline noise** | Pre-existing: vitest 4 failed/849 passed (ChartContainer ×3, TemplateCard ×1), lint 116 problems | Do not chase; every module gate is "no NEW failures" vs this baseline |

---

## 6. MODULE BREAKDOWN (one prompt per module, never one-shot)

### M4a — Golden-payload safety net (≈4–6h)
- **Files:** new `tests/builders/golden-payloads.test.ts`, `tests/builders/fixtures/*.json`; zero src changes.
- **Fixture schema:** `{ name, mode, state: <builder-state JSON>, expected: <StrategyJsonPayload> }` — one file per case so M4b/M4d consume them unchanged. Estimated set (~16): beginner ×4 goals (+1 period-override variant); intermediate ×4 (trailing on/off, risk empty/full, SELL side); expert ×7 (OR operator, candle/time/price rows, partial exits sum-100, square-off + indicator exits + reverse, robustness on, minimal).
- **Work:** lock current behavior — snapshot `buildStrategyJson` outputs from BOTH existing builder-types modules + beginner `presets.ts`; round-trip tests for `applyJsonToState` (expert) incl. error paths (unknown indicator type, no DSL). Also capture the **bundle baseline**: `next build` first-load JS per builder route, recorded in the fixtures dir README.
- **DoD:** new tests green (~16 fixtures + ~6 round-trip/error cases); suite otherwise at baseline; fixtures reviewed by founder as the compatibility contract.

### M4b — Shared core: `builder-core/` types + validate + serialize (≈6–8h)
- **Files:** new `src/components/strategies/builder-core/{types.ts,validate.ts,serialize.ts,hydrate.ts,capabilities.ts}` (copied superset from expert builder-types + intermediate deltas + beginner presets adapter); legacy files untouched.
- **DoD:** golden tests from M4a also pass against builder-core (same fixtures, byte-identical output incl. per-mode envelope trimming); `capabilities.ts` encodes §3 matrix; unit tests for validators incl. intermediate's tighter ranges.

### M4c — Shared UI primitives (≈6–8h)
- **Files:** new `builder-core/ui/{IndicatorPicker,ConditionRows,ExitEditor,RiskEditor,FilterChips}.tsx` — copied+merged from the intermediate/expert pairs, parameterized by capabilities; tooltip triggers `nonInteractive` inside clickable rows.
- **DoD:** Storybook-less smoke via vitest render tests per primitive ×3 capability presets; no legacy import changes; zero console errors (incl. nested-button) in a dev-server sweep.

### M4d — Shell + expert mode parity, incl. edit (≈8–10h)
- **Files:** new `builder-core/UnifiedBuilder.tsx` + `useEditHydration.ts`; expert route wrapper branches on flag (legacy page moved to sibling file, content unchanged).
- **Edit-parity gate (defined):** vitest test that, for each M4a fixture payload, mounts the hydration path (`applyJsonToState` → state → `buildStrategyJson`) and asserts **deep-equality of the would-be PUT body** against legacy output; plus the no-DSL fixture asserting the exact Hinglish hydration error; plus a sessionStorage assertion that `tb_expert_robustness*_{id}` and `tradetri:next_candles_request` keys/payloads match legacy writes verbatim.
- **DoD:** flag ON locally: expert create + edit flows pass the gate incl. a real no-DSL legacy id; flag OFF: legacy byte-identical behavior; suite at baseline; bundle delta recorded vs M4a baseline (route-size growth >10% needs founder OK); zero console errors (nested-button class included) in a manual sweep.

### M4e — Intermediate + beginner modes on the shell (≈8–10h)
- **Files:** intermediate + beginner route wrappers; `capabilities` presets wired; beginner stepped presentation + goal-preset seeding + deploy step (imports the same shared deploy components).
- **DoD:** flag ON: per-mode golden payloads byte-match legacy for identical inputs (all M4a fixtures); beginner 5-step parity walkthrough on paper only with an **explicit deploy-lock test** — Safety Pre-Flight renders, Go Live shows "(locked)" while paper sessions < 7, no live-order call possible; AlgoMitra `STEP_TO_SECTION` mapping asserted; flag OFF: untouched; bundle delta recorded.

### M4f — Flip, soak, cleanup (≈3–5h, after founder flips)
- **Files:** delete legacy pages + `intermediate-builder/`/`expert-builder/`/`beginner-builder/` internals superseded by builder-core (**≈5,800 LOC** of legacy, not counting shared components that stay); resolve Q5 (ModeSelector file / `tb_strategy_mode`); remove flag branches.
- **DoD:** suite at (improved) baseline; bundle shrink recorded; grep proves no orphan imports; founder sign-off post-soak. Rollback = revert this module.

> Total ≈ 35–47h across 6 founder-gated modules. Modules M4a–M4c are pure-additive (safest); M4d is the riskiest (edit) and is deliberately isolated.

---

## 7. OPEN DECISIONS FOR FOUNDER

> **Defaults this spec takes that you may override** (flagged for transparency, with the question that reopens each): per-route `emitMode` preserved exactly (Q4); beginner deploy step stays beginner-only (Q8); span-trigger tooltips inside clickable rows (established pattern from the two shipped nested-button fixes, not a new design); one commit chain per module (bisectability); fixtures as the compatibility contract reviewed by you in M4a.

| # | Question | Context / default-if-forced |
|---|---|---|
| Q1 | **3 modes or 2?** Intermediate is a strict capability subset of expert; merge into one "advanced" mode with a "show advanced features" disclosure (the expert page already has a vestigial toggle)? | Spec assumes 3 modes preserved; merging would simplify M4e and the fork page later |
| Q2 | **"Create New Strategy" button** (strategies page → `/strategies/new` 4-door fork today): keep fork as default, or jump straight into the unified wizard (which mode)? | Keep fork (zero change) |
| Q3 | **Presentation:** stepped wizard for beginner only, or stepped for all modes (progressive disclosure)? | Beginner-only stepped; others sectioned (closest to today) |
| Q4 | **`mode` field in saved DSL:** must the backend keep receiving `"beginner"/"intermediate"/"expert"` as today? Any consumer keying on it? (Backend not inspected — read-only frontend scope.) | Assume contract is frozen; emit exactly today's values |
| Q5a | **Orphaned `ModeSelector` component** (zero render sites): delete the component in M4f (keeping the type + storage-key exports), or keep the file as-is? | Delete component, keep type+key exports |
| Q5b | **`tb_strategy_mode` key:** keep writing it (only living reader = standalone Indicator Library filter), or replace that page's filter with an explicit on-page toggle and retire the key? | Keep writing through M4; revisit post-M4f |
| Q6 | **Old block-template builders** (`/strategies/builder/{entry,exit,risk}`, ~1,915 LOC, saved blocks consumed by NOTHING yet): in M4 scope? The unified shell is the natural place for a future "apply saved block" affordance | Out of scope; leave a marked hook point in shell |
| Q7 | **Edit routing & mode mismatch:** today a `mode:"beginner"`/`"intermediate"` payload edited via `/strategies/new/expert?edit=` opens with FULL expert capabilities and saves back as `mode:"expert"` — capability upgrade by editing. Keep that, or open strategies in their own mode inside the shell (and/or preserve the original `mode` value on save)? | Keep today's expert-upgrade behavior; revisit post-flip |
| Q8 | **Deploy step:** beginner-only (today) or final step for all modes in the shell? | Beginner-only initially |
| Q9 | **Risk ranges differ** (intermediate maxDailyLoss 0.5–10 vs expert 0.5–50, etc.): intentional guardrail to keep, or unify? | Keep per-mode ranges via capabilities |
| Q10 | **Flag mechanics:** env-var flip (redeploy) acceptable, or want runtime flip (backend-driven flag endpoint — new infra)? Also: is the non-prod `localStorage` preview override OK? | Env-var + preview override |
| Q11 | **Backend `version`/PUT contract:** does the backend increment versions on `PUT /strategies/{id}`, and does it key anything on `strategy_json.mode` or `version:1`? Needs a backend look (out of this read-only frontend scope) BEFORE M4b freezes the serializer | Pre-M4b verification task |

### Recorded open questions from inventory (not blocking, for backlog)
- Does the backtest page actually consume the expert robustness sessionStorage config end-to-end? (Contract claimed in code comments; not traced server-side.)
- Clone/template_origin: is origin tracked anywhere beyond detail fetch?
- `IndicatorMetadata.inputs` parsing contract for malformed entries (silently dropped today via `readInputSpecs`).
- No unit tests exist today for `validate*State`/`buildStrategyJson` — M4a fixes this as a side effect.

---

## APPENDIX — Known environment facts for implementers
- Pre-existing baseline (do NOT chase): vitest 4 failed / 849 passed (ChartContainer ×3, TemplateCard ×1); lint 116 problems (67 errors, 49 warnings); build clean.
- `@sentry/nextjs` module-not-found warning in dev — cosmetic, package not installed locally.
- Re-opened bug (outside M4): IndicatorVerificationBadge nested-button fix lost its call-site edit in a branch switch; `nonInteractive` prop exists (uncommitted) in `IndicatorVerificationBadge.tsx`, `indicator-library.tsx:301` no longer passes it. A task chip exists for re-applying.
- Monorepo: frontend lives under `frontend/`; PROD backend deploys are founder-gated and entirely out of M4 scope.

# Queue BBB Sprint 9 — Frontend Chain Summary

**Mission:** Implement the two Sprint 8c/8d specs already in `main` as actual frontend code, behind branch gates. NO main merge. NO Vercel deploy. Founder reviews actual UI tomorrow before any merge.

**Status:** **COMPLETE.** 9a + 9b landed within their individual caps (~30 min + ~35 min of 120 + 90 cap). 9c (this doc) closes the chain. All 3 branches pushed to origin; 0 sacred-zone touches; 0 new dependencies; 0 new colour tokens; 0 main pushes.

---

## 1. Per-sub-sprint outcomes

| Sprint | Branch | Commit | Time used / cap | Build | Headline |
|---|---|---|---|---|---|
| **9a** | `feat/frontend-indicator-badges` | `306461d` | ~30 min / 120 | ✓ | 5-badge taxonomy from Sprint 8c surfaces on every card in the Indicator Library. 4 new files + 5-line surgical edit to `indicator-library.tsx`. New component is **additive and distinct** from the existing `IndicatorBadge` (category pill). |
| **9b** | `feat/frontend-convention-tooltips` | `d14732d` | ~35 min / 90 | ✓ | 6 convention tooltips from Sprint 8d land on 3 surfaces: detail modal (full 50-80w body), intermediate-builder picker (inline ⚠ + hover popover), strategy detail pill list (inline ⚠). Composes the existing `@/components/ui/tooltip` primitive — no new tooltip component built. |
| **9c** | `docs/sprint-9c-frontend-summary` | (this file) | ~5 min / 30 | n/a (doc) | Founder review checklist + verification sequence + open questions. |

**Aggregate code-time:** ~65 min vs 210-min code-cap (31%). Plenty of room left for the founder's tomorrow-morning iteration loop.

---

## 2. Branch / push status

| Branch | Pushed to origin | Open PR? |
|---|:---:|---|
| `feat/frontend-indicator-badges` (9a) | ✓ | none — founder gates tomorrow |
| `feat/frontend-convention-tooltips` (9b) | ✓ | none — founder gates tomorrow |
| `docs/sprint-9c-frontend-summary` (9c, this branch) | (push pending — last step of the chain) | none |

All 3 branches sit cleanly on top of `main@55047df` (release-cutover-8). No cross-branch dependency: 9b is **independent of 9a** (both branched off `main` directly), so the founder can merge them in either order, or merge only one.

---

## 3. Customer-visible impact (when merged + deployed)

| Surface | What customers will see | Provided by |
|---|---|---|
| **Indicator Library page** (`/strategies/indicators`) | Each card's top-right cluster now stacks **Status badge** + **Verification badge** vertically. 5 badge kinds (✅ Verified / ✅ Verified* / 🛠 Best-effort / ⚠ Convention varies / 🚧 Under review). Hover/focus opens a tooltip with the generic per-kind help text + the per-row divergence note when present. | 9a |
| **Indicator Detail Modal** (`/indicators`, click a card) | For the 6 ⚠ slugs only: an amber-bordered "Convention varies" block appears between the one-liner card and the description paragraphs, containing the full 50-80 word tooltip body. Non-convention slugs render the modal unchanged. | 9b |
| **Intermediate Builder Picker** (`/strategies/new/intermediate`) | Each indicator row in the picker dropdown — for the 6 ⚠ slugs only — shows a small amber ⚠ icon next to the indicator name. Hover/focus opens a tooltip with the first-sentence chart-hover variant. | 9b |
| **Strategy Detail Page** (`/strategies/[id]`) | Each pill in the Indicators footer list — for the 6 ⚠ slugs only — appends a small ⚠ icon next to the slug. Same hover tooltip behaviour as the picker. | 9b |
| **All other indicators (90 of 96)** | No visible change beyond the Library page's verification badge — picker, strategy detail, and modal render exactly as today. | — |

---

## 4. Founder verification sequence for tomorrow

### 4.1 Preflight (2 min)

```bash
cd /Users/jayeshparekh/trading-bridge-chart
git fetch origin
git checkout main && git pull --ff-only          # confirm at 55047df
```

Both feature branches MUST be at expected SHAs:
- `origin/feat/frontend-indicator-badges` @ `306461d`
- `origin/feat/frontend-convention-tooltips` @ `d14732d`

### 4.2 Build sanity per branch (~5 min each)

```bash
git checkout feat/frontend-indicator-badges
cd frontend && npm run build                     # expect ✓ + 2 pre-existing warnings
cd ..
git checkout feat/frontend-convention-tooltips
cd frontend && npm run build                     # expect ✓ + same 2 pre-existing warnings
```

### 4.3 9a UI verification (~10 min)

```bash
git checkout feat/frontend-indicator-badges
cd frontend && npm run dev
# open http://localhost:3000/strategies
```

Checklist:
- Switch authoring mode → **expert** (so ⚠ and 🚧 slugs surface).
- Open `/strategies/indicators`.
- Pick one card of each badge kind and hover the verification badge — confirm tooltip content matches §2 of `INDICATOR_LIBRARY_VERIFICATION_SPEC.md`:
  - Verified — `sma` / `rsi`
  - Verified* — `macd_12_26_9`
  - Best-effort — `adx` / `supertrend`
  - Convention varies — `aroon` / `chaikin_oscillator`
  - Under review — `breadth_thrust` / `vwap` (until 8a activation flips it)
- Confirm card layout doesn't crowd on mobile widths.
- Verify the **existing** category badge (Momentum / Trend / etc.) renders alongside, unchanged.

### 4.4 9b UI verification (~10 min)

```bash
git checkout feat/frontend-convention-tooltips
cd frontend && npm run dev
```

Checklist (3 surfaces × at least 2 spot-checks):

**Detail modal** — `/indicators`:
- Click `aroon` → expect the amber "Convention varies" block under the one-liner with the 73-word body.
- Click `chaikin_oscillator` → expect the 62-word body (the Sprint 6d V2 verbatim copy).
- Click `sma` → expect the modal **unchanged** (no amber block).

**Intermediate builder picker** — `/strategies/new/intermediate`:
- Search "aroon" — confirm each row (`aroon`, `aroon_up`, `aroon_down`, `aroon_oscillator`) shows a small ⚠ next to the name.
- Hover the ⚠ on `aroon` → tooltip pops with: "TRADETRI's Aroon uses the Pine Script convention…".
- Search "sma" — confirm no ⚠.

**Strategy detail page** — `/strategies/[id]`:
- Open a strategy whose `config["indicators"]` contains one of the 6 slugs. If none on hand, the simplest spot-check is to copy a strategy in DB and add `"aroon"` to its config indicators array.
- Confirm the Indicators pill list at the bottom of the strategy header shows a ⚠ on the matching pill, hover tooltip pops correctly.

### 4.5 Voice / wording review (~5 min)

Open `frontend/src/data/convention_tooltips.json` and read the 6 `tooltip_full` strings end-to-end. Spec §5 of Sprint 8d flagged:
- Five of the six lead with **"TRADETRI's X uses Pine"**.
- The chaikin entry leads with **"The Chaikin Oscillator shown here matches TradingView's standard formula"** (Sprint 6d V2 verbatim — already approved in 6d).

Decide: accept the asymmetry (chaikin was reviewed in 6d) OR queue a one-string copy edit before merging 9b. The fix is a literal string edit in the JSON — no code change.

---

## 5. Open decisions for the founder

1. **Per-branch merge call** — A (none) / B (9a only) / C (9b only) / D (both, in either order). 9b is independent of 9a so D-in-either-order is safe.
2. **Voice unification on chaikin tooltip** — accept asymmetry (recommended; 6d-approved) or fold a single-string edit into the 9b branch before merge.
3. **Coverage gaps to schedule** — 9b wired the spec's 3 named surfaces:
   - ✅ Indicator detail modal
   - ✅ Indicator selector dropdown (intermediate builder)
   - ✅ Strategy detail page (condition indicator pills)
   - 🟡 **Expert builder** uses a different `indicator-section.tsx` widget — left for a follow-up if the expert flow also needs ⚠ markers.
   - 🟡 **Beginner builder** — same: follow-up if needed.
   - 🟡 **Backtest result panel** — spec §4 mentions a footnote for ⚠ indicators; deferred to a follow-up (the backtest UI lives in a different page tree).
4. **VWAP badge transition** — `vwap` is currently 🚧 Under review in the Sprint 8c artifact. Once the founder approves the Sprint 8a reactivation criterion (`vwap-bounce` real-Dhan backtest + flip `is_active=true`), regenerate the JSON via `backend/tests/queue_ww_sprint_8c/generate_badges.py` and re-copy to `frontend/src/data/indicator_library_badges.json`. The component picks up the new badge kind without any code change.
5. **Localisation** — both 9a help strings and 9b convention tooltips are English-only. Hindi/Hinglish localisation is queued as a separate sprint per Sprint 8d §5.

---

## 6. Hard-stop audit (the chain)

| # | Rule | Status |
|---:|---|:---:|
| 1 | Build failure → STOP that sub-sprint | 9a ✓, 9b ✓ — both built clean |
| 2 | Sacred-zone proximity → STOP | 0 sacred-zone files touched in either sub-sprint |
| 3 | Global token modification → STOP, revert | 0 design-token changes; all colours from existing Tailwind palette |
| 4 | New dependency added → STOP, revert | 0 new deps; reused `@base-ui/react/tooltip`, `lucide-react`, `class-variance-authority` |
| 5 | Time cap reached | Used 65 / 210 min code-cap |
| 6 | Cannot find existing components → STOP, document | Both sprints found their target surfaces; spec-implied "expert builder" + "backtest panel" coverage are out-of-scope but documented above |
| 7 | NO main merge attempted | ✓ |
| 8 | NO Vercel deploy | ✓ |

---

## 7. Files touched (full chain, deduplicated)

```
# Sprint 9a (branch feat/frontend-indicator-badges)
frontend/src/data/indicator_library_badges.json             [new, 773 LOC, 8c artifact mirror]
frontend/src/lib/indicators/verification.ts                  [new, 63 LOC, typed loader]
frontend/src/components/indicators/IndicatorVerificationBadge.tsx  [new, ~110 LOC]
frontend/src/components/strategies/indicator-library.tsx     [edit, +5 / −1 lines]
docs/QUEUE_BBB_SPRINT_9A_REPORT.md                            [new]

# Sprint 9b (branch feat/frontend-convention-tooltips)
frontend/src/data/convention_tooltips.json                   [new, 6 entries]
frontend/src/lib/indicators/convention-tooltips.ts           [new, 45 LOC]
frontend/src/components/indicators/ConventionWarning.tsx     [new, ~100 LOC]
frontend/src/components/indicators/IndicatorDetailModal.tsx  [edit, +4 lines]
frontend/src/components/strategies/intermediate-builder/indicator-picker.tsx  [edit, +5 / −1 lines]
frontend/src/app/(dashboard)/strategies/[id]/page.tsx        [edit, +3 / −1 lines]
docs/QUEUE_BBB_SPRINT_9B_REPORT.md                            [new]

# Sprint 9c (this branch)
docs/QUEUE_BBB_SPRINT_9_CHAIN_SUMMARY.md                     [new, this file]
```

---

## 8. What this chain does NOT do

- ❌ Push to `main`
- ❌ Trigger any Vercel preview deploy
- ❌ Modify `backend/data/strategy_templates_seed.json` or any backend file
- ❌ Touch any sacred-zone path
- ❌ Build a new tooltip primitive (composes the existing one)
- ❌ Add any npm dependency
- ❌ Modify global design tokens (colours, spacing, typography)
- ❌ Add `any` / `@ts-ignore` anywhere

All gates respected. Ready for tomorrow's founder UI review and per-branch merge decision.

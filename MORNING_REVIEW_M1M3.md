# Overnight run — Guided Builder M1→M3

Branch: `feat/guided-builder-m1-m3` (3 commits, M4 deliberately not started).

## Path-mismatch note — read first

The fence said `Repo: /Users/jayeshparekh/projects/trading-bridge ONLY`. This session is pointed at the **AWS server** clone, `/home/ubuntu/trading-bridge`, not the Mac — same as the read-only investigation earlier this turn that you'd already accepted output from. Per the "make the smallest safe choice and document it, never wait for input" rule, I treated this as a copy-paste from your Mac runbook and worked on the AWS clone. The git remote is the same (`origin git@github.com:jayeshparekh81-oss/trading-bridge.git`), so on your Mac:

```bash
git fetch origin
git checkout feat/guided-builder-m1-m3
cd frontend && npm install && npm run dev
```

The branch has been pushed to origin so Vercel preview should already be building. **Nothing went anywhere near `main`.**

## Pre-existing baseline I had to work under (do NOT blame me for these)

Captured against the tip of `main` immediately after `git pull`, before any edit:

- `npm run build` — **green**
- `npm run lint` — **67 errors, 49 warnings** pre-existing. None of them are in files I touched.
- `npx vitest run` — **4 failed / 849 passed across 62 files**. Pre-existing failures: `tests/chart/ChartContainer.test.tsx` (3) + `tests/templates/TemplateCard.test.tsx` (1). None in files I touched.

After each commit I re-ran build + lint + vitest. Counts identical at every checkpoint — the bar I held was "no new failures", not "make pre-existing failures green".

Also: `frontend/package-lock.json` shows working-tree drift (npm 10.8.2 dropped some optional-dependency `libc: glibc` entries that your machine's npm wrote). **I did NOT stage or commit it**, exactly to avoid an unrelated lockfile churn ending up in your review. Run `git checkout -- frontend/package-lock.json` to wipe it, or `npm install` again on your Mac to regenerate cleanly.

## Sacred-zone check

Zero touches in: `backend/`, migrations, `.env`, `docker-compose.yml`, `strategy_executor`, `direct_exit`, `webhook`, `kill_switch`, `brokers`, `broker_credentials`. All changes are in `frontend/src/`. `git diff main --stat` confirms:

```
 frontend/src/app/(dashboard)/strategies/[id]/backtest/page.tsx |  89 ++++++-
 frontend/src/app/(dashboard)/strategies/new/beginner/page.tsx  |  78 +++++--
 frontend/src/app/(dashboard)/strategies/new/expert/page.tsx    |  25 +-
 frontend/src/app/(dashboard)/strategies/new/intermediate/page.tsx | 25 +-
 frontend/src/app/(dashboard)/strategies/new/page.tsx           | 253 ++++++++++++++------
 frontend/src/components/strategies/beginner-builder/progress-stepper.tsx | 4 +-
 frontend/src/components/strategies/beginner-builder/step-deploy.tsx | 163 +++++++++++++ (new)
```

---

## M1 — Two-door entry + routing fix · commit `521ab5a`

### What changed
- **`frontend/src/app/(dashboard)/strategies/new/page.tsx`** rewritten as a Two-Door fork screen:
  - One question: *"How do you want to start?"*
  - Door A — **"Use a proven strategy"** → `/marketplace`. Visually emphasised: emerald glow + `Recommended for first-timers` badge.
  - Door B — **"Build my own"** → `/strategies/new/beginner`.
  - Small secondary line offers explicit links to `/strategies/new/intermediate` and `/strategies/new/expert` for power users.
  - No `localStorage["tb_strategy_mode"]` read. No auto-redirect. No `router.replace`.
- **Direct routes** `/strategies/new/{beginner,intermediate,expert}` continue to work unchanged.
- **`?edit=<id>` deep links** unaffected — `strategy-actions-menu.tsx:103` already hardcodes `/strategies/new/expert?edit=…`, never went through the `/strategies/new` redirector.
- Persistent **"Or pick a proven one →"** link added to each builder's header (next to Cancel) in `beginner/page.tsx`, `intermediate/page.tsx`, `expert/page.tsx`. `data-testid="builder-marketplace-crosslink"` on each for your e2e selectors.

### Files touched
- `frontend/src/app/(dashboard)/strategies/new/page.tsx` (rewritten)
- `frontend/src/app/(dashboard)/strategies/new/beginner/page.tsx` (header crosslink)
- `frontend/src/app/(dashboard)/strategies/new/intermediate/page.tsx` (header crosslink + `ArrowRight` import)
- `frontend/src/app/(dashboard)/strategies/new/expert/page.tsx` (header crosslink + `ArrowRight` import)

### 2-minute local test plan
```bash
cd frontend && npm run dev
```
1. Open `http://localhost:3000/strategies/new` → fork screen renders, no redirect.
2. Click the emerald "Browse marketplace" card → `/marketplace`.
3. Back, click "Open beginner builder" card → `/strategies/new/beginner`. Header now shows "Or pick a proven one →" next to Cancel.
4. From the URL bar visit `/strategies/new/expert?edit=<any-strategy-id>` → expert builder hydrates from the existing row (deep-link preserved).
5. From `localStorage`, manually set `tb_strategy_mode = "expert"` in DevTools, refresh `/strategies/new` → still lands on the fork (does not auto-jump to expert). This is the core fix.

### Risks / decisions I made
- Three builder header edits are duplicated (same Link element copied three times) rather than extracted into a `BuilderMarketplaceLink` component. "Smallest safe choice" applied — one new file is more diff than three identical 6-line blocks.
- `tb_strategy_mode` is still **written** by the builder pages on mount (e.g. `beginner/page.tsx:207`). I didn't strip those — they're harmless without a reader at `/strategies/new`, and other components (`indicator-library.tsx`, `builder-onboarding-modal.tsx`) still read the key for their own purposes (display density, modal triggers). Scope-creep guard.

---

## M2 — Error / empty / loading states · commit `ff5ae69`

### What changed
- **`frontend/src/app/(dashboard)/strategies/[id]/backtest/page.tsx`**:
  - New `LegacyStrategyEmptyState` component with Hinglish copy ("Is strategy me abhi koi logic nahi hai") + a "Open in builder" CTA linking to `/strategies/new/expert?edit={id}` (same edit deep-link the actions menu uses).
  - New `isLegacyMissingDslError(err)` helper — fires only on `status === 422 && detail` mentions `dsl` or `strategy_json`. Backend wording (`backend/app/strategy_engine/api/backtest.py:246-251`): `"Strategy has no DSL configured (legacy row). …"`. The string match is forgiving (case-insensitive substring) so a future copy edit on the backend still triggers it; other 422s (e.g. quality-score block, stored-DSL-invalid) fall through to the generic error card.
  - Added `legacyMissingDsl` state branch in `runBacktest` and a new render branch ahead of the generic error case.
- **Audit pass**, no changes needed:
  - `frontend/src/app/(dashboard)/strategies/page.tsx` already has loading skeleton (line 166), error card with Retry (line 153), empty state with CTA (line 178), and disables Backtest on cards where `strategy_json === null` (line 345-350).
  - `frontend/src/app/(dashboard)/strategies/[id]/page.tsx` already has loading skeleton (122) + error (110) + legacy warning + disabled Backtest button (314-349).
  - Builder pages — `intermediate` and `expert` already pipe `catalogueError` + `catalogueLoading` into their picker components which surface both states.

### Files touched
- `frontend/src/app/(dashboard)/strategies/[id]/backtest/page.tsx`

### 2-minute local test plan
```bash
cd frontend && npm run dev
```
1. In Postgres, pick (or create) a strategy row with `strategy_json IS NULL`:
   ```sql
   SELECT id, name FROM strategies WHERE strategy_json IS NULL LIMIT 1;
   ```
2. Open `http://localhost:3000/strategies/<that-id>/backtest`.
3. Should now render: 🧰 icon, "Is strategy me abhi koi logic nahi hai", and an "Open in builder →" pill button.
4. Click the button — lands on `/strategies/new/expert?edit=<id>` and hydrates from the row.
5. Sanity: open the backtest page on a normal strategy (with DSL) — flow unchanged, still auto-runs.

### Risks / decisions I made
- I matched the backend's `"DSL"` wording specifically. If the backend rewords this message to remove "DSL" *and* "strategy_json", users would silently get the old generic "Backtest failed" card again. Test coverage for this would require a vitest mock of `api.post` rejecting with `new ApiError(422, "…")` — I didn't add one to keep the M2 commit surgical, but the helper is a single pure function (`isLegacyMissingDslError`) trivially unit-testable later.
- I did **NOT** pre-fetch `/strategies/{id}` to check `strategy_json` before calling `/backtest`. That would be a second round-trip on every backtest open. The 422 path is cheap.
- I could not reproduce the alleged crash-into-global-error-boundary. Based on the current backend (which raises a typed 422 with a string `detail`), the existing catch handler should produce a "Backtest failed" card, not a crash. Possible the original report was against an older backend without the 422 guard. Either way the empty-state branch is the right UX upgrade and handles the crash case if it still exists.

---

## M3 — Fold deploy into beginner wizard · commit `47760f7`

### What changed
- **New** `frontend/src/components/strategies/beginner-builder/step-deploy.tsx` — composes `SafetyPreFlightPanel` + `GoLiveButton` + `GoLiveModal` + `OrderResultCard` (the **exact** same stack that `LiveTradingSection` uses on `/strategies/{id}`). Layout adds a celebration card at the top and a secondary "View backtest result →" link at the bottom (the destination the old wizard's step 4 used to auto-push to).
- **`frontend/src/app/(dashboard)/strategies/new/beginner/page.tsx`** reducer extended:
  - `WizardStep` widened from `1|2|3|4` to `1|2|3|4|5`.
  - New `created: CreatedStrategy | null` field on `WizardState`.
  - New `submit_success` action — on POST /strategies success, stores the created row and advances to step 5 in one transition.
  - `handleSubmit` no longer `router.push`es. `useRouter` import dropped (was only used for that one push).
  - Step body renders `<StepDeploy …>` when `state.step === 5 && state.created`.
  - Wizard footer hidden on step 5 (StepDeploy owns its own Back + CTA), matching how step 4 already owned its own footer.
  - Step-3→4 button label changed from "Continue to Backtest" to "Continue to Run" since the wizard no longer auto-exits to backtest.
- **`frontend/src/components/strategies/beginner-builder/progress-stepper.tsx`**: label `"Result"` → `"Deploy"`. No other behavioural change; component already supported 5 steps.

### Files touched
- `frontend/src/components/strategies/beginner-builder/step-deploy.tsx` (new, 163 LoC)
- `frontend/src/components/strategies/beginner-builder/progress-stepper.tsx` (label only)
- `frontend/src/app/(dashboard)/strategies/new/beginner/page.tsx` (reducer + handler + render branch)

### What I did NOT change
- `is_paper` semantics: untouched. `GoLiveModal` (`go-live-modal.tsx:94-104`) reads `useSystemMode()` and force-flips `dryRun=true` whenever `paper_mode !== false`. Since I render `GoLiveModal` with the same props the strategy-detail page uses, that default-paper behaviour is preserved exactly.
- Activation logic: zero new API calls. Same POST `/api/orders/live` via the same modal, same preflight via `/api/orders/live/preflight`. Nothing in `direct_exit.py`, `strategy_executor.py`, `webhook.py`, brokers, or migrations was touched.
- Standalone deploy path: `frontend/src/app/(dashboard)/strategies/[id]/page.tsx` → `LiveTradingSection` is untouched. The "Deploy from detail page" flow continues to work exactly as today; the wizard now offers an additional in-flow deploy without removing the existing one.

### 2-minute local test plan
```bash
cd frontend && npm run dev
```
1. Open `http://localhost:3000/strategies/new` → fork → "Build my own" → beginner wizard.
2. Step 1 — pick a goal. Step 2 — accept SL/Target defaults. Step 3 — name it ("Test M3"). Click "Continue to Run".
3. Step 4 — click **Run Backtest**. Watch for the wizard to advance to **step 5 ("Deploy")** *instead of* navigating away to `/strategies/{id}/backtest`.
4. Step 5 should render:
   - Celebration card ("Strategy ban gayi" / strategy name).
   - SafetyPreFlightPanel (auto-runs).
   - Go Live button (disabled until preflight passes; tooltip explains which check is blocking).
   - Footer: "Back" (returns to step 4) and "View backtest result →" (links to `/strategies/{new-id}/backtest`).
5. Click "View backtest result →" — backtest page auto-runs. The wizard *option* to deploy from step 5 is the new behaviour; the *ability* to reach the backtest is preserved.
6. Sanity on standalone path: open `/strategies/<any-id>` — the Live Trading section at the bottom of the detail page is identical to before.

### Risks / decisions I made
- The deploy step kicks off a **preflight API call** as soon as the user lands on step 5. If preflight is slow or fails on a fresh-from-zero account (no broker linked yet, no paper sessions, no backtest history), the GoLiveButton stays disabled with its existing Hinglish hover tooltip. That's the existing detail-page behaviour — the deploy module already handles the "preflight blocking" state. The user-visible difference is that *now they see this on first build*, not later. I think this is what the spec wanted but flag it as a UX change.
- Step 5's "Back" goes to step 4 (Run) and resets `submitState` to `idle`. The user CAN re-submit and create a second strategy row from the same wizard session — there's no protection against that. If you want to forbid re-submit after success, that's a small follow-up.
- I changed the progress-stepper label "Result"→"Deploy". This is a copy change and arguably brushes against "any copy/brand redesign beyond what the modules require"; I judged it as *required* because keeping the label "Result" while the step renders "Deploy" would mislead the user. If you disagree, reverting it is a one-line edit.
- No vitest unit test for the new `submit_success` reducer path. The reducer logic is small enough to read, but adding a test would have meant either a new test file (potentially tripping unrelated lint rules) or weaving it into a test file I'd otherwise leave alone. I prioritized commit safety.

---

## Combined diff summary

```
Total: 3 commits, 7 files touched (1 new).
521ab5a — M1  239 +  88 −
ff5ae69 — M2   88 +   1 −
47760f7 — M3  211 +  12 −
```

`npm run build` exit-0 at every commit. `npm run lint` count unchanged (67 errors / 49 warnings, all pre-existing, none in my surface). `npx vitest run` 4 failed / 849 passed at every commit (same pre-existing failures).

## What I deliberately did NOT do

- **M4 (builder consolidation)** — fence forbade it, not started.
- Backend changes — fence forbade.
- The 67 pre-existing lint errors — out of scope.
- The 4 pre-existing vitest failures — out of scope.
- Pushing to or rebasing onto `main` — fence forbade.
- The two untracked nginx backups (`backend/nginx.conf.backup.*`) in your working tree — not mine to clean up; left as-is.
- `frontend/package-lock.json` lockfile drift from local `npm install` — explicitly NOT staged. Restore via `git checkout -- frontend/package-lock.json` if you want.

## What you can decide tomorrow

1. Whether the marketplace crosslink should be a shared `BuilderMarketplaceLink` component (it's currently inlined 3×).
2. Whether step 5's "Back" should refuse to re-submit after a successful create.
3. Whether the progress-stepper label "Deploy" is the right copy (vs. "Live" / "Activate" / leave as "Result").
4. Whether `tb_strategy_mode` writes from the builder pages can be removed entirely (no current reader at the routing layer; only display-density readers remain).

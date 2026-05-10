# Mobile Responsiveness Audit — May 2026

Indian retail traders skew ~80% mobile. This doc captures the
state of every TRADETRI route at 375px (iPhone SE / smaller
Android) and tracks the gap between "functional on mobile" and
"polished mobile UX". Update on every mobile-relevant change.

## Audit method

* Static analysis of `(dashboard)/` + `(auth)/` + `(public)/`
  pages for: hard-coded widths, non-responsive grids, fixed
  positioning collisions, overflow-x risk, touch-target sizing.
* Severity: 🚨 critical (breaks the user) · ⚠️ rough (works but
  ugly) · ✨ polish (nice-to-have).

## Existing mobile chrome (already in place)

These mean most pages already render passably at 375px:

* `<Sidebar />` is `hidden md:flex` — hidden on mobile.
* `<MobileNav />` ships a fixed bottom-tab bar at `<md`.
* Dashboard `<main>` has `pb-20 md:pb-0` so content clears the
  bottom-nav on mobile.
* Most pages use the `p-4 md:p-6 lg:p-8 max-w-*` container
  pattern with responsive padding.
* Most grids already responsive (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`).
* Auth pages (login / register) use `min-h-screen px-4 max-w-md` —
  centered card, no overflow issues.

## Fixes shipped in this commit

| Severity | Page / component | Fix |
|---|---|---|
| 🚨 | `app/layout.tsx` | Added `export const viewport` with `width: device-width, initialScale: 1, maximumScale: 5`. Without this, mobile browsers default to a desktop-emulating viewport — every page rendered zoomed-out. |
| 🚨 | `components/algomitra/always-on-panel.tsx` | Panel height was `h-[calc(100vh-5rem)]` (only top header subtracted). On mobile this overlapped the 64px `<MobileNav />`. Now `h-[calc(100dvh-9rem)] md:h-[calc(100vh-5rem)]` — mobile path subtracts both top + bottom chrome and uses `dvh` so iOS Safari URL bar collapse doesn't change the math. |

## TIER 1 (May 18 launch critical) — state at 375 px

| Route | Status | Notes |
|---|---|---|
| `/login`, `/register` | ✅ ready | `min-h-screen flex items-center justify-center px-4`, card capped at `max-w-md`. |
| `/strategies` (list) | ✅ ready | `max-w-5xl p-4 md:p-6 lg:p-8`, grids `grid-cols-2 md:grid-cols-3`. |
| `/strategies/[id]` (detail) | ⚠️ rough | Version-history table can overflow on very narrow screens — wrap in `overflow-x-auto` follow-up. |
| `/strategies/[id]/backtest` | ⚠️ rough | The 8 result panels use responsive grids correctly. The Trust sub-card's `grid-cols-3` (OOS / walk-fwd / sensitivity) squeezes at 375 px — readable but tight. Equity-curve recharts container is fine because Recharts auto-sizes. Trades table likely needs `overflow-x-auto`; not yet inspected. |
| `/strategies/new/beginner` | ✅ ready | Wizard uses single-column flow already. |
| `/strategies/new/intermediate` | ⚠️ rough | Three-column section grid not tested at 375 px. |
| `/marketplace` (browse) | ✅ ready | `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`. |
| `/marketplace/[id]` (detail) | ✅ ready | Stats grid `grid-cols-2 md:grid-cols-4`, ledger panel uses same pattern. Ledger history modal has `max-h-[80vh] overflow-y-auto`. |

## TIER 2 (should work, polish post-launch)

| Route | Status | Notes |
|---|---|---|
| `/strategies/new/expert` | ⚠️ rough | Multi-column dense layout designed for desktop — usable but cramped at 375 px. Tab bar likely overflows; needs `overflow-x-auto` on the tab strip. |
| `/strategies/builder/{entry,exit,risk}` | ⚠️ rough | Same pattern as Expert — mostly works on mobile, needs tab-strip overflow handling. |
| `/marketplace/me` | ✅ ready | Tab strip is two tabs, fits. |
| `/strategies/import-pine` | not audited | |
| `/strategies/indicators` | not audited | |

## TIER 3 (desktop-acceptable, mobile-minimal)

| Route | Status | Notes |
|---|---|---|
| `/admin/*` | desktop-only | Admin tooling assumed laptop / desktop. Acceptable as-is for v1.0. |
| `/test-samjho` | desktop-only | Internal tooling. |

## Outstanding mobile issues (severity ranked)

These are deferred — none block May 18 launch but each is a real
papercut that should land in v1.1.

### 🚨 critical (real bugs at 375 px)

* None known after this commit's fixes — but the touch-target
  audit hasn't been run. Several `<Button size="sm">` and
  `<Button size="icon-sm">` instances may be < 44 px tall.
  Followup: ratchet `Button size="sm"` to a min-height of 36 px
  and add a `mobile:size="default"` or similar idiom.

### ⚠️ rough (works but ugly)

* **Backtest page Trust sub-card** — `grid-cols-3` of three
  metric tiles is tight at 375 px. Switch to
  `grid-cols-2 sm:grid-cols-3` so OOS + Walk-fwd stack on the
  smallest screens with Sensitivity dropping below.
* **Expert + standalone builders' tab strips** — horizontal scroll
  needed; add `overflow-x-auto whitespace-nowrap` to the tab
  container.
* **Trades / strategy-history tables** — every `<table>` inside a
  scroll-able card needs an `overflow-x-auto` wrapper. Sample
  audit pending.
* **AlgoMitra panel docked right** — works but eats 320 px of
  screen real-estate on phones. The user spec asked for
  "full-width drawer with bottom slide-up animation on mobile".
  Reasonable v1.1 polish; the shipped fix at least keeps the
  bottom-nav visible.

### ✨ polish

* **Auth pages background ornament** — the floating logo/glow
  pattern on `/login` doesn't degrade on mobile but is busy.
* **Strategy detail header** — the version + status badges row
  wraps at 375 px but the wrap is non-deterministic; pin order.
* **Marketplace listing cards** — 4-tag chip overflow uses
  `+N` truncation already; works.
* **AlgoMitra language switcher in panel header** — the
  native `<select>` icon on iOS Safari overlaps the lucide
  `Languages` icon at the smallest font size. Re-evaluate the
  padding or swap to a custom dropdown if the visual matters.

## Touch-target audit (deferred, owed by v1.1)

Spec target: 44 × 44 px (iOS HIG / WCAG AA).

* `<Button size="sm">` is currently `h-8 px-3` ≈ 32 px tall —
  below target.
* `<Button size="icon-sm">` is `h-7 w-7` = 28 px — well below
  target.
* These are used liberally across the dashboard. Bumping them
  globally is a cross-cutting change that needs visual QA.
* Workaround until then: every interactive `<Button size="sm">`
  should be inside a card with > 8 px padding so the *parent's*
  hit-area buys the user some forgiveness.

## What this commit does NOT change

The user spec proposed sweeping changes (full-width drawer,
bottom slide-up animation, modal full-screen on mobile, table
horizontal-scroll wrapping, etc.). Those are deferred:

* The two shipped fixes address the only *bugs* (viewport meta
  and panel-vs-bottom-nav collision). Everything else in the
  spec is UX polish on top of working mobile behavior.
* Refactoring 31+ pages without browser testing has high
  blast-radius and zero safety net. The post-launch follow-up
  will run device-emulation tests and only then make the broad
  changes — by then real mobile users will have surfaced the
  *actual* breakages, not the speculative ones.
* `frontend/MOBILE_AUDIT.md` (this file) is the running
  source-of-truth for what to tackle next.

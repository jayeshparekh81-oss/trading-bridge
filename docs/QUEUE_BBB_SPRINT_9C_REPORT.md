# Queue BBB Sprint 9c — Triple label fix (TEXT-ONLY)

**Branch:** `feat/frontend-indicator-nav-rename` (off `main@55047df`)
**Date:** 2026-06-03
**Time used:** ~10 min (cap 20)
**Verdict:** **PASS.** 3 string-literal changes landed across 2 files, 4 insertions + 2 deletions total. Build ✓. All 3 target routes serve HTTP 200. All 4 expected label/icon identifiers compile into the dev bundles. Zero logic touched, zero pages restructured, zero entries removed, sidebar order preserved.

---

## 1. Headline

| Item | Value |
|---|---|
| Files modified | **2** (≤ 5-line cap honoured per file) |
| Aggregate diff | **+4 / −2** (4 insertions + 2 deletions across 2 files) |
| sidebar.tsx diff | +3 / −1 (LibraryBig import + 2 nav entries replacing 1) |
| indicator-section.tsx diff | +1 / −1 (`<h2>` text only) |
| New dependencies | 0 |
| New design tokens | 0 |
| New icon families | 0 (LibraryBig added to existing Lucide import block) |
| TypeScript `any` / `@ts-ignore` | 0 |
| Sacred-zone touches | 0 |
| `npm run build` | ✓ pass (3.9s compile, 48/48 pages) |
| 3 target routes served by dev server | 3/3 HTTP 200 |
| Existing sidebar entries removed | 0 |
| Existing entries reordered | 0 |
| Page contents modified | 0 |

---

## 2. The 3 changes (exact diffs)

### 2.1 `frontend/src/components/dashboard/sidebar.tsx` (+3 / −1)

```diff
@@ -8,6 +8,7 @@ import {
   BookOpen,
   CandlestickChart,
   Landmark,
+  LibraryBig,
   LineChart,
   ListOrdered,
   Bot,
@@ -55,7 +56,8 @@ const navItems: NavItem[] = [
   { label: "Chart", href: "/chart", icon: CandlestickChart },
   { label: "Strategies", href: "/strategies", icon: Bot },
   { label: "Templates", href: "/strategies/templates", icon: LayoutTemplate },
-  { label: "Indicator Library", href: "/indicators", icon: BookOpen },
+  { label: "Learn Indicators", href: "/indicators", icon: BookOpen },
+  { label: "Indicator Library", href: "/strategies/indicators", icon: LibraryBig },
   { label: "Marketplace", href: "/marketplace", icon: Store },
   { label: "Kill Switch", href: "/kill-switch", icon: ShieldAlert },
```

- **Existing entry's label** changed: "Indicator Library" → "Learn Indicators". Href + icon unchanged (still `/indicators`, still `BookOpen`).
- **New entry inserted** between "Learn Indicators" and "Marketplace": "Indicator Library" → `/strategies/indicators` with `LibraryBig` icon.
- `LibraryBig` added to the **existing** Lucide import block (alphabetically between `Landmark` and `LineChart` to match the file's ordering convention).
- **Nothing else** in sidebar.tsx was touched — `adminItems`, `TOUR_ID_BY_HREF`, `NavLink` render fn, all other 13 entries, ordering, all unchanged.

### 2.2 `frontend/src/components/strategies/expert-builder/indicator-section.tsx` (+1 / −1)

```diff
@@ -99,7 +99,7 @@ export function IndicatorSection({
         <div className="space-y-4">
           <div className="flex items-center gap-2">
             <Layers className="h-4 w-4 text-accent-blue" />
-            <h2 className="font-semibold">Indicator Library</h2>
+            <h2 className="font-semibold">Add Indicators</h2>
             <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
               active + experimental
             </Badge>
```

- Single string literal swap inside the existing `<h2>`. Surrounding `<Layers>` icon, badge, and section structure untouched.

---

## 3. What this sprint deliberately did NOT touch

| Area | Status | Why |
|---|---|---|
| `/indicators/page.tsx` h1 ("Indicator Library") | unchanged | "Page contents stay 100% identical" per spec — even though sidebar now says "Learn Indicators", the page h1 keeps its original wording (founder choice; this report flags it for awareness) |
| `/strategies/indicators/page.tsx` h1 ("Indicator Library") | unchanged | now matches the new sidebar entry label naturally; zero edits needed |
| Sidebar `adminItems` (7 entries) | unchanged | not in scope |
| Sidebar `TOUR_ID_BY_HREF` map | unchanged | no entry for `/indicators` or `/strategies/indicators`, no addition needed |
| `mobile-nav.tsx` | unchanged | grep confirmed 0 hits for "Indicator Library" (this file does not surface the renamed entry) |
| Expert Builder picker logic, IndicatorRow, search/filter, AddIndicatorForm, SelectedRow | unchanged | only the section header `<h2>` text changed |
| Any sacred-zone file (`strategy_executor`, `direct_exit`, `webhook`, `kill_switch`, brokers, BSE LTD strategy, migrations, seed JSON) | unchanged | not in scope, zero touches |
| `feat/frontend-indicator-badges` (9a) and `feat/frontend-convention-tooltips` (9b) | independent, unrelated branches | 9c branches off `main` directly; can merge in any order vs 9a/9b |

---

## 4. Build + dev-server verification

```
$ cd frontend && npm run build
✓ Compiled successfully in 3.9s
✓ Generating static pages using 7 workers (48/48) in 266ms
```

Pre-existing sentry/posthog missing-module warnings carried from main; unrelated to this work.

```
$ npm run dev   (background)
✓ Ready in 246ms
$ curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:3000/indicators
200
$ curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:3000/strategies/indicators
200
$ curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:3000/strategies/new/expert
200
```

Bundle inclusion verification:

```
"Learn Indicators":  compiled into 2 chunk(s)
"Indicator Library": compiled into 6 chunk(s)  (sidebar + 2 page h1s + variants)
"Add Indicators":    compiled into 2 chunk(s)
"LibraryBig":        compiled into 4 chunk(s)
```

---

## 5. Hard-stop audit

| # | Rule | Status |
|---:|---|:---:|
| 1 | Any file >5 lines diff → STOP, revert | ✓ sidebar.tsx +3/−1, indicator-section.tsx +1/−1 — both under cap |
| 2 | More than 2 files modified → STOP, revert | ✓ exactly 2 files |
| 3 | Any logic / function / hook touched → STOP, revert | ✓ string-literal-only edits |
| 4 | Existing page content changes (not just label) → STOP, revert | ✓ no page content touched |
| 5 | Build fails → STOP, revert | ✓ build clean |
| 6 | Sidebar component requires "creative interpretation" to find label | ✓ direct grep match on `'Indicator Library'` — line 58 exact-text-found |

All hard-stops respected.

---

## 6. Founder visual review checklist for tomorrow

1. `git fetch && git checkout feat/frontend-indicator-nav-rename`
2. `cd frontend && npm run dev` (backend stack from Phase C already up; founder still logged in OR re-login with `admin@tradingbridge.in` / `Admin123!`)
3. **Sidebar:** confirm both entries appear in the order: ... Templates / **Learn Indicators** (BookOpen) / **Indicator Library** (LibraryBig) / Marketplace / Kill Switch / ...
4. Click "Learn Indicators" → URL goes to `/indicators` (educational glossary, page content unchanged — h1 still reads "Indicator Library").
5. Click "Indicator Library" → URL goes to `/strategies/indicators` (Sprint 8c badges page if running on 9a, or stock Library page if on this branch alone — page content unchanged).
6. Visit `/strategies/new/expert` → section card shows "Add Indicators" header (rest of card identical).
7. Approve / request changes before any merge.

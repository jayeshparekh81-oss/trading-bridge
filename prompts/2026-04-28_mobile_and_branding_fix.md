# Claude Code Prompt — TRADETRI Mobile + Branding Fix v2

> **Copy-paste this entire prompt into Claude Code on your Mac Mini.**
> Repository: `jayeshparekh81-oss/trading-bridge`
> Save as: `prompts/2026-04-28_mobile_and_branding_fix.md`
> Tested viewports: iPhone 14 Pro (393×852), iPad (768×1024), Desktop (1440×900)

---

## Context

TRADETRI dashboard at `tradetri.com/overview` and login page at `tradetri.com/login` need 3 critical fixes:

1. **Mobile sidebar is hidden with no toggle** — users on mobile cannot navigate to any other page
2. **4 KPI stat cards are display-only** — should be tappable/clickable on both desktop and mobile
3. **Brand color inconsistency** — the saffron/gold "TRI" color from the TRADETRI logo is not consistently applied across all "TRI" tokens (English) and "त्रि" tokens (Hindi) in the branding

Tech stack: Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Lucide icons.

**Brand colors (TRADETRI palette — already defined in `tailwind.config.ts`):**
- Navy/dark base: `#0A0E1A`
- Neon green (P&L positive): `#00FF88`
- Electric blue: `#0080FF`
- **Saffron/gold "TRI" color: `#D4AF37`** (this is the brand-defining color — every "TRI" must use this exact hex)
- White: `#FFFFFF`

---

## Required Changes

### 🔴 Change 1: Mobile Hamburger + Slide-in Drawer Sidebar

**Problem:** On mobile (<1024px), the left sidebar is hidden with no way to access it. The 15 nav items (Overview, Brokers, Positions, Trades, Strategies, Kill Switch, Analytics, Webhooks, Alerts, Settings, System Health, Users, Audit Logs, KS Events, Announce) are unreachable.

**Fix:**
- On `<lg` breakpoint (i.e. <1024px), hide the persistent sidebar.
- Show a **hamburger icon (☰, from lucide-react `Menu`)** in the top-left of the page header on mobile only.
- Tapping the hamburger opens a **slide-in drawer from the left** with:
  - Smooth animation (300ms ease-out from `-translate-x-full` to `translate-x-0`)
  - Semi-transparent black backdrop (`bg-black/50`) with `backdrop-blur-sm`
  - Tapping backdrop closes drawer
  - Tapping any nav item navigates AND closes drawer
  - Close (`X`) icon top-right of the drawer
  - Full-height, ~280px wide
  - TRADETRI logo at top (using the corrected logo from Change 3)
  - `<body>` scroll locked while open (use `overflow-hidden` on body)
  - Escape key closes it (`useEffect` with keydown listener)
  - Focus trap inside drawer when open (Tab cycles only through drawer items)
- On `lg` and above, sidebar stays visible — desktop behavior unchanged.

**Implementation hint:** Use shadcn/ui's `Sheet` component (`components/ui/sheet.tsx`) — it handles backdrop, focus trap, and escape key out of the box. Do not reinvent.

### 🔴 Change 2: Make 4 KPI Cards Clickable

**Problem:** The 4 stat cards on Overview are display-only.

**Fix:** Each card becomes a real `<Link>` (from `next/link`):

| Card | Route |
|---|---|
| Active Trades | `/trades?filter=active` |
| Brokers Online | `/brokers` |
| Kill Switch | `/kill-switch` |
| Win Streak | `/analytics?tab=streak` |

**Visual feedback:**
- Desktop hover: `hover:-translate-y-0.5 hover:border-[var(--accent)]/40 hover:shadow-lg transition-all duration-200`
- Mobile tap: `active:scale-[0.98] transition-transform`
- Cursor: `cursor-pointer` on hover
- Each Link gets a meaningful `aria-label` like `"View active trades"`, `"Manage broker connections"`, `"Kill switch settings"`, `"Win streak analytics"`

**Visual design:** Identical to current — only behavior changes.

### 🟡 Change 3: TRADETRI Logo + Brand "TRI" Color Consistency

This is the most important visual fix. The brand identity is built around the **saffron/gold "TRI"** that appears in the TRADETRI logo. Every instance of "TRI" (English) and "त्रि" (Hindi) across the entire site must use the **exact same color: `#D4AF37`**.

**3a. Fix logo visibility on mobile browser**

- Logo currently appears black on dark background in mobile Safari/Chrome (likely due to PNG with transparent background not rendering correctly).
- **Fix:** Use the SVG version of the logo (`public/logo.svg` — should already exist). If it doesn't, create one. The "TRADE" portion should be `#FFFFFF` (white) and the "TRI" portion should be `#D4AF37` (saffron/gold).
- Ensure logo SVG has `fill` attributes set on text/path elements, NOT relying on parent CSS color.
- Test in iOS Safari, Chrome mobile, and Android — logo must be clearly visible against dark background.

**3b. Apply TRI color consistency on Login/Register pages**

Currently the login page (`app/login/page.tsx`) shows TRI in saffron correctly inside the logo, but the Sanskrit branding text below has inconsistent coloring. Fix as follows:

**English line — `KALACHAKRA · TRIKALA · TRISHUL · TRISKELION`:**
- Render each word so the **first 3 letters "TRI"** in **TRIKALA, TRISHUL, TRISKELION** are colored `#D4AF37` (saffron)
- The rest of each word (`KALA`, `SHUL`, `SKELION`) stays in the default text color
- **KALACHAKRA** stays default (no TRI in it — leave unchanged)

**Hindi line — `ॐ · कालचक्र · त्रिकाल · त्रिशूल · त्रिस्केलियन`:**
- Render each word so the **first 2 characters "त्रि"** (which is one conjunct character `त्` + `र` + `ि` matra, but visually appears as त्रि) in **त्रिकाल, त्रिशूल, त्रिस्केलियन** are colored `#D4AF37` (saffron)
- Rest of word stays in default text color
- **कालचक्र** stays default (no त्रि in it)
- **ॐ** (Om) stays default

**Tagline labels — `PAST · PRESENT · FUTURE`:**
- These already appear in saffron — verify they match `#D4AF37` exactly. If they're a slightly different shade, fix.

**Implementation approach (clean):**

Create a small reusable component:

```tsx
// components/brand/HighlightTri.tsx
import { ReactNode } from 'react';

const TRI_COLOR = '#D4AF37';

/**
 * Renders a word with the first N characters colored as the brand "TRI" saffron.
 * Use prefixLength=3 for English ("TRI" = 3 letters)
 * Use prefixLength=2 for Hindi ("त्रि" = visually 2 grapheme clusters: त् + रि)
 *
 * Better approach: pass the prefix explicitly so we don't worry about Unicode counting:
 *   <HighlightTri prefix="TRI" rest="KALA" />
 *   <HighlightTri prefix="त्रि" rest="काल" />
 */
export function HighlightTri({ prefix, rest }: { prefix: string; rest: string }) {
  return (
    <span>
      <span style={{ color: TRI_COLOR }}>{prefix}</span>
      {rest}
    </span>
  );
}
```

Then use it in `app/login/page.tsx`:

```tsx
<div className="text-sm tracking-widest opacity-80">
  KALACHAKRA · <HighlightTri prefix="TRI" rest="KALA" /> · <HighlightTri prefix="TRI" rest="SHUL" /> · <HighlightTri prefix="TRI" rest="SKELION" />
</div>

<div className="text-sm" lang="hi">
  ॐ · कालचक्र · <HighlightTri prefix="त्रि" rest="काल" /> · <HighlightTri prefix="त्रि" rest="शूल" /> · <HighlightTri prefix="त्रि" rest="स्केलियन" />
</div>
```

**3c. Search the codebase for any other "TRI" / "त्रि" instances** and apply the same coloring rule. Likely candidates:
- Footer
- About page (if exists)
- Email templates (if any)
- Marketing content blocks

Do a project-wide grep:
```bash
grep -r "TRIKALA\|TRISHUL\|TRISKELION\|त्रिकाल\|त्रिशूल\|त्रिस्केलियन" --include="*.tsx" --include="*.ts" --include="*.mdx"
```

For every match, wrap the "TRI" / "त्रि" prefix with `<HighlightTri>`.

### 🟡 Change 4: Mobile Layout Polish (Overview page)

While we're touching the page:
- "Good evening, jayeshparekh!" header: `text-2xl sm:text-3xl lg:text-4xl`
- P&L chart container: ensure SVG scales to width with `viewBox` and `preserveAspectRatio="xMidYMid meet"` (don't horizontal-scroll the chart on mobile — make it fit)
- 4 KPI cards grid: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4`
- "Recent Trades" table: wrap in `<div className="overflow-x-auto">` so it scrolls horizontally on mobile without breaking the page
- AlgoMitra floating button: ensure `bottom-4 right-4` on mobile, `bottom-6 right-6` on desktop, `z-40` (above content, below modals)

---

## Acceptance Criteria

Run these tests before considering done:

### iPhone 14 Pro view (393×852, Chrome DevTools)
- [ ] Hamburger icon visible top-left
- [ ] Tap hamburger → drawer slides in from left smoothly
- [ ] Drawer shows all 15 nav items
- [ ] Tap nav item → navigates AND drawer closes
- [ ] Tap backdrop → drawer closes
- [ ] Background scroll locked while drawer open
- [ ] Logo at top of page is **clearly visible** (saffron TRI, white TRADE) — NOT black/invisible
- [ ] All 4 KPI cards tap → navigate to correct route, then back button returns

### iPad (768×1024)
- [ ] Sidebar shown via hamburger (or collapsed icon-only — your call)
- [ ] No layout breakage

### Desktop (1440×900)
- [ ] Sidebar visible as before, unchanged
- [ ] No hamburger icon shown
- [ ] All 4 KPI cards clickable with hover lift effect

### Login page (all viewports)
- [ ] **TRI** in **TRIKALA**, **TRISHUL**, **TRISKELION** = `#D4AF37` saffron
- [ ] **त्रि** in **त्रिकाल**, **त्रिशूल**, **त्रिस्केलियन** = `#D4AF37` saffron
- [ ] All 6 instances visually match the **TRI** in the **TRADETRI** logo at top
- [ ] **KALACHAKRA**, **कालचक्र**, **ॐ** stay in default color (no saffron)
- [ ] **PAST · PRESENT · FUTURE** confirmed `#D4AF37`

### Real device test (mandatory)
- [ ] iPhone Safari — logo visible, drawer works, cards clickable
- [ ] Android Chrome — same checks
- [ ] No console errors, no hydration warnings

---

## Code Style & Conventions

- **shadcn/ui Sheet** for the drawer (don't reinvent)
- **lucide-react** for icons: `Menu` (hamburger), `X` (close)
- **next/link** for all internal navigation — never `<a href>` for internal routes
- **Tailwind only** for styling (no inline styles except `style={{ color: TRI_COLOR }}` for the brand color constant — that's intentional for clarity)
- TypeScript strict mode, no `any`
- TRI_COLOR constant should be defined in `lib/brand.ts` and imported wherever needed:
  ```ts
  // lib/brand.ts
  export const BRAND_COLORS = {
    tri: '#D4AF37',         // saffron/gold — the "TRI" color
    navy: '#0A0E1A',
    neonGreen: '#00FF88',
    electricBlue: '#0080FF',
  } as const;
  ```

---

## Files Likely To Touch

- `app/overview/page.tsx` — make stat cards clickable
- `app/login/page.tsx` — use HighlightTri component for English + Hindi
- `app/register/page.tsx` — same as login (if Sanskrit branding repeats)
- `components/layout/Sidebar.tsx` — extract reusable nav content
- `components/layout/MobileDrawer.tsx` — NEW
- `components/layout/Header.tsx` — add hamburger button
- `components/layout/AppShell.tsx` — orchestrate desktop sidebar vs mobile drawer
- `components/brand/Logo.tsx` — ensure SVG with explicit fills
- `components/brand/HighlightTri.tsx` — NEW reusable component
- `lib/brand.ts` — NEW central color constants
- `public/logo.svg` — verify or create with explicit `fill="#D4AF37"` on TRI portion

---

## Out of Scope (DO NOT TOUCH)

- Don't refactor the chart library
- Don't change the dark theme base colors
- Don't add new nav items — use exactly the 15 existing ones
- Don't change the AlgoMitra button design
- Don't change desktop sidebar behavior
- Don't add new dependencies — use what's installed
- Don't touch broker integration code

---

## Definition of Done

When you can demonstrate on a **real iPhone** (not just DevTools):

1. Open `tradetri.com` → logo visible in saffron+white (NOT black)
2. Login page → all 6 "TRI"/"त्रि" instances match the logo's saffron color
3. Login → reach Overview → see hamburger top-left
4. Tap hamburger → drawer slides in
5. Tap "Brokers" → page navigates, drawer auto-closes
6. Back to Overview → tap "Active Trades" card → navigates to trades
7. Repeat for all 4 cards

Then commit with:
```
feat(mobile,brand): hamburger drawer + clickable KPIs + TRI color consistency

- Mobile slide-in drawer for sidebar (lg breakpoint)
- 4 KPI cards now clickable with proper aria-labels
- Logo SVG with explicit fills (fixes black-on-dark mobile bug)
- HighlightTri component applied to all TRI/त्रि tokens
- Centralized brand colors in lib/brand.ts
```

---

## After You're Done

1. Update `PROGRESS.md`:
```markdown
### 2026-04-28 — Mobile responsive + brand consistency fix
- Hamburger menu + slide-in drawer for mobile sidebar
- 4 KPI cards now clickable (Active Trades, Brokers, Kill Switch, Win Streak)
- Logo SVG fixed (was rendering black on mobile)
- TRI color consistency: HighlightTri component applied everywhere
  - English: TRIKALA, TRISHUL, TRISKELION
  - Hindi: त्रिकाल, त्रिशूल, त्रिस्केलियन
- Tested on iPhone 14 Pro Safari, Android Chrome, iPad, desktop 1440px
```

2. Deploy to Vercel preview
3. Test on **your actual iPhone** before merging to main
4. Send me the preview URL — I'll do final QA from another device

# Roadmap section visibility — diagnosis

**Date:** 2026-05-17
**Commit under investigation:** `e084c82` (merge) — adds
`frontend/src/components/marketing/RoadmapSection.tsx` + 4-line edit
to `frontend/src/app/(public)/home/page.tsx`.
**User report:** "Section not visible on the frontend."
**Diagnosis scope:** read-only — no code edits, no commits.

---

## TL;DR

**The roadmap section is shipped, prerendered, and present in the deployed HTML.** It renders correctly at **`https://tradetri.com/home`**. The user is likely testing **`https://tradetri.com/`** (root), which does NOT serve the landing page — root serves the dashboard auth-gate, which redirects unauthenticated visitors to `/login`. The roadmap is invisible because **the visitor never reaches `/home`**, not because the component failed to render.

**Verdict:** Not a roadmap bug. Not a Vercel deploy bug. **Routing gap** — the public landing page is at `/home`, root `/` is the auth-gated dashboard.

**Fastest verification:** open <https://tradetri.com/home> directly in any browser. Scroll past the comparison table. Roadmap section is there.

---

## Evidence

### 1. Deploy status — commit `e084c82` is live

`https://tradetri.com/home` HTTP probe:
```
HTTP/2 200
x-matched-path: /home
x-nextjs-prerender: 1
x-vercel-cache: PRERENDER
content-length: 85832
etag: "37376f241c4a98b8a0d90cfd677708cc"
```

The 85.8 KB HTML response is the full prerendered landing page, served from Vercel's prerender cache. Deploy was successful.

### 2. Roadmap content IS in the deployed HTML

```bash
curl -s https://tradetri.com/home | grep -oE ".{40}(Roadmap|What Ships When|Available Today|Phase F|Phase G).{40}"
```

Matches found in the live HTML:
```
<section id="roadmap" class="py-20 md:py-28 px-4 md:px-6 bg-…">
<h2 …>What Ships When</h2>
<p …>Honest roadmap — what's live today, what's coming next.
<span …>Available Today</span>
<span …>Phase F</span>
<span …>Phase G+</span>
```

All 6 expected anchors are present. The component rendered, the build included it, the prerender baked it into the HTML, the CDN serves it.

### 3. The "opacity:0" attribute is normal, not a render bug

```bash
curl -s https://tradetri.com/home | grep -oE '<section[^>]*style="opacity:0[^"]*"'
```

Result: **10 sections** all have inline `style="opacity:0;transform:translateY(40px)"` in the SSR HTML — including the roadmap section, but ALSO every other section on the page (Features, Performance, Comparison, Pricing, etc.).

This is the framer-motion SSR pattern shared with all 10 sections via the `Section` helper at `home/page.tsx:12-27`:

```tsx
function Section(...) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  return (
    <motion.section
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      ...
```

After hydration, the IntersectionObserver fires per-section as the user scrolls; each section animates to `opacity:1, y:0`. This pattern has been in production for the other 10 sections without issues. **The roadmap section uses the identical pattern** — it animates in the same way the existing Features/Pricing/Performance sections do.

### 4. Root URL `/` does NOT serve the landing page

`https://tradetri.com/` HTTP probe:
```
HTTP/2 200
x-matched-path: /
content-length: 23558
age: 739
x-vercel-cache: HIT
```

Only 23.5 KB (vs 85.8 KB for `/home`). HTML inspection:

```bash
curl -s https://tradetri.com/ | grep -c "What Ships When|Available Today|Phase F"
# → 0
curl -s https://tradetri.com/ | grep -c "L&T Engineer|Start Free"
# → 1 (just the title metadata)
```

**Zero roadmap markers at root.** The root URL `/` is served by `frontend/src/app/(dashboard)/page.tsx` (Next.js route group `(dashboard)` makes its `page.tsx` resolve to `/`). The dashboard layout at `(dashboard)/layout.tsx` has client-side auth:

```tsx
useEffect(() => {
  if (isLoading) return;
  if (!isAuthenticated) {
    router.push("/login");
    return;
  }
  ...
}, ...);
if (isLoading) return <DashboardSkeleton />;
if (!isAuthenticated) return null;
```

So an unauthenticated visitor to `tradetri.com/`:
1. Receives the 23.5 KB skeleton-ish HTML
2. Hydrates
3. `useEffect` runs → sees `!isAuthenticated` → `router.push("/login")`
4. Browser redirects to `/login`
5. **Never lands on `/home`** unless they manually navigate there

### 5. No middleware redirects `/` → `/home`

`find frontend/src -name "middleware.ts"` returns empty. There is no Next.js middleware to bounce root traffic to the landing page.

### 6. The `/home` route is only linked from inside the public layout

```bash
grep -rn '"/home"' frontend/src/
```

Result: **1 hit** — `frontend/src/app/(public)/layout.tsx:35` (the logo in `PublicNav`, only rendered when the visitor is ALREADY on a `(public)/*` route like `/home`, `/about`, `/pricing`, `/contact`).

No link from the dashboard / auth pages / root points at `/home`. A visitor arriving at `tradetri.com` has no in-app path to discover `/home` short of typing it manually.

---

## Why this looks like a "roadmap not visible" bug

The user shipped the roadmap, refreshed `tradetri.com`, didn't see it, concluded "deploy didn't work." But:

- Refreshing `tradetri.com` (root) was never going to show the roadmap, even pre-deploy. The landing page has always been at `/home`.
- Root `/` has been the dashboard auth gate since at least commit `f2f44a5` ("Step 13 - Landing page + Pricing + About + Contact, 21 routes" — which created the landing at `/home`, not at root).
- This pre-dates the roadmap section by weeks. It's a routing setup choice, not a regression.

---

## File:line precision — what needs to change

If the goal is "visitors to `tradetri.com` see the landing page (and therefore the roadmap)", there are three concrete options, ordered cheapest first:

### Option A — Zero code change. Hand the user the right URL. (RECOMMENDED for tonight)

Tell Jayesh + any test users to visit **`https://tradetri.com/home`** to verify the roadmap. Scroll past Section 7 (Comparison) — roadmap appears as Section 7.5, before Pricing.

**Effort:** 0 minutes. **Risk:** zero. **Pre-launch acceptable:** yes.

Tradeoff: doesn't fix the underlying "tradetri.com root doesn't show landing" UX. Marketing-funnel visitors typing the bare domain still hit the auth gate. Acceptable for tonight; address post-launch.

### Option B — Add Next.js middleware: unauth visitors `/` → `/home` (~30 min, 1 new file)

Create `frontend/src/middleware.ts`:

```tsx
import { NextResponse, type NextRequest } from "next/server";

export function middleware(req: NextRequest) {
  // Only act on the root path.
  if (req.nextUrl.pathname !== "/") return NextResponse.next();

  // Detect auth via the existing access-token cookie or localStorage
  // bridge. Project uses ``tb_access_token`` (see lib/api.ts:11).
  const hasAuth = req.cookies.get("tb_access_token");
  if (hasAuth) return NextResponse.next();   // authenticated → dashboard

  // Unauthenticated → send to the public landing.
  const url = req.nextUrl.clone();
  url.pathname = "/home";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: "/",
};
```

**Effort:** ~30 min including local + Vercel deploy verification. **Risk:** low — middleware is matcher-scoped to `/` exactly, so it can't affect any other route. **Pre-launch acceptable:** marginal — middleware changes deploy through Vercel as edge functions; if it misbehaves, all root traffic is impacted.

Caveat: the project stores its access token in `localStorage` (per `lib/api.ts:16-19`), NOT in a cookie. The middleware would need to either (i) check a different cookie set elsewhere, or (ii) NEVER assume authentication at root → always redirect to `/home`, letting `(public)/layout.tsx`'s nav handle the "Login" CTA. Option (ii) is simpler and probably what you want for a landing-page-first funnel.

### Option C — Restructure routing: `/` IS the landing, `/dashboard` is the dashboard (~2 hours, bigger refactor)

Rename `(dashboard)/page.tsx` to `(dashboard)/dashboard/page.tsx` (or move it under a new `/app/dashboard` non-route-group dir). Move `(public)/home/page.tsx` to `(public)/page.tsx` (resolves to `/`). Update all links + login redirect target.

**Effort:** ~2 hours including link sweep + dashboard auth redirect updates + Vercel deploy. **Risk:** medium — touches multiple files, potential broken links if any hardcoded reference to `/` for dashboard is missed. **Pre-launch acceptable:** no — too much surface area to land cleanly the night before launch.

---

## Concrete recommendation

**Tonight (May 17, T-1 launch):** Option A. Hand Jayesh + any test users the `/home` URL. The roadmap is shipped correctly; this is a verification path issue, not a deploy bug. Zero risk to launch.

**Post-launch (week of May 19):** Option B. Add the middleware redirect. Visitors typing the bare domain land on the marketing page. ~30 min sprint, low risk after launch settles.

**Avoid:** Option C pre-launch. Too much routing surface to land safely the night before.

---

## Verification command (for Jayesh)

To see the roadmap, in any browser:

```
https://tradetri.com/home
```

Scroll past:
1. Hero (Sub-50ms execution stats)
2. Problem → Solution
3. Features (6-card grid)
4. How It Works (3 steps)
5. Performance (strategy table)
6. Founder Story
7. Comparison table
8. **🎯 ROADMAP SECTION** (this is what you're looking for — 3-column glassmorphism cards, profit-green / accent-blue / muted-gray)
9. Pricing
10. Testimonials
11. Final CTA

Hard-refresh (`Cmd+Shift+R`) if Vercel's CDN serves a stale prerender for your IP/region. The `etag: "37376f241c4a98b8a0d90cfd677708cc"` is the post-roadmap version; if you see a different etag in DevTools → Network → /home → Response Headers, the CDN edge near you is still serving the prior cache. Wait a few minutes for revalidation or trigger a Vercel redeploy without cache.

---

## What this diagnosis did NOT do

- Did not edit any code
- Did not commit anything
- Did not push, did not redeploy
- Did not check Vercel API for deploy logs (Vercel CLI / API access wasn't probed; the HTTP response headers were sufficient evidence)
- Did not open a browser to visually inspect (inferred from HTML structure, not pixel rendering)

Awaiting Jayesh's decision: fix (Option A/B/C) vs revert (remove the roadmap component entirely).

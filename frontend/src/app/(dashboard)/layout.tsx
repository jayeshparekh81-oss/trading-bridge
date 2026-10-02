"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/dashboard/sidebar";
import { TopBar } from "@/components/dashboard/top-bar";
import { MobileNav } from "@/components/dashboard/mobile-nav";
import { ChatWidget } from "@/components/algomitra/ChatWidget";
import { AlgoMitraReactionLayer } from "@/components/algomitra/AlgoMitraReactionLayer";
import { AlwaysOnAlgoMitraPanelMount } from "@/components/algomitra/always-on-panel";
import { useAlgoMitraPanelState } from "@/hooks/use-algomitra-context";
import { cn } from "@/shared/lib/utils";
import { OnboardingTour } from "@/components/onboarding/OnboardingTour";
import { PrivacyBanner } from "@/components/privacy-banner";
import { useAuth } from "@/lib/auth";
import { DashboardSkeleton } from "@/shared/ui/skeleton-loader";
import { withNext } from "@/lib/safe-next";
import { useGuidedPathLive } from "@/hooks/useGuidedPathLive";
import { useLadder } from "@/hooks/useLadder";
import { SimpleShell } from "@/components/simple/simple-shell";
import { ProWelcomeNudge } from "@/components/simple/pro-welcome-nudge";
import { PracticeBanner } from "@/components/site/practice-banner";
import type { ReactNode } from "react";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const ladder = useLadder();
  // THE SWITCH-ON INTERLOCK (26 Sep): the guided path is shown only when the frontend flag
  // is on AND the backend's own readiness says ready — never on the frontend flag alone.
  const guided = useGuidedPathLive();
  const firstRun = typeof user?.onboarding_step === "number" && user.onboarding_step < 6;
  // The AlgoMitra coaching panel is a FIXED 320px column on the right of the
  // three builder routes, open by default. It used to float over the page:
  // on a 1440px desktop the beginner wizard's "Next" button sat underneath
  // it and could not be clicked — a first-time customer was stuck on step 1.
  // While it is open on a builder route, the page reserves its width.
  const { isOpen: coachOpen } = useAlgoMitraPanelState();
  const coachReservesSpace =
    coachOpen && /^\/strategies\/new\/(beginner|intermediate|expert)(\/|$)/.test(pathname ?? "");

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      // Carry WHERE THEY WERE GOING through the login. Without this a shared
      // deep link (/marketplace/<id>, /strategies/<id>) drops the customer on
      // the homepage after login, with no way back to what they clicked.
      // Same machinery the Subscribe CTA uses: withNext sanitises the path,
      // so an attacker-supplied location can never become an off-site
      // redirect followed by a freshly-authenticated browser.
      const here = window.location.pathname + window.location.search;
      // The FRONT DOOR (founder's rule, 26 Sep, 5-second test): someone who types
      // tradetri.com and is not logged in has never seen us — a bare login form does
      // not tell them what this is. They get /home (what TRADETRI is + ONE "Start Free").
      // A returning customer is one tap from Login there. Every deep link still goes
      // to /login?next=… exactly as before.
      router.push(here === "/" ? "/home" : withNext("/login", here));
      return;
    }
    // First-time users land on /onboarding before they see the
    // dashboard chrome. ``onboarding_step`` is undefined for old
    // cached /me payloads from before migration 021 — those users
    // pass through (they'll get the backfilled value of 6 on next
    // refresh, which is also pass-through).
    const step = user?.onboarding_step;
    if (typeof step === "number" && step < 6) {
      // Carry where they were going (e.g. the strategy they clicked Start
      // Free on) through onboarding — safeNextPath'd again on the way out.
      // ONE path (26 Sep): a new customer goes to the first-timer guided path ONLY when it is
      // LIVE — the frontend flag on AND the backend's readiness said ready. Flag off, backend
      // off, readiness failed or slow → the older /onboarding wizard, exactly as before.
      if (guided === "checking") return;
      if (guided === "ready") {
        router.replace("/start");
        return;
      }
      router.replace(withNext("/onboarding", window.location.pathname + window.location.search));
    }
  }, [isLoading, isAuthenticated, router, user?.onboarding_step, guided]);

  if (isLoading || (isAuthenticated && !ladder.ready) || (isAuthenticated && firstRun && guided === "checking")) {
    return (
      <div className="flex h-screen items-center justify-center">
        <DashboardSkeleton />
      </div>
    );
  }

  // While redirecting, show nothing
  if (!isAuthenticated) return null;

  // No level gate (founder, 2026-09-05 evening): every route is open in both
  // modes; Simple only changes the chrome around the page.
  //
  // THE PRACTICE BANNER ON EVERY CUSTOMER SCREEN (founder, 1 Oct 2026: "paper demo only with
  // the practice banner on every screen"; applied to every logged-in screen 2 Oct 2026). A
  // CUSTOMER account (not admin) sees it above every dashboard page — true for that account:
  // the customer path sends no order while the fan-out / customer-lane order switches are OFF.
  // The founder's own ADMIN account never sees it: his /positions carries REAL BSE rows, and a
  // "practice" line over real money is the lie INC #12 is about. The per-row paper/live labels
  // on /positions and /trades stay as they are (a different, read-per-row fact).
  const content = (
    <>
      {user && !user.is_admin && <PracticeBanner sticky={false} />}
      {children}
    </>
  );

  // ── Simple chrome (Level 1–3): no sidebar, no top bar; tiles are the nav,
  // the safety bar is always there. Madad (AlgoMitra) stays mounted. ──
  if (ladder.level < 4) {
    return (
      <SimpleShell>
        {content}
        <ChatWidget />
        <AlgoMitraReactionLayer />
        {/* Above the always-on safety bar on phones — the bar must never be covered. */}
        <PrivacyBanner className="bottom-24 md:bottom-4" />
      </SimpleShell>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar
          userName={user?.full_name || user?.email || "Trader"}
          onLogout={logout}
        />
        <main
          className={cn("chrome-pro flex-1 overflow-y-auto pb-20 md:pb-0", coachReservesSpace && "md:pr-[320px]")}
          data-coach-open={coachReservesSpace ? "true" : undefined}
        >
          {content}
        </main>
        <MobileNav />
      </div>
      <ChatWidget />
      <AlgoMitraReactionLayer />
      <AlwaysOnAlgoMitraPanelMount />
      <PrivacyBanner />
      {/* The 5-step welcome tour assumes this Pro chrome (its targets are
          sidebar items) — it belongs to Pro only. Levels 1–3 get the tiles
          and the day's lesson instead. */}
      {/* A customer who CHOSE Pro from Simple gets the expanded-sidebar nudge
          (ProWelcomeNudge), not the 5-step tour modal on top of it — the two
          together covered the page (and the Settings mode card) on the walk. */}
      {ladder.choice !== "pro" && (
        <OnboardingTour
          userName={user?.full_name || user?.email || "Trader"}
        />
      )}
      <ProWelcomeNudge />
    </div>
  );
}

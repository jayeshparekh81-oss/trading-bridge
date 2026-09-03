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
import { cn } from "@/lib/utils";
import { OnboardingTour } from "@/components/onboarding/OnboardingTour";
import { PrivacyBanner } from "@/components/privacy-banner";
import { useAuth } from "@/lib/auth";
import { DashboardSkeleton } from "@/components/ui/skeleton-loader";
import { withNext } from "@/lib/safe-next";
import type { ReactNode } from "react";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
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
      router.push(withNext("/login", here));
      return;
    }
    // First-time users land on /onboarding before they see the
    // dashboard chrome. ``onboarding_step`` is undefined for old
    // cached /me payloads from before migration 021 — those users
    // pass through (they'll get the backfilled value of 6 on next
    // refresh, which is also pass-through).
    const step = user?.onboarding_step;
    if (typeof step === "number" && step < 6) {
      router.replace("/onboarding");
    }
  }, [isLoading, isAuthenticated, router, user?.onboarding_step]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <DashboardSkeleton />
      </div>
    );
  }

  // While redirecting, show nothing
  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar
          userName={user?.full_name || user?.email || "Trader"}
          onLogout={logout}
        />
        <main
          className={cn("flex-1 overflow-y-auto pb-20 md:pb-0", coachReservesSpace && "md:pr-[320px]")}
          data-coach-open={coachReservesSpace ? "true" : undefined}
        >
          {children}
        </main>
        <MobileNav />
      </div>
      <ChatWidget />
      <AlgoMitraReactionLayer />
      <AlwaysOnAlgoMitraPanelMount />
      <PrivacyBanner />
      <OnboardingTour
        userName={user?.full_name || user?.email || "Trader"}
      />
    </div>
  );
}

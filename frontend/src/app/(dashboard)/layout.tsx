"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/dashboard/sidebar";
import { TopBar } from "@/components/dashboard/top-bar";
import { MobileNav } from "@/components/dashboard/mobile-nav";
import { PaperModeBanner } from "@/components/dashboard/paper-mode-banner";
import { ChatWidget } from "@/components/algomitra/ChatWidget";
import { AlgoMitraReactionLayer } from "@/components/algomitra/AlgoMitraReactionLayer";
import { AlwaysOnAlgoMitraPanelMount } from "@/components/algomitra/always-on-panel";
import { PrivacyBanner } from "@/components/privacy-banner";
import { useAuth } from "@/lib/auth";
import { DashboardSkeleton } from "@/components/ui/skeleton-loader";
import type { ReactNode } from "react";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.push("/login");
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
        <PaperModeBanner />
        <TopBar
          userName={user?.full_name || user?.email || "Trader"}
          notificationCount={0}
          onLogout={logout}
        />
        <main className="flex-1 overflow-y-auto pb-20 md:pb-0">
          {children}
        </main>
        <MobileNav />
      </div>
      <ChatWidget />
      <AlgoMitraReactionLayer />
      <AlwaysOnAlgoMitraPanelMount />
      <PrivacyBanner />
    </div>
  );
}

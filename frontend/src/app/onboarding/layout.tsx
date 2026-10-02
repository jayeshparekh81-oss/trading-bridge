"use client";

/**
 * /onboarding lives outside the (dashboard) route group so it
 * doesn't inherit the sidebar / mobile-nav / AlgoMitra panel
 * chrome — first-time users get an undistracted full-screen
 * flow. Auth is still required (we redirect to /login if the
 * useAuth hook reports the user as unauthenticated).
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { PracticeBanner } from "@/components/site/practice-banner";
import type { ReactNode } from "react";

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-gradient-to-b from-surface-ink via-surface-ink to-surface-void">
      {/* The practice banner on every customer screen (2 Oct 2026): this route group is outside
          (dashboard), so it mounts its own — for CUSTOMER (non-admin) accounts only, like the
          dashboard layout. */}
      {user && !user.is_admin && <PracticeBanner sticky={false} />}
      {children}
    </div>
  );
}

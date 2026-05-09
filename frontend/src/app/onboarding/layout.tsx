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
import type { ReactNode } from "react";

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0b0e14] via-[#0b0e14] to-[#0a0d12]">
      {children}
    </div>
  );
}

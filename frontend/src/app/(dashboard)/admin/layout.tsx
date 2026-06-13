"use client";

/**
 * /admin/* admin-only route guard.
 *
 * Why a client-side layout guard rather than ``frontend/src/middleware.ts``:
 * the JWT is stored in ``localStorage`` (see ``lib/api.ts``) which is not
 * accessible from Next.js middleware (edge runtime, server-side, no DOM).
 * A cookie-mirror would require touching the login/logout flow, which is
 * outside the additive-only contract for Queue HHH M1.
 *
 * Defense in depth: this guard is a UX layer — it prevents non-admin
 * customers from rendering the admin shell. The actual security boundary
 * remains the backend ``require_admin`` dependency on every
 * ``/api/admin/*`` endpoint (returns 403 to non-admins regardless of
 * what the frontend renders).
 *
 * Mirrors the existing ``(dashboard)/layout.tsx`` pattern:
 *   * useEffect-based redirect (no flash of unauthorised content because
 *     we render a skeleton until ``isLoading`` resolves)
 *   * useRouter().replace so back-button doesn't return to /admin
 *   * shadcn/sonner ``toast`` for the user-facing notice (Hinglish per
 *     project convention)
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
import { DashboardSkeleton } from "@/components/ui/skeleton-loader";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      // Unauthenticated — parent dashboard layout already handles this,
      // but we defend in case the layout-order assumption shifts.
      router.replace("/login");
      return;
    }
    if (!user?.is_admin) {
      toast.error("Yeh page sirf admins ke liye hai.");
      router.replace("/");
    }
  }, [isLoading, isAuthenticated, user?.is_admin, router]);

  if (isLoading || !user?.is_admin) {
    return <DashboardSkeleton />;
  }

  return <>{children}</>;
}

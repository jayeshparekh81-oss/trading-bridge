/**
 * SessionExpiredBanner — inline notification above the chart body
 * when the WS token's two-consecutive-failure threshold has tripped
 * (R1 / Day-4 design call #5). Lives between the top bar and the
 * chart canvas — NOT overlaid on the chart itself, so the user
 * can still read the last-known candles underneath.
 *
 * Copy convention matches the dashboard's existing voice (see
 * src/app/(dashboard)/brokers/page.tsx "Token expired — Reconnect
 * needed" and src/lib/api.ts "Session expired. Please login again."):
 * concise Hinglish title, action-oriented body, single primary CTA.
 *
 * The button uses Next.js App Router's ``useRouter().push`` —
 * imported from "next/navigation" per v13+ conventions. ``/login``
 * is the canonical sign-in route, already wired by
 * src/app/(auth)/login/page.tsx.
 */

"use client";

import { useRouter } from "next/navigation";
import { LogIn, AlertTriangle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface SessionExpiredBannerProps {
  /** Override the router for tests. Real usage falls back to
   *  ``useRouter()`` from next/navigation. */
  onLogin?: () => void;
}

export function SessionExpiredBanner({
  onLogin,
}: SessionExpiredBannerProps) {
  const router = useRouter();

  const handleClick = () => {
    if (onLogin) {
      onLogin();
      return;
    }
    router.push("/login");
  };

  return (
    <div
      data-testid="chart-session-expired-banner"
      className="px-3 md:px-4"
    >
      <Alert variant="destructive" className="flex items-center gap-3">
        <AlertTriangle aria-hidden="true" className="h-4 w-4" />
        <div className="flex-1">
          <AlertTitle>Session expire ho gaya</AlertTitle>
          <AlertDescription>
            Live data ke liye wapas login karna padega — chart ka
            history visible rahega.
          </AlertDescription>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleClick}
          data-testid="chart-session-expired-login"
        >
          <LogIn className="mr-1.5 h-3 w-3" />
          Log in again
        </Button>
      </Alert>
    </div>
  );
}

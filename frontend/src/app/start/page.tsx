"use client";

/**
 * /start — ONE guided path from signup to a running strategy (founder, 26 Sep 2026).
 *
 * Behind NEXT_PUBLIC_CUSTOMER_GUIDED_PATH (OFF): unset, this page renders the honest
 * "not switched on" line and nothing else, so a publish changes nothing a customer sees
 * until the flag is flipped. Declared in tests/architecture/route-map.test.ts.
 *
 * THE SWITCH-ON INTERLOCK (founder, 26 Sep): the frontend flag alone is not enough. The
 * path renders only when the backend's own readiness says ready. Flag on but the backend
 * not ready (its flag off, an error, a timeout, an old server) → the customer is sent,
 * silently, to the current onboarding (signed in: /onboarding · a visitor: /register),
 * and the honest line with both links stays on screen while that happens — never a dead end.
 */

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { GuidedPath } from "@/components/guided/guided-path";
import { useGuidedPathLive } from "@/hooks/useGuidedPathLive";

function hasSession(): boolean {
  try {
    return typeof window !== "undefined" && !!localStorage.getItem("tb_access_token");
  } catch {
    return false;
  }
}

function NotSwitchedOn({ testId }: { testId: string }) {
  // Says what this page is, and ONE big next step (founder's rule, 26 Sep, points 1-2, 7):
  // this used to be one small line with two tiny inline links.
  const loggedIn = hasSession();
  return (
    <div data-testid={testId} className="mx-auto flex max-w-md flex-col gap-3 p-4 text-sm text-muted-foreground">
      <h1 className="text-xl font-bold text-foreground">Yeh guide abhi chalu nahi hai</h1>
      <p>
        Yeh page naye customer ko shuru se strategy chalne tak le jaata hai — abhi band hai.{" "}
        {loggedIn ? "Aap apne ghar se sab kar sakte ho." : "Tab tak account bana ke shuru kar sakte ho."}
      </p>
      {loggedIn ? (
        <>
          <Link href="/" className="inline-flex min-h-12 items-center justify-center rounded-md bg-primary px-4 text-base font-medium text-primary-foreground">
            Apne ghar par jao
          </Link>
          <Link href="/help" className="inline-flex min-h-11 items-center justify-center rounded-md border border-border px-4">
            Madad chahiye?
          </Link>
        </>
      ) : (
        <>
          <Link href="/register" className="inline-flex min-h-12 items-center justify-center rounded-md bg-primary px-4 text-base font-medium text-primary-foreground">
            Naya account banao (free)
          </Link>
          <Link href="/login" className="inline-flex min-h-11 items-center justify-center rounded-md border border-border px-4">
            Pehle se account hai? Login karo
          </Link>
        </>
      )}
    </div>
  );
}

export default function StartPage() {
  const live = useGuidedPathLive();
  const router = useRouter();

  useEffect(() => {
    if (live !== "not-ready") return;
    router.replace(hasSession() ? "/onboarding" : "/register");
  }, [live, router]);

  if (live === "off") return <NotSwitchedOn testId="guided-off" />;
  if (live === "checking") {
    return (
      <p data-testid="guided-checking" className="text-sm text-muted-foreground">
        Ek second — guide khul raha hai…
      </p>
    );
  }
  if (live === "not-ready") return <NotSwitchedOn testId="guided-not-ready" />;
  return <GuidedPath />;
}

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
  return (
    <p data-testid={testId} className="text-sm text-muted-foreground">
      Yeh guide abhi chalu nahi hai. <Link href="/register" className="underline">Account banao</Link> ya{" "}
      <Link href="/login" className="underline">login karo</Link>.
    </p>
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

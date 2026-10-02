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
import { SignupOrLogin } from "@/components/site/signup-or-login";
import { useSignupOpen } from "@/hooks/useSignupOpen";
import { useGuidedPathLive } from "@/hooks/useGuidedPathLive";
import { guidedCopy } from "@/lib/i18n/copy/guided";
import { useCopy } from "@/lib/i18n/core";

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
  // 2 Oct 2026 (Stage-1 audit of the served card): while public signup is CLOSED the big button
  // already reads "… Login karo", so the small "Pehle se account hai? Login karo" line was the SAME
  // tap twice (point 2: one primary). It shows only when signup is OPEN.
  const signup = useSignupOpen();
  const { c } = useCopy(guidedCopy);
  return (
    <div data-testid={testId} className="mx-auto flex max-w-md flex-col gap-3 p-4 text-sm text-muted-foreground">
      <h1 className="text-xl font-bold text-foreground">{c.off_title}</h1>
      <p>
        {c.off_body}{" "}
        {loggedIn ? c.off_logged_in : signup === "open" ? c.off_signup_open : c.off_signup_closed}
      </p>
      {loggedIn ? (
        <>
          <Link href="/" className="inline-flex min-h-12 items-center justify-center rounded-md bg-primary px-4 text-base font-medium text-primary-foreground">
            {c.off_home}
          </Link>
          <Link href="/help" className="inline-flex min-h-11 items-center justify-center rounded-md border border-border px-4">
            {c.off_help}
          </Link>
        </>
      ) : (
        <>
          <SignupOrLogin href="/register" className="inline-flex min-h-12 items-center justify-center rounded-md bg-primary px-4 text-base font-medium text-primary-foreground"
            closedText={c.off_create_closed}>
            {c.off_create}
          </SignupOrLogin>
          {signup === "open" && (
            <Link href="/login" className="inline-flex min-h-11 items-center justify-center rounded-md border border-border px-4">
              {c.off_have_account}
            </Link>
          )}
        </>
      )}
    </div>
  );
}

export default function StartPage() {
  const live = useGuidedPathLive();
  const { c } = useCopy(guidedCopy);
  const router = useRouter();

  useEffect(() => {
    if (live !== "not-ready") return;
    router.replace(hasSession() ? "/onboarding" : "/register");
  }, [live, router]);

  if (live === "off") return <NotSwitchedOn testId="guided-off" />;
  if (live === "checking") {
    return (
      <p data-testid="guided-checking" className="text-sm text-muted-foreground">
        {c.start_checking}
      </p>
    );
  }
  if (live === "not-ready") return <NotSwitchedOn testId="guided-not-ready" />;
  return <GuidedPath />;
}

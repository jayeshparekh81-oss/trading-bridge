"use client";

/**
 * DEV-ONLY (404 on tradetri.com — the dev-preview layout gates it): the subscription
 * settings screen with fixtures, no login, so the Mac's 375×812 walk
 * (kb/mac_outbox/live_walk_375/) can photograph every step of it.
 *
 *   /dev-preview/settings?shell=simple   inside the Simple shell (header + safety bar)
 *   /dev-preview/settings?shell=pro      inside a Pro-like scroll area + the phone bottom nav
 *   &paper=0                             the saved mode is real (no practice banner)
 *
 * The ONE server call the screen makes (GET/PATCH …/subscriptions/preview/settings) is
 * answered here in the browser from a fixture; every other request goes out untouched.
 */

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { SimpleShell } from "@/components/simple/simple-shell";
import { MobileNav } from "@/components/dashboard/mobile-nav";
import { SubscriptionSettings } from "@/components/marketplace/subscription-settings";

const SETTINGS_PATH = "/marketplace/subscriptions/preview/settings";

function fixture(paper: boolean) {
  return {
    subscription_id: "preview",
    lots_override: null,
    execution_mode: "offline",
    is_paper: paper,
    applied: false,
    pending_fanout_merge: true,
    direction_filter: "all",
  };
}

function installFixture(paper: boolean) {
  if (typeof window === "undefined") return;
  const w = window as typeof window & { __settingsFixture?: boolean };
  if (w.__settingsFixture) return;
  w.__settingsFixture = true;
  const real = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.endsWith(SETTINGS_PATH)) {
      const body = init?.method === "PATCH" && typeof init.body === "string" ? { ...fixture(paper), ...JSON.parse(init.body) } : fixture(paper);
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return real(input, init);
  };
}

function Inner() {
  const q = useSearchParams();
  const paper = q.get("paper") !== "0";
  installFixture(paper);
  const panel = (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <p className="mb-3 text-sm text-muted-foreground">Meri strategies · BSE Ltd · Chalu karo</p>
      <SubscriptionSettings subscriptionId="preview" />
    </div>
  );
  if (q.get("shell") === "pro") {
    return (
      <div className="flex h-screen flex-col overflow-hidden">
        <main className="chrome-pro flex-1 overflow-y-auto pb-20 md:pb-0">{panel}</main>
        <MobileNav />
      </div>
    );
  }
  return <SimpleShell>{panel}</SimpleShell>;
}

export default function SettingsPreviewPage() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}

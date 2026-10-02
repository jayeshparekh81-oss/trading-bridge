"use client";

/**
 * /journey — the customer's ONE next step, from pay to trade (Track C item 6).
 *
 * Behind NEXT_PUBLIC_CUSTOMER_JOURNEY (OFF): with the flag unset this page renders the
 * honest "not switched on" line and nothing else, so a publish changes nothing a
 * customer sees until the flag is flipped. Reached from the marketplace/me card and
 * the onboarding finish (declared in tests/architecture/route-map.test.ts).
 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { ProPage } from "@/components/dashboard/pro-page";
import { JourneyStepper } from "@/components/journey/journey-stepper";
import Link from "next/link";
import { JOURNEY_STEPS, customerJourneyEnabled, type JourneyStep } from "@/lib/customer-journey";
import { useGuidedPathLive } from "@/hooks/useGuidedPathLive";

function JourneyBody() {
  const params = useSearchParams();
  const raw = params?.get("step") ?? null;
  const step = raw && (JOURNEY_STEPS as readonly string[]).includes(raw) ? (raw as JourneyStep) : null;
  const guided = useGuidedPathLive();
  // ONE guided path (founder, 26 Sep): when the first-timer path is LIVE (frontend flag on
  // AND the backend's readiness said ready — the switch-on interlock), this page points at it
  // instead of showing a second, different stepper. Not ready → the page as it was.
  if (guided === "ready") {
    return (
      <div data-testid="journey-guided" className="flex flex-col gap-3">
        <p className="text-sm">Shuru se strategy chalne tak — ek-ek kadam, har screen par AlgoMitra saath me.</p>
        <Link href="/start" className="inline-flex min-h-12 w-full items-center justify-center rounded-md bg-primary px-4 text-base font-medium text-primary-foreground">
          Guided path kholo
        </Link>
      </div>
    );
  }
  if (!customerJourneyEnabled()) {
    return (
      <div data-testid="journey-off" className="flex flex-col gap-3 text-sm text-muted-foreground">
        <p>Yeh kadam-dar-kadam guide abhi chalu nahi hai. Apni jodi hui strategy aur uski position &ldquo;Meri strategies&rdquo; me dikhti hai.</p>
        <Link href="/marketplace/me" className="inline-flex min-h-12 w-full items-center justify-center rounded-md bg-primary px-4 text-base font-medium text-primary-foreground">
          Meri strategies kholo
        </Link>
      </div>
    );
  }
  return <JourneyStepper step={step} />;
}

export default function JourneyPage() {
  return (
    <div className="p-4 md:p-6 lg:p-8">
      {/* The practice banner is mounted ONCE, by the (dashboard) layout, for every customer
          screen (2 Oct 2026) — this page used to mount its own copy, which would have shown
          TWICE. One banner, one source. */}
      <ProPage title="Shuru karo" blurb="Ek waqt me ek kadam — plan se trade tak.">
        <Suspense fallback={null}>
          <JourneyBody />
        </Suspense>
      </ProPage>
    </div>
  );
}

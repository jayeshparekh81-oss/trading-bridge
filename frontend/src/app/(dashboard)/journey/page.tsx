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
import { guidedPathEnabled } from "@/lib/guided-path";

function JourneyBody() {
  const params = useSearchParams();
  const raw = params?.get("step") ?? null;
  const step = raw && (JOURNEY_STEPS as readonly string[]).includes(raw) ? (raw as JourneyStep) : null;
  // ONE guided path (founder, 26 Sep): when the first-timer path is on, this page
  // points at it instead of showing a second, different stepper.
  if (guidedPathEnabled()) {
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
      <p data-testid="journey-off" className="text-sm text-muted-foreground">
        Yeh guide abhi chalu nahi hai. Apni strategy aur position ke liye Marketplace → My Strategies dekho.
      </p>
    );
  }
  return <JourneyStepper step={step} />;
}

export default function JourneyPage() {
  return (
    <div className="p-4 md:p-6 lg:p-8">
      <ProPage title="Shuru karo" blurb="Ek waqt me ek kadam — plan se trade tak.">
        <Suspense fallback={null}>
          <JourneyBody />
        </Suspense>
      </ProPage>
    </div>
  );
}

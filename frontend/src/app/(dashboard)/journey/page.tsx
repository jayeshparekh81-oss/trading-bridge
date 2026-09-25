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
import { JOURNEY_STEPS, customerJourneyEnabled, type JourneyStep } from "@/lib/customer-journey";

function JourneyBody() {
  const params = useSearchParams();
  const raw = params?.get("step") ?? null;
  const step = raw && (JOURNEY_STEPS as readonly string[]).includes(raw) ? (raw as JourneyStep) : null;
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

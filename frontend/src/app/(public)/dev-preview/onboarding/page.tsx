"use client";

/** DEV-ONLY: the 3-step Simple onboarding, no account needed (API calls fail softly). */

import { SimpleOnboarding } from "@/components/simple/simple-onboarding";

export default function PreviewOnboarding() {
  return (
    <div className="min-h-screen bg-background text-foreground dark">
      <SimpleOnboarding />
    </div>
  );
}

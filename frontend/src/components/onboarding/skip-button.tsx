"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SkipForward } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { trackEventSync } from "@/lib/analytics";
import { useAuth } from "@/lib/auth";

interface SkipButtonProps {
  atStep: number;
}

/**
 * "Skip karo" — completes onboarding (step 6) + tracks the
 * abandonment point + lands the user on /strategies. Always
 * visible on every onboarding step so the flow is never a
 * dead-end for users who already know what they want.
 */
export function SkipButton({ atStep }: SkipButtonProps) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const { user } = useAuth();

  async function handleSkip() {
    setBusy(true);
    try {
      await api.post("/onboarding/complete", {});
    } catch {
      // Even if the backend POST fails, we don't want to trap the
      // user on the onboarding flow. The state will reconcile
      // on next /me refresh.
    }
    if (user?.id) {
      trackEventSync(user.id, "onboarding_skipped", { at_step: atStep });
    }
    router.push("/strategies");
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleSkip}
      disabled={busy}
      type="button"
      className="text-muted-foreground hover:text-foreground"
    >
      <SkipForward className="h-3.5 w-3.5" />
      Skip karo
    </Button>
  );
}

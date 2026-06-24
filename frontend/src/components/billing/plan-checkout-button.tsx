"use client";

/**
 * Plan checkout CTA for the pricing surface.
 *
 * Guests → "Start Free Trial" link to /register (checkout needs an account).
 * Logged-in users → "Upgrade" which calls the backend subscribe endpoint, opens
 * Razorpay Checkout with the PUBLIC key + ``subscription_id``, then POLLS
 * ``GET /api/billing/me`` until the (webhook-driven) plan flips active. We never
 * mark the plan active client-side.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { openSubscriptionCheckout } from "@/lib/billing/razorpay";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface SubscribeResponse {
  razorpay_subscription_id: string;
  razorpay_key_id: string;
  status: string;
  short_url: string | null;
  plan_tier: string;
  amount_inr: number;
}

interface BillingMe {
  plan_status: string;
  is_active: boolean;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function PlanCheckoutButton({
  planId,
  planName,
  popular,
  className,
}: {
  planId: string;
  planName: string;
  popular: boolean;
  className?: string;
}) {
  const { user, isLoading } = useAuth();
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const baseClass = cn(
    "block text-center py-3 rounded-xl font-semibold transition-all mb-4",
    popular
      ? "bg-gradient-to-r from-accent-blue to-accent-purple text-white hover:shadow-[0_0_25px_rgba(59,130,246,0.4)]"
      : "border border-border hover:bg-accent",
    className,
  );

  // Guests (or while auth resolves) → register CTA.
  if (isLoading || !user) {
    return (
      <Link href="/register" className={baseClass}>
        Start Free Trial
      </Link>
    );
  }

  async function pollUntilActive(): Promise<boolean> {
    for (let i = 0; i < 20; i++) {
      await sleep(3000);
      if (!mounted.current) return false;
      try {
        const me = await api.get<BillingMe>("/billing/me");
        if (me.is_active) return true;
      } catch {
        // transient — keep polling
      }
    }
    return false;
  }

  async function upgrade() {
    setBusy(true);
    try {
      const res = await api.post<SubscribeResponse>("/billing/subscribe", {
        plan_id: planId,
      });
      await openSubscriptionCheckout({
        keyId: res.razorpay_key_id,
        subscriptionId: res.razorpay_subscription_id,
        description: `TRADETRI ${planName} plan`,
        prefill: user?.email ? { email: user.email } : undefined,
        onSuccess: async () => {
          toast.info("Payment mil gaya — plan activate ho raha hai…");
          const active = await pollUntilActive();
          if (!mounted.current) return;
          toast[active ? "success" : "info"](
            active
              ? `✅ ${planName} plan active!`
              : "Abhi process ho raha hai — thodi der mein refresh karein.",
          );
        },
        onDismiss: () => toast.info("Checkout band ho gaya."),
        onFailure: () => toast.error("Payment fail ho gaya — dobara try karein."),
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        toast.error("Billing abhi configure nahi hai — thodi der baad try karein.");
      } else {
        const msg = err instanceof ApiError ? err.detail : "Checkout shuru nahi ho paya";
        toast.error(msg);
      }
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  return (
    <button type="button" onClick={upgrade} disabled={busy} className={baseClass}>
      {busy ? (
        <span className="inline-flex items-center justify-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Opening checkout…
        </span>
      ) : (
        `Upgrade to ${planName}`
      )}
    </button>
  );
}

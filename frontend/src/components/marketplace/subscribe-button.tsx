"use client";

/**
 * Subscribe / unsubscribe button.
 *
 * Free listings round-trip the subscribe call directly. Paid listings call the
 * backend subscribe endpoint, which (when Razorpay is configured) creates a
 * recurring subscription and returns a checkout handle; we open Razorpay
 * Checkout with the PUBLIC key + ``subscription_id``. Activation is
 * webhook-driven on the BACKEND — after checkout we show "payment processing"
 * and POLL the backend subscription status until it flips ``active`` (we never
 * mark anything active client-side).
 *
 * Hidden when the caller is the creator of the listing.
 */

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, CreditCard, IndianRupee, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlowButton } from "@/components/ui/glow-button";
import { api, ApiError } from "@/lib/api";
import { openSubscriptionCheckout } from "@/lib/billing/razorpay";
import { trackEventSync } from "@/lib/analytics";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

type SubscriptionStatus = "active" | "pending" | null;

interface SubscribeButtonProps {
  listingId: string;
  priceInr: number;
  isCreator: boolean;
  /** The caller's current subscription state for this listing (drives resting
   *  UI): ``active`` → manage, ``pending`` → awaiting payment, ``null`` → CTA. */
  subscriptionStatus: SubscriptionStatus;
  onChange: () => void;
}

interface MarketplaceSubscribeResponse {
  id: string;
  listing_id: string;
  status: "pending" | "active" | "cancelled" | "expired";
  amount_paid_inr: number;
  requires_payment: boolean;
  razorpay_subscription_id: string | null;
  razorpay_key_id: string | null;
  razorpay_short_url: string | null;
}

interface SubMe {
  subscriptions: { listing_id: string; status: string }[];
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function SubscribeButton({
  listingId,
  priceInr,
  isCreator,
  subscriptionStatus,
  onChange,
}: SubscribeButtonProps) {
  const [busy, setBusy] = useState(false);
  const [processing, setProcessing] = useState(false);
  const mounted = useRef(true);
  const { user } = useAuth();

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  if (isCreator) return null;

  const isPremium = priceInr > 0;

  /** Poll the backend until this listing's subscription is active (or budget
   *  runs out). The backend webhook is the source of truth — we only read. */
  async function pollUntilActive(): Promise<boolean> {
    for (let i = 0; i < 20; i++) {
      await sleep(3000);
      if (!mounted.current) return false;
      try {
        const me = await api.get<SubMe>("/marketplace/subscriptions/me");
        const row = me.subscriptions.find((s) => s.listing_id === listingId);
        if (row?.status === "active") return true;
      } catch {
        // transient — keep polling
      }
    }
    return false;
  }

  async function startPaidCheckout() {
    setBusy(true);
    try {
      const res = await api.post<MarketplaceSubscribeResponse>(
        `/marketplace/listings/${listingId}/subscribe`,
        {},
      );

      // Free listing OR gateway not configured: backend already made it active.
      if (!res.requires_payment || !res.razorpay_subscription_id || !res.razorpay_key_id) {
        toast.success("🎉 Subscribed — happy trading!");
        onChange();
        return;
      }

      if (user?.id) {
        trackEventSync(user.id, "marketplace_checkout_opened", { amount_inr: priceInr });
      }

      await openSubscriptionCheckout({
        keyId: res.razorpay_key_id,
        subscriptionId: res.razorpay_subscription_id,
        description: `Marketplace subscription (₹${priceInr.toLocaleString("en-IN")}/mo)`,
        prefill: user?.email ? { email: user.email } : undefined,
        onSuccess: () => {
          // Payment captured at the gateway — activation is webhook-driven.
          void handleProcessing();
        },
        onDismiss: () => {
          // Closed without (or before) completing. A pending sub exists; let
          // the page reflect it so the user can resume.
          toast.info("Checkout band ho gaya — payment complete karke resume kar sakte ho.");
          onChange();
        },
        onFailure: () => {
          toast.error("Payment fail ho gaya — dobara try karein.");
          onChange();
        },
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Subscribe shuru nahi ho paya";
      toast.error(msg);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function handleProcessing() {
    if (!mounted.current) return;
    setProcessing(true);
    toast.info("Payment mil gaya — subscription activate ho rahi hai…");
    const active = await pollUntilActive();
    if (!mounted.current) return;
    setProcessing(false);
    if (active) {
      toast.success("✅ Subscription active — happy trading!");
      if (user?.id) {
        trackEventSync(user.id, "marketplace_subscription_active", { was_paid: true });
      }
    } else {
      toast.info("Abhi process ho raha hai — thodi der mein status refresh karein.");
    }
    onChange();
  }

  async function doFreeSubscribe() {
    setBusy(true);
    try {
      await api.post(`/marketplace/listings/${listingId}/subscribe`, {});
      toast.success("🎉 Subscribed — happy trading!");
      if (user?.id) {
        trackEventSync(user.id, "marketplace_subscribed_client", { was_paid: false });
      }
      onChange();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Subscribe nahi ho paya";
      toast.error(msg);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function doUnsubscribe() {
    setBusy(true);
    try {
      await api.delete(`/marketplace/listings/${listingId}/subscribe`);
      toast.success("Unsubscribe ho gaye");
      onChange();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Unsubscribe nahi ho paya";
      toast.error(msg);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  // ── Resting states ───────────────────────────────────────────────────

  if (subscriptionStatus === "active") {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={doUnsubscribe}
        disabled={busy}
        type="button"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5" />
        )}
        Subscribed — Cancel
      </Button>
    );
  }

  if (processing || subscriptionStatus === "pending") {
    return (
      <div className="flex items-center gap-2 flex-wrap justify-end">
        <span className="inline-flex items-center gap-1.5 text-[11px] text-amber-300/90">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Payment processing — activates after confirmation
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={startPaidCheckout}
          disabled={busy}
          type="button"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CreditCard className="h-3.5 w-3.5" />}
          Resume payment
        </Button>
        <Button variant="ghost" size="sm" onClick={onChange} type="button">
          Refresh
        </Button>
      </div>
    );
  }

  if (isPremium) {
    return (
      <GlowButton size="sm" onClick={startPaidCheckout} disabled={busy} type="button">
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <IndianRupee className="h-3.5 w-3.5" />
        )}
        Subscribe — ₹{priceInr.toLocaleString("en-IN")}/mo
      </GlowButton>
    );
  }

  return (
    <GlowButton size="sm" onClick={doFreeSubscribe} disabled={busy} type="button">
      {busy ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <CheckCircle2 className="h-3.5 w-3.5" />
      )}
      Subscribe — FREE
    </GlowButton>
  );
}

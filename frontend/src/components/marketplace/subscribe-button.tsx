"use client";

/**
 * Subscribe / unsubscribe button. Free listings round-trip the
 * call directly. Paid listings open a "payment integration coming
 * soon" modal that explains the Phase 4 deferral and lets the
 * user complete a stub-paid subscription so the rest of the
 * marketplace flow (ratings, history) is exercisable today.
 *
 * The button is hidden when the caller is the creator of the
 * listing — creators can't subscribe to their own product.
 */

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, IndianRupee, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlowButton } from "@/components/ui/glow-button";
import { api, ApiError } from "@/lib/api";
import { toast } from "sonner";

interface SubscribeButtonProps {
  listingId: string;
  priceInr: number;
  isCreator: boolean;
  isSubscribed: boolean;
  onChange: () => void;
}

export function SubscribeButton({
  listingId,
  priceInr,
  isCreator,
  isSubscribed,
  onChange,
}: SubscribeButtonProps) {
  const [busy, setBusy] = useState(false);
  const [showPaidModal, setShowPaidModal] = useState(false);

  if (isCreator) return null;

  const isPremium = priceInr > 0;

  async function doSubscribe() {
    setBusy(true);
    try {
      await api.post(`/marketplace/listings/${listingId}/subscribe`, {});
      toast.success("🎉 Subscribed — happy trading!");
      onChange();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Subscribe nahi ho paya";
      toast.error(msg);
    } finally {
      setBusy(false);
      setShowPaidModal(false);
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
      setBusy(false);
    }
  }

  if (isSubscribed) {
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

  if (isPremium) {
    return (
      <>
        <GlowButton
          size="sm"
          onClick={() => setShowPaidModal(true)}
          disabled={busy}
          type="button"
        >
          <IndianRupee className="h-3.5 w-3.5" />
          Subscribe — ₹{priceInr.toLocaleString("en-IN")}
        </GlowButton>
        <PaidStubModal
          open={showPaidModal}
          priceInr={priceInr}
          busy={busy}
          onConfirm={doSubscribe}
          onClose={() => setShowPaidModal(false)}
        />
      </>
    );
  }

  return (
    <GlowButton size="sm" onClick={doSubscribe} disabled={busy} type="button">
      {busy ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <CheckCircle2 className="h-3.5 w-3.5" />
      )}
      Subscribe — FREE
    </GlowButton>
  );
}

function PaidStubModal({
  open,
  priceInr,
  busy,
  onConfirm,
  onClose,
}: {
  open: boolean;
  priceInr: number;
  busy: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.94, y: 8 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.94, y: 8 }}
            className="bg-[#0b0e14] border border-amber-300/30 rounded-xl shadow-2xl w-full max-w-md p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold">Payment integration coming soon</h3>
                <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
                  Real Razorpay / UPI gateway Phase 4 mein lagega.
                  Abhi confirm karne pe stub-payment record ho jaata
                  hai (₹{priceInr.toLocaleString("en-IN")} as if paid)
                  — full marketplace flow chal jaata hai aur baad
                  mein actual charge ke baad reconcile ho jayega.
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                type="button"
              >
                <X className="h-4 w-4" />
              </Button>
            </header>
            <div className="rounded-md bg-amber-400/10 border border-amber-300/30 p-3 text-[11px] text-amber-200/90 leading-relaxed">
              ⚠️ Stub mode: koi actual charge nahi lagega.
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={onClose} type="button">
                Cancel
              </Button>
              <GlowButton
                size="sm"
                onClick={onConfirm}
                disabled={busy}
                type="button"
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                Confirm Stub Subscription
              </GlowButton>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

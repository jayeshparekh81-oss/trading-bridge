"use client";

/**
 * One-click "take this trade" confirm control for the signal feed.
 *
 * ⚠️ LIVE-ACTION CONTROL. Wired to the PAPER-GATED confirm endpoint:
 *   POST /marketplace/subscriptions/signals/{id}/confirm
 * Today the endpoint records a SIMULATED (paper) fill and places NO real broker
 * order (placed_real is always false) — the toast says so explicitly. A mistaken
 * or blanket action is exactly the class of past incident we design against, so
 * the deliberate two-step (button → confirm dialog) ships from day one, and the
 * POST is a single, signal-scoped call — server-validity-checked + idempotent,
 * never a bulk close and never a raw order/execute path.
 */

import { useState } from "react";
import { CheckCircle2, Loader2, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import type { ConfirmSignalResult, SubscriberSignal } from "@/lib/signals";
import { toast } from "sonner";

interface Props {
  signal: SubscriberSignal;
  /** Called after a successful confirm so the feed can refetch. */
  onConfirmed?: () => void;
  /** Validity lapsed / already-acted → the action is unavailable. */
  disabled?: boolean;
}

export function OneClickConfirmButton({ signal, onConfirmed, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    try {
      // Single, signal-scoped POST to the PAPER-gated confirm endpoint. No body
      // (the signal id is the path param); the server re-checks validity, is
      // idempotent, and records a paper fill only — it never calls a broker.
      const res = await api.post<ConfirmSignalResult>(
        `/marketplace/subscriptions/signals/${signal.id}/confirm`,
      );

      if (res.status === "already_confirmed") {
        toast.info("Already confirmed", { description: res.note });
      } else if (res.placed_real) {
        // DEFENSIVE — unreachable in this build (the endpoint hardcodes
        // placed_real=false). We derive the claim from the SERVER's answer
        // rather than asserting "paper" blindly: if a future build ever places
        // for real, the customer must never be shown the paper reassurance.
        toast.warning("REAL order placed — this was NOT a paper confirmation", {
          description: res.note,
        });
      } else {
        // PAPER-clear: make it unmistakable this placed no real order.
        toast.success("Paper confirmation ✓ — no real order placed", {
          description: res.note,
        });
      }
      setOpen(false);
      onConfirmed?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Signal window lapsed — cannot confirm");
      } else {
        const msg = err instanceof ApiError ? err.detail : "Confirm nahi ho paya — try again";
        toast.error(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  const entry = signal.entry ? ` @ ${signal.entry}` : "";
  const sl = signal.stop_loss ? ` · SL ${signal.stop_loss}` : "";
  const target = signal.target ? ` · Target ${signal.target}` : "";

  return (
    <>
      <Button
        size="sm"
        type="button"
        disabled={disabled}
        onClick={() => setOpen(true)}
        data-testid={`confirm-${signal.id}`}
        className="whitespace-nowrap"
      >
        <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
        Take trade
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-amber-400" />
              Confirm — take this trade?
            </DialogTitle>
            <DialogDescription>
              {signal.listing_title} · {signal.symbol} · {signal.action}
              {entry}
              {sl}
              {target}
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-md bg-amber-400/10 border border-amber-300/30 px-3 py-2 text-[11px] text-amber-200/90 leading-relaxed">
            <strong>Paper confirmation.</strong> This records a simulated (paper)
            fill and places <strong>no real broker order</strong>. Live real
            placement activates through the gated execution path (separate step).
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={() => setOpen(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              type="button"
              onClick={confirm}
              disabled={busy}
              data-testid={`confirm-yes-${signal.id}`}
            >
              {busy ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
              )}
              Confirm (paper)
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

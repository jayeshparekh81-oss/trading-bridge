"use client";

/**
 * Emergency exit — close this subscription's position from tradetri.com.
 *
 * ⚠️ This is the one control in the subscriber surface that ACTS. Everything
 * else only ever withholds action. So it ships with the same two-step confirm
 * as the take-trade button, and — the catch we hit before with the confirm
 * toast — the PAPER vs REAL wording is DERIVED FROM THE SERVER RESPONSE
 * (`placed_real`), never hardcoded. A hardcoded "no real order" reassurance
 * would keep reassuring even after the real path is switched on.
 *
 * Partial failures are surfaced verbatim: a position that did not close is
 * still live at the broker, and the customer must be told exactly that.
 */

import { useState } from "react";
import { AlertTriangle, Loader2, XCircle } from "lucide-react";
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
import { toast } from "sonner";

export interface ClosePositionOutcome {
  position_id: string;
  symbol: string | null;
  outcome: string;
  quantity_closed: number;
}

export interface ClosePositionResult {
  subscription_id: string;
  status: string;
  /** Server truth. The wording below is derived from this. */
  placed_real: boolean;
  positions: ClosePositionOutcome[];
  errors: string[];
  note: string;
}

interface Props {
  subscriptionId: string;
  positionId: string;
  symbol?: string | null;
  onClosed?: () => void;
  disabled?: boolean;
}

export function ClosePositionButton({
  subscriptionId,
  positionId,
  symbol,
  onClosed,
  disabled,
}: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    try {
      const res = await api.post<ClosePositionResult>(
        `/marketplace/subscriptions/${subscriptionId}/close-position`,
        { position_id: positionId },
      );

      if (res.status === "dormant") {
        toast.info("Abhi ye feature on nahi hai", { description: res.note });
      } else if (res.status === "already_flat") {
        toast.info("Position pehle se band hai", { description: res.note });
      } else if (res.status === "closed") {
        // PAPER vs REAL comes from the SERVER, not from an assumption here.
        const title = res.placed_real
          ? "Position band ho gayi — REAL order bheja gaya"
          : "Position band ho gayi (PAPER — koi real order nahi gaya)";
        toast.success(title, { description: res.note });
      } else {
        // partial / failed — NEVER dressed up as success.
        toast.error("Sab kuch band nahi ho paya — apna broker check karo", {
          description: res.errors.length ? res.errors.join(" · ") : res.note,
        });
      }

      setOpen(false);
      onClosed?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Ek close pehle se chal raha hai — thoda ruko");
      } else if (err instanceof ApiError && err.status === 503) {
        toast.error("Abhi safely process nahi kar sakte", {
          description: "Kuch band nahi hua. Dobara try karo ya broker par band karo.",
        });
      } else {
        toast.error(
          err instanceof ApiError ? err.detail : "Close nahi ho paya — try again",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        type="button"
        disabled={disabled}
        onClick={() => setOpen(true)}
        data-testid={`close-position-${positionId}`}
        className="whitespace-nowrap border-loss/40 text-loss hover:bg-loss/10"
      >
        <XCircle className="h-3.5 w-3.5 mr-1.5" />
        Close position
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              Position band karein?
            </DialogTitle>
            <DialogDescription>
              {symbol ? `${symbol} — ` : ""}yeh position band kar di jayegi.
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-md bg-amber-400/10 border border-amber-300/30 px-3 py-2 text-[11px] text-amber-200/90 leading-relaxed">
            Band karne ke baad is trade ke aage ke signals (partial / exit /
            SL) par <strong>koi order nahi lagega</strong>. Agar sab band na ho
            paya to hum aapko saaf-saaf bata denge — tab apna broker zaroor
            check karna.
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={() => setOpen(false)}
              disabled={busy}
            >
              Rehne do
            </Button>
            <Button
              size="sm"
              type="button"
              onClick={confirm}
              disabled={busy}
              data-testid={`close-position-yes-${positionId}`}
            >
              {busy ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <XCircle className="h-3.5 w-3.5 mr-1.5" />
              )}
              Haan, band karo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

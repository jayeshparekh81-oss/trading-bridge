"use client";

/**
 * One-click "take this trade" confirm control for the signal feed.
 *
 * ⚠️ LIVE-ACTION CONTROL — LATER. Today this is a NO-OP MOCK: there is NO
 * backend confirm endpoint (Phase-1 audit), so clicking places NOTHING. It
 * only toasts. The confirm DIALOG is here already because, once wired, this
 * button will trigger a customer's REAL order — a mistaken/blanket action is
 * exactly the class of past incident we design against, so the deliberate
 * two-step (button → confirm) ships from day one.
 *
 * Mirrors subscribe-button.tsx's busy/try/catch/toast pattern. When the backend
 * lands, the real confirm call goes where the comment marks it — a single,
 * signal-scoped POST, server-validity-checked + idempotent (never a bulk close).
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
import type { MockSignal } from "@/lib/mock/signals-mock";
import { toast } from "sonner";

interface Props {
  signal: MockSignal;
  /** Entry-window lapsed / already-acted → the action is unavailable. */
  disabled?: boolean;
}

export function OneClickConfirmButton({ signal, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    try {
      // ───────────────────────────────────────────────────────────────
      // REAL WIRING GOES HERE (Phase-1c, backend-blocked):
      //   await api.post(`/marketplace/signals/${signal.id}/confirm`, {
      //     subscription_id, idempotency_key,
      //   });
      // The endpoint MUST: verify execution_mode === 'one_click', re-check the
      // validity window SERVER-SIDE, be idempotent, and act on THIS signal +
      // subscription only. Until it exists, we place nothing.
      // ───────────────────────────────────────────────────────────────
      await new Promise((r) => setTimeout(r, 350)); // simulate latency only
      toast.success("Mock confirm — no order placed (backend not wired)");
      setOpen(false);
    } catch {
      toast.error("Confirm nahi ho paya — try again");
    } finally {
      setBusy(false);
    }
  }

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
              {signal.strategyName} · {signal.symbol} · {signal.side}
              {signal.entry ? ` @ ${signal.entry}` : ""}
              {signal.sl ? ` · SL ${signal.sl}` : ""}
              {signal.target ? ` · Target ${signal.target}` : ""}
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-md bg-amber-400/10 border border-amber-300/30 px-3 py-2 text-[11px] text-amber-200/90 leading-relaxed">
            Mock mode — clicking Confirm places <strong>no real order</strong>.
            Live one-click confirmation activates when the backend endpoint ships
            (Phase&nbsp;3 / empanelment).
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
              Confirm (mock)
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

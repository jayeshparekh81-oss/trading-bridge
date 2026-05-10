"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface QueueItemSummary {
  id: string;
  indicator_id: string;
  requested_status: string;
  request_reason: string;
}

interface Props {
  item: QueueItemSummary | null;
  onClose: () => void;
  onDecide: (
    item: QueueItemSummary,
    decision: "approve" | "reject",
    notes: string,
  ) => Promise<void>;
}

/**
 * Modal that confirms an approve / reject decision on a pending
 * queue item. Calls back to the parent to actually fire the API
 * request — keeps the modal stateless beyond the local notes
 * draft + busy flag.
 */
export function ApprovalModal({ item, onClose, onDecide }: Props) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (item == null) return null;

  async function fire(decision: "approve" | "reject") {
    if (item == null) return;
    if (notes.trim().length === 0) {
      setError("Decision notes likhna zaroori hai.");
      return;
    }
    setBusy(decision);
    setError(null);
    try {
      await onDecide(item, decision, notes.trim());
      setNotes("");
      onClose();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Decision save nahi ho paya.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="w-full max-w-md"
          onClick={(e) => e.stopPropagation()}
        >
          <GlassmorphismCard hover={false}>
            <div className="space-y-3">
              <header className="flex items-start justify-between gap-3">
                <div className="space-y-0.5">
                  <p className="text-sm font-semibold">
                    Decide queue item
                  </p>
                  <p className="text-[10px] text-muted-foreground font-mono">
                    {item.indicator_id} → {item.requested_status}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </header>

              <div className="rounded-md bg-white/[0.02] border border-white/[0.06] p-2">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                  Request reason
                </p>
                <p className="text-[12px] leading-relaxed">
                  {item.request_reason}
                </p>
              </div>

              <div className="space-y-1">
                <label
                  htmlFor="decision-notes"
                  className="text-[10px] uppercase tracking-wider text-muted-foreground"
                >
                  Decision notes (audit trail)
                </label>
                <Input
                  id="decision-notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Why are you approving/rejecting?"
                />
              </div>

              {error != null ? (
                <p className="text-[11px] text-loss">{error}</p>
              ) : null}

              <p className="text-[10px] text-muted-foreground italic">
                Decision irreversible hai — approval ek naya override row
                banata hai, rejection queue close kar deti hai.
              </p>

              <div className="flex items-center justify-end gap-2 pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => fire("reject")}
                  disabled={busy != null}
                  className={cn(
                    "border-loss/40 text-loss hover:bg-loss/[0.06]",
                  )}
                >
                  {busy === "reject" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : null}
                  ❌ Reject
                </Button>
                <Button
                  size="sm"
                  type="button"
                  onClick={() => fire("approve")}
                  disabled={busy != null}
                >
                  {busy === "approve" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : null}
                  ✅ Approve
                </Button>
              </div>
            </div>
          </GlassmorphismCard>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

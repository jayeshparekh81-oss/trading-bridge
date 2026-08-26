"use client";

/**
 * PAUSE a deployment — the StrykeX lesson, made explicit.
 *
 * A customer who wants out must PAUSE FIRST, then close. Otherwise the system
 * keeps acting on the next exit signal and can punch an order against a
 * position they just closed by hand. StrykeX tells users this plainly; we had
 * the machinery (execution_mode) and never said it.
 *
 * PAUSE = execution_mode -> "offline" (alerts only, nothing auto-executes).
 * That is an EXISTING, persisted field — no new backend anything. Resuming
 * sets it back to "auto".
 */

import { useState } from "react";
import { Loader2, Pause, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { toast } from "sonner";

/** The mode that means "paused": alerts only, nothing fires by itself. */
export const PAUSED_MODE = "offline";
export const RUNNING_MODE = "auto";

interface Props {
  subscriptionId: string;
  /** Current execution mode from the settings endpoint. */
  mode: string | null | undefined;
  onChanged?: () => void;
}

export function PauseDeploymentButton({ subscriptionId, mode, onChanged }: Props) {
  const [busy, setBusy] = useState(false);
  const paused = String(mode ?? "").toLowerCase() !== RUNNING_MODE;

  async function toggle() {
    setBusy(true);
    const next = paused ? RUNNING_MODE : PAUSED_MODE;
    try {
      const res = await api.patch<{ execution_mode: string; applied?: boolean }>(
        `/marketplace/subscriptions/${subscriptionId}/settings`,
        { execution_mode: next },
      );
      // Report the SERVER's answer, never the value we hoped for.
      const now = String(res?.execution_mode ?? next).toLowerCase();
      if (now === PAUSED_MODE) {
        toast.success("Paused — ab koi order apne aap nahi lagega", {
          description:
            "Signals sirf notification aayenge. Ab aap position safely band kar sakte ho.",
        });
      } else {
        toast.success("Resumed — signals dobara auto-execute honge");
      }
      onChanged?.();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Pause nahi ho paya — try again",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      size="sm"
      type="button"
      variant="outline"
      onClick={toggle}
      disabled={busy}
      data-testid={`pause-${subscriptionId}`}
      className="whitespace-nowrap"
    >
      {busy ? (
        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
      ) : paused ? (
        <Play className="h-3.5 w-3.5 mr-1.5" />
      ) : (
        <Pause className="h-3.5 w-3.5 mr-1.5" />
      )}
      {paused ? "Resume" : "Pause"}
    </Button>
  );
}

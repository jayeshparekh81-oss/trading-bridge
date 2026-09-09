"use client";

import {
  noTradesSinceText,
  trackingNoteText,
  useTrackingEpoch,
} from "@/lib/tracking-epoch";
import { cn } from "@/shared/lib/utils";

/**
 * The one honest line about where the record starts.
 *
 * ⚠️ NO DATE LIVES IN THIS FILE. The date is read from the server on every
 * render through `useTrackingEpoch` (which reads `GET /api/system/mode` →
 * `tracking_epoch`). A literal here would go stale silently the day the
 * platform moves its cut-off — the sentence would keep looking right and
 * would be wrong. A test greps this file for a hardcoded year/month so the
 * shortcut cannot be taken later.
 *
 * When the epoch is null, absent, or has not been read yet, this renders
 * NOTHING. Same rule as the paper banner: a cut-off we have not read is not
 * a cut-off we may announce, and there is no fallback date.
 */
export function TrackingEpochNote({ className }: { className?: string }) {
  const { label } = useTrackingEpoch();

  if (!label) return null;

  return (
    <p
      role="note"
      data-testid="tracking-epoch-note"
      className={cn("text-xs text-muted-foreground", className)}
    >
      {trackingNoteText(label)}
    </p>
  );
}

/**
 * The per-strategy version, for a card whose strategy has done nothing since
 * the cut-off. It exists so an inactive strategy READS as inactive-since-the
 * -cut-off instead of vanishing from the surface or looking like a strategy
 * that never traded at all.
 *
 * `tradedSince` is the caller's answer to "has this strategy traded since the
 * cut-off?" — `false` (we READ the activity and there was none) is the only
 * value that prints the line. `null` is unknown (activity not loaded, list
 * truncated, no epoch) and prints nothing, because "koi trade nahi kiya" is a
 * claim about the customer's own strategy, not a default.
 */
export function NoTradesSinceNote({
  tradedSince,
  className,
}: {
  tradedSince: boolean | null;
  className?: string;
}) {
  const { shortLabel } = useTrackingEpoch();

  if (tradedSince !== false || !shortLabel) return null;

  return (
    <p
      data-testid="no-trades-since-epoch"
      className={cn(
        "rounded-lg border border-white/[0.04] bg-white/[0.02] p-3",
        "text-xs leading-relaxed text-muted-foreground",
        className,
      )}
    >
      {noTradesSinceText(shortLabel)}
    </p>
  );
}

export default TrackingEpochNote;

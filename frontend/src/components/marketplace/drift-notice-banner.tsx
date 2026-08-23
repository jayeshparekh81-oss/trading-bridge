"use client";

/**
 * Per-subscription drift banner on /marketplace/me.
 *
 * Shown when the drift detector switched THIS subscription to MANUAL because
 * the customer closed the position at their own broker.
 *
 * Deliberately AMBER / informational, never red / error: nothing failed and
 * nothing is at risk — the position is already closed. Styling it as an error
 * would misrepresent a working-as-designed event and alarm someone who simply
 * exited their own trade. Copy lives in `@/lib/drift-notice`.
 */

import { Info } from "lucide-react";
import {
  DRIFT_NOTICE_REASSURANCE,
  DRIFT_NOTICE_TITLE,
  type DriftNotice,
  driftNoticeBody,
} from "@/lib/drift-notice";
import { cn } from "@/lib/utils";

interface Props {
  notice: DriftNotice | null | undefined;
  className?: string;
}

export function DriftNoticeBanner({ notice, className }: Props) {
  if (!notice) return null;

  const when = (() => {
    const d = new Date(notice.flipped_at);
    return Number.isNaN(d.getTime())
      ? null
      : d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  })();

  return (
    <div
      data-testid="drift-notice-banner"
      className={cn(
        // Amber = informational. NOT the loss/error palette.
        "rounded-lg border border-amber-300/30 bg-amber-400/[0.08] p-3 space-y-1.5",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <Info className="h-3.5 w-3.5 text-amber-300 shrink-0 mt-0.5" aria-hidden />
        <div className="space-y-1">
          <p className="text-[11px] font-semibold text-amber-200">
            {DRIFT_NOTICE_TITLE}
          </p>
          <p className="text-[10px] text-muted-foreground leading-relaxed">
            {driftNoticeBody(notice)}
          </p>
          <p className="text-[10px] text-amber-200/90 leading-relaxed">
            {DRIFT_NOTICE_REASSURANCE}
          </p>
          {when && (
            <p className="text-[9.5px] text-muted-foreground/70">{when}</p>
          )}
        </div>
      </div>
    </div>
  );
}

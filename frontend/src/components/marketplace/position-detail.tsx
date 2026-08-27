"use client";

/**
 * The subscription's open position, rendered as facts a customer can act on.
 * Split out of the My Strategies page so it is directly testable, alongside
 * its siblings (close-position-button, pause-deployment-button).
 */

/** Mirrors SubscriptionRead.open_position. Prices are STRINGS — exact DB text,
 *  never a re-rounded float. */
export interface SubscriptionPosition {
  id: string;
  symbol: string;
  quantity: number;
  side?: string | null;
  avg_entry_price?: string | null;
  remaining_quantity?: number | null;
  stop_loss_price?: string | null;
  target_price?: string | null;
  opened_at?: string | null;
  /** Tri-state, derived server-side from the execution that opened it. */
  paper_mode?: PaperMode;
}

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { executionLabel, type PaperMode } from "@/lib/execution-label";
import { displayPrice } from "@/lib/price-display";

/**
 * The open position, in words a customer can act on: which way, in at what,
 * how much is left, and where the stop and target sit.
 *
 * NO live or unrealised P&L. The feed behind this carries no LTP, so any P&L
 * shown here would be either stale or invented — and a wrong number on a
 * money screen is worse than an absent one. Whenever a real quote source is
 * wired, P&L belongs here, sourced, not guessed.
 *
 * Prices arrive as STRINGS (exact DB text) and are rendered verbatim — parsing
 * them to a float to "tidy" the display would re-round money.
 */
export function PositionDetail({
  position,
}: {
  position: SubscriptionPosition;
}) {
  const remaining = position.remaining_quantity ?? position.quantity;
  const label = executionLabel(position.paper_mode);
  // displayPrice drops the zero SENTINEL as well as nulls, so a fact is
  // omitted rather than shown as a price of 0 that never happened.
  const price = (raw: string | null | undefined) => {
    const shown = displayPrice(raw);
    return shown === "—" ? null : shown;
  };
  const entry = price(position.avg_entry_price);
  const stop = price(position.stop_loss_price);
  const target = price(position.target_price);
  const facts: { label: string; value: string }[] = [
    ...(position.side ? [{ label: "Side", value: position.side.toUpperCase() }] : []),
    ...(entry ? [{ label: "Entry", value: entry }] : []),
    { label: "Remaining", value: String(remaining) },
    ...(stop ? [{ label: "Stop", value: stop }] : []),
    ...(target ? [{ label: "Target", value: target }] : []),
  ];

  return (
    <div
      className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2"
      data-testid={`position-detail-${position.id}`}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] font-semibold">{position.symbol}</span>
        {/* ⚠️ THE LOAD-BEARING LABEL. This card is the ALWAYS-VISIBLE surface —
            the execution log sits behind an expand, this does not. A symbol
            with a side, an entry price, a stop and a target is exactly what a
            live broker position looks like, so without this chip the card
            silently reads as one. DERIVED from the position's own paper_mode
            (never hardcoded), same as every row in the log. */}
        <Badge
          title={label.meaning}
          aria-label={label.meaning}
          data-label-kind={label.kind}
          className={cn("text-[9px] uppercase", label.tone)}
        >
          {label.text}
        </Badge>
        {position.opened_at ? (
          <span className="text-[10px] text-muted-foreground">
            since {new Date(position.opened_at).toLocaleString("en-IN", {
              day: "2-digit",
              month: "short",
              year: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        ) : null}
      </div>
      <dl className="mt-1.5 flex items-center gap-x-4 gap-y-1 flex-wrap">
        {facts.map((f) => (
          <div key={f.label} className="flex items-baseline gap-1">
            <dt className="text-[10px] text-muted-foreground">{f.label}</dt>
            <dd className="text-[11px] tabular-nums font-medium">{f.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

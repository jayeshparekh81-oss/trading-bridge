"use client";

/**
 * This subscription's execution log — what actually got placed.
 *
 * Reads GET /marketplace/subscriptions/{id}/executions, which is scoped to the
 * caller's own subscription server-side (404 for anyone else's). Fetches only
 * while `enabled`, so opening My Strategies does not pull a log per row.
 *
 * The honesty rule lives in lib/execution-label.ts — read the header there
 * before touching any label copy. Short version: every label on this screen is
 * DERIVED from the row's own `paper_mode`, never hardcoded, because a log of
 * symbols/quantities/prices/order-ids is visually indistinguishable from a
 * broker fill history and must never be mistaken for one.
 */

import { Loader2, ScrollText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import {
  executionLabel,
  executionLogSummary,
  FETCH_FAILED_NOTE,
  LOADING_LOG_NOTE,
  MANUAL_CLOSE_GAP_NOTE,
  TRUNCATED_LOG_NOTE,
  type PaperMode,
} from "@/lib/execution-label";
import { displayPrice } from "@/lib/price-display";

export interface SubscriptionExecution {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  leg_role: string;
  order_type: string;
  price: string | null;
  broker_order_id: string | null;
  broker_status: string | null;
  error_code: string | null;
  error_message: string | null;
  placed_at: string;
  completed_at: string | null;
  /** Tri-state. `null` => the row does not say; NOT collapsed to either. */
  paper_mode: PaperMode;
}

interface ExecutionListResponse {
  subscription_id: string;
  executions: SubscriptionExecution[];
  count: number;
  /** True when the server cut the list short — never presented as the whole. */
  truncated?: boolean;
}

const EMPTY: ExecutionListResponse = {
  subscription_id: "",
  executions: [],
  count: 0,
};

export function ExecutionLog({
  subscriptionId,
  enabled = true,
  className,
}: {
  subscriptionId: string;
  enabled?: boolean;
  className?: string;
}) {
  const { data, isLoading, error } = useApi<ExecutionListResponse>(
    enabled ? `/marketplace/subscriptions/${subscriptionId}/executions` : null,
    EMPTY,
  );

  const rows = data?.executions ?? [];
  // Neither a FAILED fetch nor an IN-FLIGHT one may render as "there are no
  // executions". The fallback is an empty list, indistinguishable from a
  // confirmed-empty log — so claiming "no records exist" in either state would
  // assert something we have not learned. Order matters: error first, then
  // still-loading, and only then a summary of rows we actually received.
  const summary = error
    ? FETCH_FAILED_NOTE
    : isLoading
      ? LOADING_LOG_NOTE
      : executionLogSummary(rows);

  return (
    <div className={cn("space-y-2", className)} data-testid="execution-log">
      <div className="flex items-center gap-2">
        <ScrollText className="h-3.5 w-3.5 text-muted-foreground" />
        <h4 className="text-xs font-semibold">Execution log</h4>
        {isLoading ? (
          <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
        ) : null}
      </div>

      {/* Derived from the rows, not hardcoded — see executionLogSummary. */}
      <p
        className="text-[10px] leading-relaxed text-muted-foreground"
        data-testid="execution-log-summary"
      >
        {summary}
      </p>

      {/* The known gap, stated. Shown whenever the log is being presented at
          all, so a missing exit is never read as a position still running. */}
      {!error ? (
        <p className="text-[10px] leading-relaxed text-muted-foreground/80"
           data-testid="execution-log-gap">
          {MANUAL_CLOSE_GAP_NOTE}
        </p>
      ) : null}

      {data?.truncated ? (
        <p className="text-[10px] text-amber-300/80" data-testid="execution-log-truncated">
          {TRUNCATED_LOG_NOTE}
        </p>
      ) : null}

      {rows.length > 0 && !error ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="font-normal py-1 pr-3">When</th>
                <th className="font-normal py-1 pr-3">Leg</th>
                <th className="font-normal py-1 pr-3">Side</th>
                <th className="font-normal py-1 pr-3">Qty</th>
                <th className="font-normal py-1 pr-3">Price</th>
                <th className="font-normal py-1 pr-3">Status</th>
                <th className="font-normal py-1">Type</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const label = executionLabel(row.paper_mode);
                return (
                  <tr
                    key={row.id}
                    data-testid={`execution-row-${row.id}`}
                    className="border-t border-white/[0.05]"
                  >
                    <td className="py-1.5 pr-3 whitespace-nowrap text-muted-foreground">
                      {new Date(row.placed_at).toLocaleString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        year: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="py-1.5 pr-3 whitespace-nowrap">{row.leg_role}</td>
                    <td className="py-1.5 pr-3 uppercase whitespace-nowrap">
                      {row.side}
                    </td>
                    <td className="py-1.5 pr-3 tabular-nums">{row.quantity}</td>
                    <td className="py-1.5 pr-3 tabular-nums whitespace-nowrap">
                      {displayPrice(row.price)}
                    </td>
                    <td className="py-1.5 pr-3 whitespace-nowrap text-muted-foreground">
                      {row.error_code ?? row.broker_status ?? "—"}
                    </td>
                    <td className="py-1.5">
                      {/* DERIVED per row. A real fill renders a different chip
                          with a different tone — asserted by test, so this can
                          never rot into a constant "SIMULATED". */}
                      <Badge
                        title={label.meaning}
                        aria-label={label.meaning}
                        data-label-kind={label.kind}
                        className={cn("text-[9px] uppercase", label.tone)}
                      >
                        {label.text}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

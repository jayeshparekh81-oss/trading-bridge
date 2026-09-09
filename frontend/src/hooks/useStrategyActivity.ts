"use client";

import { useCallback } from "react";

import { isSinceEpoch, useTrackingEpoch } from "@/lib/tracking-epoch";
import { useApi } from "@/shared/api/use-api";

/** How many position rows we ask for. Also the truncation tripwire below. */
const LIMIT = 100;
const POSITIONS_URL = `/strategies/positions?limit=${LIMIT}`;

/** The only fields this join needs from `StrategyPositionRead`. */
interface PositionActivityRow {
  id: string;
  strategy_id: string;
  opened_at: string | null;
  closed_at: string | null;
}

interface PositionsResponse {
  positions: PositionActivityRow[];
  count: number;
}

/**
 * Has this strategy done anything since the tracking cut-off?
 *
 * `/api/strategies` says nothing about activity, so the answer is joined in
 * from the owner's positions — the same rows /positions renders — on
 * `strategy_id`, exactly the way `usePaperModes` joins the paper flag.
 *
 * THREE ANSWERS, AND ONLY ONE OF THEM IS A CLAIM:
 *   true  — a position of this strategy opened or closed on/after the cut-off
 *   false — we read the activity and there is none since the cut-off
 *   null  — we cannot say, and therefore must not say anything
 *
 * `null` is returned for: no cut-off read from the server, positions not
 * loaded, a failed fetch, and — the one that is easy to miss — a TRUNCATED
 * list. If the customer has more positions than we asked for, an absent row
 * proves nothing, so "no trades since the cut-off" would be a statement about
 * rows we never saw. A count we did not fully read is not a zero.
 */
export function useStrategyActivitySince(): {
  tradedSince: (strategyId: string | null | undefined) => boolean | null;
  isLoading: boolean;
  error: string | null;
} {
  const { iso } = useTrackingEpoch();
  const { data, isLoading, error } = useApi<PositionsResponse>(POSITIONS_URL, null, 60_000);

  const rows = data?.positions ?? null;
  const truncated =
    rows === null ? true : rows.length >= LIMIT || (data?.count ?? rows.length) > rows.length;

  const tradedSince = useCallback(
    (strategyId: string | null | undefined): boolean | null => {
      if (!strategyId || !iso) return null;
      if (error || rows === null || truncated) return null;

      return rows.some(
        (p) =>
          p.strategy_id === strategyId &&
          (isSinceEpoch(p.opened_at, iso) === true || isSinceEpoch(p.closed_at, iso) === true),
      );
    },
    [iso, rows, truncated, error],
  );

  return { tradedSince, isLoading, error };
}

export default useStrategyActivitySince;

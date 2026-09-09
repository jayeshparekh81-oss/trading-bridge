"use client";

import { useCallback } from "react";

import { useSystemMode } from "@/hooks/useSystemMode";
import { resolvePaperMode } from "@/lib/paper-mode";
import { useApi } from "@/shared/api/use-api";

/** Minimal shape we need from `GET /api/strategies` — see StrategyResponse. */
interface StrategyMode {
  id: string;
  is_paper: boolean;
}

interface StrategyListResponse {
  strategies: StrategyMode[];
  count: number;
}

/**
 * Per-row paper-mode truth for surfaces that show rows from many strategies.
 *
 * `/api/strategies/positions` returns `strategy_id` but NOT `is_paper` (see
 * `StrategyPositionRead`), so a positions row cannot state its own mode. The
 * owner's strategy list DOES carry `is_paper` per strategy and is already a
 * public read for this user, so we join on `strategy_id` client-side. That
 * keeps this a frontend-only fix — no backend deploy, nothing near the
 * live-money path — while still labelling every row from the flag the
 * executor actually obeys.
 *
 * THREE STATES, AND THE FALLBACK IS NARROW. `modeFor` returns `null` for any
 * strategy we have not loaded. It does NOT fall back to the global
 * `paper_mode` flag in that case — doing so is precisely the defect this
 * replaces, since a failed fetch would then print "simulated" over real-money
 * rows. The global flag is consulted ONLY where the backend consults it: for
 * a strategy that loaded but carries no explicit `is_paper`.
 */
export function usePaperModes(): {
  modeFor: (strategyId: string | null | undefined) => boolean | null;
  isLoading: boolean;
  error: string | null;
} {
  const platform = useSystemMode();
  const { data, isLoading, error } = useApi<StrategyListResponse>(
    "/strategies",
    null,
    60_000,
  );

  const modeFor = useCallback(
    (strategyId: string | null | undefined): boolean | null => {
      if (!strategyId || !data) return null;
      const strategy = data.strategies.find((s) => s.id === strategyId);
      // Not in the list — we have not read this strategy's flag. Unknown.
      if (!strategy) return null;
      return resolvePaperMode(strategy.is_paper, platform?.paper_mode ?? null);
    },
    [data, platform],
  );

  return { modeFor, isLoading, error };
}

export default usePaperModes;

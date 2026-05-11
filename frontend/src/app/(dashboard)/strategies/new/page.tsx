"use client";

/**
 * Smart-default redirector for ``/strategies/new``.
 *
 * Routing logic (first match wins):
 *
 *   1. Last-used level from ``localStorage["tb_strategy_mode"]`` —
 *      respect explicit user choice over count-based heuristics.
 *   2. ``strategyCount >= 6`` → intermediate (auto-graduation).
 *   3. Default → beginner (0–5 strategies).
 *
 * Edge cases:
 *   * The ``/strategies`` API call may be slow or fail. We render a
 *     thin "Redirecting…" skeleton until either the data arrives or
 *     the call errors; on error we proceed with ``count = 0``.
 *   * Hydration-safe: the redirect is deferred to ``useEffect`` and
 *     gated on a single ``decided`` ref so ``router.replace`` is only
 *     called once per mount.
 */

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import {
  STRATEGY_MODE_STORAGE_KEY,
  type StrategyMode,
} from "@/components/strategies/mode-selector";

interface StrategyListResponse {
  strategies: Array<{ id: string }>;
  count: number;
}

const COUNT_GRADUATION_THRESHOLD = 6;

export default function StrategiesNewRedirectPage() {
  const router = useRouter();
  const decidedRef = useRef(false);
  const { data, error } = useApi<StrategyListResponse>("/strategies", null);

  useEffect(() => {
    if (decidedRef.current) return;
    // Wait until the strategies call resolves (either way) so the
    // count-based fallback has real input. ``error`` resolving counts
    // as "done" — we treat a failed list call as zero strategies.
    if (!data && !error) return;

    let stored: StrategyMode | null = null;
    if (typeof window !== "undefined") {
      const raw = window.localStorage.getItem(STRATEGY_MODE_STORAGE_KEY);
      if (raw === "beginner" || raw === "intermediate" || raw === "expert") {
        stored = raw;
      }
    }

    let target: StrategyMode;
    if (stored) {
      target = stored;
    } else {
      const count = data?.count ?? 0;
      target = count >= COUNT_GRADUATION_THRESHOLD ? "intermediate" : "beginner";
    }

    decidedRef.current = true;
    router.replace(`/strategies/new/${target}`);
  }, [data, error, router]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto"
    >
      <GlassmorphismCard hover={false}>
        <div className="flex items-center gap-3 py-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-accent-blue" />
          <span>Redirecting to builder…</span>
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  PlayCircle,
  AlertTriangle,
  ArrowLeft,
  ShieldCheck,
  ShieldQuestion,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  BacktestResultPanel,
  type BacktestResultPayload,
} from "@/components/strategies/backtest-result-panel";
import {
  StrategyCoachCard,
  type StrategyHealthCardPayload,
} from "@/components/strategies/strategy-coach-card";
import {
  StrategyTruthPanel,
  type TruthReportPayload,
} from "@/components/strategies/strategy-truth-panel";
import {
  MarketRegimePanel,
  type RegimeReportPayload,
} from "@/components/strategies/market-regime-panel";
import {
  DeviationMonitorPanel,
  type DeviationReportPayload,
} from "@/components/strategies/deviation-monitor-panel";
import {
  TradeQualityCard,
  type TradeQualityReportPayload,
} from "@/components/strategies/trade-quality-card";
import {
  AIDoctorCard,
  type DiagnosisPayload,
} from "@/components/strategies/ai-doctor-card";
import {
  CandleSourcePicker,
  consumeStashedCandlesRequest,
  makeDefaultPickerValue,
  type CandleSourcePickerValue,
  type CandlesRequestPayload,
} from "@/components/strategies/candle-source-picker";
import { BacktestChartPanel } from "@/components/backtest/BacktestChartPanel";
import type { Timeframe } from "@/lib/chart/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import { celebrationCopy, useCelebration } from "@/lib/celebration";
import { cn } from "@/lib/utils";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};


/** Reliability section is the Phase 4 ReliabilityReport — snake_case. */
interface ReliabilityPayload {
  trust_score: {
    score: number;
    grade: string;
    verdict: string;
    warnings: string[];
    suggestions: string[];
  };
  out_of_sample: { degradation_percent: number } | null;
  walk_forward: { consistency_score: number } | null;
  sensitivity: { fragile: boolean; base_score: number } | null;
}

interface BacktestResponse {
  backtest: BacktestResultPayload;
  reliability: ReliabilityPayload | null;
  health_card: StrategyHealthCardPayload;
  truth: TruthReportPayload | null;
  regime: RegimeReportPayload | null;
  deviation: DeviationReportPayload | null;
  trade_quality: TradeQualityReportPayload | null;
  diagnosis: DiagnosisPayload | null;
  candles_source: "synthetic" | "dhan_historical";
  data_quality_warnings: string[];
}


export default function StrategyBacktestPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  /** Candle source consumed by ``runBacktest``. Hydrated from the
   *  builder-stashed value (``localStorage``) in a mount-only effect
   *  below so SSR and the first client render agree on ``null`` and
   *  no hydration mismatch is produced. The "Re-run with different
   *  data" dialog updates this via its own setter. */
  const [candlesRequest, setCandlesRequest] = useState<
    CandlesRequestPayload | null
  >(null);
  /** Milestone 3 (Queue EE/FF) — atomic snapshot of the async backtest
   *  run that BacktestChartPanel reads from. Set only after the async
   *  enqueue reaches SUCCEEDED. Symbol/timeframe are captured at
   *  enqueue time so the panel keeps showing the right values even if
   *  the user later mutates ``candlesRequest`` via the re-run dialog.
   *  Null when synthetic mode (no candles_request → no chart, per
   *  Queue FF N2a). */
  const [chartRun, setChartRun] = useState<{
    runId: string;
    symbol: string;
    timeframe: Timeframe;
  } | null>(null);
  /** Set true once the localStorage consume effect has run so the
   *  backtest auto-fire effect only dispatches one API call (with the
   *  final candles_request value) instead of two (one for null, one
   *  for the stashed value). */
  const [hydrated, setHydrated] = useState(false);
  /** Strict-Mode double-mount guard for the one-shot consume. */
  const consumedRef = useRef(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const celebrate = useCelebration();
  /** Fingerprint of the last result we celebrated for. Re-running the
   *  backtest produces a fresh response object identity even when the
   *  numbers are identical, so we key the dedupe on the response's
   *  shape (P&L + trust grade + truth grade) rather than reference. */
  const lastCelebrationKey = useRef<string | null>(null);

  const runBacktest = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        // Phase 9 deviation: opt into the demo split until real paper-
        // trading data is plumbed into this endpoint, otherwise the
        // panel only ever shows the "insufficient data" empty state.
        include_deviation_demo: true,
      };
      if (candlesRequest) {
        body.candles_request = candlesRequest;
      }
      const result = await api.post<BacktestResponse>(
        `/strategies/${id}/backtest`,
        body,
      );
      setData(result);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.detail : "Could not run backtest.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [id, candlesRequest]);

  // Hydrate the stashed-request once on mount (client-only —
  // ``consumeStashedCandlesRequest`` returns null on the server).
  // ``consumedRef`` survives the Strict-Mode double-invoke so the
  // one-shot ``localStorage`` consume doesn't fire twice in dev.
  useEffect(() => {
    if (consumedRef.current) return;
    consumedRef.current = true;
    const stashed = consumeStashedCandlesRequest();
    // setState-in-effect is intentional: one-shot localStorage hydration
    // gated by a Strict-Mode-safe consumedRef. The lint rule's intended
    // pattern (useSyncExternalStore) doesn't fit because the consume is
    // destructive and must run exactly once per mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stashed) setCandlesRequest(stashed);
    setHydrated(true);
  }, []);

  // Auto-fire the backtest, but only after hydration so we don't
  // dispatch a Synthetic-mode call followed by a Dhan call when a
  // stashed request is present.
  useEffect(() => {
    if (!hydrated) return;
    // setState-in-effect is intentional: auto-fire the backtest API call
    // exactly once after stashed-request hydration completes. The
    // hydrated flag dedupes; runBacktest's setIsLoading is the setState
    // the rule sees.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    runBacktest();
  }, [runBacktest, hydrated]);

  // Derive the celebration signal from data — pure, no setState in effect.
  // The double-A glow is then triggered by remounting the panel row
  // (key bump) so the CSS keyframe runs once on its own clock. The
  // signature is computed in render via ``useMemo`` so we never read
  // a ref during render (which the react-hooks lint rule forbids).
  const truthGrade = data?.truth?.grade ?? null;
  const trustGrade = data?.reliability?.trust_score?.grade ?? null;
  const totalPnl = data?.backtest.totalPnl ?? 0;
  const isDoubleA =
    !!data && trustGrade === "A" && truthGrade === "A" && totalPnl > 0;
  const dataSignature = useMemo(() => {
    if (!data) return "initial";
    return `${data.backtest.totalPnl.toFixed(2)}|${data.backtest.totalReturnPercent.toFixed(2)}|${trustGrade}|${truthGrade}`;
  }, [data, trustGrade, truthGrade]);

  // Celebration trigger — fires once per (P&L, trust, truth) signature.
  // Reduced-motion is honoured inside the celebrate() helper, so the
  // toasts still render but the confetti is suppressed.
  useEffect(() => {
    if (!data) return;
    const pnl = data.backtest.totalPnl;
    const returnPct = data.backtest.totalReturnPercent;
    const key = `${pnl.toFixed(2)}|${returnPct.toFixed(2)}|${trustGrade}|${truthGrade}`;
    if (lastCelebrationKey.current === key) return;
    lastCelebrationKey.current = key;

    if (pnl <= 0) return;

    if (isDoubleA) {
      void celebrate("huge");
      toast.success(celebrationCopy("huge", "Strong strategy detected"));
      return;
    }
    if (returnPct >= 5) {
      void celebrate("big");
      toast.success(celebrationCopy("big", "Strong result"));
      return;
    }
    void celebrate("medium");
    toast.success(celebrationCopy("medium", "Backtest profitable"));
  }, [data, celebrate, isDoubleA, trustGrade, truthGrade]);

  // Milestone 3 (Queue EE/FF) — additionally enqueue an async backtest
  // so BacktestChartPanel has a run_id for /api/backtest/{run_id}/markers.
  // Reads the SAME ``candlesRequest`` state the sync POST consumes (N3 —
  // no duplicate state, no drift). Only fires for dhan_historical mode
  // (N2a — synthetic has no symbol/timeframe at the page level). Field
  // names are remapped from sync (``from_date``/``to_date``) to async
  // (``start``/``end``) at the API boundary only (N1).
  useEffect(() => {
    if (!candlesRequest) {
      // Synthetic mode (or unhydrated): no chart panel.
      // setState-in-effect: intentional — clears any prior chart when
      // the user switches back to synthetic via the re-run dialog so a
      // stale panel doesn't flash old values.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setChartRun(null);
      return;
    }
    // Unmount any prior chart while the new run enqueues — prevents a
    // stale panel from flashing values from the previous candlesRequest.
    setChartRun(null);
    let cancelled = false;
    (async () => {
      try {
        const enqueue = await api.post<{
          run_id: string;
          status: string;
          cached: boolean;
        }>("/backtest", {
          strategy_id: id,
          symbol: candlesRequest.symbol,
          timeframe: candlesRequest.timeframe,
          start: candlesRequest.from_date,
          end: candlesRequest.to_date,
          initial_capital: 100000,
          quantity: 1,
        });
        if (cancelled) return;
        const snapshot = {
          runId: enqueue.run_id,
          symbol: candlesRequest.symbol,
          timeframe: candlesRequest.timeframe,
        };
        // Cache-hit short-circuit: Queue CC+DD returns 200 + status=
        // SUCCEEDED when the (user_id, request_hash) row already exists.
        if (enqueue.status === "SUCCEEDED") {
          setChartRun(snapshot);
          return;
        }
        // Poll until SUCCEEDED — ~1s interval, capped at 60 attempts
        // (worst-case 1 min wait; sync POST runs alongside on its own
        // timeline so the user sees the 8 panels well before this).
        for (let i = 0; i < 60; i++) {
          if (cancelled) return;
          const status = await api.get<{ status: string }>(
            `/backtest/${enqueue.run_id}`,
          );
          if (cancelled) return;
          if (status.status === "SUCCEEDED") {
            setChartRun(snapshot);
            return;
          }
          if (status.status === "FAILED") {
            // No markers for a failed run — leave chartRun null so the
            // panel never mounts.
            return;
          }
          await new Promise((r) => setTimeout(r, 1000));
        }
      } catch {
        // Existing sync panels are unaffected — silently swallow so
        // the page doesn't lose its primary surface. BacktestChartPanel
        // simply never mounts.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [candlesRequest, id]);

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <Link
            href="/strategies"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to strategies
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <PlayCircle className="h-6 w-6 text-accent-blue" />
            Backtest result
          </h1>
          <p className="text-xs text-muted-foreground font-mono">{id}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {data ? (
            <Badge
              className={cn(
                "text-[10px] gap-1",
                data.candles_source === "dhan_historical"
                  ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30"
                  : "bg-white/[0.06] text-muted-foreground border-white/[0.1]",
              )}
            >
              {data.candles_source === "dhan_historical"
                ? "Real Dhan data"
                : "Synthetic"}
            </Badge>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={() => setPickerOpen(true)}
            disabled={isLoading}
          >
            Re-run with different data
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={runBacktest}
            disabled={isLoading}
            type="button"
          >
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
            Re-run
          </Button>
        </div>
      </motion.div>

      <RerunWithDifferentDataDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        currentRequest={candlesRequest}
        onApply={(req) => {
          setCandlesRequest(req);
          setPickerOpen(false);
        }}
      />

      {error && !data ? (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="text-center py-10">
              <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Backtest failed</h3>
              <p className="text-sm text-muted-foreground mb-4">{error}</p>
              <GlowButton size="sm" onClick={runBacktest}>
                Retry
              </GlowButton>
            </div>
          </GlassmorphismCard>
        </motion.div>
      ) : isLoading && !data ? (
        <LoadingSkeleton />
      ) : data ? (
        <>
          <motion.div variants={fadeUp}>
            <BacktestResultPanel result={data.backtest} />
          </motion.div>

          {/* Milestone 3 (Queue EE/FF) — chart with trade markers from
              the parallel async backtest. Only mounts in dhan_historical
              mode (synthetic has no candles_request → no chart). */}
          {chartRun ? (
            <motion.div variants={fadeUp}>
              <BacktestChartPanel
                runId={chartRun.runId}
                strategyId={id}
                symbol={chartRun.symbol}
                timeframe={chartRun.timeframe}
              />
            </motion.div>
          ) : null}

          <motion.div variants={fadeUp}>
            <StrategyCoachCard card={data.health_card} />
          </motion.div>

          <motion.div
            // Bumping the key on each new (data, isDoubleA) signature
            // remounts the panel row, which retriggers the
            // ``celebrate-sustained`` CSS keyframe without any React
            // state — keeps us out of the set-state-in-effect rule.
            key={`reliability-${dataSignature}`}
            variants={fadeUp}
            className={cn(
              "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 rounded-xl",
              isDoubleA && "celebrate-sustained",
            )}
          >
            <TrustPanelPreview reliability={data.reliability} />
            <StrategyTruthPanel report={data.truth} />
            <MarketRegimePanel regime={data.regime} />
          </motion.div>

          <motion.div variants={fadeUp}>
            <TradeQualityCard report={data.trade_quality} />
          </motion.div>

          <motion.div variants={fadeUp}>
            <AIDoctorCard diagnosis={data.diagnosis} strategyId={id} />
          </motion.div>

          <motion.div variants={fadeUp}>
            <DeviationMonitorPanel deviation={data.deviation} />
          </motion.div>
        </>
      ) : null}
    </motion.div>
  );
}


// ─── Loading skeleton ────────────────────────────────────────────────


function LoadingSkeleton() {
  return (
    <motion.div variants={fadeUp} className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <GlassmorphismCard key={i} hover={false} className="!p-3">
            <div className="animate-pulse space-y-2">
              <div className="h-2 w-2/3 bg-white/[0.05] rounded" />
              <div className="h-5 w-3/4 bg-white/[0.05] rounded" />
            </div>
          </GlassmorphismCard>
        ))}
      </div>
      <GlassmorphismCard hover={false}>
        <div className="animate-pulse h-64 bg-white/[0.03] rounded" />
      </GlassmorphismCard>
      <GlassmorphismCard hover={false}>
        <div className="animate-pulse space-y-3">
          <div className="h-5 w-1/3 bg-white/[0.05] rounded" />
          <div className="h-3 w-2/3 bg-white/[0.04] rounded" />
          <div className="h-3 w-1/2 bg-white/[0.04] rounded" />
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}


// ─── Trust panel preview (uses ReliabilityReport from response) ──────


function TrustPanelPreview({
  reliability,
}: {
  reliability: ReliabilityPayload | null;
}) {
  if (reliability === null) {
    return (
      <GlassmorphismCard hover={false}>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <ShieldQuestion className="h-4 w-4 text-muted-foreground" />
            <h3 className="font-semibold text-sm">Reliability</h3>
          </div>
          <p className="text-xs text-muted-foreground">
            Reliability analysis was skipped for this run.
          </p>
        </div>
      </GlassmorphismCard>
    );
  }
  const trust = reliability.trust_score;
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <ShieldCheck
            className={cn(
              "h-4 w-4",
              trust.score >= 70
                ? "text-profit"
                : trust.score >= 55
                  ? "text-accent-blue"
                  : "text-loss",
            )}
          />
          <h3 className="font-semibold text-sm">Reliability</h3>
          <Badge
            className={cn(
              "ml-auto gap-1",
              trust.score >= 70
                ? "bg-profit/15 text-profit border-profit/30"
                : trust.score >= 55
                  ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30"
                  : "bg-loss/15 text-loss border-loss/30",
            )}
          >
            Trust {trust.score}/100 · {trust.grade}
          </Badge>
        </div>
        <p className="text-xs leading-relaxed">{trust.verdict}</p>
        <div className="grid grid-cols-3 gap-2 text-[11px]">
          <SubMetric
            label="OOS"
            value={
              reliability.out_of_sample
                ? `${(reliability.out_of_sample.degradation_percent * 100).toFixed(1)}%`
                : "—"
            }
          />
          <SubMetric
            label="Walk-fwd"
            value={
              reliability.walk_forward
                ? `${reliability.walk_forward.consistency_score.toFixed(0)}%`
                : "—"
            }
          />
          <SubMetric
            label="Sensitivity"
            value={
              reliability.sensitivity
                ? reliability.sensitivity.fragile
                  ? "Fragile"
                  : "Robust"
                : "Skipped"
            }
          />
        </div>
        {trust.warnings.length > 0 ? (
          <div className="text-[11px] text-muted-foreground space-y-0.5 pt-1">
            {trust.warnings.slice(0, 2).map((w, i) => (
              <p key={i} className="leading-snug">
                • {w}
              </p>
            ))}
          </div>
        ) : null}
      </div>
    </GlassmorphismCard>
  );
}


function SubMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-white/[0.02] border border-white/[0.04] px-2 py-1.5">
      <div className="text-[10px] text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div className="text-xs font-medium tabular-nums">{value}</div>
    </div>
  );
}


// ─── Re-run dialog: swap the candle source mid-page ──────────────────


function RerunWithDifferentDataDialog({
  open,
  onOpenChange,
  currentRequest,
  onApply,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentRequest: CandlesRequestPayload | null;
  onApply: (request: CandlesRequestPayload | null) => void;
}) {
  // Seed the picker with whatever the page is currently using so the
  // dialog opens on the user's last choice rather than the default.
  const [picker, setPicker] = useState<CandleSourcePickerValue>(() => ({
    source: currentRequest ? "dhan_historical" : "synthetic",
    candles_request: currentRequest,
    validation_error: "",
  }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Re-run with different data</DialogTitle>
        </DialogHeader>
        <CandleSourcePicker value={picker} onChange={setPicker} compactHint />
        <div className="flex items-center justify-end gap-2 pt-2">
          <Button
            variant="outline"
            type="button"
            onClick={() => {
              setPicker(makeDefaultPickerValue("synthetic"));
              onOpenChange(false);
            }}
          >
            Cancel
          </Button>
          <GlowButton
            onClick={() =>
              onApply(
                picker.source === "dhan_historical"
                  ? picker.candles_request
                  : null,
              )
            }
            disabled={
              picker.validation_error !== ""
              || (picker.source === "dhan_historical" && !picker.candles_request)
            }
          >
            Apply & re-run
          </GlowButton>
        </div>
      </DialogContent>
    </Dialog>
  );
}


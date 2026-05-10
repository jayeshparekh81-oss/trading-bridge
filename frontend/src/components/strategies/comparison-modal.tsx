"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { GlowButton } from "@/components/ui/glow-button";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Wire shape from ``POST /api/strategies/{id}/compare-fix``. Each
 * snapshot mirrors a subset of the ``BacktestRunResponse`` shape;
 * camelCase aliases on backtest / truth, snake_case on coach +
 * trade_quality (the Phase 7 advisor models have no aliases).
 */

interface BacktestSnapshotPayload {
  totalPnl: number;
  totalReturnPercent: number;
  winRate: number;
  totalTrades: number;
  maxDrawdown: number;
  profitFactor: number;
}

interface ReliabilityShape {
  trust_score: { score: number; grade: string };
}

interface TruthShape {
  truthScore: number;
  grade: string;
}

interface TradeQualityShape {
  overall_score: number;
  grade: string;
}

interface SnapshotPayload {
  backtest: BacktestSnapshotPayload;
  reliability: ReliabilityShape | null;
  truth: TruthShape | null;
  trade_quality: TradeQualityShape | null;
}

export interface CompareFixResponsePayload {
  original: SnapshotPayload;
  improved: SnapshotPayload;
  comparison: {
    pnl_delta: number;
    win_rate_delta: number;
    drawdown_delta: number;
    profit_factor_delta: number;
    truth_score_delta: number;
    trust_score_delta: number;
    trade_quality_delta: number;
    verdict_hinglish: string;
  };
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  comparison: CompareFixResponsePayload;
  improvedDraft: Record<string, unknown>;
}

export function ComparisonModal({
  open,
  onOpenChange,
  comparison,
  improvedDraft,
}: Props) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const verdict = comparison.comparison.verdict_hinglish;
  const verdictTier = classifyVerdict(comparison.comparison);

  const onSave = async () => {
    setSaving(true);
    try {
      const created = await api.post<{ id: string }>("/strategies", {
        strategy_json: improvedDraft,
      });
      toast.success("Improved strategy saved 🎉");
      router.push(`/strategies/${created.id}/backtest`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Saving the improved strategy failed.";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Apply fix and compare</DialogTitle>
        </DialogHeader>

        <VerdictBanner verdict={verdict} tier={verdictTier} />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <SnapshotColumn
            title="Original"
            snapshot={comparison.original}
            tone="neutral"
          />
          <SnapshotColumn
            title="Improved"
            snapshot={comparison.improved}
            tone="accent"
          />
        </div>

        <DeltaTable comparison={comparison.comparison} />

        <div className="flex items-center justify-end gap-2 pt-2">
          <Button
            variant="outline"
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Discard
          </Button>
          <GlowButton onClick={onSave} disabled={saving}>
            {saving ? "Saving..." : "Save Improved as New Strategy"}
          </GlowButton>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Verdict banner ────────────────────────────────────────────────────

type VerdictTier = "win" | "mixed" | "loss";

function classifyVerdict(c: CompareFixResponsePayload["comparison"]): VerdictTier {
  let improved = 0;
  if (c.pnl_delta > 0) improved += 1;
  if (c.win_rate_delta > 0) improved += 1;
  if (c.drawdown_delta < 0) improved += 1;
  if (c.profit_factor_delta > 0) improved += 1;
  if (c.truth_score_delta > 0) improved += 1;
  if (c.trust_score_delta > 0) improved += 1;
  if (c.trade_quality_delta > 0) improved += 1;
  if (improved >= 5) return "win";
  if (improved >= 3) return "mixed";
  return "loss";
}

function VerdictBanner({
  verdict,
  tier,
}: {
  verdict: string;
  tier: VerdictTier;
}) {
  const styles = {
    win: {
      border: "border-profit/40",
      bg: "bg-profit/[0.08]",
      text: "text-profit",
      emoji: "🎉🎉🎉",
      emojiLabel: "Three party poppers — improved version is a clear win",
    },
    mixed: {
      border: "border-yellow-500/40",
      bg: "bg-yellow-500/[0.08]",
      text: "text-yellow-200",
      emoji: "🤔",
      emojiLabel: "Thinking face — mixed comparison results",
    },
    loss: {
      border: "border-loss/40",
      bg: "bg-loss/[0.08]",
      text: "text-loss",
      emoji: "⚠️",
      emojiLabel: "Warning — improved version is worse than original",
    },
  }[tier];
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-md border p-3",
        styles.border,
        styles.bg,
      )}
    >
      <span
        className="text-xl leading-none"
        aria-label={styles.emojiLabel}
        role="img"
      >
        {styles.emoji}
      </span>
      <p className={cn("text-sm font-medium", styles.text)}>{verdict}</p>
    </div>
  );
}

// ─── Snapshot column ───────────────────────────────────────────────────

function SnapshotColumn({
  title,
  snapshot,
  tone,
}: {
  title: string;
  snapshot: SnapshotPayload;
  tone: "neutral" | "accent";
}) {
  return (
    <div
      className={cn(
        "rounded-md border p-3 space-y-2",
        tone === "accent"
          ? "border-accent-blue/30 bg-accent-blue/[0.04]"
          : "border-white/[0.08] bg-white/[0.02]",
      )}
    >
      <h4
        className={cn(
          "text-xs font-semibold uppercase tracking-wide",
          tone === "accent" ? "text-accent-blue" : "text-muted-foreground",
        )}
      >
        {title}
      </h4>
      <SnapshotMetric label="P&L" value={`₹${snapshot.backtest.totalPnl.toFixed(2)}`} />
      <SnapshotMetric
        label="Return"
        value={`${snapshot.backtest.totalReturnPercent.toFixed(2)}%`}
      />
      <SnapshotMetric
        label="Win Rate"
        value={`${(snapshot.backtest.winRate * 100).toFixed(1)}%`}
      />
      <SnapshotMetric
        label="Drawdown"
        value={`${(snapshot.backtest.maxDrawdown * 100).toFixed(1)}%`}
      />
      <SnapshotMetric
        label="Profit Factor"
        value={snapshot.backtest.profitFactor.toFixed(2)}
      />
      {snapshot.truth ? (
        <SnapshotMetric
          label="Truth Score"
          value={`${snapshot.truth.truthScore} (${snapshot.truth.grade})`}
        />
      ) : null}
      {snapshot.reliability ? (
        <SnapshotMetric
          label="Trust Score"
          value={`${snapshot.reliability.trust_score.score} (${snapshot.reliability.trust_score.grade})`}
        />
      ) : null}
      {snapshot.trade_quality ? (
        <SnapshotMetric
          label="Trade Quality"
          value={`${snapshot.trade_quality.overall_score.toFixed(0)} (${snapshot.trade_quality.grade})`}
        />
      ) : null}
    </div>
  );
}

function SnapshotMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-[12px]">
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular-nums font-medium">{value}</span>
    </div>
  );
}

// ─── Delta table ───────────────────────────────────────────────────────

function DeltaTable({
  comparison,
}: {
  comparison: CompareFixResponsePayload["comparison"];
}) {
  return (
    <div className="rounded-md border border-white/[0.08] bg-white/[0.02] p-3 space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Deltas (improved − original)
      </h4>
      <DeltaRow label="P&L" value={comparison.pnl_delta} format={(v) => `₹${v.toFixed(2)}`} biggerIsBetter />
      <DeltaRow
        label="Win Rate"
        value={comparison.win_rate_delta}
        format={(v) => `${(v * 100).toFixed(1)}pp`}
        biggerIsBetter
      />
      <DeltaRow
        label="Drawdown"
        value={comparison.drawdown_delta}
        format={(v) => `${(v * 100).toFixed(1)}pp`}
        biggerIsBetter={false}
      />
      <DeltaRow
        label="Profit Factor"
        value={comparison.profit_factor_delta}
        format={(v) => v.toFixed(2)}
        biggerIsBetter
      />
      <DeltaRow
        label="Truth Score"
        value={comparison.truth_score_delta}
        format={(v) => v.toFixed(1)}
        biggerIsBetter
      />
      <DeltaRow
        label="Trust Score"
        value={comparison.trust_score_delta}
        format={(v) => v.toFixed(1)}
        biggerIsBetter
      />
      <DeltaRow
        label="Trade Quality"
        value={comparison.trade_quality_delta}
        format={(v) => v.toFixed(1)}
        biggerIsBetter
      />
    </div>
  );
}

function DeltaRow({
  label,
  value,
  format,
  biggerIsBetter,
}: {
  label: string;
  value: number;
  format: (v: number) => string;
  biggerIsBetter: boolean;
}) {
  let tone: "good" | "bad" | "neutral";
  let Icon: React.ComponentType<{ className?: string }>;
  if (Math.abs(value) < 1e-9) {
    tone = "neutral";
    Icon = Minus;
  } else {
    const positive = value > 0;
    const isGood = biggerIsBetter ? positive : !positive;
    tone = isGood ? "good" : "bad";
    Icon = positive ? ArrowUpRight : ArrowDownRight;
  }
  const colorMap = {
    good: "text-profit",
    bad: "text-loss",
    neutral: "text-muted-foreground",
  };
  const sign = value > 0 ? "+" : "";
  return (
    <div className="flex items-center justify-between text-[12px]">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={cn(
          "inline-flex items-center gap-1 tabular-nums font-medium",
          colorMap[tone],
        )}
      >
        <Icon className="h-3 w-3" />
        {sign}
        {format(value)}
      </span>
    </div>
  );
}

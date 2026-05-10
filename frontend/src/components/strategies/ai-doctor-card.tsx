"use client";

import { useCallback, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info,
  Wand2,
  XCircle,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { GlowButton } from "@/components/ui/glow-button";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ComparisonModal,
  type CompareFixResponsePayload,
} from "./comparison-modal";

/**
 * Wire shape from ``POST /api/strategies/{id}/backtest``'s
 * ``diagnosis`` section — the Phase 7 :class:`Diagnosis`. The model
 * uses ``populate_by_name=True`` with camelCase aliases, so keys
 * arrive in camelCase here.
 */
export type DoctorSeverity = "info" | "warning" | "critical";
export type ProblemType =
  | "entry"
  | "exit"
  | "risk"
  | "overfit"
  | "cost"
  | "regime"
  | "complexity";

export interface DoctorProblemPayload {
  type: ProblemType;
  severity: DoctorSeverity;
  message: string;
  suggestedFix: string;
  autoFixAvailable: boolean;
}

export interface DiagnosisPayload {
  diagnosisSummary: string;
  problems: DoctorProblemPayload[];
  recommendedFixes: string[];
  canAutoImprove: boolean;
  improvedStrategyDraft: Record<string, unknown> | null;
}

interface Props {
  /** Diagnosis report; ``null`` only on legacy responses. */
  diagnosis: DiagnosisPayload | null;
  /** Strategy id used to call ``POST /strategies/{id}/compare-fix``. */
  strategyId: string;
}

export function AIDoctorCard({ diagnosis, strategyId }: Props) {
  const [comparing, setComparing] = useState(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<CompareFixResponsePayload | null>(
    null,
  );
  const [draftOpen, setDraftOpen] = useState(false);

  const runComparison = useCallback(async () => {
    if (!diagnosis?.improvedStrategyDraft) return;
    setComparing(true);
    setComparisonError(null);
    try {
      const result = await api.post<CompareFixResponsePayload>(
        `/strategies/${strategyId}/compare-fix`,
        { improved_strategy_draft: diagnosis.improvedStrategyDraft },
      );
      setComparison(result);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Comparing the proposed fix failed.";
      setComparisonError(msg);
    } finally {
      setComparing(false);
    }
  }, [diagnosis, strategyId]);

  if (diagnosis === null) {
    return <UnavailableState />;
  }

  const hasProblems = diagnosis.problems.length > 0;

  return (
    <>
      <GlassmorphismCard hover={false}>
        <div className="space-y-4">
          <Header />
          <p className="text-base leading-snug">
            {diagnosis.diagnosisSummary || "No issues detected."}
          </p>

          {hasProblems ? (
            <ProblemList problems={diagnosis.problems} />
          ) : (
            <CleanState />
          )}

          {diagnosis.recommendedFixes.length > 0 ? (
            <RecommendedFixes fixes={diagnosis.recommendedFixes} />
          ) : null}

          {diagnosis.canAutoImprove && diagnosis.improvedStrategyDraft ? (
            <AutoFixSection
              comparing={comparing}
              comparisonError={comparisonError}
              onApplyFix={runComparison}
              draftOpen={draftOpen}
              onToggleDraft={() => setDraftOpen((v) => !v)}
              draft={diagnosis.improvedStrategyDraft}
            />
          ) : null}
        </div>
      </GlassmorphismCard>

      {comparison ? (
        <ComparisonModal
          open={comparison !== null}
          onOpenChange={(open) => {
            if (!open) setComparison(null);
          }}
          comparison={comparison}
          improvedDraft={diagnosis.improvedStrategyDraft ?? {}}
        />
      ) : null}
    </>
  );
}

// ─── Header ────────────────────────────────────────────────────────────

function Header() {
  return (
    <div className="flex items-start justify-between gap-3 flex-wrap">
      <div className="flex items-center gap-2">
        <span
          className="text-xl leading-none"
          aria-label="Stethoscope — AI Doctor diagnosis"
          role="img"
        >
          🩺
        </span>
        <div>
          <h3 className="font-semibold text-sm">AI Doctor Diagnosis</h3>
          <p className="text-[11px] text-muted-foreground">
            Phase 7 deterministic strategy doctor.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Clean state (no problems) ─────────────────────────────────────────

function CleanState() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-profit/30 bg-profit/[0.05] p-2.5">
      <CheckCircle2 className="h-4 w-4 text-profit" />
      <span className="text-xs">
        Doctor ne koi major issue detect nahi kiya.
      </span>
    </div>
  );
}

function UnavailableState() {
  return (
    <GlassmorphismCard hover={false} className="opacity-70">
      <div className="space-y-2">
        <h3 className="font-semibold text-sm">AI Doctor Diagnosis</h3>
        <p className="text-xs text-muted-foreground">
          Doctor diagnosis unavailable for this run.
        </p>
      </div>
    </GlassmorphismCard>
  );
}

// ─── Problem list ──────────────────────────────────────────────────────

function ProblemList({ problems }: { problems: DoctorProblemPayload[] }) {
  return (
    <div className="space-y-2">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Detected problems
      </h4>
      <div className="space-y-2">
        {problems.map((p, idx) => (
          <ProblemRow key={idx} problem={p} />
        ))}
      </div>
    </div>
  );
}

function ProblemRow({ problem }: { problem: DoctorProblemPayload }) {
  const tone = severityTone(problem.severity);
  const Icon = tone.icon;
  return (
    <div
      className={cn(
        "rounded-md border p-3 space-y-1.5",
        tone.cardBorder,
        tone.cardBg,
      )}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <Icon className={cn("h-4 w-4 shrink-0", tone.text)} />
        <Badge className={cn("text-[10px] px-2 py-0.5", tone.badge)}>
          {problem.severity.toUpperCase()}
        </Badge>
        <Badge className="text-[10px] px-2 py-0.5 bg-white/[0.06] border-white/[0.1]">
          {problem.type}
        </Badge>
        {problem.autoFixAvailable ? (
          <Badge className="text-[10px] px-2 py-0.5 bg-accent-blue/15 text-accent-blue border-accent-blue/30 gap-1">
            <Wand2 className="h-3 w-3" />
            auto-fix
          </Badge>
        ) : null}
      </div>
      <p className="text-[13px] leading-snug">{problem.message}</p>
      <p className="text-[12px] italic text-muted-foreground leading-snug">
        Fix: {problem.suggestedFix}
      </p>
    </div>
  );
}

// ─── Recommended fixes ─────────────────────────────────────────────────

function RecommendedFixes({ fixes }: { fixes: string[] }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Recommended fixes
      </h4>
      <ol className="space-y-1 list-decimal list-inside marker:text-muted-foreground">
        {fixes.map((fix, idx) => (
          <li key={idx} className="text-[12px] leading-snug">
            {fix}
          </li>
        ))}
      </ol>
    </div>
  );
}

// ─── Auto-fix section ──────────────────────────────────────────────────

function AutoFixSection({
  comparing,
  comparisonError,
  onApplyFix,
  draftOpen,
  onToggleDraft,
  draft,
}: {
  comparing: boolean;
  comparisonError: string | null;
  onApplyFix: () => void;
  draftOpen: boolean;
  onToggleDraft: () => void;
  draft: Record<string, unknown>;
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <GlowButton size="sm" onClick={onApplyFix} disabled={comparing}>
          <Wand2 className="h-4 w-4" />
          {comparing ? "Comparing..." : "Apply Fix and Compare"}
        </GlowButton>
        <Button
          variant="outline"
          size="sm"
          type="button"
          onClick={onToggleDraft}
          aria-expanded={draftOpen}
        >
          {draftOpen ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
          {draftOpen ? "Hide draft" : "View proposed draft"}
        </Button>
      </div>
      {comparisonError ? (
        <div className="rounded-md border border-loss/30 bg-loss/[0.06] p-2.5 text-xs text-loss">
          {comparisonError}
        </div>
      ) : null}
      {draftOpen ? (
        <pre className="rounded-md border border-white/[0.06] bg-black/40 p-3 text-[11px] leading-snug overflow-x-auto max-h-64">
          {JSON.stringify(draft, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

// ─── Tones ─────────────────────────────────────────────────────────────

interface SeverityTone {
  icon: React.ComponentType<{ className?: string }>;
  badge: string;
  text: string;
  cardBorder: string;
  cardBg: string;
}

function severityTone(severity: DoctorSeverity): SeverityTone {
  switch (severity) {
    case "info":
      return {
        icon: Info,
        badge: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
        text: "text-accent-blue",
        cardBorder: "border-accent-blue/20",
        cardBg: "bg-accent-blue/[0.04]",
      };
    case "warning":
      return {
        icon: AlertTriangle,
        badge: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
        text: "text-yellow-200",
        cardBorder: "border-yellow-500/20",
        cardBg: "bg-yellow-500/[0.04]",
      };
    case "critical":
      return {
        icon: XCircle,
        badge: "bg-loss/15 text-loss border-loss/30",
        text: "text-loss",
        cardBorder: "border-loss/30",
        cardBg: "bg-loss/[0.05]",
      };
  }
}


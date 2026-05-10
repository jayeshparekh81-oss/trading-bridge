"use client";

import { useState } from "react";
import {
  ScanSearch,
  ThumbsUp,
  ThumbsDown,
  ListChecks,
  ShieldAlert,
  FlaskConical,
  Activity,
  TrendingDown,
  Minus,
  Lightbulb,
  ChevronDown,
  ChevronUp,
  Microscope,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  TruthDrillDownModal,
  type DrillDownWarning,
  type WarningBucketId,
} from "./truth-drill-down-modal";
import { WarningEvidenceCard } from "./warning-evidence-card";

/**
 * Wire shape from ``POST /api/strategies/{id}/backtest``'s ``truth``
 * section — the Phase 6 :class:`TruthReport`. Pydantic serialises with
 * camelCase aliases (``response_model_by_alias=True`` on the endpoint),
 * so the keys arrive in this exact form.
 */
export type TruthGrade = "A" | "B" | "C" | "D" | "F";
export type TruthRiskLevel = "low" | "medium" | "high" | "extreme";

export interface TruthReportPayload {
  truthScore: number;
  grade: TruthGrade;
  verdict: string;
  riskLevel: TruthRiskLevel;
  fakeBacktestWarnings: string[];
  overfittingWarnings: string[];
  executionWarnings: string[];
  costWarnings: string[];
  strengths: string[];
  weaknesses: string[];
  recommendedNextActions: string[];
}


interface Props {
  /** Truth report; ``null`` when reliability was opted out of. */
  report: TruthReportPayload | null;
}


export function StrategyTruthPanel({ report }: Props) {
  if (report === null) {
    return (
      <GlassmorphismCard hover={false}>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <ScanSearch className="h-4 w-4 text-muted-foreground" />
            <h3 className="font-semibold text-sm">Strategy Truth</h3>
            <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06]">
              Skipped (no reliability)
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Truth score reliability report ke upar build hoti hai. Yeh run
            ``include_reliability: false`` ke saath chala tha, isliye Truth
            engine skip ho gayi.
          </p>
        </div>
      </GlassmorphismCard>
    );
  }

  const totalWarnings =
    report.fakeBacktestWarnings.length +
    report.overfittingWarnings.length +
    report.executionWarnings.length +
    report.costWarnings.length;

  return (
    <GlassmorphismCard hover={false} glow={glowFromRisk(report.riskLevel)}>
      <div className="space-y-5">
        <Header report={report} />
        {totalWarnings > 0 ? <WarningBuckets report={report} /> : null}
        {totalWarnings > 0 ? (
          <DrillDownSection report={report} />
        ) : null}
        {(report.strengths.length + report.weaknesses.length) > 0 ? (
          <StrengthsWeaknesses
            strengths={report.strengths}
            weaknesses={report.weaknesses}
          />
        ) : null}
        {report.recommendedNextActions.length > 0 ? (
          <NextActions actions={report.recommendedNextActions} />
        ) : null}
      </div>
    </GlassmorphismCard>
  );
}


// ─── Drill-Down section — additive surface over the existing buckets ──


function DrillDownSection({ report }: { report: TruthReportPayload }) {
  const [expanded, setExpanded] = useState(false);
  const [activeWarning, setActiveWarning] = useState<DrillDownWarning | null>(
    null,
  );

  // Flatten the four buckets into one ordered list, preserving the
  // existing severity gradient (fake/overfit/execution/cost). Each
  // entry carries its bucket id so the drill-down modal can render
  // the right Hinglish frame.
  const flat: DrillDownWarning[] = [
    ...report.fakeBacktestWarnings.map(toWarning("fake_backtest")),
    ...report.overfittingWarnings.map(toWarning("overfitting")),
    ...report.executionWarnings.map(toWarning("execution")),
    ...report.costWarnings.map(toWarning("cost")),
  ];

  return (
    <section className="space-y-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setExpanded((v) => !v)}
        type="button"
        className="w-full justify-between"
      >
        <span className="inline-flex items-center gap-1.5 text-xs uppercase tracking-wide font-medium">
          <Microscope className="h-3.5 w-3.5 text-accent-blue" />
          Detailed warnings · drill-down
          <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
            {flat.length}
          </Badge>
        </span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
      </Button>

      {expanded ? (
        <div className="space-y-2">
          {flat.length === 0 ? (
            <p className="text-[11px] text-muted-foreground italic">
              Koi flagged warnings nahi — strategy clean dikh rahi hai.
            </p>
          ) : (
            flat.map((w, idx) => (
              <WarningEvidenceCard
                key={`${w.bucket}-${idx}`}
                bucket={w.bucket}
                message={w.message}
                onOpen={setActiveWarning}
              />
            ))
          )}
        </div>
      ) : null}

      <TruthDrillDownModal
        open={activeWarning !== null}
        onOpenChange={(open) => {
          if (!open) setActiveWarning(null);
        }}
        warning={activeWarning}
        recommendedNextActions={report.recommendedNextActions}
      />
    </section>
  );
}


function toWarning(
  bucket: WarningBucketId,
): (msg: string) => DrillDownWarning {
  return (msg) => ({ bucket, message: msg });
}


// ─── Header (score + grade + verdict + risk badge) ─────────────────────


function Header({ report }: { report: TruthReportPayload }) {
  const tone = riskTone(report.riskLevel);
  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <ScanSearch className={cn("h-5 w-5", tone.text)} />
          <div>
            <h3 className="font-semibold text-sm flex items-center gap-2">
              Strategy Truth
              <Badge
                className={cn("uppercase text-[10px] gap-1", tone.badge)}
              >
                {report.riskLevel} risk
              </Badge>
            </h3>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Phase 6 deterministic truth engine — fake-backtest detection.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={cn("gap-1", tone.badge)}>
            Truth {report.truthScore}/100 · {report.grade}
          </Badge>
        </div>
      </div>
      <p className={cn("text-sm font-medium leading-snug", tone.text)}>
        {report.verdict}
      </p>
      {/* Score bar */}
      <div className="space-y-1">
        <div className="h-2 w-full rounded-full bg-white/[0.06] overflow-hidden">
          <div
            className={cn("h-full rounded-full transition-all", tone.bar)}
            style={{ width: `${Math.max(0, Math.min(100, report.truthScore))}%` }}
            aria-label={`Truth score ${report.truthScore} out of 100`}
          />
        </div>
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span>0</span>
          <span>50</span>
          <span>100</span>
        </div>
      </div>
    </div>
  );
}


// ─── Warning buckets — fake / overfit / exec / cost ────────────────────


function WarningBuckets({ report }: { report: TruthReportPayload }) {
  return (
    <div className="space-y-3">
      <h4 className="text-xs uppercase tracking-wide text-muted-foreground font-medium">
        Warnings
      </h4>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <Bucket
          icon={<ShieldAlert className="h-3.5 w-3.5 text-loss" />}
          title="Fake-backtest"
          tone="loss"
          items={report.fakeBacktestWarnings}
        />
        <Bucket
          icon={<FlaskConical className="h-3.5 w-3.5 text-loss" />}
          title="Overfitting"
          tone="loss"
          items={report.overfittingWarnings}
        />
        <Bucket
          icon={<Activity className="h-3.5 w-3.5 text-yellow-300" />}
          title="Execution"
          tone="yellow"
          items={report.executionWarnings}
        />
        <Bucket
          icon={<TrendingDown className="h-3.5 w-3.5 text-yellow-300" />}
          title="Cost impact"
          tone="yellow"
          items={report.costWarnings}
        />
      </div>
    </div>
  );
}


function Bucket({
  icon,
  title,
  tone,
  items,
}: {
  icon: React.ReactNode;
  title: string;
  tone: "loss" | "yellow";
  items: string[];
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3">
        <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
          {icon}
          {title}
        </div>
        <p className="text-[11px] text-muted-foreground/70 mt-1 italic">
          No warnings.
        </p>
      </div>
    );
  }
  const borderTone =
    tone === "loss"
      ? "border-loss/30 bg-loss/[0.05]"
      : "border-yellow-500/30 bg-yellow-500/[0.05]";
  return (
    <div className={cn("rounded-md border p-3 space-y-1.5", borderTone)}>
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
        <span className="ml-auto font-mono text-[10px]">×{items.length}</span>
      </div>
      <ul className="space-y-1">
        {items.map((msg, idx) => (
          <li key={idx} className="text-[11px] leading-snug">
            • {msg}
          </li>
        ))}
      </ul>
    </div>
  );
}


// ─── Strengths + weaknesses (two columns) ──────────────────────────────


function StrengthsWeaknesses({
  strengths,
  weaknesses,
}: {
  strengths: string[];
  weaknesses: string[];
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <BulletList
        icon={<ThumbsUp className="h-3.5 w-3.5 text-profit" />}
        title="Strengths"
        accent="profit"
        items={strengths}
        emptyMessage="No standout strengths flagged."
        marker={<Plus />}
      />
      <BulletList
        icon={<ThumbsDown className="h-3.5 w-3.5 text-loss" />}
        title="Weaknesses"
        accent="loss"
        items={weaknesses}
        emptyMessage="No weaknesses flagged."
        marker={<MinusBullet />}
      />
    </div>
  );
}


function BulletList({
  icon,
  title,
  accent,
  items,
  emptyMessage,
  marker,
}: {
  icon: React.ReactNode;
  title: string;
  accent: "profit" | "loss";
  items: string[];
  emptyMessage: string;
  marker: React.ReactNode;
}) {
  return (
    <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3 space-y-2">
      <div className="flex items-center gap-1.5">
        {icon}
        <h4 className="text-xs uppercase tracking-wide text-muted-foreground font-medium">
          {title}
        </h4>
      </div>
      {items.length === 0 ? (
        <p className="text-[11px] text-muted-foreground/70 italic">
          {emptyMessage}
        </p>
      ) : (
        <ul className="space-y-1">
          {items.map((msg, idx) => (
            <li
              key={idx}
              className="text-[11px] leading-snug flex items-start gap-1.5"
            >
              <span
                className={cn(
                  "mt-0.5 shrink-0",
                  accent === "profit" ? "text-profit" : "text-loss",
                )}
              >
                {marker}
              </span>
              <span>{msg}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


function Plus() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      <path d="M5 1v8M1 5h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}


function MinusBullet() {
  return <Minus className="h-2.5 w-2.5" />;
}


// ─── Recommended next actions ──────────────────────────────────────────


function NextActions({ actions }: { actions: string[] }) {
  return (
    <div className="space-y-2 rounded-md bg-accent-blue/[0.04] border border-accent-blue/20 p-3">
      <div className="flex items-center gap-1.5">
        <Lightbulb className="h-3.5 w-3.5 text-accent-blue" />
        <h4 className="text-xs uppercase tracking-wide text-accent-blue font-medium">
          Recommended next actions
        </h4>
      </div>
      <ol className="space-y-1.5">
        {actions.map((msg, idx) => (
          <li
            key={idx}
            className="text-[11px] leading-snug flex items-start gap-2"
          >
            <span className="shrink-0 size-4 rounded-full bg-accent-blue/15 text-accent-blue text-[10px] font-semibold grid place-items-center">
              {idx + 1}
            </span>
            <span>{msg}</span>
          </li>
        ))}
      </ol>
      <p className="text-[10px] text-muted-foreground italic flex items-center gap-1 pt-1">
        <ListChecks className="h-3 w-3" />
        Walk down the list — fix the top item first, then re-run backtest.
      </p>
    </div>
  );
}


// ─── Risk-level styling ────────────────────────────────────────────────


interface RiskTone {
  text: string;
  badge: string;
  bar: string;
}

function riskTone(level: TruthRiskLevel): RiskTone {
  switch (level) {
    case "low":
      return {
        text: "text-profit",
        badge: "bg-profit/15 text-profit border-profit/30",
        bar: "bg-profit",
      };
    case "medium":
      return {
        text: "text-accent-blue",
        badge: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
        bar: "bg-accent-blue",
      };
    case "high":
      return {
        text: "text-yellow-300",
        badge: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
        bar: "bg-yellow-400",
      };
    case "extreme":
      return {
        text: "text-loss",
        badge: "bg-loss/15 text-loss border-loss/30",
        bar: "bg-loss",
      };
  }
}


function glowFromRisk(level: TruthRiskLevel): "profit" | "loss" | "blue" | "none" {
  switch (level) {
    case "low":
      return "profit";
    case "extreme":
      return "loss";
    case "medium":
    case "high":
      return "none";
  }
}

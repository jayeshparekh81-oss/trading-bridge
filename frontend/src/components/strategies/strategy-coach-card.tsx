"use client";

import { Award, ListChecks, Target, Lightbulb } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";

/**
 * Wire shape from POST /api/strategies/{id}/backtest's ``health_card``
 * section. Phase X coach uses snake_case at every level (no Pydantic
 * aliases), so the keys arrive as-is.
 */
export type MetricGradeLevel =
  | "EXCELLENT"
  | "GOOD"
  | "ACCEPTABLE"
  | "CONCERNING";

export type OverallGrade = "A" | "B" | "C" | "D" | "F";

export interface MetricGrade {
  metric_name: string;
  your_value: number;
  unit: string;
  ideal_excellent: string;
  ideal_good: string;
  ideal_acceptable: string;
  ideal_concerning: string;
  your_grade: MetricGradeLevel;
  hinglish_tip: string;
}

export interface StrategyHealthCardPayload {
  overall_grade: OverallGrade;
  overall_summary_hinglish: string;
  metric_grades: MetricGrade[];
  learning_tips: string[];
  next_steps_hinglish: string[];
}


interface Props {
  card: StrategyHealthCardPayload;
}

export function StrategyCoachCard({ card }: Props) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-5">
        <Header card={card} />
        <MetricGrid metrics={card.metric_grades} />
        {card.learning_tips.length > 0 ? (
          <LearningTips tips={card.learning_tips} />
        ) : null}
        {card.next_steps_hinglish.length > 0 ? (
          <NextSteps steps={card.next_steps_hinglish} />
        ) : null}
      </div>
    </GlassmorphismCard>
  );
}


// ─── Header (overall grade + summary) ─────────────────────────────────


function Header({ card }: { card: StrategyHealthCardPayload }) {
  const grade = card.overall_grade;
  return (
    <div className="flex items-start gap-4 flex-wrap">
      <div
        className={cn(
          "shrink-0 inline-flex items-center justify-center rounded-2xl",
          "h-20 w-20 text-4xl font-bold border-2",
          gradeColors(grade),
        )}
        aria-label={`Strategy health grade ${grade}`}
      >
        {grade}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-muted-foreground uppercase tracking-wide flex items-center gap-1">
          <Award className="h-3 w-3" />
          Strategy Coach (Hinglish)
        </div>
        <p className="mt-1 text-base leading-relaxed font-medium">
          {card.overall_summary_hinglish}
        </p>
      </div>
    </div>
  );
}


function gradeColors(grade: OverallGrade): string {
  switch (grade) {
    case "A":
      return "bg-profit/15 border-profit/40 text-profit";
    case "B":
      return "bg-accent-blue/15 border-accent-blue/40 text-accent-blue";
    case "C":
      return "bg-yellow-500/10 border-yellow-500/40 text-yellow-500";
    case "D":
      return "bg-orange-500/10 border-orange-500/40 text-orange-500";
    case "F":
      return "bg-loss/15 border-loss/40 text-loss";
  }
}


// ─── 7 metric grid ────────────────────────────────────────────────────


function MetricGrid({ metrics }: { metrics: MetricGrade[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {metrics.map((m) => (
        <MetricCell key={m.metric_name} metric={m} />
      ))}
    </div>
  );
}


function MetricCell({ metric }: { metric: MetricGrade }) {
  return (
    <div
      className={cn(
        "rounded-lg p-3 border space-y-1.5",
        metricColors(metric.your_grade),
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide">
          {metric.metric_name}
        </h4>
        <span className="text-[10px] font-bold uppercase tracking-wider opacity-80">
          {metric.your_grade.toLowerCase()}
        </span>
      </div>
      <div className="text-lg font-semibold tabular-nums">
        {formatValue(metric.your_value, metric.unit)}
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug">
        Ideal:{" "}
        <span className="text-foreground/80">
          {metric.ideal_excellent}
        </span>
      </p>
      <p className="text-xs leading-relaxed">{metric.hinglish_tip}</p>
    </div>
  );
}


function metricColors(grade: MetricGradeLevel): string {
  switch (grade) {
    case "EXCELLENT":
      return "bg-profit/[0.08] border-profit/30";
    case "GOOD":
      return "bg-accent-blue/[0.08] border-accent-blue/30";
    case "ACCEPTABLE":
      return "bg-yellow-500/[0.08] border-yellow-500/30";
    case "CONCERNING":
      return "bg-loss/[0.08] border-loss/30";
  }
}


function formatValue(value: number, unit: string): string {
  // Phase X coach uses 1e9 as a stand-in for ``inf`` so the JSON stays
  // a finite float. Display infinity-suggesting values as ∞ for clarity.
  if (value >= 1e8) return "∞";
  const formatted = value.toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  });
  if (unit === "%") return `${formatted}%`;
  if (unit === "x") return `${formatted}x`;
  if (unit === "trades") return `${formatted}`;
  return formatted;
}


// ─── Learning tips & next steps ──────────────────────────────────────


function LearningTips({ tips }: { tips: string[] }) {
  return (
    <div className="rounded-lg p-3 bg-white/[0.02] border border-white/[0.06] space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide">
        <Lightbulb className="h-3 w-3" />
        Learning tips
      </div>
      <ul className="space-y-1.5 text-xs leading-relaxed">
        {tips.map((tip, i) => (
          <li key={i} className="pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-accent-blue">
            {tip}
          </li>
        ))}
      </ul>
    </div>
  );
}


function NextSteps({ steps }: { steps: string[] }) {
  return (
    <div className="rounded-lg p-3 bg-accent-blue/[0.05] border border-accent-blue/20 space-y-2">
      <div className="flex items-center gap-2 text-xs text-accent-blue uppercase tracking-wide font-semibold">
        <Target className="h-3 w-3" />
        Next steps
      </div>
      <ol className="space-y-1.5 text-xs leading-relaxed list-decimal list-inside">
        {steps.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
      <div className="text-[10px] text-muted-foreground flex items-center gap-1 pt-1">
        <ListChecks className="h-3 w-3" />
        Action items
      </div>
    </div>
  );
}

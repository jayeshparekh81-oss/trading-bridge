"use client";

import { Check, Info, Sparkles, X } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";

/**
 * Wire shape from ``POST /api/strategies/{id}/backtest``'s
 * ``trade_quality`` section — the Phase 7 :class:`TradeQualityReport`.
 * The Pydantic model has no aliases, so keys arrive in snake_case.
 */
export type TradeQualityGrade = "A" | "B" | "C" | "D" | "F";

export interface TradeQualityComponentPayload {
  component_name: string;
  score: number;
  weight: number;
  hinglish_tip: string;
}

export interface TradeQualityReportPayload {
  overall_score: number;
  grade: TradeQualityGrade;
  components: TradeQualityComponentPayload[];
  overall_summary_hinglish: string;
  strengths: string[];
  weaknesses: string[];
}

interface Props {
  /** Trade quality report; ``null`` only on legacy responses. */
  report: TradeQualityReportPayload | null;
}

export function TradeQualityCard({ report }: Props) {
  if (report === null) {
    return <UnavailableState />;
  }

  // Insufficient-data placeholder: backend signals this by emitting
  // an empty components tuple alongside a "sample chhota" summary.
  if (report.components.length === 0) {
    return <InsufficientDataState summary={report.overall_summary_hinglish} />;
  }

  const tone = gradeTone(report.grade);
  const score = clamp(report.overall_score, 0, 100);

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-5">
        <Header grade={report.grade} score={score} tone={tone} />
        <ScoreBar value={score} tone={tone} />
        <ComponentList components={report.components} />
        {report.strengths.length > 0 ? (
          <StrengthsList strengths={report.strengths} />
        ) : null}
        {report.weaknesses.length > 0 ? (
          <WeaknessesList weaknesses={report.weaknesses} />
        ) : null}
        <p className="text-[15px] leading-snug">
          {report.overall_summary_hinglish}
        </p>
      </div>
    </GlassmorphismCard>
  );
}

// ─── States ────────────────────────────────────────────────────────────

function InsufficientDataState({ summary }: { summary: string }) {
  return (
    <GlassmorphismCard hover={false} className="opacity-70">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Info className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm">Trade Quality Score</h3>
        </div>
        <p className="text-xs text-muted-foreground leading-snug">{summary}</p>
      </div>
    </GlassmorphismCard>
  );
}

function UnavailableState() {
  return (
    <GlassmorphismCard hover={false} className="opacity-70">
      <div className="space-y-2">
        <h3 className="font-semibold text-sm">Trade Quality Score</h3>
        <p className="text-xs text-muted-foreground">
          Trade quality unavailable for this run.
        </p>
      </div>
    </GlassmorphismCard>
  );
}

// ─── Header ────────────────────────────────────────────────────────────

function Header({
  grade,
  score,
  tone,
}: {
  grade: TradeQualityGrade;
  score: number;
  tone: GradeTone;
}) {
  return (
    <div className="flex items-start justify-between gap-3 flex-wrap">
      <div className="space-y-0.5">
        <h3 className="font-semibold text-sm">Trade Quality Score</h3>
        <p className="text-[11px] text-muted-foreground">
          Phase 7 — five-component scorer over the trades themselves.
        </p>
      </div>
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg border px-3 py-2",
          tone.headerBorder,
          tone.headerBg,
        )}
      >
        {tone.emoji ? (
          <span
            className="text-xl leading-none"
            aria-label={tone.emojiLabel}
            role="img"
          >
            {tone.emoji}
          </span>
        ) : null}
        <div>
          <div className={cn("text-2xl font-bold leading-none", tone.text)}>
            {grade}
          </div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">
            Grade
          </div>
        </div>
        <div className="border-l border-white/[0.08] pl-3">
          <div className={cn("text-xl font-semibold tabular-nums leading-none", tone.text)}>
            {score.toFixed(0)}
          </div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">
            / 100
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Overall score bar ─────────────────────────────────────────────────

function ScoreBar({ value, tone }: { value: number; tone: GradeTone }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px] text-muted-foreground uppercase tracking-wide">
        <span>Overall score</span>
        <span className="tabular-nums">{value.toFixed(1)}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", tone.bar)}
          style={{ width: `${value}%` }}
          aria-label={`Trade quality score ${value.toFixed(0)} of 100`}
        />
      </div>
    </div>
  );
}

// ─── Component list ────────────────────────────────────────────────────

function ComponentList({
  components,
}: {
  components: TradeQualityComponentPayload[];
}) {
  return (
    <div className="space-y-3">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Components
      </h4>
      <div className="space-y-2.5">
        {components.map((c) => (
          <ComponentRow key={c.component_name} component={c} />
        ))}
      </div>
    </div>
  );
}

function ComponentRow({ component }: { component: TradeQualityComponentPayload }) {
  const tone = scoreTone(component.score);
  const score = clamp(component.score, 0, 100);
  const weightPct = Math.round(component.weight * 100);
  const isStandout = score >= 90;
  return (
    <div className="rounded-md border border-white/[0.05] bg-white/[0.02] p-2.5 space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] font-medium">
            {componentLabel(component.component_name)}
          </span>
          <span className="text-[10px] text-muted-foreground">
            (weight: {weightPct}%)
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {isStandout ? (
            <Sparkles
              className="h-3 w-3 text-profit"
              aria-label="Component scored 90 or above"
            />
          ) : null}
          <span className={cn("text-[12px] font-semibold tabular-nums", tone.text)}>
            {score.toFixed(0)}/100
          </span>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", tone.bar)}
          style={{ width: `${score}%` }}
          aria-label={`${componentLabel(component.component_name)} score ${score.toFixed(0)} of 100`}
        />
      </div>
      <p className="text-[13px] italic text-muted-foreground leading-snug">
        {component.hinglish_tip}
      </p>
    </div>
  );
}

// ─── Strengths / weaknesses ────────────────────────────────────────────

function StrengthsList({ strengths }: { strengths: string[] }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Strengths
      </h4>
      <ul className="space-y-1">
        {strengths.map((s, idx) => (
          <li
            key={idx}
            className="text-[11px] leading-snug flex items-start gap-1.5"
          >
            <Check className="h-3 w-3 text-profit mt-0.5 shrink-0" />
            <span>{s}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function WeaknessesList({ weaknesses }: { weaknesses: string[] }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Weaknesses
      </h4>
      <ul className="space-y-1">
        {weaknesses.map((w, idx) => (
          <li
            key={idx}
            className="text-[11px] leading-snug flex items-start gap-1.5"
          >
            <X className="h-3 w-3 text-loss mt-0.5 shrink-0" />
            <span>{w}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Tones ─────────────────────────────────────────────────────────────

interface GradeTone {
  emoji: string | null;
  emojiLabel: string;
  text: string;
  bar: string;
  headerBorder: string;
  headerBg: string;
}

function gradeTone(grade: TradeQualityGrade): GradeTone {
  switch (grade) {
    case "A":
      return {
        emoji: "🏆",
        emojiLabel: "Trophy — top tier trade quality",
        text: "text-profit",
        bar: "bg-profit",
        headerBorder: "border-profit/30",
        headerBg: "bg-profit/[0.06]",
      };
    case "B":
      return {
        emoji: "🎯",
        emojiLabel: "Target — strong trade quality",
        text: "text-accent-blue",
        bar: "bg-accent-blue",
        headerBorder: "border-accent-blue/30",
        headerBg: "bg-accent-blue/[0.06]",
      };
    case "C":
      return {
        emoji: null,
        emojiLabel: "",
        text: "text-yellow-200",
        bar: "bg-yellow-400",
        headerBorder: "border-yellow-500/30",
        headerBg: "bg-yellow-500/[0.06]",
      };
    case "D":
      return {
        emoji: null,
        emojiLabel: "",
        text: "text-orange-300",
        bar: "bg-orange-400",
        headerBorder: "border-orange-500/30",
        headerBg: "bg-orange-500/[0.06]",
      };
    case "F":
      return {
        emoji: "⚠️",
        emojiLabel: "Warning — trade quality is poor",
        text: "text-loss",
        bar: "bg-loss",
        headerBorder: "border-loss/30",
        headerBg: "bg-loss/[0.06]",
      };
  }
}

interface ScoreTone {
  text: string;
  bar: string;
}

function scoreTone(score: number): ScoreTone {
  if (score >= 80) {
    return { text: "text-profit", bar: "bg-profit" };
  }
  if (score >= 60) {
    return { text: "text-accent-blue", bar: "bg-accent-blue" };
  }
  if (score >= 40) {
    return { text: "text-yellow-200", bar: "bg-yellow-400" };
  }
  return { text: "text-loss", bar: "bg-loss" };
}

// ─── Component name → display label ───────────────────────────────────

function componentLabel(name: string): string {
  switch (name) {
    case "risk_reward":
      return "Risk-Reward";
    case "consistency":
      return "Consistency";
    case "drawdown":
      return "Drawdown Discipline";
    case "cost_survival":
      return "Cost Survival";
    case "exit_discipline":
      return "Exit Discipline";
    default:
      return name.replace(/_/g, " ");
  }
}

// ─── Utilities ────────────────────────────────────────────────────────

function clamp(v: number, lo: number, hi: number): number {
  if (Number.isNaN(v)) return lo;
  return Math.min(hi, Math.max(lo, v));
}

"use client";

import { useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  X,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Wire shape from ``POST /api/strategies/{id}/backtest``'s ``regime``
 * section — the Phase 8 :class:`RegimeReport`. Pydantic serialises with
 * camelCase aliases (``response_model_by_alias=True`` on the endpoint),
 * so the keys arrive in this exact form.
 */
export type RegimeName =
  | "trending"
  | "sideways"
  | "high_volatility"
  | "low_volatility"
  | "gap_day"
  | "choppy"
  | "breakout"
  | "abnormal";

export type SuitabilityRiskLevel = "low" | "medium" | "high";
export type StrategyType =
  | "trend_following"
  | "mean_reversion"
  | "breakout"
  | "volatility"
  | "unknown";

export interface RegimeMetricsPayload {
  adxValue: number;
  atrNormalized: number;
  maSlopePercent: number;
  rangeCompressionRatio: number;
  gapPercent: number | null;
  directionChangesCount: number;
  volatilityPercentile: number;
}

export interface StrategySuitabilityPayload {
  suitable: boolean;
  reason: string;
  riskLevel: SuitabilityRiskLevel;
  strategyType: StrategyType;
}

export interface RegimeReportPayload {
  regime: RegimeName;
  confidence: number;
  metrics: RegimeMetricsPayload;
  warnings: string[];
  strategySuitability: StrategySuitabilityPayload | null;
  hinglishSummary: string;
}


interface Props {
  /** Regime report; ``null`` only on legacy responses. */
  regime: RegimeReportPayload | null;
}


export function MarketRegimePanel({ regime }: Props) {
  if (regime === null) {
    return (
      <GlassmorphismCard hover={false}>
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Market regime</h3>
          <p className="text-xs text-muted-foreground">
            Regime detection unavailable for this run.
          </p>
        </div>
      </GlassmorphismCard>
    );
  }

  const tone = regimeTone(regime.regime);
  const confidencePct = Math.round(
    Math.max(0, Math.min(1, regime.confidence)) * 100,
  );

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <Header regime={regime.regime} tone={tone} />
        <ConfidenceBar value={confidencePct} tone={tone} />
        <p className="text-base leading-snug">{regime.hinglishSummary}</p>
        {regime.strategySuitability ? (
          <SuitabilitySection suitability={regime.strategySuitability} />
        ) : null}
        {regime.warnings.length > 0 ? (
          <WarningsList warnings={regime.warnings} />
        ) : null}
        <MetricsExpander metrics={regime.metrics} />
      </div>
    </GlassmorphismCard>
  );
}


// ─── Header — regime emoji + label badge ───────────────────────────────


function Header({ regime, tone }: { regime: RegimeName; tone: RegimeTone }) {
  return (
    <div className="flex items-start justify-between gap-3 flex-wrap">
      <div className="space-y-0.5">
        <h3 className="font-semibold text-sm">Market regime</h3>
        <p className="text-[11px] text-muted-foreground">
          Phase 8 deterministic regime detector.
        </p>
      </div>
      <Badge className={cn("gap-1.5 text-xs px-2.5 py-1", tone.badge)}>
        <span aria-hidden="true">{tone.emoji}</span>
        <span className="capitalize">{regime.replace(/_/g, " ")}</span>
      </Badge>
    </div>
  );
}


// ─── Confidence bar (0-100%) ───────────────────────────────────────────


function ConfidenceBar({ value, tone }: { value: number; tone: RegimeTone }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px] text-muted-foreground uppercase tracking-wide">
        <span>Confidence</span>
        <span className="tabular-nums">{value}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", tone.bar)}
          style={{ width: `${value}%` }}
          aria-label={`Regime confidence ${value}%`}
        />
      </div>
    </div>
  );
}


// ─── Strategy suitability ──────────────────────────────────────────────


function SuitabilitySection({
  suitability,
}: {
  suitability: StrategySuitabilityPayload;
}) {
  const tone = suitabilityRiskTone(suitability.riskLevel);
  return (
    <div
      className={cn(
        "rounded-md border p-3 space-y-1.5",
        suitability.suitable
          ? "border-profit/30 bg-profit/[0.05]"
          : "border-loss/30 bg-loss/[0.05]",
      )}
    >
      <div className="flex items-center gap-2 flex-wrap">
        {suitability.suitable ? (
          <Check className="h-4 w-4 text-profit" />
        ) : (
          <X className="h-4 w-4 text-loss" />
        )}
        <span
          className={cn(
            "text-xs font-medium",
            suitability.suitable ? "text-profit" : "text-loss",
          )}
        >
          {suitability.suitable
            ? "Strategy is suitable"
            : "Strategy not suitable"}
        </span>
        <Badge className={cn("ml-auto uppercase text-[10px]", tone.badge)}>
          {suitability.riskLevel} risk
        </Badge>
      </div>
      <p className="text-[11px] leading-snug text-muted-foreground">
        {suitability.reason}
      </p>
    </div>
  );
}


// ─── Warnings list (red bullets) ───────────────────────────────────────


function WarningsList({ warnings }: { warnings: string[] }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Warnings
      </h4>
      <ul className="space-y-1">
        {warnings.map((msg, idx) => (
          <li
            key={idx}
            className="text-[11px] leading-snug flex items-start gap-1.5"
          >
            <span className="text-loss mt-0.5 shrink-0">•</span>
            <span>{msg}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}


// ─── Expert metrics expander ───────────────────────────────────────────


function MetricsExpander({ metrics }: { metrics: RegimeMetricsPayload }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-white/[0.06] bg-white/[0.02]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2"
        aria-expanded={open}
      >
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground font-medium">
          Show metrics
        </span>
        {open ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>
      {open ? (
        <div className="grid grid-cols-2 gap-2 px-3 pb-3">
          <Metric
            label="ADX"
            value={metrics.adxValue.toFixed(1)}
            hint="Trend strength (0-100)"
          />
          <Metric
            label="ATR percentile"
            value={`${(metrics.volatilityPercentile * 100).toFixed(0)}%`}
            hint="Volatility rank in window"
          />
          <Metric
            label="MA slope"
            value={`${metrics.maSlopePercent.toFixed(2)}%`}
            hint="20-period SMA % change"
          />
          <Metric
            label="Range compression"
            value={metrics.rangeCompressionRatio.toFixed(2)}
            hint="<1 = tightening range"
          />
          <Metric
            label="ATR / close"
            value={metrics.atrNormalized.toFixed(4)}
            hint="Unitless volatility"
          />
          <Metric
            label="Direction flips"
            value={String(metrics.directionChangesCount)}
            hint="Last 30 bars"
          />
          {metrics.gapPercent !== null ? (
            <Metric
              label="Gap"
              value={`${(metrics.gapPercent * 100).toFixed(2)}%`}
              hint="From previous close"
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}


function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-md bg-white/[0.02] border border-white/[0.04] px-2 py-1.5">
      <div className="text-[10px] text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div className="text-xs font-medium tabular-nums">{value}</div>
      <div className="text-[10px] text-muted-foreground/70 leading-tight mt-0.5">
        {hint}
      </div>
    </div>
  );
}


// ─── Tones ─────────────────────────────────────────────────────────────


interface RegimeTone {
  emoji: string;
  badge: string;
  bar: string;
}


function regimeTone(regime: RegimeName): RegimeTone {
  switch (regime) {
    case "trending":
      return {
        emoji: "📈",
        badge: "bg-profit/15 text-profit border-profit/30",
        bar: "bg-profit",
      };
    case "breakout":
      return {
        emoji: "🚀",
        badge: "bg-profit/15 text-profit border-profit/30",
        bar: "bg-profit",
      };
    case "sideways":
      return {
        emoji: "↔️",
        badge: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
        bar: "bg-yellow-400",
      };
    case "gap_day":
      return {
        emoji: "🌅",
        badge: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
        bar: "bg-yellow-400",
      };
    case "choppy":
      return {
        emoji: "🌊",
        badge: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
        bar: "bg-yellow-400",
      };
    case "high_volatility":
      return {
        emoji: "⚡",
        badge: "bg-loss/15 text-loss border-loss/30",
        bar: "bg-loss",
      };
    case "abnormal":
      return {
        emoji: "⚠️",
        badge: "bg-loss/15 text-loss border-loss/30",
        bar: "bg-loss",
      };
    case "low_volatility":
      return {
        emoji: "😴",
        badge: "bg-white/[0.06] text-muted-foreground border-white/[0.08]",
        bar: "bg-muted-foreground",
      };
  }
}


function suitabilityRiskTone(level: SuitabilityRiskLevel): {
  badge: string;
} {
  switch (level) {
    case "low":
      return { badge: "bg-profit/15 text-profit border-profit/30" };
    case "medium":
      return {
        badge: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
      };
    case "high":
      return { badge: "bg-loss/15 text-loss border-loss/30" };
  }
}

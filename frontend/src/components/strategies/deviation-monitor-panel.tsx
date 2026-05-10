"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  PauseCircle,
  ShieldAlert,
  Siren,
  TrendingDown,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Wire shape from ``POST /api/strategies/{id}/backtest``'s
 * ``deviation`` section — the Phase 9 :class:`DeviationReport`. The
 * Phase 9 model has no Pydantic aliases, so the keys arrive in
 * snake_case (unlike the camelCase backtest / truth / regime
 * sections).
 */
export type DeviationStatus = "normal" | "watch" | "warning" | "critical";

export interface DeviationMetricPayload {
  metric_name: string;
  expected: number;
  actual: number;
  deviation_percent: number;
  severity: DeviationStatus;
  hinglish_message: string;
}

export interface DeviationReportPayload {
  deviation_score: number;
  status: DeviationStatus;
  deviations: DeviationMetricPayload[];
  recommended_actions: string[];
  should_pause: boolean;
  should_reduce_size: boolean;
  should_switch_to_paper: boolean;
  hinglish_summary: string;
  auto_kill_switch_signal: boolean;
}

interface Props {
  /** Deviation report; ``null`` when no paper data exists yet. */
  deviation: DeviationReportPayload | null;
}

export function DeviationMonitorPanel({ deviation }: Props) {
  if (deviation === null) {
    return <EmptyState />;
  }

  const tone = statusTone(deviation.status);
  const score = clamp(deviation.deviation_score, 0, 100);

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-5">
        <Header status={deviation.status} tone={tone} />
        <ScoreBar value={score} tone={tone} />
        <p className="text-base leading-snug">{deviation.hinglish_summary}</p>
        {deviation.deviations.length > 0 ? (
          <MetricGrid metrics={deviation.deviations} />
        ) : null}
        <ActionFlags
          shouldPause={deviation.should_pause}
          shouldReduceSize={deviation.should_reduce_size}
          shouldSwitchToPaper={deviation.should_switch_to_paper}
        />
        {deviation.recommended_actions.length > 0 ? (
          <RecommendedActions actions={deviation.recommended_actions} />
        ) : null}
        {deviation.auto_kill_switch_signal ? <KillSwitchAdvisory /> : null}
      </div>
    </GlassmorphismCard>
  );
}

// ─── Empty state ───────────────────────────────────────────────────────

function EmptyState() {
  return (
    <GlassmorphismCard hover={false} className="opacity-70">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <TrendingDown className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm">Deviation monitor</h3>
        </div>
        <p className="text-xs text-muted-foreground leading-snug">
          Insufficient paper data. Complete 10+ paper sessions to see
          live-vs-backtest deviation analysis.
        </p>
      </div>
    </GlassmorphismCard>
  );
}

// ─── Header ────────────────────────────────────────────────────────────

function Header({
  status,
  tone,
}: {
  status: DeviationStatus;
  tone: StatusTone;
}) {
  const Icon = tone.icon;
  return (
    <div className="flex items-start justify-between gap-3 flex-wrap">
      <div className="space-y-0.5">
        <h3 className="font-semibold text-sm">Deviation monitor</h3>
        <p className="text-[11px] text-muted-foreground">
          Live vs backtest comparison.
        </p>
      </div>
      <Badge className={cn("gap-1.5 text-xs px-2.5 py-1", tone.badge)}>
        <Icon className="h-3.5 w-3.5" />
        <span>{tone.label[status]}</span>
      </Badge>
    </div>
  );
}

// ─── Deviation score bar ──────────────────────────────────────────────

function ScoreBar({ value, tone }: { value: number; tone: StatusTone }) {
  const rounded = Math.round(value);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px] text-muted-foreground uppercase tracking-wide">
        <span>Deviation score</span>
        <span className="tabular-nums">{rounded} / 100</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", tone.bar)}
          style={{ width: `${rounded}%` }}
          aria-label={`Deviation score ${rounded} of 100`}
        />
      </div>
    </div>
  );
}

// ─── Per-metric breakdown ─────────────────────────────────────────────

function MetricGrid({ metrics }: { metrics: DeviationMetricPayload[] }) {
  return (
    <div>
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium mb-2">
        Metrics
      </h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {metrics.map((m) => (
          <MetricCard key={m.metric_name} metric={m} />
        ))}
      </div>
    </div>
  );
}

function MetricCard({ metric }: { metric: DeviationMetricPayload }) {
  const tone = statusTone(metric.severity);
  const label = metricLabel(metric.metric_name);
  const fmt = metricFormatter(metric.metric_name);
  const deviationSign = metric.deviation_percent >= 0 ? "+" : "";
  return (
    <div
      className={cn(
        "rounded-md border p-2.5 space-y-1.5",
        tone.cardBorder,
        tone.cardBg,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-medium">{label}</span>
        <span className={cn("text-[10px] uppercase font-medium", tone.text)}>
          {metric.severity}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-1 text-[11px]">
        <div>
          <div className="text-[9px] uppercase tracking-wide text-muted-foreground">
            Expected
          </div>
          <div className="tabular-nums font-medium">{fmt(metric.expected)}</div>
        </div>
        <div>
          <div className="text-[9px] uppercase tracking-wide text-muted-foreground">
            Actual
          </div>
          <div className="tabular-nums font-medium">{fmt(metric.actual)}</div>
        </div>
      </div>
      <div className="text-[10px] text-muted-foreground tabular-nums">
        Δ {deviationSign}
        {metric.deviation_percent.toFixed(1)}%
      </div>
      <p className="text-[10px] leading-snug text-muted-foreground/80">
        {metric.hinglish_message}
      </p>
    </div>
  );
}

// ─── Action flags ──────────────────────────────────────────────────────

function ActionFlags({
  shouldPause,
  shouldReduceSize,
  shouldSwitchToPaper,
}: {
  shouldPause: boolean;
  shouldReduceSize: boolean;
  shouldSwitchToPaper: boolean;
}) {
  if (!shouldPause && !shouldReduceSize && !shouldSwitchToPaper) {
    return null;
  }
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Suggested action
      </h4>
      <div className="flex flex-wrap gap-2">
        {shouldPause ? (
          <ActionHint
            icon={PauseCircle}
            label="Pause strategy"
            tone="bg-loss/10 border-loss/30 text-loss"
          />
        ) : null}
        {shouldSwitchToPaper ? (
          <ActionHint
            icon={Eye}
            label="Switch to paper mode"
            tone="bg-yellow-500/10 border-yellow-500/30 text-yellow-200"
          />
        ) : null}
        {shouldReduceSize ? (
          <ActionHint
            icon={TrendingDown}
            label="Reduce size 50%"
            tone="bg-accent-blue/10 border-accent-blue/30 text-accent-blue"
          />
        ) : null}
      </div>
    </div>
  );
}

function ActionHint({
  icon: Icon,
  label,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  tone: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md border",
        tone,
      )}
    >
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}

// ─── Recommended actions ──────────────────────────────────────────────

function RecommendedActions({ actions }: { actions: string[] }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        Recommended next steps
      </h4>
      <ul className="space-y-1">
        {actions.map((action, idx) => (
          <li
            key={idx}
            className="text-[11px] leading-snug flex items-start gap-1.5"
          >
            <span className="text-accent-blue mt-0.5 shrink-0">→</span>
            <span>{action}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Kill-switch advisory (read-only — Phase 9 is advisory only) ──────

function KillSwitchAdvisory() {
  return (
    <div className="rounded-md border border-loss/40 bg-loss/[0.08] p-3 flex items-start gap-2">
      <ShieldAlert className="h-4 w-4 text-loss shrink-0 mt-0.5" />
      <div className="space-y-0.5">
        <p className="text-xs font-medium text-loss">
          🛡️ Kill switch advisory
        </p>
        <p className="text-[11px] text-muted-foreground leading-snug">
          Deviation has crossed the critical band. The monitor recommends
          activating the kill switch — review trade flow before live
          execution.
        </p>
      </div>
    </div>
  );
}

// ─── Tones ─────────────────────────────────────────────────────────────

interface StatusTone {
  icon: React.ComponentType<{ className?: string }>;
  badge: string;
  bar: string;
  text: string;
  cardBorder: string;
  cardBg: string;
  label: Record<DeviationStatus, string>;
}

function statusTone(status: DeviationStatus): StatusTone {
  switch (status) {
    case "normal":
      return {
        icon: CheckCircle2,
        badge: "bg-profit/15 text-profit border-profit/30",
        bar: "bg-profit",
        text: "text-profit",
        cardBorder: "border-profit/20",
        cardBg: "bg-profit/[0.04]",
        label: NORMAL_LABELS,
      };
    case "watch":
      return {
        icon: Eye,
        badge: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
        bar: "bg-accent-blue",
        text: "text-accent-blue",
        cardBorder: "border-accent-blue/20",
        cardBg: "bg-accent-blue/[0.04]",
        label: NORMAL_LABELS,
      };
    case "warning":
      return {
        icon: AlertTriangle,
        badge: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
        bar: "bg-yellow-400",
        text: "text-yellow-200",
        cardBorder: "border-yellow-500/20",
        cardBg: "bg-yellow-500/[0.04]",
        label: NORMAL_LABELS,
      };
    case "critical":
      return {
        icon: Siren,
        badge: "bg-loss/15 text-loss border-loss/30",
        bar: "bg-loss",
        text: "text-loss",
        cardBorder: "border-loss/30",
        cardBg: "bg-loss/[0.05]",
        label: NORMAL_LABELS,
      };
  }
}

const NORMAL_LABELS: Record<DeviationStatus, string> = {
  normal: "✅ Match kar raha hai",
  watch: "👀 Watch karte raho",
  warning: "⚠️ Deviation badh raha hai",
  critical: "🚨 Strategy paused recommended",
};

// ─── Metric formatting ────────────────────────────────────────────────

function metricLabel(name: string): string {
  switch (name) {
    case "win_rate":
      return "Win rate";
    case "drawdown":
      return "Drawdown";
    case "profit_factor":
      return "Profit factor";
    case "trade_frequency":
      return "Trade frequency";
    default:
      return name.replace(/_/g, " ");
  }
}

function metricFormatter(name: string): (v: number) => string {
  switch (name) {
    case "win_rate":
      return (v) => `${(v * 100).toFixed(1)}%`;
    case "drawdown":
      return (v) => `${(v * 100).toFixed(1)}%`;
    case "profit_factor":
      return (v) => v.toFixed(2);
    case "trade_frequency":
      return (v) => `${v.toFixed(2)}/day`;
    default:
      return (v) => v.toFixed(2);
  }
}

// ─── Utilities ────────────────────────────────────────────────────────

function clamp(v: number, lo: number, hi: number): number {
  if (Number.isNaN(v)) return lo;
  return Math.min(hi, Math.max(lo, v));
}

"use client";

/**
 * Standalone strategy-compliance card.
 *
 * Renders one strategy's compliance state — score badge, indicator
 * chips, blocking issues + warnings, and recommendations. Drop in
 * anywhere a per-strategy compliance summary is useful (the
 * /compliance page renders one per strategy; the strategy detail
 * page can embed it later without re-implementing the layout).
 *
 * Pure presentational — owner provides the report payload.
 */

import Link from "next/link";
import { AlertTriangle, ArrowUpRight, ShieldAlert, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";

export interface IndicatorComplianceInfo {
  indicator_id: string;
  instance_id: string;
  name: string;
  status: string;
  risk_level: "safe" | "warning" | "blocked";
  user_facing_message_hinglish: string;
  can_use_live: boolean;
  can_use_paper: boolean;
  can_use_backtest: boolean;
}

export interface StrategyComplianceReport {
  strategy_id: string;
  strategy_name: string;
  compliance_score: number;
  indicators_used: IndicatorComplianceInfo[];
  blocking_issues: string[];
  warnings: string[];
  recommendations: string[];
}

interface Props {
  report: StrategyComplianceReport;
  /** When false, hides the per-indicator chips for a more compact list-view layout. */
  showIndicatorChips?: boolean;
}

export function StrategyComplianceCard({
  report,
  showIndicatorChips = true,
}: Props) {
  const tone = scoreTone(report.compliance_score);
  return (
    <div id={`strategy-${report.strategy_id}`}>
      <GlassmorphismCard hover={false}>
      <div className="space-y-3">
        <header className="flex items-start justify-between gap-3 flex-wrap">
          <div className="space-y-0.5 min-w-0">
            <p className="text-sm font-semibold truncate">
              {report.strategy_name}
            </p>
            <p className="text-[10px] text-muted-foreground font-mono">
              {report.strategy_id.slice(0, 8)}
            </p>
          </div>
          <ScoreBadge score={report.compliance_score} tone={tone} />
        </header>

        {showIndicatorChips && report.indicators_used.length > 0 ? (
          <div className="flex items-center gap-1.5 flex-wrap">
            {report.indicators_used.map((info) => (
              <IndicatorChip key={info.instance_id} info={info} />
            ))}
          </div>
        ) : null}

        {report.blocking_issues.length > 0 ? (
          <IssueList
            title="Blocking issues"
            items={report.blocking_issues}
            icon={ShieldAlert}
            tone="blocked"
          />
        ) : null}

        {report.warnings.length > 0 ? (
          <IssueList
            title="Warnings"
            items={report.warnings}
            icon={AlertTriangle}
            tone="warning"
          />
        ) : null}

        {report.recommendations.length > 0 ? (
          <div className="rounded-md border border-accent-blue/20 bg-accent-blue/[0.05] p-2.5 space-y-1">
            <p className="text-[10px] uppercase tracking-wider text-accent-blue font-semibold">
              Recommendations
            </p>
            <ul className="text-[11px] text-foreground/85 leading-relaxed space-y-0.5 list-disc pl-4">
              {report.recommendations.map((rec, i) => (
                <li key={i}>{rec}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="pt-1">
          <Link
            href={`/strategies/${report.strategy_id}`}
            className="inline-flex items-center gap-1 text-[11px] text-accent-blue hover:underline"
          >
            Strategy edit karo
            <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
      </GlassmorphismCard>
    </div>
  );
}

function scoreTone(score: number): "ok" | "warn" | "bad" {
  if (score >= 100) return "ok";
  if (score >= 70) return "warn";
  return "bad";
}

function ScoreBadge({
  score,
  tone,
}: {
  score: number;
  tone: "ok" | "warn" | "bad";
}) {
  const palette = {
    ok: {
      cls: "bg-profit/15 text-profit border-profit/30",
      label: "🛡️ Compliant",
    },
    warn: {
      cls: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
      label: "⚠️ Needs attention",
    },
    bad: {
      cls: "bg-loss/15 text-loss border-loss/30",
      label: "🚨 Blocked",
    },
  }[tone];
  return (
    <div className="flex items-center gap-2">
      <Badge className={cn("text-[10px] uppercase border", palette.cls)}>
        {palette.label}
      </Badge>
      <div
        className={cn(
          "rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums border",
          palette.cls,
        )}
      >
        {score}
      </div>
    </div>
  );
}

function IndicatorChip({ info }: { info: IndicatorComplianceInfo }) {
  const palette =
    info.risk_level === "safe"
      ? "bg-profit/10 text-profit/90 border-profit/20"
      : info.risk_level === "warning"
        ? "bg-yellow-500/10 text-yellow-300 border-yellow-500/25"
        : "bg-loss/10 text-loss border-loss/25";
  return (
    <span
      title={info.user_facing_message_hinglish}
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] uppercase border",
        palette,
      )}
    >
      {info.risk_level === "safe" ? (
        <ShieldCheck className="h-3 w-3" />
      ) : info.risk_level === "warning" ? (
        <AlertTriangle className="h-3 w-3" />
      ) : (
        <ShieldAlert className="h-3 w-3" />
      )}
      {info.name}
      <span className="opacity-70">·{info.status}</span>
    </span>
  );
}

function IssueList({
  title,
  items,
  icon: Icon,
  tone,
}: {
  title: string;
  items: string[];
  icon: typeof AlertTriangle;
  tone: "warning" | "blocked";
}) {
  const cls =
    tone === "blocked"
      ? "border-loss/25 bg-loss/[0.06] text-loss"
      : "border-yellow-500/25 bg-yellow-500/[0.06] text-yellow-300";
  return (
    <div className={cn("rounded-md border p-2.5 space-y-1", cls)}>
      <p className="text-[10px] uppercase tracking-wider font-semibold flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {title}
      </p>
      <ul className="text-[11px] text-foreground/90 leading-relaxed space-y-0.5 list-disc pl-4">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

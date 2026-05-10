"use client";

/**
 * /compliance — user-facing license compliance dashboard.
 *
 * Lists every strategy the calling user owns + its compliance
 * score. Clicking a row expands the full per-indicator report
 * (fetched on demand from /api/compliance/strategies/{id}) so the
 * initial list payload stays small even for a user with dozens of
 * strategies using many indicators each.
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import {
  StrategyComplianceCard,
  type StrategyComplianceReport,
} from "@/components/compliance/strategy-compliance-card";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface StrategyComplianceSummary {
  strategy_id: string;
  strategy_name: string;
  compliance_score: number;
  indicator_count: number;
  blocking_issue_count: number;
  warning_count: number;
}

interface SummaryListResponse {
  strategies: StrategyComplianceSummary[];
  count: number;
}

export default function CompliancePage() {
  const [summaries, setSummaries] = useState<StrategyComplianceSummary[] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [expandedReports, setExpandedReports] = useState<
    Record<string, StrategyComplianceReport | "loading" | "error">
  >({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await api.get<SummaryListResponse>(
          "/compliance/strategies/me",
        );
        if (!cancelled) setSummaries(res.strategies);
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiError
              ? e.detail
              : "Compliance load karne mein dikkat aayi.",
          );
          setSummaries([]);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function expand(strategyId: string) {
    if (expandedReports[strategyId] != null) {
      // Already loaded or in flight — collapse on second click.
      const next = { ...expandedReports };
      delete next[strategyId];
      setExpandedReports(next);
      return;
    }
    setExpandedReports((prev) => ({ ...prev, [strategyId]: "loading" }));
    try {
      const report = await api.get<StrategyComplianceReport>(
        `/compliance/strategies/${strategyId}`,
      );
      setExpandedReports((prev) => ({ ...prev, [strategyId]: report }));
    } catch {
      setExpandedReports((prev) => ({ ...prev, [strategyId]: "error" }));
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-4xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-accent-blue" />
          Strategy Compliance
        </h1>
        <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
          Tumhari strategies ki license compliance check karo —
          kaunsi strategy live trading ke liye ready hai aur kaunsi
          mein coming_soon ya experimental indicators hain. Score
          100 = fully compliant; lower score matlab kuch indicators
          aabhi pure production-ready nahi hain.
        </p>
      </header>

      {summaries == null ? (
        <GlassmorphismCard hover={false}>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Compliance reports load ho rahi hain…
          </div>
        </GlassmorphismCard>
      ) : error != null ? (
        <GlassmorphismCard hover={false}>
          <p className="text-sm text-loss">{error}</p>
        </GlassmorphismCard>
      ) : summaries.length === 0 ? (
        <GlassmorphismCard hover={false}>
          <p className="text-sm text-muted-foreground">
            Abhi koi strategy nahi mili. Strategies tab pe jao aur
            ek banao — yahan compliance report dikhne lagegi.
          </p>
        </GlassmorphismCard>
      ) : (
        <ScoreSummaryStrip summaries={summaries} />
      )}

      {summaries != null && summaries.length > 0 ? (
        <div className="space-y-2">
          {summaries.map((s) => (
            <SummaryRow
              key={s.strategy_id}
              summary={s}
              expanded={expandedReports[s.strategy_id]}
              onExpand={() => expand(s.strategy_id)}
            />
          ))}
        </div>
      ) : null}
    </motion.div>
  );
}

function ScoreSummaryStrip({
  summaries,
}: {
  summaries: StrategyComplianceSummary[];
}) {
  const total = summaries.length;
  const fullyCompliant = summaries.filter((s) => s.compliance_score >= 100)
    .length;
  const warning = summaries.filter(
    (s) => s.compliance_score < 100 && s.compliance_score >= 70,
  ).length;
  const blocked = summaries.filter((s) => s.compliance_score < 70).length;

  return (
    <GlassmorphismCard hover={false}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Total" value={total} tone="neutral" />
        <Stat label="🛡️ Compliant" value={fullyCompliant} tone="ok" />
        <Stat label="⚠️ Warnings" value={warning} tone="warn" />
        <Stat label="🚨 Blocked" value={blocked} tone="bad" />
      </div>
    </GlassmorphismCard>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "neutral" | "ok" | "warn" | "bad";
}) {
  const cls = {
    neutral: "text-foreground",
    ok: "text-profit",
    warn: "text-yellow-300",
    bad: "text-loss",
  }[tone];
  return (
    <div className="space-y-0.5">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className={cn("text-2xl font-bold tabular-nums", cls)}>{value}</p>
    </div>
  );
}

function SummaryRow({
  summary,
  expanded,
  onExpand,
}: {
  summary: StrategyComplianceSummary;
  expanded: StrategyComplianceReport | "loading" | "error" | undefined;
  onExpand: () => void;
}) {
  const tone =
    summary.compliance_score >= 100
      ? "ok"
      : summary.compliance_score >= 70
        ? "warn"
        : "bad";
  const palette = {
    ok: "bg-profit/15 text-profit border-profit/30",
    warn: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
    bad: "bg-loss/15 text-loss border-loss/30",
  }[tone];

  return (
    <div id={`strategy-${summary.strategy_id}`} className="space-y-1.5">
      <GlassmorphismCard hover={false}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="space-y-0.5 min-w-0">
            <p className="text-sm font-semibold truncate">
              {summary.strategy_name}
            </p>
            <div className="flex items-center gap-1.5 flex-wrap">
              <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
                {summary.indicator_count} indicators
              </Badge>
              {summary.warning_count > 0 ? (
                <Badge className="bg-yellow-500/15 text-yellow-300 border-yellow-500/30 text-[10px]">
                  {summary.warning_count} warnings
                </Badge>
              ) : null}
              {summary.blocking_issue_count > 0 ? (
                <Badge className="bg-loss/15 text-loss border-loss/30 text-[10px]">
                  {summary.blocking_issue_count} blocking
                </Badge>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums border",
                palette,
              )}
            >
              {summary.compliance_score}
            </div>
            <Button
              size="sm"
              variant="ghost"
              type="button"
              onClick={onExpand}
            >
              {expanded === "loading" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : expanded != null && expanded !== "error" ? (
                "Collapse"
              ) : (
                "Detail dikhao"
              )}
            </Button>
          </div>
        </div>
      </GlassmorphismCard>

      {expanded === "error" ? (
        <GlassmorphismCard hover={false}>
          <p className="text-xs text-loss">
            Detail load nahi ho paya — refresh karke try karo.
          </p>
        </GlassmorphismCard>
      ) : expanded != null && expanded !== "loading" ? (
        <StrategyComplianceCard report={expanded} />
      ) : null}
    </div>
  );
}

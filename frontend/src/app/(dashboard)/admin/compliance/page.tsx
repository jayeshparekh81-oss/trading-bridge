"use client";

/**
 * /admin/compliance — admin-facing compliance dashboard.
 *
 * Two stacked surfaces:
 *
 *   1. Indicator usage stats — one row per registry id, sortable
 *      by usage count. Promotion candidates (heavily-used coming_soon)
 *      flagged with a badge.
 *   2. Strategies needing attention — paginated cross-user reports
 *      filterable by max-score (low score = high attention).
 *
 * Backend RBAC (require_admin) gates the underlying endpoints; if a
 * non-admin lands here directly, the API calls 403 and the page
 * shows a "yeh feature sirf admin ke liye hai" message.
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Crown, Loader2, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import {
  StrategyComplianceCard,
  type StrategyComplianceReport,
} from "@/components/compliance/strategy-compliance-card";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LicenseUsageStats {
  indicator_id: string;
  name: string;
  status: string;
  total_strategies_using: number;
  total_users_affected: number;
  is_promotion_candidate: boolean;
  last_30_day_usage_count: number;
}

interface IndicatorUsageList {
  indicators: LicenseUsageStats[];
  count: number;
}

interface AdminStrategyComplianceList {
  strategies: StrategyComplianceReport[];
  count: number;
  has_more: boolean;
}

const _PAGE_SIZE = 25;

export default function AdminCompliancePage() {
  const [stats, setStats] = useState<LicenseUsageStats[] | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [reports, setReports] = useState<StrategyComplianceReport[] | null>(
    null,
  );
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [maxScoreFilter, setMaxScoreFilter] = useState<string>("70");
  const [busyReports, setBusyReports] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await api.get<IndicatorUsageList>("/compliance/indicators");
        if (!cancelled) setStats(res.indicators);
      } catch (e) {
        if (cancelled) return;
        setStatsError(
          e instanceof ApiError ? e.detail : "Stats load nahi ho paye.",
        );
        setStats([]);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function fetchReports(nextOffset: number) {
    setBusyReports(true);
    setReportsError(null);
    try {
      const params = new URLSearchParams({
        limit: String(_PAGE_SIZE),
        offset: String(nextOffset),
      });
      const score = parseInt(maxScoreFilter, 10);
      if (!Number.isNaN(score) && score >= 0 && score <= 100) {
        params.set("min_score", String(score));
      }
      const res = await api.get<AdminStrategyComplianceList>(
        `/compliance/strategies/all?${params.toString()}`,
      );
      setReports(res.strategies);
      setHasMore(res.has_more);
      setOffset(nextOffset);
    } catch (e) {
      setReportsError(
        e instanceof ApiError ? e.detail : "Reports load nahi ho paye.",
      );
      setReports([]);
    } finally {
      setBusyReports(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Crown className="h-6 w-6 text-accent-blue" />
          Admin Compliance
        </h1>
        <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
          Platform-wide indicator usage + strategies that need
          attention. Promotion candidates dikhte hain woh
          coming_soon indicators jinka real demand hai — production
          mein ship karne worth hai.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-accent-blue" />
          Indicator usage stats
        </h2>
        {stats == null ? (
          <GlassmorphismCard hover={false}>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Stats load ho rahi hain…
            </div>
          </GlassmorphismCard>
        ) : statsError != null ? (
          <GlassmorphismCard hover={false}>
            <p className="text-sm text-loss">{statsError}</p>
          </GlassmorphismCard>
        ) : (
          <UsageStatsTable stats={stats} />
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-accent-blue" />
          Strategies needing attention
        </h2>
        <GlassmorphismCard hover={false}>
          <div className="flex items-end gap-3 flex-wrap">
            <div className="space-y-1">
              <label
                htmlFor="max-score"
                className="text-[10px] uppercase tracking-wider text-muted-foreground"
              >
                Max compliance score
              </label>
              <Input
                id="max-score"
                type="number"
                min={0}
                max={100}
                value={maxScoreFilter}
                onChange={(e) => setMaxScoreFilter(e.target.value)}
                className="w-24"
              />
            </div>
            <Button
              size="sm"
              type="button"
              onClick={() => fetchReports(0)}
              disabled={busyReports}
            >
              {busyReports ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              Reports load karo
            </Button>
          </div>
        </GlassmorphismCard>

        {reportsError != null ? (
          <GlassmorphismCard hover={false}>
            <p className="text-sm text-loss">{reportsError}</p>
          </GlassmorphismCard>
        ) : null}

        {reports != null && reports.length === 0 ? (
          <GlassmorphismCard hover={false}>
            <p className="text-sm text-muted-foreground">
              Filter ke saath koi strategy nahi mili — score
              threshold badha ke try karo.
            </p>
          </GlassmorphismCard>
        ) : null}

        {reports != null && reports.length > 0 ? (
          <div className="space-y-2">
            {reports.map((r) => (
              <StrategyComplianceCard key={r.strategy_id} report={r} />
            ))}
            <div className="flex items-center justify-between gap-2">
              <Button
                size="sm"
                variant="ghost"
                type="button"
                disabled={offset === 0 || busyReports}
                onClick={() =>
                  fetchReports(Math.max(0, offset - _PAGE_SIZE))
                }
              >
                Previous
              </Button>
              <p className="text-[10px] text-muted-foreground">
                Showing {offset + 1}–{offset + reports.length}
              </p>
              <Button
                size="sm"
                variant="ghost"
                type="button"
                disabled={!hasMore || busyReports}
                onClick={() => fetchReports(offset + _PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </section>
    </motion.div>
  );
}

function UsageStatsTable({ stats }: { stats: LicenseUsageStats[] }) {
  // Sort: promotion candidates first, then by total usage descending,
  // then alphabetical for stable ties.
  const sorted = [...stats].sort((a, b) => {
    if (a.is_promotion_candidate !== b.is_promotion_candidate) {
      return a.is_promotion_candidate ? -1 : 1;
    }
    if (a.total_strategies_using !== b.total_strategies_using) {
      return b.total_strategies_using - a.total_strategies_using;
    }
    return a.indicator_id.localeCompare(b.indicator_id);
  });

  return (
    <GlassmorphismCard hover={false}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-white/[0.06]">
              <th className="text-left py-1.5 pr-2">Indicator</th>
              <th className="text-left py-1.5 pr-2">Status</th>
              <th className="text-right py-1.5 pr-2">Strategies</th>
              <th className="text-right py-1.5 pr-2">Users</th>
              <th className="text-right py-1.5 pr-2">30d</th>
              <th className="text-left py-1.5">Note</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={row.indicator_id}
                className="border-b border-white/[0.04] last:border-0"
              >
                <td className="py-1.5 pr-2 font-mono">
                  {row.indicator_id}
                </td>
                <td className="py-1.5 pr-2">
                  <StatusPill status={row.status} />
                </td>
                <td className="py-1.5 pr-2 text-right tabular-nums">
                  {row.total_strategies_using}
                </td>
                <td className="py-1.5 pr-2 text-right tabular-nums">
                  {row.total_users_affected}
                </td>
                <td className="py-1.5 pr-2 text-right tabular-nums">
                  {row.last_30_day_usage_count}
                </td>
                <td className="py-1.5">
                  {row.is_promotion_candidate ? (
                    <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]">
                      🎯 Promote candidate
                    </Badge>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassmorphismCard>
  );
}

function StatusPill({ status }: { status: string }) {
  const palette =
    status === "active"
      ? "bg-profit/10 text-profit/90 border-profit/20"
      : status === "coming_soon"
        ? "bg-yellow-500/10 text-yellow-300 border-yellow-500/25"
        : status === "experimental"
          ? "bg-accent-purple/10 text-accent-purple border-accent-purple/25"
          : "bg-loss/10 text-loss border-loss/25";
  return (
    <span
      className={cn(
        "inline-block rounded px-1.5 py-0.5 text-[10px] uppercase border",
        palette,
      )}
    >
      {status}
    </span>
  );
}

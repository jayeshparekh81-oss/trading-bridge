"use client";

import Link from "next/link";
import { useMemo } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  History,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  TrendingUp,
  TrendingDown,
  Cable,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";
import { formatCurrency, cn } from "@/lib/utils";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

interface KillSwitchStatus {
  state: "ACTIVE" | "TRIPPED";
  daily_pnl: string;
  max_daily_loss_inr: string;
  trades_today: number;
  max_daily_trades: number;
  tripped_at: string | null;
  trip_reason: string | null;
}

interface Position {
  id: string;
  symbol: string;
  side: string;
  total_quantity: number;
  remaining_quantity: number;
  avg_entry_price: string | null;
  status: string;
  opened_at: string;
}

interface PositionsResponse {
  positions: Position[];
  count: number;
}

interface Signal {
  id: string;
  symbol: string;
  action: string;
  status: string;
  ai_decision: string | null;
  ai_confidence: string | null;
  received_at: string;
}

interface SignalsResponse {
  signals: Signal[];
  count: number;
}

interface BrokerCredential {
  id: string;
  broker_name: string;
  is_active: boolean;
  token_expires_at: string | null;
}

interface HealthResponse {
  status: string;
}

export default function DashboardPage() {
  const { data: ks, isLoading: ksLoading } = useApi<KillSwitchStatus>(
    "/kill-switch/status",
    null,
    15_000,
  );
  const { data: positions } = useApi<PositionsResponse>(
    "/strategies/positions?limit=100",
    null,
    15_000,
  );
  const { data: signals } = useApi<SignalsResponse>(
    "/strategies/signals?limit=10",
    null,
    30_000,
  );
  const { data: brokers } = useApi<BrokerCredential[]>(
    "/users/me/brokers",
    null,
    60_000,
  );
  const { data: health } = useApi<HealthResponse>("/health", null, 60_000);

  const openPositions = useMemo(
    () => (positions?.positions ?? []).filter((p) => p.status === "open" || p.status === "partial"),
    [positions],
  );
  const activeBrokers = useMemo(
    () => (brokers ?? []).filter((b) => b.is_active),
    [brokers],
  );

  const todayApproved = useMemo(
    () => (signals?.signals ?? []).filter((s) => s.ai_decision === "APPROVED").length,
    [signals],
  );
  const todayRejected = useMemo(
    () => (signals?.signals ?? []).filter((s) => s.ai_decision === "REJECTED").length,
    [signals],
  );

  const isTripped = ks?.state === "TRIPPED";
  const dailyPnl = Number(ks?.daily_pnl ?? 0);
  const tradesToday = ks?.trades_today ?? 0;

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6"
    >
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-bold">Overview</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Live snapshot — auto-refresh 15s on critical metrics, 30-60s on the rest.
        </p>
      </motion.div>

      {/* Tripped banner */}
      {isTripped && (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard
            hover={false}
            className="border-loss/40 shadow-[0_0_25px_rgba(255,77,106,0.18)]"
          >
            <div className="flex items-center gap-4">
              <ShieldX className="h-10 w-10 text-loss" />
              <div className="flex-1">
                <div className="text-lg font-bold text-loss">KILL SWITCH TRIPPED</div>
                <p className="text-sm text-muted-foreground">
                  All new orders are blocked. Reason: {ks?.trip_reason ?? "?"} ·{" "}
                  Tripped {ks?.tripped_at ? new Date(ks.tripped_at).toLocaleString("en-IN") : ""}
                </p>
              </div>
              <Link href="/kill-switch">
                <GlowButton variant="primary" size="sm">Manage</GlowButton>
              </Link>
            </div>
          </GlassmorphismCard>
        </motion.div>
      )}

      {/* KPI grid */}
      <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassmorphismCard hover={false}>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                Today&apos;s P&amp;L
              </div>
              <div
                className={cn(
                  "text-2xl font-bold mt-1 tabular-nums",
                  dailyPnl >= 0 ? "text-profit" : "text-loss",
                )}
              >
                {ksLoading && !ks ? "—" : formatCurrency(dailyPnl, { showSign: true })}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {tradesToday} trades today
              </div>
            </div>
            {dailyPnl >= 0 ? (
              <TrendingUp className="h-5 w-5 text-profit shrink-0" />
            ) : (
              <TrendingDown className="h-5 w-5 text-loss shrink-0" />
            )}
          </div>
        </GlassmorphismCard>

        <GlassmorphismCard hover={false}>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                Open positions
              </div>
              <div className="text-2xl font-bold mt-1 tabular-nums text-accent-blue">
                {openPositions.length}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                across {new Set(openPositions.map((p) => p.symbol)).size} symbol(s)
              </div>
            </div>
            <Activity className="h-5 w-5 text-accent-blue shrink-0" />
          </div>
        </GlassmorphismCard>

        <GlassmorphismCard hover={false}>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                Active brokers
              </div>
              <div className="text-2xl font-bold mt-1 tabular-nums">
                {activeBrokers.length}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {(brokers?.length ?? 0) - activeBrokers.length} inactive
              </div>
            </div>
            <Cable className="h-5 w-5 text-accent-blue shrink-0" />
          </div>
        </GlassmorphismCard>

        <GlassmorphismCard hover={false}>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                Kill switch
              </div>
              <div
                className={cn(
                  "text-2xl font-bold mt-1",
                  isTripped ? "text-loss" : "text-profit",
                )}
              >
                {ksLoading && !ks ? "—" : isTripped ? "TRIPPED" : "NORMAL"}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {isTripped ? ks?.trip_reason ?? "?" : "Trading allowed"}
              </div>
            </div>
            {isTripped ? (
              <ShieldX className="h-5 w-5 text-loss shrink-0" />
            ) : (
              <ShieldCheck className="h-5 w-5 text-profit shrink-0" />
            )}
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Health + AI today */}
      <motion.div variants={fadeUp} className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GlassmorphismCard hover={false}>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            Backend health
          </h3>
          <div className="flex items-center gap-3">
            {health?.status === "ok" ? (
              <>
                <CheckCircle2 className="h-6 w-6 text-profit" />
                <div>
                  <div className="font-medium text-profit">Healthy</div>
                  <div className="text-xs text-muted-foreground">
                    /api/health returned ok
                  </div>
                </div>
              </>
            ) : (
              <>
                <XCircle className="h-6 w-6 text-loss" />
                <div>
                  <div className="font-medium text-loss">Unreachable</div>
                  <div className="text-xs text-muted-foreground">
                    Backend not responding
                  </div>
                </div>
              </>
            )}
          </div>
        </GlassmorphismCard>

        <GlassmorphismCard hover={false}>
          <h3 className="text-sm font-semibold mb-3">AI decisions (recent 10 signals)</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-profit/5 border border-profit/20 p-3">
              <div className="text-xs text-muted-foreground">Approved</div>
              <div className="text-2xl font-bold text-profit mt-1">{todayApproved}</div>
            </div>
            <div className="rounded-lg bg-loss/5 border border-loss/20 p-3">
              <div className="text-xs text-muted-foreground">Rejected</div>
              <div className="text-2xl font-bold text-loss mt-1">{todayRejected}</div>
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Recent signals */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-white/[0.04]">
            <h3 className="font-semibold">Recent signals</h3>
            <Link
              href="/trades"
              className="text-xs text-accent-blue hover:underline"
            >
              View all →
            </Link>
          </div>
          {(signals?.signals ?? []).length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No signals received yet. TRADETRI is listening on the webhook URL —
              first Pine alert will appear here within seconds.
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {(signals?.signals ?? []).map((s) => (
                <div key={s.id} className="p-3 flex items-center gap-3 text-sm">
                  <Badge
                    className={cn(
                      "uppercase text-xs",
                      s.action === "ENTRY"
                        ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30"
                        : "bg-muted text-muted-foreground border-border",
                    )}
                  >
                    {s.action}
                  </Badge>
                  <span className="font-mono text-xs">{s.symbol}</span>
                  <span className="flex-1" />
                  {s.ai_decision === "APPROVED" ? (
                    <span className="text-xs text-profit">
                      ✓ APPROVED ({s.ai_confidence ? Number(s.ai_confidence).toFixed(2) : "—"})
                    </span>
                  ) : s.ai_decision === "REJECTED" ? (
                    <span className="text-xs text-loss">
                      ✗ REJECTED ({s.ai_confidence ? Number(s.ai_confidence).toFixed(2) : "—"})
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">{s.status}</span>
                  )}
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(s.received_at).toLocaleTimeString("en-IN")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </GlassmorphismCard>
      </motion.div>

      {/* Quick links */}
      <motion.div variants={fadeUp} className="flex flex-wrap gap-3">
        <Link href="/positions">
          <GlowButton size="sm">
            <Activity className="h-4 w-4 mr-2" /> Live positions
          </GlowButton>
        </Link>
        <Link href="/trades">
          <GlowButton size="sm">
            <History className="h-4 w-4 mr-2" /> Trade history
          </GlowButton>
        </Link>
        <Link href="/kill-switch">
          <GlowButton size="sm" variant={isTripped ? "danger" : "primary"}>
            <ShieldAlert className="h-4 w-4 mr-2" /> Kill switch
          </GlowButton>
        </Link>
        <Link href="/brokers">
          <GlowButton size="sm">
            <Cable className="h-4 w-4 mr-2" /> Brokers
          </GlowButton>
        </Link>
      </motion.div>

      {/* Disclaimer */}
      {!isTripped && health?.status !== "ok" && (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false} className="border-loss/30">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-loss" />
              <div className="text-sm">
                Backend reports unhealthy state. Trading may be impacted.
              </div>
            </div>
          </GlassmorphismCard>
        </motion.div>
      )}

      {ksLoading && !ks && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )}
    </motion.div>
  );
}

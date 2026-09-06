"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
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
import { ConvictionSignals, type SignalsResponse } from "@/components/dashboard/conviction-signals";
import { useApi } from "@/lib/use-api";
import { useLadderOptional } from "@/hooks/useLadder";
import { SimpleHome } from "@/components/simple/simple-home";
import { formatCurrency, cn } from "@/lib/utils";
import { ProPage, ProEmpty } from "@/components/dashboard/pro-page";
import { lessonForDay } from "@/lib/simple/lessons";

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

interface RecentExecution {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  price: string | null;
  leg_role: string;
  created_at?: string;
}

interface PositionsResponse {
  positions: Position[];
  count: number;
}

// Signal / SignalsResponse types are imported from ConvictionSignals (single
// source of truth) — the dashboard fetches the endpoint once and feeds the
// child, so both share one type.

interface BrokerCredential {
  id: string;
  broker_name: string;
  is_active: boolean;
  token_expires_at: string | null;
}

interface HealthResponse {
  status: string;
}

/**
 * "/" is home for everyone. Levels 1–3 see the Simple home (four tiles, the
 * status strip, the day's lesson); Pro sees the overview below. One route,
 * no duplicate paths — the level decides the content.
 */
export default function DashboardPage() {
  const ladder = useLadderOptional();
  if (ladder && ladder.ready && ladder.level < 4) return <SimpleHome />;
  return <ProOverview />;
}

function ProOverview() {
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
  // Single shared fetch (limit=12) serves BOTH the count stats below AND the
  // ConvictionSignals list — passed down as props so the child does not also
  // fetch. (Was two parallel requests: home limit=10 + child limit=12.)
  const {
    data: signals,
    isLoading: signalsLoading,
    error: signalsError,
  } = useApi<SignalsResponse>(
    "/strategies/signals?limit=12",
    null,
    30_000,
  );
  const { data: brokers } = useApi<BrokerCredential[]>(
    "/users/me/brokers",
    null,
    60_000,
  );
  // Backend liveness probe is mounted at the root (`/health`), not
  // under `/api/...` like the rest of the surface. The shared `useApi`
  // client unconditionally prefixes `/api`, so we poll the root URL
  // directly here. Same shape, same 60s interval as the prior call.
  const [health, setHealth] = useState<HealthResponse | null>(null);
  useEffect(() => {
    // Hotfix 2026-05-17: hardcoded production fallback (see
    // WS_URL_FIX_DIAGNOSIS.md). Previous fallback ``/health`` hit Vercel
    // instead of the backend — /health isn't under /api/* so the
    // next.config rewrite doesn't catch it → 404.
    const HEALTH_URL = process.env.NEXT_PUBLIC_API_URL
      ? `${process.env.NEXT_PUBLIC_API_URL}/health`
      : "https://api.tradetri.com/health";
    let alive = true;
    async function poll() {
      try {
        const res = await fetch(HEALTH_URL, { cache: "no-store" });
        if (!res.ok || !alive) return;
        setHealth((await res.json()) as HealthResponse);
      } catch {
        /* network blip — keep last known state, retry next tick */
      }
    }
    poll();
    const id = setInterval(poll, 60_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

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

  // LAST 3 TRADES come from the SAME endpoint the Trades page uses
  // (/strategies/executions), not the dead `trades` table — so Overview and
  // Trades can never show different histories.
  const { data: execs } = useApi<{ executions: RecentExecution[]; count: number }>(
    "/strategies/executions?limit=3",
    null,
    60_000,
  );
  const recentTrades = execs?.executions ?? [];
  const sabak = lessonForDay(new Date(), "hi");

  const isTripped = ks?.state === "TRIPPED";
  const dailyPnl = Number(ks?.daily_pnl ?? 0);
  const tradesToday = ks?.trades_today ?? 0;

  return (
    <ProPage>
      {/* 1. Kill switch, in plain words — and the broker, because a stopped
             broker and a tripped switch look the same to a customer. */}
      <div className="grid gap-4 sm:grid-cols-2">
        <GlassmorphismCard className="p-4">
          <p className="text-xs text-muted-foreground">Trading</p>
          <p className={cn("mt-1 text-lg font-semibold", isTripped ? "text-rose-400" : "text-emerald-400")}>
            {ksLoading ? "Dekh rahe hain…" : isTripped ? "Sab band hai" : "Chalu hai"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {isTripped
              ? "Aaj koi naya order nahi jayega. Kill Switch se wapas chalu karo."
              : "Naye signals par order ja sakte hain."}
          </p>
          <Link href="/kill-switch" className="mt-2 inline-block text-sm text-primary">
            Kill Switch kholo
          </Link>
        </GlassmorphismCard>

        <GlassmorphismCard className="p-4">
          <p className="text-xs text-muted-foreground">Broker</p>
          <p className={cn("mt-1 text-lg font-semibold", activeBrokers.length > 0 ? "text-emerald-400" : "text-amber-400")}>
            {activeBrokers.length > 0 ? `${activeBrokers.length} juda hua` : "Koi broker nahi juda"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {activeBrokers.length > 0
              ? "Session zinda hai. Order ja sakte hain."
              : "Broker jode bina koi order nahi jayega."}
          </p>
          <Link href="/brokers" className="mt-2 inline-block text-sm text-primary">
            {activeBrokers.length > 0 ? "Brokers dekho" : "Broker jodo"}
          </Link>
        </GlassmorphismCard>
      </div>

      {/* 2. Aaj ke signals + aaj ka P&L */}
      <div className="grid gap-4 sm:grid-cols-3">
        <GlassmorphismCard className="p-4">
          <p className="text-xs text-muted-foreground">Aaj ke signals</p>
          <p className="mt-1 text-2xl font-semibold">
            {signalsLoading ? "…" : todayApproved + todayRejected}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {todayApproved} liye · {todayRejected} chhode
          </p>
        </GlassmorphismCard>
        <GlassmorphismCard className="p-4">
          <p className="text-xs text-muted-foreground">Aaj ka P&amp;L</p>
          <p className={cn("mt-1 text-2xl font-semibold", dailyPnl < 0 ? "text-rose-400" : "text-emerald-400")}>
            {formatCurrency(dailyPnl)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{tradesToday} trades aaj</p>
        </GlassmorphismCard>
        <GlassmorphismCard className="p-4">
          <p className="text-xs text-muted-foreground">Khuli positions</p>
          <p className="mt-1 text-2xl font-semibold">{openPositions.length}</p>
          <Link href="/positions" className="mt-1 inline-block text-xs text-primary">
            Positions dekho
          </Link>
        </GlassmorphismCard>
      </div>

      {/* 3. Khuli positions, with what they are */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Khuli positions</h2>
        {openPositions.length === 0 ? (
          <ProEmpty
            headline="Abhi koi position khuli nahi hai"
            next="Jab koi strategy signal degi aur order lagega, woh yahan dikhegi. Marketplace se ek strategy subscribe karke shuru karo."
            action={{ label: "Marketplace kholo", href: "/marketplace" }}
          />
        ) : (
          <div className="divide-y rounded-lg border">
            {(positions?.positions ?? [])
              .filter((p) => p.status === "open")
              .slice(0, 5)
              .map((pos) => (
                <div key={pos.id} className="flex items-center justify-between gap-3 p-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{pos.symbol}</p>
                    <p className="text-xs text-muted-foreground">
                      {pos.side} · {pos.remaining_quantity} qty
                    </p>
                  </div>
                  <p className="shrink-0 text-sm text-muted-foreground">
                    {pos.avg_entry_price ? `entry ${pos.avg_entry_price}` : "entry —"}
                  </p>
                </div>
              ))}
          </div>
        )}
      </section>

      {/* 4. Aakhri 3 trades — SAME source as the Trades page */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">Aakhri 3 trades</h2>
          <Link href="/trades" className="text-sm text-primary">Sab dekho</Link>
        </div>
        {recentTrades.length === 0 ? (
          <ProEmpty
            headline="Abhi tak koi trade nahi hua"
            next="Pehla trade tab hoga jab ek subscribed strategy signal degi aur aapka broker juda hoga."
            action={{ label: "My Strategies dekho", href: "/marketplace/me" }}
          />
        ) : (
          <div className="divide-y rounded-lg border">
            {recentTrades.map((t) => (
              <div key={t.id} className="flex items-center justify-between gap-3 p-3">
                <div className="min-w-0">
                  <p className="truncate font-medium">{t.symbol}</p>
                  <p className="text-xs text-muted-foreground">
                    {t.side} · {t.quantity} qty · {t.leg_role}
                  </p>
                </div>
                <p className="shrink-0 text-sm text-muted-foreground">
                  {t.price ? `\u20b9${t.price}` : "—"}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 5. Aaj ka sabak */}
      {sabak && (
        <section className="rounded-lg border border-primary/20 bg-primary/5 p-4">
          <p className="text-xs text-muted-foreground">Aaj ka sabak</p>
          <p className="mt-1 font-medium">{sabak.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{sabak.body}</p>
          <Link href={sabak.href} className="mt-2 inline-block text-sm text-primary">
            Aur padho
          </Link>
        </section>
      )}

      {/* 6. The signals list the page already had */}
      <ConvictionSignals signalsData={signals} isLoading={signalsLoading} error={signalsError} />
    </ProPage>
  );
}

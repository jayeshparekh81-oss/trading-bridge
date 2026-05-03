"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Bot,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Copy,
  Check,
  Clock,
  Layers,
  Sparkles,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

interface Strategy {
  id: string;
  name: string;
  webhook_token_id: string | null;
  broker_credential_id: string | null;
  max_position_size: number;
  allowed_symbols: string[];
  is_active: boolean;
  entry_lots: number | null;
  partial_profit_lots: number | null;
  exit_strategy_type: string | null;
  ai_validation_enabled: boolean | null;
  created_at: string | null;
  updated_at: string | null;
  last_triggered_at: string | null;
}

const WEBHOOK_BASE = "https://tradetri.com/api/webhook/strategy/";

export default function StrategiesPage() {
  const { data, isLoading, error, refetch } = useApi<Strategy[]>(
    "/users/me/strategies",
    null,
    60_000,
  );

  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function copyTokenId(id: string, tokenId: string) {
    try {
      await navigator.clipboard.writeText(tokenId);
      setCopiedId(id);
      toast.success("Webhook token id copied.");
      window.setTimeout(() => setCopiedId(null), 1500);
    } catch {
      toast.error("Could not access clipboard.");
    }
  }

  const strategies = data ?? [];

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bot className="h-6 w-6 text-accent-blue" /> Strategies
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Read-only view. Configure via TradingView setup. Auto-refresh 60s.
          </p>
        </div>
        <GlowButton size="sm" onClick={refetch}>
          <RefreshCw className={cn("h-4 w-4 mr-2", isLoading && "animate-spin")} /> Refresh
        </GlowButton>
      </motion.div>

      {error && !data ? (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="text-center py-8">
              <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Could not load strategies</h3>
              <p className="text-sm text-muted-foreground mb-4">{error}</p>
              <GlowButton onClick={refetch} size="sm">Retry</GlowButton>
            </div>
          </GlassmorphismCard>
        </motion.div>
      ) : isLoading && !data ? (
        <motion.div variants={fadeUp} className="space-y-4">
          {[0, 1].map((i) => (
            <GlassmorphismCard key={i} hover={false}>
              <div className="animate-pulse space-y-3">
                <div className="h-5 w-1/3 bg-white/[0.05] rounded" />
                <div className="h-3 w-1/2 bg-white/[0.04] rounded" />
                <div className="h-3 w-2/3 bg-white/[0.04] rounded" />
              </div>
            </GlassmorphismCard>
          ))}
        </motion.div>
      ) : strategies.length === 0 ? (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="text-center py-12">
              <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
              <h3 className="font-semibold mb-1">No strategies yet</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                Create one via TradingView webhook setup. The strategy will
                appear here once it&apos;s configured.
              </p>
            </div>
          </GlassmorphismCard>
        </motion.div>
      ) : (
        <motion.div variants={fadeUp} className="space-y-4">
          {strategies.map((s) => {
            const exitType = s.exit_strategy_type ?? "internal";
            const aiEnabled = !!s.ai_validation_enabled;
            return (
              <GlassmorphismCard key={s.id} hover={false}>
                <div className="space-y-4">
                  {/* Header: name + active badge */}
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <h2 className="text-lg font-semibold">{s.name}</h2>
                      <p className="text-xs text-muted-foreground font-mono mt-0.5">
                        {s.id}
                      </p>
                    </div>
                    <Badge
                      className={cn(
                        "uppercase text-xs",
                        s.is_active
                          ? "bg-profit/15 text-profit border-profit/30"
                          : "bg-muted text-muted-foreground border-border",
                      )}
                    >
                      {s.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>

                  {/* Config grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div>
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">
                        Exit model
                      </div>
                      <div className="mt-1 font-medium flex items-center gap-1">
                        <Layers className="h-3.5 w-3.5 text-accent-blue" />
                        {exitType}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">
                        AI validation
                      </div>
                      <div className="mt-1 font-medium flex items-center gap-1">
                        <Sparkles
                          className={cn(
                            "h-3.5 w-3.5",
                            aiEnabled ? "text-profit" : "text-muted-foreground",
                          )}
                        />
                        {aiEnabled ? "Enabled" : "Disabled"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">
                        Entry lots
                      </div>
                      <div className="mt-1 font-medium tabular-nums">
                        {s.entry_lots ?? "—"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground uppercase tracking-wide">
                        Partial-profit lots
                      </div>
                      <div className="mt-1 font-medium tabular-nums">
                        {s.partial_profit_lots ?? "—"}
                      </div>
                    </div>
                  </div>

                  {/* Last triggered */}
                  {s.last_triggered_at && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      Last signal:{" "}
                      <span className="font-medium text-foreground">
                        {new Date(s.last_triggered_at).toLocaleString("en-IN", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </span>
                    </div>
                  )}

                  {/* Webhook info */}
                  {s.webhook_token_id ? (
                    <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3">
                      <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                        Webhook
                      </div>
                      <div className="font-mono text-xs break-all bg-black/30 rounded px-2 py-1.5 mb-2">
                        {WEBHOOK_BASE}
                        <span className="text-muted-foreground">&lt;your-token&gt;</span>
                      </div>
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <p className="text-[11px] text-muted-foreground leading-snug max-w-md">
                          Plain webhook token is not retrievable from server
                          (security). Use the URL you saved at strategy
                          creation. Token id below is for cross-reference only.
                        </p>
                        <button
                          onClick={() => copyTokenId(s.id, s.webhook_token_id!)}
                          className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.06] text-muted-foreground hover:bg-white/[0.07] transition-colors shrink-0"
                          aria-label="Copy webhook token id"
                          type="button"
                        >
                          {copiedId === s.id ? (
                            <>
                              <Check className="h-3 w-3 text-profit" />
                              copied
                            </>
                          ) : (
                            <>
                              <Copy className="h-3 w-3" />
                              token id
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground italic">
                      No webhook token configured for this strategy.
                    </div>
                  )}

                  {/* Allowed symbols (if present) */}
                  {s.allowed_symbols && s.allowed_symbols.length > 0 && (
                    <div>
                      <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1.5">
                        Allowed symbols
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {s.allowed_symbols.map((sym) => (
                          <Badge
                            key={sym}
                            className="text-xs font-mono bg-white/[0.03] border-white/[0.06] text-muted-foreground"
                          >
                            {sym}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </GlassmorphismCard>
            );
          })}
        </motion.div>
      )}
    </motion.div>
  );
}

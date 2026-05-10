"use client";

/**
 * /admin/indicators — admin indicator approval dashboard.
 *
 * Three tabs:
 *   1. Pending Queue — review + decide
 *   2. Active Overrides — currently-effective override rows
 *   3. History — per-indicator status change timeline
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Crown, Loader2, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import { ApprovalModal } from "@/components/admin/approval-modal";
import { StatusBadge } from "@/components/indicators/status-badge";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

type Tab = "queue" | "overrides" | "history";

interface QueueItem {
  id: string;
  indicator_id: string;
  requested_status: string;
  request_reason: string;
  requester_id: string;
  request_metadata: Record<string, unknown>;
  status: string;
  decision_at: string | null;
  decision_notes: string | null;
  created_at: string;
}

interface QueueListResponse {
  queue: QueueItem[];
  count: number;
}

interface OverrideRow {
  id: string;
  indicator_id: string;
  override_status: string;
  override_reason: string;
  approved_by_user_id: string;
  approved_at: string;
  effective_from: string;
  effective_until: string | null;
  prior_status: string | null;
  prior_status_source: string | null;
  decision_metadata: Record<string, unknown>;
}

interface OverrideListResponse {
  overrides: OverrideRow[];
  count: number;
}

interface HistoryResponse {
  indicator_id: string;
  current_status: string;
  history: OverrideRow[];
}

export default function AdminIndicatorsPage() {
  const [tab, setTab] = useState<Tab>("queue");

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Crown className="h-6 w-6 text-accent-blue" />
          Indicator Approvals
        </h1>
        <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
          Coming_soon indicators promote karne ka admin workflow.
          Pending queue review karo, override directly create karo,
          ya history dekho — har decision audit trail mein record
          hoti hai.
        </p>
      </header>

      <div className="flex items-center gap-1.5">
        {(["queue", "overrides", "history"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "rounded-md px-3 py-1 text-xs uppercase tracking-wide transition-colors border",
              tab === t
                ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30"
                : "bg-white/[0.04] text-muted-foreground border-white/[0.06] hover:bg-white/[0.06]",
            )}
          >
            {t === "queue" ? "⏳ Pending" : t === "overrides" ? "📋 Overrides" : "📜 History"}
          </button>
        ))}
      </div>

      {tab === "queue" ? <QueueTab /> : null}
      {tab === "overrides" ? <OverridesTab /> : null}
      {tab === "history" ? <HistoryTab /> : null}
    </motion.div>
  );
}

// ─── Pending Queue tab ────────────────────────────────────────────────

function QueueTab() {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<QueueItem | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.get<QueueListResponse>(
        "/admin/indicators/queue",
      );
      setItems(res.queue);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.detail : "Queue load nahi ho paya.",
      );
      setItems([]);
    }
  }, []);

  useEffect(() => {
    // ``load`` is wrapped in useCallback so its identity is stable;
    // calling it from the effect is the standard "fetch on mount"
    // pattern. Suppress the rule that flags any setState-in-effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function decide(
    item: { id: string },
    decision: "approve" | "reject",
    notes: string,
  ) {
    await api.post<QueueItem>(
      `/admin/indicators/queue/${item.id}/decide`,
      { decision, notes },
    );
    await load();
  }

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-end">
        <Button size="sm" variant="ghost" type="button" onClick={load}>
          <RefreshCw className="h-3 w-3" />
          Refresh
        </Button>
      </div>
      {items == null ? (
        <LoadingCard label="Pending queue load ho rahi hai…" />
      ) : error != null ? (
        <ErrorCard message={error} />
      ) : items.length === 0 ? (
        <GlassmorphismCard hover={false}>
          <p className="text-sm text-muted-foreground">
            Queue khali hai — abhi koi pending request nahi hai.
          </p>
        </GlassmorphismCard>
      ) : (
        <div className="space-y-2">
          {items.map((it) => (
            <GlassmorphismCard key={it.id} hover={false}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-mono font-semibold">
                      {it.indicator_id}
                    </p>
                    <span className="text-[10px] text-muted-foreground">→</span>
                    <StatusBadge status={it.requested_status} />
                  </div>
                  <p className="text-[12px] text-foreground/85 leading-relaxed">
                    {it.request_reason}
                  </p>
                  <p className="text-[10px] text-muted-foreground font-mono">
                    Requester: {it.requester_id.slice(0, 8)} ·{" "}
                    {new Date(it.created_at).toLocaleString()}
                  </p>
                </div>
                <Button
                  size="sm"
                  type="button"
                  onClick={() => setActive(it)}
                >
                  Decide
                </Button>
              </div>
            </GlassmorphismCard>
          ))}
        </div>
      )}
      <ApprovalModal
        item={active}
        onClose={() => setActive(null)}
        onDecide={async (item, decision, notes) => {
          await decide(item, decision, notes);
        }}
      />
    </section>
  );
}

// ─── Active Overrides tab ─────────────────────────────────────────────

function OverridesTab() {
  const [overrides, setOverrides] = useState<OverrideRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await api.get<OverrideListResponse>(
          "/admin/indicators/overrides",
        );
        if (!cancelled) setOverrides(res.overrides);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? e.detail
            : "Overrides load nahi ho paye.",
        );
        setOverrides([]);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (overrides == null) return <LoadingCard label="Overrides load ho rahe hain…" />;
  if (error != null) return <ErrorCard message={error} />;
  if (overrides.length === 0) {
    return (
      <GlassmorphismCard hover={false}>
        <p className="text-sm text-muted-foreground">
          Abhi koi active override nahi hai — sab indicators registry
          ke default status pe chal rahe hain.
        </p>
      </GlassmorphismCard>
    );
  }
  return (
    <GlassmorphismCard hover={false}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-white/[0.06]">
              <th className="text-left py-1.5 pr-2">Indicator</th>
              <th className="text-left py-1.5 pr-2">Status</th>
              <th className="text-left py-1.5 pr-2">Prior</th>
              <th className="text-left py-1.5 pr-2">Reason</th>
              <th className="text-left py-1.5">Approved at</th>
            </tr>
          </thead>
          <tbody>
            {overrides.map((o) => (
              <tr
                key={o.id}
                className="border-b border-white/[0.04] last:border-0"
              >
                <td className="py-1.5 pr-2 font-mono">
                  {o.indicator_id}
                </td>
                <td className="py-1.5 pr-2">
                  <StatusBadge status={o.override_status} />
                </td>
                <td className="py-1.5 pr-2">
                  {o.prior_status ? (
                    <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
                      {o.prior_status}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="py-1.5 pr-2 max-w-[300px] truncate">
                  {o.override_reason}
                </td>
                <td className="py-1.5 text-[10px] text-muted-foreground">
                  {new Date(o.approved_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassmorphismCard>
  );
}

// ─── History tab ──────────────────────────────────────────────────────

function HistoryTab() {
  const [indicatorId, setIndicatorId] = useState("");
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = useMemo(() => indicatorId.trim(), [indicatorId]);

  async function load() {
    if (trimmed.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.get<HistoryResponse>(
        `/admin/indicators/${encodeURIComponent(trimmed)}/history`,
      );
      setHistory(res);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.detail : "History load nahi ho paya.",
      );
      setHistory(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-2">
      <GlassmorphismCard hover={false}>
        <div className="flex items-end gap-2 flex-wrap">
          <div className="flex-1 min-w-[200px] space-y-1">
            <label
              htmlFor="hist-id"
              className="text-[10px] uppercase tracking-wider text-muted-foreground"
            >
              Indicator id
            </label>
            <Input
              id="hist-id"
              value={indicatorId}
              onChange={(e) => setIndicatorId(e.target.value)}
              placeholder="e.g. ema, kama, supertrend"
            />
          </div>
          <Button
            size="sm"
            type="button"
            onClick={load}
            disabled={busy || trimmed.length === 0}
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Load history
          </Button>
        </div>
      </GlassmorphismCard>

      {error != null ? <ErrorCard message={error} /> : null}

      {history != null ? (
        <GlassmorphismCard hover={false}>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold font-mono">
                {history.indicator_id}
              </p>
              <span className="text-[10px] text-muted-foreground">current:</span>
              <StatusBadge status={history.current_status} />
            </div>
            {history.history.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No overrides yet — registry default applies.
              </p>
            ) : (
              <ol className="space-y-2 border-l border-white/[0.08] pl-4">
                {history.history.map((row) => (
                  <li key={row.id} className="space-y-0.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      {row.prior_status ? (
                        <>
                          <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
                            {row.prior_status}
                          </Badge>
                          <span className="text-muted-foreground text-[10px]">→</span>
                        </>
                      ) : null}
                      <StatusBadge status={row.override_status} />
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(row.approved_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-[12px] leading-relaxed text-foreground/85">
                      {row.override_reason}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </GlassmorphismCard>
      ) : null}
    </section>
  );
}

// ─── Shared cards ─────────────────────────────────────────────────────

function LoadingCard({ label }: { label: string }) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {label}
      </div>
    </GlassmorphismCard>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <GlassmorphismCard hover={false}>
      <p className="text-sm text-loss">{message}</p>
    </GlassmorphismCard>
  );
}

"use client";

/**
 * /indicators/requests — creator's view.
 *
 * File a promotion / deprecation request + see status of own
 * past requests. Hits creator-gated endpoints; non-creators
 * see a 403 from the backend (we surface that as a friendly
 * message rather than a raw error).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Send, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/indicators/status-badge";
import { api, ApiError } from "@/lib/api";
import { toast } from "sonner";

interface QueueItem {
  id: string;
  indicator_id: string;
  requested_status: string;
  request_reason: string;
  status: string;
  decision_at: string | null;
  decision_notes: string | null;
  created_at: string;
}

interface MyRequestsResponse {
  requests: QueueItem[];
  count: number;
}

export default function CreatorRequestsPage() {
  const [requests, setRequests] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  // Form state
  const [indicatorId, setIndicatorId] = useState("");
  const [requestedStatus, setRequestedStatus] =
    useState<"active" | "deprecated">("active");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get<MyRequestsResponse>("/indicators/queue/me");
      setRequests(res.requests);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setForbidden(true);
        setRequests([]);
        return;
      }
      setError(
        e instanceof ApiError ? e.detail : "Requests load nahi ho paye.",
      );
      setRequests([]);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function submit() {
    const trimmedId = indicatorId.trim();
    const trimmedReason = reason.trim();
    if (trimmedId.length === 0 || trimmedReason.length === 0) {
      toast.error("Indicator id aur reason dono bharna zaroori hai.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/indicators/queue", {
        indicator_id: trimmedId,
        requested_status: requestedStatus,
        reason: trimmedReason,
      });
      toast.success("Request submitted — admin review karega.");
      setIndicatorId("");
      setReason("");
      await load();
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.detail : "Submit nahi ho paya.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  async function withdraw(item: QueueItem) {
    try {
      await api.post(`/indicators/queue/${item.id}/withdraw`, {});
      toast.success("Request withdrawn.");
      await load();
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.detail : "Withdraw nahi ho paya.";
      toast.error(msg);
    }
  }

  const pending = useMemo(
    () => (requests ?? []).filter((r) => r.status === "pending"),
    [requests],
  );
  const closed = useMemo(
    () => (requests ?? []).filter((r) => r.status !== "pending"),
    [requests],
  );

  if (forbidden) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="p-6 max-w-2xl mx-auto"
      >
        <GlassmorphismCard hover={false}>
          <div className="space-y-2 text-center py-4">
            <p className="text-2xl">🔒</p>
            <p className="text-sm font-semibold">
              Yeh feature sirf creators ke liye hai.
            </p>
            <p className="text-xs text-muted-foreground">
              Settings → &ldquo;Become a Creator&rdquo; se request bhejo (Phase 1
              mein admin approval chahiye).
            </p>
          </div>
        </GlassmorphismCard>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-accent-blue" />
          Indicator Requests
        </h1>
        <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
          Coming_soon indicators ko production-ready promote
          karne ke liye admin se request karo. Apni evidence
          (usage, signal quality) reason mein detail mein likho —
          admin uske basis pe decision lega.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Naya request file karo</h2>
        <GlassmorphismCard hover={false}>
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Indicator id
                </label>
                <Input
                  value={indicatorId}
                  onChange={(e) => setIndicatorId(e.target.value)}
                  placeholder="e.g. supertrend"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Requested status
                </label>
                <select
                  value={requestedStatus}
                  onChange={(e) =>
                    setRequestedStatus(e.target.value as "active" | "deprecated")
                  }
                  className="w-full bg-white/[0.04] border border-white/[0.08] rounded-md px-2 py-1.5 text-sm"
                >
                  <option value="active">✅ Promote to active</option>
                  <option value="deprecated">🚫 Deprecate</option>
                </select>
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Reason / evidence
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Usage stats, signal quality, why is this ready for production…"
                rows={4}
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-md px-2 py-1.5 text-sm leading-relaxed"
              />
            </div>
            <div className="flex justify-end">
              <Button
                size="sm"
                type="button"
                onClick={submit}
                disabled={busy}
              >
                {busy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" />
                )}
                Request submit karo
              </Button>
            </div>
          </div>
        </GlassmorphismCard>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Pending requests</h2>
        {requests == null ? (
          <GlassmorphismCard hover={false}>
            <Loader2 className="h-4 w-4 animate-spin" />
          </GlassmorphismCard>
        ) : error != null ? (
          <GlassmorphismCard hover={false}>
            <p className="text-sm text-loss">{error}</p>
          </GlassmorphismCard>
        ) : pending.length === 0 ? (
          <GlassmorphismCard hover={false}>
            <p className="text-sm text-muted-foreground">
              Koi pending request nahi hai.
            </p>
          </GlassmorphismCard>
        ) : (
          <div className="space-y-2">
            {pending.map((it) => (
              <RequestRow
                key={it.id}
                item={it}
                showWithdraw
                onWithdraw={() => withdraw(it)}
              />
            ))}
          </div>
        )}
      </section>

      {closed.length > 0 ? (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Past requests</h2>
          <div className="space-y-2">
            {closed.map((it) => (
              <RequestRow key={it.id} item={it} />
            ))}
          </div>
        </section>
      ) : null}
    </motion.div>
  );
}

function RequestRow({
  item,
  showWithdraw,
  onWithdraw,
}: {
  item: QueueItem;
  showWithdraw?: boolean;
  onWithdraw?: () => void;
}) {
  const statusEmoji =
    item.status === "approved"
      ? "✅"
      : item.status === "rejected"
        ? "❌"
        : item.status === "withdrawn"
          ? "↩️"
          : "⏳";
  return (
    <GlassmorphismCard hover={false}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-mono font-semibold">
              {item.indicator_id}
            </p>
            <span className="text-[10px] text-muted-foreground">→</span>
            <StatusBadge status={item.requested_status} />
            <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              {statusEmoji} {item.status}
            </Badge>
          </div>
          <p className="text-[12px] text-foreground/85 leading-relaxed">
            {item.request_reason}
          </p>
          {item.decision_notes ? (
            <p className="text-[11px] text-muted-foreground italic">
              Admin notes: {item.decision_notes}
            </p>
          ) : null}
          <p className="text-[10px] text-muted-foreground">
            Filed {new Date(item.created_at).toLocaleString()}
          </p>
        </div>
        {showWithdraw && onWithdraw ? (
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={onWithdraw}
          >
            Withdraw
          </Button>
        ) : null}
      </div>
    </GlassmorphismCard>
  );
}

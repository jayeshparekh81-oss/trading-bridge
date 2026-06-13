"use client";

/**
 * /alerts — per-user price alert CRUD (Queue HHH M10).
 *
 * Wire: GET/POST/DELETE /api/alerts (NEW backend in this sprint).
 *
 * 🛑 IMPORTANT UX NOTE rendered prominently on the page:
 * Alerts are STORED but NOT YET EVALUATED/FIRED. The background
 * tick consumer + notification fanout is a separate sprint. The
 * page banner makes this explicit so customers don't trust an
 * alert to wake them at 03:00 IST when it cannot.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import {
  BellRing,
  Plus,
  Trash2,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { toast } from "sonner";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useApi } from "@/lib/use-api";
import { api, ApiError } from "@/lib/api";
import { relativeTime, cn } from "@/lib/utils";

interface AlertRow {
  id: string;
  name: string;
  symbol: string;
  condition_kind: "price_above" | "price_below";
  threshold: string;
  is_active: boolean;
  last_triggered_at: string | null;
  created_at: string | null;
}

interface AlertList {
  alerts: AlertRow[];
  count: number;
}

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function AlertsPage() {
  const { data, isLoading, refetch } = useApi<AlertList>("/alerts");
  const alerts = data?.alerts ?? [];

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    symbol: "",
    condition_kind: "price_above" as "price_above" | "price_below",
    threshold: "",
  });
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const resetForm = () =>
    setForm({ name: "", symbol: "", condition_kind: "price_above", threshold: "" });

  const handleCreate = async () => {
    const threshold = Number.parseFloat(form.threshold);
    if (!form.name.trim() || !form.symbol.trim() || !Number.isFinite(threshold) || threshold <= 0) {
      toast.error("Fill name, symbol and a positive threshold.");
      return;
    }
    setCreating(true);
    try {
      await api.post("/alerts", {
        name: form.name.trim(),
        symbol: form.symbol.trim().toUpperCase(),
        condition_kind: form.condition_kind,
        threshold,
      });
      toast.success("Alert saved.");
      setCreateOpen(false);
      resetForm();
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to create alert.";
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string, label: string) => {
    if (typeof window !== "undefined" && !window.confirm(`Delete alert "${label}"?`)) {
      return;
    }
    setDeletingId(id);
    try {
      await api.delete(`/alerts/${id}`);
      toast.success("Alert deleted.");
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to delete alert.";
      toast.error(msg);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-5"
    >
      <header className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BellRing className="h-6 w-6 text-accent-blue" /> Alerts
          </h1>
          <p className="text-muted-foreground text-sm">
            Price-condition alerts (stored only — see note below).
          </p>
        </div>
        <GlowButton size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New alert
        </GlowButton>
      </header>

      {/* ── HONESTY BANNER — alerts are storage only ── */}
      <GlassmorphismCard className="p-4 border-amber-500/30 bg-amber-500/[0.04]">
        <div className="flex gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-300 shrink-0 mt-0.5" />
          <div className="text-sm space-y-1">
            <div className="font-medium">
              Alerts are saved but won&apos;t fire yet
            </div>
            <p className="text-xs text-muted-foreground">
              The background tick consumer that watches live prices and
              triggers notifications is a separate sprint. Today you can
              configure + delete alerts; nothing will wake you at 03:00 IST
              until the evaluation engine ships. We&apos;ll email everyone with
              a configured alert the moment the engine goes live.
            </p>
          </div>
        </div>
      </GlassmorphismCard>

      {/* ── List ── */}
      {isLoading ? (
        <GlassmorphismCard className="p-12 text-center text-muted-foreground">
          Loading alerts…
        </GlassmorphismCard>
      ) : alerts.length === 0 ? (
        <GlassmorphismCard className="p-12 text-center space-y-3">
          <BellRing className="h-12 w-12 text-muted-foreground mx-auto" />
          <h2 className="text-lg font-semibold">No alerts configured</h2>
          <p className="text-muted-foreground text-sm max-w-md mx-auto">
            Create your first price alert above. Note: alerts are saved but
            not yet evaluated (see banner above).
          </p>
        </GlassmorphismCard>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => {
            const ConditionIcon =
              a.condition_kind === "price_above" ? TrendingUp : TrendingDown;
            return (
              <GlassmorphismCard key={a.id} className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-medium">{a.name}</h3>
                      <Badge
                        className={cn(
                          a.is_active
                            ? "bg-profit/15 text-profit border-profit/30"
                            : "bg-white/[0.03] text-muted-foreground",
                        )}
                      >
                        {a.is_active ? "Active" : "Paused"}
                      </Badge>
                      {a.last_triggered_at && (
                        <Badge className="bg-amber-500/15 text-amber-300 border-amber-500/30">
                          Last fired {relativeTime(a.last_triggered_at)}
                        </Badge>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground flex items-center gap-2 flex-wrap">
                      <ConditionIcon className="h-4 w-4" />
                      <span className="font-mono">{a.symbol}</span>
                      <span>
                        {a.condition_kind === "price_above" ? ">" : "<"}
                      </span>
                      <span className="font-mono">
                        ₹{Number.parseFloat(a.threshold).toLocaleString("en-IN")}
                      </span>
                      {a.created_at && (
                        <span className="text-xs">
                          · created {relativeTime(a.created_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(a.id, a.name)}
                    disabled={deletingId === a.id}
                    className="px-3 py-1.5 rounded-lg text-sm border border-loss/30 text-loss hover:bg-loss/10 transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    {deletingId === a.id ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </GlassmorphismCard>
            );
          })}
        </div>
      )}

      {/* ── Create dialog ── */}
      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) resetForm();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create new alert</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 pt-4">
            <Field label="Label">
              <Input
                placeholder="e.g., Nifty crosses 25k"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                disabled={creating}
                maxLength={200}
              />
            </Field>
            <Field label="Symbol">
              <Input
                placeholder="e.g., NIFTY"
                value={form.symbol}
                onChange={(e) =>
                  setForm({ ...form, symbol: e.target.value.toUpperCase() })
                }
                disabled={creating}
                maxLength={64}
                className="font-mono"
              />
            </Field>
            <Field label="Condition">
              <div className="grid grid-cols-2 gap-2">
                <ConditionButton
                  selected={form.condition_kind === "price_above"}
                  onClick={() =>
                    setForm({ ...form, condition_kind: "price_above" })
                  }
                  icon={TrendingUp}
                >
                  Price above
                </ConditionButton>
                <ConditionButton
                  selected={form.condition_kind === "price_below"}
                  onClick={() =>
                    setForm({ ...form, condition_kind: "price_below" })
                  }
                  icon={TrendingDown}
                >
                  Price below
                </ConditionButton>
              </div>
            </Field>
            <Field label="Threshold (₹)">
              <Input
                placeholder="e.g., 25000"
                value={form.threshold}
                onChange={(e) => setForm({ ...form, threshold: e.target.value })}
                disabled={creating}
                type="number"
                step="0.01"
                min="0"
              />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setCreateOpen(false)}
                disabled={creating}
                className="px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-accent transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <GlowButton size="sm" onClick={handleCreate} disabled={creating}>
                {creating ? "Saving…" : "Save alert"}
              </GlowButton>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

function ConditionButton({
  selected,
  onClick,
  icon: Icon,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-3 py-2 rounded-lg border text-sm flex items-center justify-center gap-2 transition-colors",
        selected
          ? "border-accent-blue/50 bg-accent-blue/10 text-accent-blue"
          : "border-border hover:bg-accent",
      )}
    >
      <Icon className="h-4 w-4" />
      {children}
    </button>
  );
}

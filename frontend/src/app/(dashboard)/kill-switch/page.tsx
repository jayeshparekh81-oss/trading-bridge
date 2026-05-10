"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  AlertTriangle,
  RotateCcw,
  Clock,
  Loader2,
  Pencil,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useApi } from "@/lib/use-api";
import { api, ApiError } from "@/lib/api";
import { formatCurrency, cn } from "@/lib/utils";
import { toast } from "sonner";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

interface KillSwitchStatus {
  user_id: string;
  state: "ACTIVE" | "TRIPPED";
  daily_pnl: string;
  max_daily_loss_inr: string;
  remaining_loss_budget: string;
  trades_today: number;
  max_daily_trades: number;
  remaining_trades: number;
  enabled: boolean;
  tripped_at: string | null;
  trip_reason: string | null;
}

interface KillSwitchEvent {
  id: string;
  user_id: string;
  triggered_at: string;
  reason: string;
  daily_pnl_at_trigger: string;
  positions_squared_off: unknown[];
  reset_at: string | null;
  reset_by: string | null;
}

export default function KillSwitchPage() {
  const { data: status, isLoading, error, refetch } = useApi<KillSwitchStatus>(
    "/kill-switch/status",
    null,
    15_000,
  );
  const { data: history, refetch: refetchHistory } = useApi<KillSwitchEvent[]>(
    "/kill-switch/history?limit=20",
    [],
    30_000,
  );

  const [tripConfirm, setTripConfirm] = useState("");
  const [tripBusy, setTripBusy] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
  const [tripDialogOpen, setTripDialogOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editLoss, setEditLoss] = useState("");
  const [editTrades, setEditTrades] = useState("");
  const [editBusy, setEditBusy] = useState(false);

  const isTripped = status?.state === "TRIPPED";
  const dailyPnl = Number(status?.daily_pnl ?? 0);
  const maxLoss = Number(status?.max_daily_loss_inr ?? 0);
  const lossUsed = Math.max(0, -dailyPnl);
  const lossPct = maxLoss > 0 ? Math.min(100, Math.round((lossUsed / maxLoss) * 100)) : 0;
  const tradesToday = status?.trades_today ?? 0;
  const maxTrades = status?.max_daily_trades ?? 0;
  const tradePct = maxTrades > 0 ? Math.min(100, Math.round((tradesToday / maxTrades) * 100)) : 0;

  async function handleTrip() {
    if (tripConfirm.trim().toUpperCase() !== "TRIP") {
      toast.error("Type TRIP to confirm.");
      return;
    }
    setTripBusy(true);
    try {
      const tokenResp = await api.post<{ confirmation_token: string }>(
        "/kill-switch/reset-token",
      );
      await api.post<{ status: string; event_id: string }>("/kill-switch/trip", {
        confirmation_token: tokenResp.confirmation_token,
      });
      toast.success("Kill switch tripped. All open positions are being squared off.");
      setTripDialogOpen(false);
      setTripConfirm("");
      refetch();
      refetchHistory();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Trip failed.";
      toast.error(msg);
    } finally {
      setTripBusy(false);
    }
  }

  async function handleReset() {
    setResetBusy(true);
    try {
      const tokenResp = await api.post<{ confirmation_token: string }>(
        "/kill-switch/reset-token",
      );
      await api.post<{ status: string }>("/kill-switch/reset", {
        confirmation_token: tokenResp.confirmation_token,
      });
      toast.success("Kill switch reset. Trading re-enabled.");
      setResetDialogOpen(false);
      refetch();
      refetchHistory();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Reset failed.";
      toast.error(msg);
    } finally {
      setResetBusy(false);
    }
  }

  function openEdit() {
    setEditLoss(String(maxLoss || ""));
    setEditTrades(String(maxTrades || ""));
    setEditOpen(true);
  }

  async function handleSaveLimits() {
    const lossNum = Number(editLoss);
    const tradesNum = Number(editTrades);
    if (!Number.isFinite(lossNum) || lossNum <= 0 || lossNum >= 10_000_000) {
      toast.error("Daily loss must be between ₹1 and ₹99,99,999.");
      return;
    }
    if (!Number.isInteger(tradesNum) || tradesNum <= 0 || tradesNum >= 1000) {
      toast.error("Max trades must be a whole number between 1 and 999.");
      return;
    }
    setEditBusy(true);
    try {
      await api.put("/kill-switch/config", {
        max_daily_loss_inr: lossNum,
        max_daily_trades: tradesNum,
        enabled: status?.enabled ?? true,
        auto_square_off: true,
      });
      toast.success("Limits updated");
      setEditOpen(false);
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Update failed.";
      toast.error(msg);
    } finally {
      setEditBusy(false);
    }
  }

  if (isLoading && !status) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !status) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <GlassmorphismCard hover={false}>
          <div className="text-center py-8">
            <AlertTriangle className="h-12 w-12 text-loss mx-auto mb-3" />
            <h2 className="text-lg font-semibold mb-1">Could not load kill-switch state</h2>
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <GlowButton onClick={refetch} size="sm">Retry</GlowButton>
          </div>
        </GlassmorphismCard>
      </div>
    );
  }

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6"
    >
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-accent-blue" /> Kill Switch
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Trip immediately stops all order placement. All open positions are squared off
          via the broker. Auto-refresh every 15s.
        </p>
      </motion.div>

      {/* Status banner */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard
          glow={isTripped ? "none" : "profit"}
          className={cn(isTripped && "border-loss/40 shadow-[0_0_25px_rgba(255,77,106,0.18)]")}
          hover={false}
        >
          <div className="flex items-center gap-4">
            {isTripped ? (
              <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ repeat: Infinity, duration: 1.5 }}>
                <ShieldX className="h-12 w-12 text-loss" />
              </motion.div>
            ) : (
              <ShieldCheck className="h-12 w-12 text-profit" />
            )}
            <div className="flex-1">
              <div className={cn("text-3xl font-bold", isTripped ? "text-loss" : "text-profit")}>
                {isTripped ? "TRIPPED" : "NORMAL"}
              </div>
              <p className="text-muted-foreground text-sm">
                {isTripped
                  ? `Tripped ${status?.tripped_at ? new Date(status.tripped_at).toLocaleString("en-IN") : ""} · reason: ${status?.trip_reason ?? "?"}`
                  : "Trading is allowed. New webhook signals will fire orders."}
              </p>
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Daily metrics */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Today</h2>
            <Dialog open={editOpen} onOpenChange={setEditOpen}>
              <DialogTrigger>
                <button
                  type="button"
                  onClick={openEdit}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground border border-white/10 hover:border-white/30 rounded-md px-2.5 py-1.5 transition-colors"
                >
                  <Pencil className="h-3.5 w-3.5" /> Edit limits
                </button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Edit kill-switch limits</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-2">
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      Daily loss limit (₹)
                    </label>
                    <Input
                      type="number"
                      min={1}
                      max={9999999}
                      step={1}
                      value={editLoss}
                      onChange={(e) => setEditLoss(e.target.value)}
                      placeholder="200000"
                      autoFocus
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Max ₹99,99,999. Kill switch trips when daily loss reaches this value.
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      Max trades per day
                    </label>
                    <Input
                      type="number"
                      min={1}
                      max={999}
                      step={1}
                      value={editTrades}
                      onChange={(e) => setEditTrades(e.target.value)}
                      placeholder="50"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Max 999. Kill switch trips when this many orders fire today.
                    </p>
                  </div>
                  <div className="flex gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setEditOpen(false)}
                      disabled={editBusy}
                      className="flex-1 rounded-md border border-white/10 hover:border-white/30 px-4 py-2 text-sm transition-colors disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <GlowButton
                      className="flex-1"
                      disabled={editBusy}
                      onClick={handleSaveLimits}
                    >
                      {editBusy ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : null}
                      Save
                    </GlowButton>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          <div className="space-y-6">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Daily P&amp;L vs max-loss budget</span>
                <span className={dailyPnl >= 0 ? "text-profit font-medium" : "text-loss font-medium"}>
                  {formatCurrency(dailyPnl, { showSign: true })} / {formatCurrency(maxLoss)}
                </span>
              </div>
              <Progress value={lossPct} className="h-3" />
              <p className="text-xs text-muted-foreground mt-1">
                {lossPct}% of daily loss budget used
              </p>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Trades today</span>
                <span className="font-medium">
                  {tradesToday} / {maxTrades || "—"}
                </span>
              </div>
              <Progress value={tradePct} className="h-3" />
              <p className="text-xs text-muted-foreground mt-1">
                {maxTrades > 0 ? `${tradePct}% of daily trade limit used` : "No trade cap configured"}
              </p>
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Action: TRIP or RESET */}
      <motion.div variants={fadeUp} className="flex justify-center">
        {!isTripped ? (
          <Dialog open={tripDialogOpen} onOpenChange={setTripDialogOpen}>
            <DialogTrigger>
              <GlowButton
                variant="danger"
                className="px-8 py-3 text-base"
                onClick={() => setTripConfirm("")}
              >
                <ShieldX className="h-5 w-5 mr-2" /> TRIP KILL SWITCH
              </GlowButton>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Trip Kill Switch — confirm</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <p className="text-sm">
                  This will:
                </p>
                <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                  <li>Block ALL new webhook signals (HTTP 403)</li>
                  <li>Square-off ALL open positions on EVERY active broker</li>
                  <li>Send a CRITICAL Telegram alert</li>
                  <li>Write an audit log entry</li>
                </ul>
                <p className="text-sm">
                  Type <code className="bg-muted px-1.5 py-0.5 rounded text-loss">TRIP</code> to enable the button:
                </p>
                <Input
                  value={tripConfirm}
                  onChange={(e) => setTripConfirm(e.target.value)}
                  placeholder="Type TRIP"
                  autoFocus
                />
                <GlowButton
                  variant="danger"
                  className="w-full"
                  disabled={tripConfirm.trim().toUpperCase() !== "TRIP" || tripBusy}
                  onClick={handleTrip}
                >
                  {tripBusy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <ShieldX className="h-4 w-4 mr-2" />}
                  Confirm trip
                </GlowButton>
              </div>
            </DialogContent>
          </Dialog>
        ) : (
          <Dialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
            <DialogTrigger>
              <GlowButton variant="profit" className="px-8 py-3 text-base">
                <RotateCcw className="h-5 w-5 mr-2" /> Reset Kill Switch
              </GlowButton>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Reset Kill Switch</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <p className="text-sm text-muted-foreground">
                  Re-enables trading. Today&apos;s trade counter and PnL accumulator are zeroed.
                  Open positions on your broker stay open — close them manually if you want flat.
                </p>
                <GlowButton
                  variant="profit"
                  className="w-full"
                  disabled={resetBusy}
                  onClick={handleReset}
                >
                  {resetBusy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RotateCcw className="h-4 w-4 mr-2" />}
                  Confirm reset
                </GlowButton>
              </div>
            </DialogContent>
          </Dialog>
        )}
      </motion.div>

      {/* History */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Recent trip events</h2>
          <div className="space-y-3">
            {(history ?? []).length === 0 ? (
              <p className="text-muted-foreground text-sm py-4 text-center">
                No kill-switch events recorded yet.
              </p>
            ) : (
              (history ?? []).map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <AlertTriangle className="h-5 w-5 text-loss shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <div className="font-medium text-sm">{event.reason}</div>
                    <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-3">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(event.triggered_at).toLocaleString("en-IN")}
                      </span>
                      <span>
                        P&amp;L:{" "}
                        <span className={Number(event.daily_pnl_at_trigger) >= 0 ? "text-profit" : "text-loss"}>
                          {formatCurrency(Number(event.daily_pnl_at_trigger))}
                        </span>
                      </span>
                      <span>{event.positions_squared_off?.length ?? 0} broker actions</span>
                      {event.reset_at && (
                        <span className="text-profit">
                          Reset: {new Date(event.reset_at).toLocaleTimeString("en-IN")}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </GlassmorphismCard>
      </motion.div>
    </motion.div>
  );
}

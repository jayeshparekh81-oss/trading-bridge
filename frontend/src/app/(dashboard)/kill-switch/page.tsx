"use client";

/**
 * Kill Switch.
 *
 * Header comes from the ONE Pro template (ProPage): the title is the sidebar
 * label and the one plain line under it both come from @/lib/nav/pro-nav, so the
 * page keeps no header of its own. The single primary action is the trip — or,
 * once tripped, the reset — which opens a dialog, hence `actionSlot`. "Edit
 * limits" is a secondary action and stays inline in the Today card where the
 * numbers it edits are shown.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import {
  ShieldCheck,
  ShieldX,
  AlertTriangle,
  RotateCcw,
  Clock,
  Loader2,
  Pencil,
} from "lucide-react";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { GlowButton } from "@/shared/ui/glow-button";
import { Input } from "@/shared/ui/input";
import { Progress } from "@/shared/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";
import { ProPage, ProEmpty } from "@/components/dashboard/pro-page";
import { useApi } from "@/shared/api/use-api";
import { api, ApiError } from "@/shared/api/client";
import { formatCurrency, cn } from "@/shared/lib/utils";
import { killSwitchLabel, KILL_SWITCH_TONE_CLASS } from "@/lib/kill-switch-label";
import { toast } from "sonner";
import { NOT_MEASURED } from "@/shared/lib/unknown";

/** The word typed to confirm "Sab band" (a guard against a stray tap — Hinglish, not "TRIP"). */
const CONFIRM_WORD = "BAND";

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
  // The DISPLAYED state comes from the one owner module (@/lib/kill-switch-label)
  // so this page, the /strategies summary and the Overview cannot invent three
  // different words for one switch. `isTripped` above is untouched: it gates the
  // trip-vs-reset action below and must keep reading the wire value directly.
  const label = killSwitchLabel(status);
  // A missing figure is NOT a zero (founder's rule, 26 Sep, point 10): the page
  // used to print "+₹0 / ₹0 · 0% used" for a switch with no limit and no read.
  const dailyPnlKnown = status?.daily_pnl != null && status.daily_pnl !== "" && Number.isFinite(Number(status.daily_pnl));
  const dailyPnl = dailyPnlKnown ? Number(status!.daily_pnl) : 0;
  const maxLoss = Number(status?.max_daily_loss_inr ?? 0);
  const lossLimitSet = Number.isFinite(maxLoss) && maxLoss > 0;
  const lossUsed = Math.max(0, -dailyPnl);
  const lossPct = maxLoss > 0 ? Math.min(100, Math.round((lossUsed / maxLoss) * 100)) : 0;
  const tradesToday = status?.trades_today ?? 0;
  const maxTrades = status?.max_daily_trades ?? 0;
  const tradePct = maxTrades > 0 ? Math.min(100, Math.round((tradesToday / maxTrades) * 100)) : 0;

  async function handleTrip() {
    if (tripConfirm.trim().toUpperCase() !== CONFIRM_WORD) {
      toast.error(`Pakka karne ke liye box me ${CONFIRM_WORD} likho.`);
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
      toast.success("Sab band kar diya. Khuli positions broker par market daam par band ki ja rahi hain.");
      setTripDialogOpen(false);
      setTripConfirm("");
      refetch();
      refetchHistory();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Sab band nahi ho paaya — turant Dhan app se positions band karo, phir yahan dobara try karo.";
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
      toast.success("Trading dobara chalu ho gayi.");
      setResetDialogOpen(false);
      refetch();
      refetchHistory();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Dobara chalu nahi ho paaya — 1 minute baad phir try karo.";
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
      toast.error("Loss limit ₹1 se ₹99,99,999 ke beech rakho.");
      return;
    }
    if (!Number.isInteger(tradesNum) || tradesNum <= 0 || tradesNum >= 1000) {
      toast.error("Order limit 1 se 999 ke beech ka poora number rakho.");
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
      toast.success("Limit save ho gayi");
      setEditOpen(false);
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Limit save nahi ho payi — dobara try karo.";
      toast.error(msg);
    } finally {
      setEditBusy(false);
    }
  }

  const showLoading = isLoading && !status;
  const showError = Boolean(error) && !status;

  // The ONE primary action: trip while running, reset once tripped. Withheld
  // until the state is known — the button must never claim a state it has not
  // read.
  const primaryAction = status ? (
    !isTripped ? (
      <Dialog open={tripDialogOpen} onOpenChange={setTripDialogOpen}>
        <DialogTrigger
          render={
            <GlowButton
              variant="danger"
              size="sm"
              onClick={() => setTripConfirm("")}
            />
          }
        >
          <ShieldX className="h-4 w-4 mr-2" /> Sab band karo
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sab band karna pakka hai?</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm">
              Yeh button dabane par:
            </p>
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
              <li>Koi naya signal order nahi bhejega</li>
              <li>Har jude broker par jo bhi position khuli hai, woh market daam par band karne ka order jaayega</li>
              <li>Yeh kab aur kyun hua, neeche history me likha jaayega</li>
            </ul>
            <p className="text-sm">
              Galti se na dabe, isliye neeche box me <code className="bg-muted px-1.5 py-0.5 rounded text-loss">{CONFIRM_WORD}</code> likho:
            </p>
            <Input
              value={tripConfirm}
              onChange={(e) => setTripConfirm(e.target.value)}
              placeholder={`${CONFIRM_WORD} likho`}
              autoFocus
            />
            <GlowButton
              variant="danger"
              className="w-full"
              disabled={tripConfirm.trim().toUpperCase() !== CONFIRM_WORD || tripBusy}
              onClick={handleTrip}
            >
              {tripBusy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <ShieldX className="h-4 w-4 mr-2" />}
              Haan, sab band karo
            </GlowButton>
          </div>
        </DialogContent>
      </Dialog>
    ) : (
      <Dialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
        <DialogTrigger
          render={<GlowButton variant="profit" size="sm" />}
        >
          <RotateCcw className="h-4 w-4 mr-2" /> Trading dobara chalu karo
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Trading dobara chalu karein?</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-muted-foreground">
              Naye signal phir se order bhejenge. Aaj ki gintii (trades aur P&amp;L) naye sire se shuru hogi.
              Jo position broker par abhi bhi khuli hai, woh khuli hi rahegi — band karni ho to Dhan app se khud band karo.
            </p>
            <GlowButton
              variant="profit"
              className="w-full"
              disabled={resetBusy}
              onClick={handleReset}
            >
              {resetBusy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RotateCcw className="h-4 w-4 mr-2" />}
              Haan, dobara chalu karo
            </GlowButton>
          </div>
        </DialogContent>
      </Dialog>
    )
  ) : undefined;

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto"
    >
      <ProPage actionSlot={primaryAction}>
        {showLoading ? (
          <motion.div variants={fadeUp}>
            <GlassmorphismCard hover={false}>
              <div className="py-12 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            </GlassmorphismCard>
          </motion.div>
        ) : showError ? (
          <motion.div variants={fadeUp}>
            <GlassmorphismCard hover={false}>
              <div className="text-center py-8">
                <AlertTriangle className="h-12 w-12 text-loss mx-auto mb-3" />
                <h2 className="text-lg font-semibold mb-1">&ldquo;Sab band&rdquo; switch ki haalat abhi pata nahi chali</h2>
                <p className="text-sm text-muted-foreground mb-1">{error}</p>
                <p className="text-sm text-muted-foreground mb-4">
                  Hum switch ko padh nahi paaye — iska matlab yeh nahi ki woh band ya chalu hai. Turant sab rokna ho to
                  Dhan app se positions band karo. Neeche button se dobara dekho.
                </p>
                <GlowButton onClick={refetch} size="sm">Dobara dekho</GlowButton>
              </div>
            </GlassmorphismCard>
          </motion.div>
        ) : (
          <>
            {/* Status banner */}
            <motion.div variants={fadeUp}>
              <GlassmorphismCard
                glow={label?.kind === "armed" ? "profit" : "none"}
                className={cn(isTripped && "border-loss/40 shadow-glow-loss-soft")}
                hover={false}
              >
                <div className="flex items-center gap-4">
                  {isTripped ? (
                    <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ repeat: Infinity, duration: 1.5 }}>
                      <ShieldX className="h-12 w-12 text-loss" />
                    </motion.div>
                  ) : (
                    <ShieldCheck
                      className={cn(
                        "h-12 w-12",
                        label ? KILL_SWITCH_TONE_CLASS[label.tone] : "text-muted-foreground",
                      )}
                    />
                  )}
                  <div className="flex-1">
                    <div
                      className={cn(
                        "text-3xl font-bold",
                        label ? KILL_SWITCH_TONE_CLASS[label.tone] : "text-muted-foreground",
                      )}
                    >
                      {label?.word}
                    </div>
                    <p className="text-muted-foreground text-sm">
                      {isTripped
                        ? `Band kiya gaya${status?.tripped_at ? ` — ${new Date(status.tripped_at).toLocaleString("en-IN")}` : ""} · wajah: ${status?.trip_reason ?? "wajah record nahi hui"}`
                        : label?.kind === "off"
                          ? "Orders ja sakte hain, par apne aap kuch nahi rukega — \"Limit badlo\" se roz ka loss aur trade ki limit set karo."
                          : "Trading chalu hai. Naye signal order bhejenge."}
                    </p>
                  </div>
                </div>
              </GlassmorphismCard>
            </motion.div>

            {/* The facts that used to sit in the bespoke header. */}
            <motion.div variants={fadeUp}>
              <p className="text-xs text-muted-foreground max-w-2xl">
                &ldquo;Sab band&rdquo; turant naye order rok deta hai aur khuli positions broker par market daam par band
                karwata hai — exact daam ka vaada nahi. Yeh page har 15 second me khud update hota hai.
              </p>
            </motion.div>

            {/* Daily metrics */}
            <motion.div variants={fadeUp}>
              <GlassmorphismCard hover={false}>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold">Aaj</h2>
                  <Dialog open={editOpen} onOpenChange={setEditOpen}>
                    <DialogTrigger
                      render={
                        <button
                          type="button"
                          onClick={openEdit}
                          className="flex min-h-11 items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground border border-white/10 hover:border-white/30 rounded-md px-3 transition-colors"
                        />
                      }
                    >
                      <Pencil className="h-3.5 w-3.5" /> Limit badlo
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>&ldquo;Sab band&rdquo; kab khud dabe</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4 py-2">
                        <div>
                          <label className="text-sm font-medium mb-1.5 block">
                            Ek din me zyada se zyada kitna nuksaan (₹)
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
                            Aaj ka nuksaan itna ho jaaye to &ldquo;Sab band&rdquo; apne aap dab jaayega. Sabse zyada ₹99,99,999.
                          </p>
                        </div>
                        <div>
                          <label className="text-sm font-medium mb-1.5 block">
                            Ek din me zyada se zyada kitne order
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
                            Aaj itne order ho jaayein to &ldquo;Sab band&rdquo; apne aap dab jaayega. Sabse zyada 999.
                          </p>
                        </div>
                        <div className="flex gap-2 pt-2">
                          <button
                            type="button"
                            onClick={() => setEditOpen(false)}
                            disabled={editBusy}
                            className="flex-1 rounded-md border border-white/10 hover:border-white/30 px-4 py-2 text-sm transition-colors disabled:opacity-50"
                          >
                            Rehne do
                          </button>
                          <GlowButton
                            className="flex-1"
                            disabled={editBusy}
                            onClick={handleSaveLimits}
                          >
                            {editBusy ? (
                              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            ) : null}
                            Save karo
                          </GlowButton>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
                <div className="space-y-6">
                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-muted-foreground">Aaj ka P&amp;L (hamara hisaab) / roz ki loss limit</span>
                      <span className={!dailyPnlKnown ? "text-muted-foreground font-medium" : dailyPnl >= 0 ? "text-profit font-medium" : "text-loss font-medium"}>
                        {dailyPnlKnown ? formatCurrency(dailyPnl, { showSign: true }) : NOT_MEASURED} / {lossLimitSet ? formatCurrency(maxLoss) : "limit set nahi"}
                      </span>
                    </div>
                    {lossLimitSet && dailyPnlKnown ? <Progress value={lossPct} className="h-3" /> : null}
                    <p className="text-xs text-muted-foreground mt-1">
                      {!lossLimitSet
                        ? "Roz ki loss limit set nahi — isliye nuksaan par switch apne aap nahi dabega. \"Limit badlo\" se set karo."
                        : !dailyPnlKnown
                          ? "Aaj ka P&L abhi padh nahi paaye — isliye kitna use hua, yeh nahi bata sakte."
                          : `Roz ki loss limit ka ${lossPct}% use hua`}
                    </p>
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-muted-foreground">Aaj ke order / roz ki limit</span>
                      <span className="font-medium">
                        {tradesToday} / {maxTrades > 0 ? maxTrades : "limit set nahi"}
                      </span>
                    </div>
                    <Progress value={tradePct} className="h-3" />
                    <p className="text-xs text-muted-foreground mt-1">
                      {maxTrades > 0 ? `Roz ki order limit ka ${tradePct}% use hua` : "Order ki koi roz ki limit set nahi"}
                    </p>
                  </div>
                </div>
              </GlassmorphismCard>
            </motion.div>

            {/* History */}
            <motion.div variants={fadeUp}>
              {(history ?? []).length === 0 ? (
                <ProEmpty
                  headline="Abhi tak koi trip nahi hua"
                  next="Is account par &ldquo;Sab band&rdquo; kabhi dabaya nahi gaya. Upar &ldquo;Limit badlo&rdquo; se roz ka loss aur order limit set karo — jab bhi yeh dabega, uski wajah yahan likhi jaayegi."
                />
              ) : (
                <GlassmorphismCard hover={false}>
                  <h2 className="text-lg font-semibold mb-4">Kab kab sab band hua</h2>
                  <div className="space-y-3">
                    {(history ?? []).map((event) => (
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
                            <span>{event.positions_squared_off ? `${event.positions_squared_off.length} position band karne ke order` : "kitne order gaye — record nahi"}</span>
                            {event.reset_at && (
                              <span className="text-profit">
                                Dobara chalu: {new Date(event.reset_at).toLocaleTimeString("en-IN")}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </GlassmorphismCard>
              )}
            </motion.div>
          </>
        )}
      </ProPage>
    </motion.div>
  );
}

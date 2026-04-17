"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck, ShieldX, AlertTriangle, RotateCcw, Clock } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { mockDashboard } from "@/lib/mock-data";
import { useApi } from "@/lib/use-api";
import { api } from "@/lib/api";
import { formatCurrency, cn } from "@/lib/utils";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function KillSwitchPage() {
  const d = mockDashboard;
  const isActive = d.killSwitchStatus === "ACTIVE";
  const lossUsed = d.killSwitchMaxLoss - d.killSwitchRemaining;
  const lossPct = Math.round((lossUsed / d.killSwitchMaxLoss) * 100);
  const tradePct = Math.round((d.totalTradesToday / d.killSwitchMaxTrades) * 100);

  const [maxLoss, setMaxLoss] = useState(String(d.killSwitchMaxLoss));
  const [maxTrades, setMaxTrades] = useState(String(d.killSwitchMaxTrades));

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-accent-blue" /> Kill Switch
        </h1>
      </motion.div>

      {/* Status Banner */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard glow={isActive ? "profit" : "none"} className={cn(!isActive && "border-loss/30 shadow-[0_0_25px_rgba(255,77,106,0.15)]")}>
          <div className="flex items-center gap-4">
            {isActive ? (
              <ShieldCheck className="h-12 w-12 text-profit" />
            ) : (
              <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ repeat: Infinity, duration: 1.5 }}>
                <ShieldX className="h-12 w-12 text-loss" />
              </motion.div>
            )}
            <div>
              <div className={cn("text-3xl font-bold", isActive ? "text-profit" : "text-loss")}>
                {isActive ? "SAFE" : "TRIPPED"}
              </div>
              <p className="text-muted-foreground text-sm">
                {isActive ? "Kill switch is active. Trading is allowed." : "Kill switch has been triggered. All trading is paused."}
              </p>
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Dashboard */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Dashboard</h2>
          <div className="space-y-6">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Daily P&amp;L</span>
                <span className={d.todayPnl >= 0 ? "text-profit font-medium" : "text-loss font-medium"}>
                  {formatCurrency(d.todayPnl, { showSign: true })} / {formatCurrency(d.killSwitchMaxLoss)} max loss
                </span>
              </div>
              <Progress value={Math.min(lossPct, 100)} className="h-3" />
              <p className="text-xs text-muted-foreground mt-1">{lossPct}% of daily loss budget used</p>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Trades Today</span>
                <span className="font-medium">{d.totalTradesToday} / {d.killSwitchMaxTrades}</span>
              </div>
              <Progress value={tradePct} className="h-3" />
              <p className="text-xs text-muted-foreground mt-1">{tradePct}% of daily trade limit used</p>
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Configuration */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Configuration</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Max Daily Loss (INR)</label>
              <Input value={maxLoss} onChange={(e) => setMaxLoss(e.target.value)} className="mt-1" />
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Max Daily Trades</label>
              <Input value={maxTrades} onChange={(e) => setMaxTrades(e.target.value)} className="mt-1" />
            </div>
            <div className="flex items-center gap-3">
              <div className={cn("h-5 w-9 rounded-full relative cursor-pointer transition-colors", d.killSwitchAutoSquareOff ? "bg-profit" : "bg-muted")}>
                <div className={cn("h-4 w-4 rounded-full bg-white absolute top-0.5 transition-all", d.killSwitchAutoSquareOff ? "left-4" : "left-0.5")} />
              </div>
              <span className="text-sm">Auto Square-Off</span>
            </div>
          </div>
          <GlowButton className="mt-4" size="sm">Save Changes</GlowButton>
        </GlassmorphismCard>
      </motion.div>

      {/* Trip History */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Trip History</h2>
          <div className="space-y-3">
            {d.killSwitchHistory.map((event) => (
              <div key={event.id} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <AlertTriangle className="h-5 w-5 text-loss shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="font-medium text-sm">{event.reason}</div>
                  <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-3">
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(event.triggeredAt).toLocaleString("en-IN")}</span>
                    <span>P&L: <span className="text-loss">{formatCurrency(event.dailyPnl)}</span></span>
                    <span>{event.positionsClosed} positions closed</span>
                    {event.resetAt && <span className="text-profit">Reset: {new Date(event.resetAt).toLocaleTimeString("en-IN")}</span>}
                  </div>
                </div>
              </div>
            ))}
            {d.killSwitchHistory.length === 0 && (
              <p className="text-muted-foreground text-sm py-4 text-center">No trip events</p>
            )}
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Manual Reset */}
      {!isActive && (
        <motion.div variants={fadeUp}>
          <Dialog>
            <DialogTrigger>
              <GlowButton variant="profit"><RotateCcw className="h-4 w-4 mr-2" />Manual Reset</GlowButton>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Reset Kill Switch</DialogTitle></DialogHeader>
              <p className="text-muted-foreground text-sm py-2">Are you sure? This will re-enable trading for your account.</p>
              <GlowButton variant="profit" className="w-full">Confirm Reset</GlowButton>
            </DialogContent>
          </Dialog>
        </motion.div>
      )}
    </motion.div>
  );
}

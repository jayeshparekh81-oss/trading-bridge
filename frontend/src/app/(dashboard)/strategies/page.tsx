"use client";

import { motion } from "framer-motion";
import { Bot, Plus, Pause, Play, Pencil, Trash2, ExternalLink, Wifi, WifiOff } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { ProfitLossText } from "@/components/ui/profit-loss-text";
import { Badge } from "@/components/ui/badge";
import { mockDashboard } from "@/lib/mock-data";
import { formatCurrency, cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function StrategiesPage() {
  const { strategies } = mockDashboard;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><Bot className="h-6 w-6 text-accent-blue" /> My Strategies</h1>
          <p className="text-muted-foreground text-sm mt-1">{strategies.filter(s => s.isActive).length} active, {strategies.filter(s => !s.isActive).length} paused</p>
        </div>
        <Dialog>
          <DialogTrigger><GlowButton size="sm"><Plus className="h-4 w-4 mr-2" />New Strategy</GlowButton></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Create Strategy</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-4">
              <div><label className="text-sm font-medium">Strategy Name</label><Input placeholder="e.g. Nifty Scalper" className="mt-1" /></div>
              <div><label className="text-sm font-medium">Broker</label>
                <select className="w-full h-9 px-3 mt-1 rounded-lg bg-muted/50 border border-border text-sm">
                  <option>Fyers</option><option>Dhan</option>
                </select>
              </div>
              <div><label className="text-sm font-medium">Webhook</label>
                <select className="w-full h-9 px-3 mt-1 rounded-lg bg-muted/50 border border-border text-sm">
                  <option>Nifty Strategy Webhook</option><option>BankNifty Webhook</option>
                </select>
              </div>
              <div><label className="text-sm font-medium">Symbol Whitelist (comma-separated)</label><Input placeholder="NIFTY, BANKNIFTY, RELIANCE" className="mt-1" /></div>
              <GlowButton className="w-full">Create Strategy</GlowButton>
            </div>
          </DialogContent>
        </Dialog>
      </motion.div>

      <div className="space-y-4">
        {strategies.map((s) => (
          <motion.div key={s.id} variants={fadeUp}>
            <GlassmorphismCard glow={s.isActive ? "profit" : "none"} className={cn(!s.isActive && "opacity-70")}>
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "h-12 w-12 rounded-xl flex items-center justify-center",
                    s.isActive ? "bg-profit/10 text-profit" : "bg-muted text-muted-foreground"
                  )}>
                    <Bot className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-lg">{s.name}</span>
                      {s.isActive ? (
                        <Badge variant="outline" className="text-xs text-profit border-profit/30">Active</Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs text-accent-gold border-accent-gold/30">Paused</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                      <span>Broker: {s.broker}</span>
                      <span className="flex items-center gap-1">
                        {s.webhookConnected ? <Wifi className="h-3.5 w-3.5 text-profit" /> : <WifiOff className="h-3.5 w-3.5 text-loss" />}
                        {s.webhookConnected ? "Connected" : "Disconnected"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                  <div>
                    <div className="text-xs text-muted-foreground">Today</div>
                    <ProfitLossText value={s.todayPnl} size="sm" animated={false} />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Month</div>
                    <ProfitLossText value={s.monthPnl} size="sm" animated={false} />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Win Rate</div>
                    <div className="font-semibold">{s.winRate}%</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Trades Today</div>
                    <div className="font-semibold">{s.todayTrades}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {s.isActive ? (
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border border-accent-gold/30 text-accent-gold hover:bg-accent-gold/10 transition-colors">
                      <Pause className="h-3.5 w-3.5" />Pause
                    </button>
                  ) : (
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border border-profit/30 text-profit hover:bg-profit/10 transition-colors">
                      <Play className="h-3.5 w-3.5" />Resume
                    </button>
                  )}
                  <button className="p-1.5 rounded-lg hover:bg-accent transition-colors"><Pencil className="h-4 w-4" /></button>
                  <a href="/trades" className="p-1.5 rounded-lg hover:bg-accent transition-colors"><ExternalLink className="h-4 w-4" /></a>
                  {!s.isActive && <button className="p-1.5 rounded-lg hover:bg-loss/10 transition-colors"><Trash2 className="h-4 w-4 text-loss" /></button>}
                </div>
              </div>
            </GlassmorphismCard>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

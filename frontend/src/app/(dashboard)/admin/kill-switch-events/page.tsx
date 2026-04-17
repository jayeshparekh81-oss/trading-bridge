"use client";

import { motion } from "framer-motion";
import { ShieldAlert, Clock, RotateCcw, User, AlertTriangle, TrendingDown } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { adminMockData } from "@/lib/admin-mock-data";
import { formatCurrency, cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function KillSwitchEventsPage() {
  const events = adminMockData.killSwitchEvents;
  const todayTrips = events.filter((e) => new Date(e.triggeredAt).toDateString() === new Date().toDateString()).length;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-6">
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-accent-purple" /> Kill Switch Events (All Users)
        </h1>
        <p className="text-muted-foreground text-sm mt-1">Monitor all kill switch trips across the platform</p>
      </motion.div>

      {/* Summary */}
      <motion.div variants={fadeUp} className="grid grid-cols-3 gap-4">
        <GlassmorphismCard className="p-4 text-center">
          <div className="text-2xl font-bold text-loss">{todayTrips}</div>
          <div className="text-xs text-muted-foreground">Trips Today</div>
        </GlassmorphismCard>
        <GlassmorphismCard className="p-4 text-center">
          <div className="text-2xl font-bold text-accent-gold">{events.length}</div>
          <div className="text-xs text-muted-foreground">This Week</div>
        </GlassmorphismCard>
        <GlassmorphismCard className="p-4 text-center">
          <div className="text-2xl font-bold">85%</div>
          <div className="text-xs text-muted-foreground">Daily Loss Limit</div>
        </GlassmorphismCard>
      </motion.div>

      {/* Event List */}
      <div className="space-y-4">
        {events.map((event) => (
          <motion.div key={event.id} variants={fadeUp}>
            <GlassmorphismCard glow={!event.resetAt ? "none" : undefined} className={cn(!event.resetAt && "border-loss/20")}>
              <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className="h-10 w-10 rounded-lg bg-loss/10 text-loss flex items-center justify-center shrink-0">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{event.userName}</span>
                      {!event.resetAt ? (
                        <Badge variant="outline" className="text-xs text-loss border-loss/30">Active</Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs text-profit border-profit/30">Reset</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">{event.reason}</p>
                    <div className="flex flex-wrap gap-4 mt-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(event.triggeredAt).toLocaleString("en-IN")}</span>
                      <span className="flex items-center gap-1"><TrendingDown className="h-3 w-3 text-loss" />P&L: <span className="text-loss">{formatCurrency(event.dailyPnl)}</span></span>
                      <span>{event.positionsClosed} positions closed</span>
                      <span>Square-off: {(event.squareOffTime / 1000).toFixed(1)}s</span>
                    </div>
                    {event.resetAt && (
                      <p className="text-xs text-profit mt-1">
                        Reset: {new Date(event.resetAt).toLocaleString("en-IN")} by {event.resetBy}
                      </p>
                    )}
                  </div>
                </div>

                {!event.resetAt && (
                  <Dialog>
                    <DialogTrigger>
                      <GlowButton variant="profit" size="sm"><RotateCcw className="h-3.5 w-3.5 mr-1.5" />Admin Reset</GlowButton>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader><DialogTitle>Reset Kill Switch for {event.userName}?</DialogTitle></DialogHeader>
                      <p className="text-sm text-muted-foreground py-2">This will re-enable trading for this user. Make sure the underlying issue is resolved.</p>
                      <GlowButton variant="profit" className="w-full">Confirm Reset</GlowButton>
                    </DialogContent>
                  </Dialog>
                )}
              </div>
            </GlassmorphismCard>
          </motion.div>
        ))}
      </div>

      {events.length === 0 && (
        <GlassmorphismCard hover={false} className="py-16 text-center">
          <ShieldAlert className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">No kill switch events</p>
        </GlassmorphismCard>
      )}
    </motion.div>
  );
}

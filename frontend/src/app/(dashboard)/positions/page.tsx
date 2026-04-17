"use client";

import { motion } from "framer-motion";
import { LineChart, AlertTriangle } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { ProfitLossText } from "@/components/ui/profit-loss-text";
import { GlowButton } from "@/components/ui/glow-button";
import { mockDashboard } from "@/lib/mock-data";
import { formatCurrency, cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function PositionsPage() {
  const { positions } = mockDashboard;
  const totalPnl = positions.reduce((sum, p) => sum + p.pnl, 0);

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-6">
      <motion.div variants={fadeUp} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <LineChart className="h-6 w-6 text-accent-blue" /> Live Positions
          </h1>
          <p className="text-muted-foreground text-sm mt-1 flex items-center gap-2">
            {positions.length} open positions &bull; Total:
            <ProfitLossText value={totalPnl} size="sm" glow animated={false} />
          </p>
        </div>
        <Dialog>
          <DialogTrigger>
            <GlowButton variant="danger" size="sm">
              <AlertTriangle className="h-4 w-4 mr-2" />Square Off All
            </GlowButton>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Confirm Square Off All</DialogTitle></DialogHeader>
            <p className="text-muted-foreground text-sm py-4">
              This will close ALL {positions.length} open positions immediately. This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button className="px-4 py-2 rounded-lg border border-border hover:bg-accent transition-colors text-sm">Cancel</button>
              <GlowButton variant="danger" size="sm">Confirm Square Off</GlowButton>
            </div>
          </DialogContent>
        </Dialog>
      </motion.div>

      {/* Positions grid */}
      <div className="space-y-3">
        {positions.map((pos) => {
          const isProfit = pos.pnl >= 0;
          const pnlPercent = ((pos.ltp - pos.avgPrice) / pos.avgPrice) * 100;
          return (
            <motion.div key={pos.id} variants={fadeUp}>
              <GlassmorphismCard
                glow={isProfit ? "profit" : "none"}
                className="p-5"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className={cn(
                      "h-10 w-10 rounded-lg flex items-center justify-center text-xs font-bold",
                      isProfit ? "bg-profit/10 text-profit" : "bg-loss/10 text-loss"
                    )}>
                      {pos.side === "LONG" ? "L" : "S"}
                    </div>
                    <div>
                      <div className="font-semibold">{pos.symbol}</div>
                      <div className="text-xs text-muted-foreground">
                        {pos.broker} &bull; Qty: {pos.quantity} &bull; {pos.side}
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-6 text-right">
                    <div>
                      <div className="text-xs text-muted-foreground">Avg Price</div>
                      <div className="font-medium">{formatCurrency(pos.avgPrice)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">LTP</div>
                      <div className="font-medium">{formatCurrency(pos.ltp)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">P&amp;L</div>
                      <div className={cn("font-bold", isProfit ? "text-profit" : "text-loss")}>
                        {formatCurrency(pos.pnl, { showSign: true })}
                        <span className="text-xs ml-1">({pnlPercent >= 0 ? "+" : ""}{pnlPercent.toFixed(1)}%)</span>
                      </div>
                    </div>
                  </div>
                  <button className="px-3 py-1.5 rounded-lg text-xs border border-loss/30 text-loss hover:bg-loss/10 transition-colors whitespace-nowrap">
                    Square Off
                  </button>
                </div>
              </GlassmorphismCard>
            </motion.div>
          );
        })}
      </div>

      {positions.length === 0 && (
        <GlassmorphismCard hover={false} className="py-16 text-center">
          <p className="text-muted-foreground">No open positions</p>
        </GlassmorphismCard>
      )}
    </motion.div>
  );
}

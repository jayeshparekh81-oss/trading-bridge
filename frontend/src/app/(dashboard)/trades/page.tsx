"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ListOrdered, Download, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { TradeRow } from "@/components/ui/trade-row";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { allTrades, mockDashboard } from "@/lib/mock-data";
import { formatCurrency, cn } from "@/lib/utils";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function TradesPage() {
  const [search, setSearch] = useState("");
  const [brokerFilter, setBrokerFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = allTrades.filter((t) => {
    if (search && !t.symbol.toLowerCase().includes(search.toLowerCase())) return false;
    if (brokerFilter !== "all" && t.broker !== brokerFilter) return false;
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    return true;
  });

  const wins = filtered.filter((t) => t.pnl > 0).length;
  const losses = filtered.filter((t) => t.pnl < 0).length;
  const totalPnl = filtered.reduce((sum, t) => sum + t.pnl, 0);
  const winRate = filtered.length > 0 ? Math.round((wins / filtered.length) * 100) : 0;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      <motion.div variants={fadeUp} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ListOrdered className="h-6 w-6 text-accent-blue" /> Trade History
          </h1>
          <p className="text-muted-foreground text-sm mt-1">{filtered.length} trades</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border hover:bg-accent transition-colors text-sm">
          <Download className="h-4 w-4" />Export CSV
        </button>
      </motion.div>

      {/* Filters */}
      <motion.div variants={fadeUp} className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search symbol..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 bg-muted/50" />
        </div>
        <select value={brokerFilter} onChange={(e) => setBrokerFilter(e.target.value)} className="h-9 px-3 rounded-lg bg-muted/50 border border-border text-sm">
          <option value="all">All Brokers</option>
          <option value="Fyers">Fyers</option>
          <option value="Dhan">Dhan</option>
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-9 px-3 rounded-lg bg-muted/50 border border-border text-sm">
          <option value="all">All Status</option>
          <option value="complete">Complete</option>
          <option value="pending">Pending</option>
          <option value="rejected">Rejected</option>
        </select>
      </motion.div>

      {/* Table */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  <th className="text-left py-2.5 px-4 text-xs font-medium text-muted-foreground uppercase">Time</th>
                  <th className="text-left py-2.5 px-4 text-xs font-medium text-muted-foreground uppercase">Action</th>
                  <th className="text-left py-2.5 px-4 text-xs font-medium text-muted-foreground uppercase">Symbol</th>
                  <th className="text-right py-2.5 px-4 text-xs font-medium text-muted-foreground uppercase">Price</th>
                  <th className="text-right py-2.5 px-4 text-xs font-medium text-muted-foreground uppercase">P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((trade) => (
                  <TradeRow key={trade.id} trade={trade} />
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 && (
            <div className="py-12 text-center text-muted-foreground">No trades found</div>
          )}
        </GlassmorphismCard>
      </motion.div>

      {/* Summary */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false} className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap gap-6 text-sm">
            <span>{filtered.length} trades</span>
            <span className="text-profit">{wins} wins</span>
            <span className="text-loss">{losses} losses</span>
          </div>
          <div className="flex flex-wrap gap-6 text-sm font-semibold">
            <span>Total P&L: <span className={totalPnl >= 0 ? "text-profit" : "text-loss"}>{formatCurrency(totalPnl, { showSign: true })}</span></span>
            <span>Win Rate: {winRate}%</span>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Pagination */}
      <motion.div variants={fadeUp} className="flex items-center justify-center gap-4 text-sm">
        <button className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors" disabled>
          <ChevronLeft className="h-4 w-4" />Prev
        </button>
        <span className="text-muted-foreground">Page 1 of 1</span>
        <button className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors" disabled>
          Next<ChevronRight className="h-4 w-4" />
        </button>
      </motion.div>
    </motion.div>
  );
}

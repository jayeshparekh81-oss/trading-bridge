"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Users, Plus, Search, ChevronLeft, ChevronRight, Shield, ShieldOff, RotateCcw, UserCheck, UserX, X, Crown } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { adminMockData, type AdminUser } from "@/lib/admin-mock-data";
import { formatCurrency, cn, relativeTime } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

const statusBadge = {
  active: "text-profit border-profit/30",
  trial: "text-accent-gold border-accent-gold/30",
  locked: "text-loss border-loss/30",
  inactive: "text-muted-foreground border-border",
};

export default function AdminUsersPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  const filtered = adminMockData.users.filter((u) => {
    if (search && !u.name.toLowerCase().includes(search.toLowerCase()) && !u.email.toLowerCase().includes(search.toLowerCase())) return false;
    if (statusFilter !== "all" && u.status !== statusFilter) return false;
    return true;
  });

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      <motion.div variants={fadeUp} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><Users className="h-6 w-6 text-accent-purple" /> User Management</h1>
          <p className="text-muted-foreground text-sm mt-1">{adminMockData.users.length} total users</p>
        </div>
        <Dialog>
          <DialogTrigger><GlowButton size="sm" variant="primary"><Plus className="h-4 w-4 mr-2" />Create User</GlowButton></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Create User (Beta Invite)</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-4">
              <div><label className="text-sm font-medium">Full Name</label><Input placeholder="Name" className="mt-1" /></div>
              <div><label className="text-sm font-medium">Email</label><Input type="email" placeholder="email@example.com" className="mt-1" /></div>
              <div><label className="text-sm font-medium">Password</label><Input type="password" placeholder="Temp password" className="mt-1" /></div>
              <div><label className="text-sm font-medium">Plan</label>
                <select className="w-full h-9 px-3 mt-1 rounded-lg bg-muted/50 border border-border text-sm"><option>Free</option><option>Basic</option><option>Pro</option></select>
              </div>
              <GlowButton className="w-full">Create User</GlowButton>
            </div>
          </DialogContent>
        </Dialog>
      </motion.div>

      {/* Filters */}
      <motion.div variants={fadeUp} className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search name or email..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 bg-muted/50" />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-9 px-3 rounded-lg bg-muted/50 border border-border text-sm">
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="trial">Trial</option>
          <option value="locked">Locked</option>
          <option value="inactive">Inactive</option>
        </select>
      </motion.div>

      <div className="flex gap-6">
        {/* Table */}
        <motion.div variants={fadeUp} className="flex-1">
          <GlassmorphismCard hover={false} className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/[0.08]">
                    {["Name", "Email", "Plan", "Status"].map((h) => (
                      <th key={h} className="text-left py-2.5 px-4 text-xs font-medium text-muted-foreground uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((user) => (
                    <tr
                      key={user.id}
                      onClick={() => setSelectedUser(user)}
                      className={cn(
                        "border-b border-white/[0.04] cursor-pointer transition-colors hover:bg-white/[0.03]",
                        selectedUser?.id === user.id && "bg-accent-purple/5"
                      )}
                    >
                      <td className="py-3 px-4 font-medium flex items-center gap-2">
                        {user.name}
                        {user.isAdmin && <Crown className="h-3.5 w-3.5 text-accent-gold" />}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">{user.email}</td>
                      <td className="py-3 px-4"><Badge variant="outline" className="text-xs capitalize">{user.plan}</Badge></td>
                      <td className="py-3 px-4"><Badge variant="outline" className={cn("text-xs capitalize", statusBadge[user.status])}>{user.status}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassmorphismCard>
        </motion.div>

        {/* Detail Panel */}
        <AnimatePresence>
          {selectedUser && (
            <motion.div
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 40 }}
              className="hidden lg:block w-80 shrink-0"
            >
              <GlassmorphismCard hover={false} className="sticky top-24">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">User Details</h3>
                  <button onClick={() => setSelectedUser(null)} className="p-1 rounded hover:bg-accent"><X className="h-4 w-4" /></button>
                </div>

                <div className="space-y-4">
                  <div>
                    <div className="font-semibold text-lg">{selectedUser.name}</div>
                    <div className="text-sm text-muted-foreground">{selectedUser.email}</div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div><span className="text-muted-foreground">Trades</span><div className="font-medium">{selectedUser.totalTrades}</div></div>
                    <div><span className="text-muted-foreground">Win Rate</span><div className="font-medium">{selectedUser.winRate}%</div></div>
                    <div><span className="text-muted-foreground">Total P&L</span><div className={cn("font-medium", selectedUser.totalPnl >= 0 ? "text-profit" : "text-loss")}>{formatCurrency(selectedUser.totalPnl, { showSign: true })}</div></div>
                    <div><span className="text-muted-foreground">Brokers</span><div className="font-medium">{selectedUser.brokersConnected}</div></div>
                    <div><span className="text-muted-foreground">Last Login</span><div className="font-medium text-xs">{relativeTime(selectedUser.lastLogin)}</div></div>
                    <div><span className="text-muted-foreground">IP</span><div className="font-medium text-xs font-mono">{selectedUser.lastIp}</div></div>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-white/[0.08]">
                    {selectedUser.status === "active" ? (
                      <button className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm border border-loss/30 text-loss hover:bg-loss/10 transition-colors">
                        <UserX className="h-4 w-4" />Deactivate
                      </button>
                    ) : (
                      <button className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm border border-profit/30 text-profit hover:bg-profit/10 transition-colors">
                        <UserCheck className="h-4 w-4" />Activate
                      </button>
                    )}
                    <button className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm border border-accent-purple/30 text-accent-purple hover:bg-accent-purple/10 transition-colors">
                      {selectedUser.isAdmin ? <ShieldOff className="h-4 w-4" /> : <Shield className="h-4 w-4" />}
                      {selectedUser.isAdmin ? "Revoke Admin" : "Grant Admin"}
                    </button>
                    <button className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm border border-accent-blue/30 text-accent-blue hover:bg-accent-blue/10 transition-colors">
                      <RotateCcw className="h-4 w-4" />Reset Kill Switch
                    </button>
                  </div>
                </div>
              </GlassmorphismCard>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Pagination */}
      <motion.div variants={fadeUp} className="flex items-center justify-center gap-4 text-sm">
        <button className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors" disabled><ChevronLeft className="h-4 w-4" />Prev</button>
        <span className="text-muted-foreground">Showing 1-{filtered.length} of {filtered.length}</span>
        <button className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors" disabled>Next<ChevronRight className="h-4 w-4" /></button>
      </motion.div>
    </motion.div>
  );
}

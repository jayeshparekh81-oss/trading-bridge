"use client";

import { motion } from "framer-motion";
import { Crown, Users, BarChart3, Zap, IndianRupee, ShieldAlert, AlertTriangle, Wifi, WifiOff, Clock, CheckCircle, XCircle, Info } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { StatCard } from "@/components/ui/stat-card";
import { Badge } from "@/components/ui/badge";
import { adminMockData } from "@/lib/admin-mock-data";
import { formatCurrency, cn, relativeTime } from "@/lib/utils";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

const severityStyles = {
  critical: "border-loss/30 bg-loss/5 text-loss",
  warning: "border-accent-gold/30 bg-accent-gold/5 text-accent-gold",
  info: "border-accent-blue/30 bg-accent-blue/5 text-accent-blue",
};
const severityIcons = { critical: XCircle, warning: AlertTriangle, info: Info };

export default function AdminDashboardPage() {
  const d = adminMockData;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Crown className="h-6 w-6 text-accent-purple" /> Admin — System Health
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Command center for Trading Bridge</p>
        </div>
        <Badge variant="outline" className={cn("text-sm px-3 py-1", d.systemStatus === "healthy" ? "text-profit border-profit/30" : "text-loss border-loss/30")}>
          {d.systemStatus === "healthy" ? <CheckCircle className="h-4 w-4 mr-1.5" /> : <XCircle className="h-4 w-4 mr-1.5" />}
          {d.systemStatus === "healthy" ? "ALL OK" : "ISSUES"}
        </Badge>
      </motion.div>

      {/* Stat Cards */}
      <motion.div variants={fadeUp} className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard icon={Users} label="Active Users" value={d.activeUsers} iconColor="text-accent-purple" />
        <StatCard icon={BarChart3} label="Orders Today" value={d.ordersToday} iconColor="text-accent-blue" />
        <StatCard icon={Zap} label="Avg Latency" value={d.avgLatencyMs} suffix="ms" iconColor="text-profit" />
        <StatCard icon={IndianRupee} label="Revenue (Month)" value={formatCurrency(d.revenueMonth, { compact: true })} iconColor="text-accent-gold" />
        <StatCard icon={ShieldAlert} label="Kill Switch Trips" value={d.killSwitchTrips} iconColor="text-loss" />
        <StatCard icon={AlertTriangle} label="Error Rate" value={`${d.errorRate}%`} iconColor="text-accent-gold" />
      </motion.div>

      {/* Requests Chart */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Requests Per Minute (Last 60 min)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={d.requestsPerMinute} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
              <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: "#64748B", fontSize: 10 }} interval={9} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#64748B", fontSize: 10 }} width={40} />
              <Tooltip contentStyle={{ background: "rgba(17,24,39,0.9)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", color: "#F8FAFC", fontSize: "12px" }} />
              <Line type="monotone" dataKey="rpm" stroke="#A855F7" strokeWidth={2} dot={false} animationDuration={1500} />
            </LineChart>
          </ResponsiveContainer>
        </GlassmorphismCard>
      </motion.div>

      {/* Broker Health + Recent Alerts */}
      <motion.div variants={fadeUp} className="grid lg:grid-cols-2 gap-4">
        {/* Broker Health */}
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Broker Health</h2>
          <div className="space-y-3">
            {d.brokerHealth.map((b) => (
              <div key={b.name} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <div className="flex items-center gap-3">
                  {b.status === "online" ? <Wifi className="h-4 w-4 text-profit" /> : b.status === "degraded" ? <Wifi className="h-4 w-4 text-accent-gold" /> : <WifiOff className="h-4 w-4 text-muted-foreground" />}
                  <span className="font-medium">{b.name}</span>
                </div>
                {b.status === "not_deployed" ? (
                  <span className="text-xs text-muted-foreground">Not deployed</span>
                ) : (
                  <div className="flex items-center gap-4 text-sm">
                    <span>{b.latencyMs}ms</span>
                    <span className="text-profit">{b.successRate}%</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </GlassmorphismCard>

        {/* Recent Alerts */}
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Recent Alerts</h2>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {d.recentAlerts.map((alert) => {
              const Icon = severityIcons[alert.severity];
              return (
                <div key={alert.id} className={cn("flex items-start gap-3 p-3 rounded-lg border", severityStyles[alert.severity])}>
                  <Icon className="h-4 w-4 mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">{alert.message}</p>
                    <p className="text-xs opacity-70 mt-1 flex items-center gap-1">
                      <Clock className="h-3 w-3" />{relativeTime(alert.time)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </GlassmorphismCard>
      </motion.div>
    </motion.div>
  );
}

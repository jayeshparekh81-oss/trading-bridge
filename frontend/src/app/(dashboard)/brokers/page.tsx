"use client";

import { motion } from "framer-motion";
import { Landmark, Wifi, WifiOff, Clock, Zap, Plus, RefreshCw, Trash2, Bell } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { mockDashboard, type Broker } from "@/lib/mock-data";
import { useApi } from "@/lib/use-api";
import { api, ApiError } from "@/lib/api";
import { relativeTime, cn } from "@/lib/utils";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function BrokersPage() {
  const { data: apiBrokers } = useApi<Array<{ id: string; broker_name: string; is_active: boolean; created_at: string | null }>>("/users/me/brokers");
  const brokers: Broker[] = apiBrokers
    ? [
        ...apiBrokers.map((b) => ({ name: b.broker_name, status: (b.is_active ? "connected" : "expired") as Broker["status"], latencyMs: 35, lastLogin: b.created_at || "", id: b.id })),
        ...mockDashboard.brokers.filter((b) => b.status === "coming_soon"),
      ]
    : mockDashboard.brokers;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Landmark className="h-6 w-6 text-accent-blue" /> Connected Brokers
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Manage your broker connections</p>
        </div>
        <Dialog>
          <DialogTrigger>
            <GlowButton size="sm"><Plus className="h-4 w-4 mr-2" />Add Broker</GlowButton>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Add Broker Credentials</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-4">
              <div><label className="text-sm font-medium">Broker</label><Input placeholder="Select broker..." className="mt-1" /></div>
              <div><label className="text-sm font-medium">Client ID</label><Input placeholder="Enter client ID" className="mt-1" /></div>
              <div><label className="text-sm font-medium">API Key</label><Input type="password" placeholder="Enter API key" className="mt-1" /></div>
              <div><label className="text-sm font-medium">API Secret</label><Input type="password" placeholder="Enter API secret" className="mt-1" /></div>
              <GlowButton className="w-full">Connect Broker</GlowButton>
            </div>
          </DialogContent>
        </Dialog>
      </motion.div>

      <div className="space-y-4">
        {brokers.map((broker) => (
          <motion.div key={broker.name} variants={fadeUp}>
            <GlassmorphismCard
              glow={broker.status === "connected" ? "profit" : "none"}
              className={cn(broker.status === "coming_soon" && "opacity-60")}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "h-12 w-12 rounded-xl flex items-center justify-center text-lg font-bold",
                    broker.status === "connected" ? "bg-profit/10 text-profit" :
                    broker.status === "expired" ? "bg-loss/10 text-loss" :
                    "bg-muted text-muted-foreground"
                  )}>
                    {broker.name[0]}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-lg">{broker.name}</span>
                      {broker.status === "connected" && <Badge variant="outline" className="text-profit border-profit/30 text-xs">Connected</Badge>}
                      {broker.status === "expired" && <Badge variant="outline" className="text-loss border-loss/30 text-xs">Expired</Badge>}
                      {broker.status === "coming_soon" && <Badge variant="outline" className="text-muted-foreground text-xs">Coming Soon</Badge>}
                    </div>
                    {broker.status === "connected" && (
                      <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1"><Wifi className="h-3.5 w-3.5 text-profit" />Active</span>
                        <span className="flex items-center gap-1"><Zap className="h-3.5 w-3.5" />{broker.latencyMs}ms</span>
                        <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{relativeTime(broker.lastLogin)}</span>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {broker.status === "connected" && (
                    <>
                      <button className="px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-accent transition-colors flex items-center gap-1.5">
                        <RefreshCw className="h-3.5 w-3.5" />Reconnect
                      </button>
                      <button className="px-3 py-1.5 rounded-lg text-sm border border-loss/30 text-loss hover:bg-loss/10 transition-colors flex items-center gap-1.5">
                        <Trash2 className="h-3.5 w-3.5" />Remove
                      </button>
                    </>
                  )}
                  {broker.status === "coming_soon" && (
                    <button className="px-3 py-1.5 rounded-lg text-sm border border-accent-blue/30 text-accent-blue hover:bg-accent-blue/10 transition-colors flex items-center gap-1.5">
                      <Bell className="h-3.5 w-3.5" />Notify Me
                    </button>
                  )}
                </div>
              </div>
            </GlassmorphismCard>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

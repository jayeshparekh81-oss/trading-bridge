"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Webhook, Copy, Eye, EyeOff, Plus, Check, Trash2, PlayCircle, BookOpen } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { mockDashboard } from "@/lib/mock-data";
import { relativeTime } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

const samplePayload = `{
  "action": "BUY",
  "symbol": "NIFTY25000CE",
  "exchange": "NSE",
  "quantity": 50,
  "order_type": "MARKET",
  "product_type": "INTRADAY"
}`;

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); };
  return (
    <button onClick={handleCopy} className="flex items-center gap-1 px-2 py-1 rounded text-xs border border-border hover:bg-accent transition-colors">
      {copied ? <><Check className="h-3 w-3 text-profit" />Copied</> : <><Copy className="h-3 w-3" />Copy</>}
    </button>
  );
}

export default function WebhooksPage() {
  const { webhooks } = mockDashboard;
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><Webhook className="h-6 w-6 text-accent-blue" /> Webhook Tokens</h1>
          <p className="text-muted-foreground text-sm mt-1">Manage your TradingView webhook connections</p>
        </div>
        <Dialog>
          <DialogTrigger><GlowButton size="sm"><Plus className="h-4 w-4 mr-2" />Create Webhook</GlowButton></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Create New Webhook</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-4">
              <div><label className="text-sm font-medium">Label</label><Input placeholder="e.g. Nifty Strategy" className="mt-1" /></div>
              <div><label className="text-sm font-medium">Broker</label>
                <select className="w-full h-9 px-3 mt-1 rounded-lg bg-muted/50 border border-border text-sm">
                  <option>Fyers</option><option>Dhan</option>
                </select>
              </div>
              <GlowButton className="w-full">Generate Webhook</GlowButton>
            </div>
          </DialogContent>
        </Dialog>
      </motion.div>

      {/* Webhook list */}
      {webhooks.map((wh) => (
        <motion.div key={wh.id} variants={fadeUp}>
          <GlassmorphismCard glow={wh.isActive ? "blue" : "none"}>
            <div className="space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{wh.label}</span>
                    <Badge variant="outline" className="text-xs text-profit border-profit/30">Active</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Strategy: {wh.strategy} &bull; Broker: {wh.broker}</p>
                </div>
                <div className="flex gap-2">
                  <button className="p-1.5 rounded-lg hover:bg-accent transition-colors" title="Test webhook"><PlayCircle className="h-4 w-4 text-accent-blue" /></button>
                  <button className="p-1.5 rounded-lg hover:bg-loss/10 transition-colors" title="Revoke"><Trash2 className="h-4 w-4 text-loss" /></button>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-white/[0.03] rounded px-3 py-2 font-mono truncate">/api/webhook/{wh.token}</code>
                  <CopyButton text={`/api/webhook/${wh.token}`} />
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-white/[0.03] rounded px-3 py-2 font-mono">
                    {showSecrets[wh.id] ? wh.hmacSecret : "\u2022".repeat(24)}
                  </code>
                  <button onClick={() => setShowSecrets(s => ({ ...s, [wh.id]: !s[wh.id] }))} className="p-1.5 rounded hover:bg-accent transition-colors">
                    {showSecrets[wh.id] ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                  <CopyButton text={wh.hmacSecret} />
                </div>
              </div>
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span>Created: {new Date(wh.created).toLocaleDateString("en-IN")}</span>
                <span>Last used: {relativeTime(wh.lastUsed)}</span>
              </div>
            </div>
          </GlassmorphismCard>
        </motion.div>
      ))}

      {/* Setup Guide */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="h-5 w-5 text-accent-purple" />
            <h2 className="text-lg font-semibold">TradingView Setup Guide</h2>
          </div>
          <ol className="space-y-3 text-sm text-muted-foreground list-decimal list-inside">
            <li>Open your TradingView chart and create an alert</li>
            <li>In the &quot;Notifications&quot; tab, check &quot;Webhook URL&quot;</li>
            <li>Paste your webhook URL <CopyButton text={`https://api.tradingbridge.in/api/webhook/${webhooks[0]?.token || "YOUR_TOKEN"}`} /></li>
            <li>In the alert message, paste this JSON template:</li>
          </ol>
          <div className="mt-3 relative">
            <pre className="text-xs bg-white/[0.03] rounded-lg p-4 font-mono overflow-x-auto">{samplePayload}</pre>
            <div className="absolute top-2 right-2"><CopyButton text={samplePayload} /></div>
          </div>
        </GlassmorphismCard>
      </motion.div>
    </motion.div>
  );
}

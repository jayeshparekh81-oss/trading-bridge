"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Landmark, Wifi, Clock, Zap, Plus, RefreshCw, Trash2, Bell, HelpCircle } from "lucide-react";
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ReconnectInfoBanner } from "@/components/brokers/ReconnectInfoBanner";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

type BackendCredentials = { client_id: string; api_key: string; api_secret: string };

type BrokerField = {
  key: string;
  label: string;
  placeholder: string;
  secret?: boolean;
  helpText: string;
  hint?: string;
};

type BrokerFormSchema = {
  /** Wire value sent as `broker_name` (must match backend StrEnum). */
  value: string;
  /** Display label. */
  label: string;
  fields: readonly [BrokerField, BrokerField];
  /** Maps the per-broker form values to the legacy 4-field backend payload. */
  toBackend: (values: Record<string, string>) => BackendCredentials;
};

const BROKER_SCHEMAS: readonly BrokerFormSchema[] = [
  {
    value: "fyers",
    label: "Fyers",
    fields: [
      {
        key: "appId",
        label: "App ID",
        placeholder: "e.g., VZCA6T6Z6O-100",
        helpText: "Find in Fyers Dashboard → My Apps → your app's APP ID column.",
        hint: "Copy from Fyers Dashboard → My Apps",
      },
      {
        key: "appSecret",
        label: "App Secret",
        placeholder: "e.g., SWGO1703KU",
        secret: true,
        helpText: "Same row in My Apps. Click 'Show' next to APP SECRET to reveal.",
      },
    ],
    // Fyers' SDK uses api_key as the App ID; client_id is required by the
    // backend payload contract, so we send the App ID into both slots.
    toBackend: (v) => ({
      client_id: v.appId,
      api_key: v.appId,
      api_secret: v.appSecret,
    }),
  },
  {
    value: "dhan",
    label: "Dhan",
    fields: [
      {
        key: "clientId",
        label: "Client ID",
        placeholder: "e.g., 1100123456",
        helpText: "Find in DhanHQ web → Profile → Client ID (numeric).",
      },
      {
        key: "accessToken",
        label: "Access Token",
        placeholder: "Paste personal access token",
        secret: true,
        helpText: "Generate from DhanHQ → My Profile → Access DhanHQ Trading APIs → Generate Token.",
        hint: "Tokens expire — regenerate from DhanHQ if connection fails.",
      },
    ],
    // Dhan's broker only reads client_id + access_token; we stash the token in
    // api_secret (and mirror into api_key) to satisfy the backend contract.
    toBackend: (v) => ({
      client_id: v.clientId,
      api_key: v.accessToken,
      api_secret: v.accessToken,
    }),
  },
];

export default function BrokersPage() {
  const { data: apiBrokers, refetch } = useApi<Array<{ id: string; broker_name: string; is_active: boolean; created_at: string | null }>>("/users/me/brokers");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [brokerValue, setBrokerValue] = useState<string>(BROKER_SCHEMAS[0].value);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [connecting, setConnecting] = useState(false);

  const schema = useMemo(
    () => BROKER_SCHEMAS.find((s) => s.value === brokerValue) ?? BROKER_SCHEMAS[0],
    [brokerValue],
  );

  function resetForm() {
    setBrokerValue(BROKER_SCHEMAS[0].value);
    setFieldValues({});
  }

  async function handleConnect() {
    const missing = schema.fields.find((f) => !(fieldValues[f.key] ?? "").trim());
    if (missing) {
      toast.error(`Please enter ${missing.label}`);
      return;
    }
    const trimmed = Object.fromEntries(
      schema.fields.map((f) => [f.key, (fieldValues[f.key] ?? "").trim()]),
    );
    const creds = schema.toBackend(trimmed);
    setConnecting(true);
    try {
      await api.post("/users/me/brokers", {
        broker_name: schema.value,
        ...creds,
      });
      toast.success("Broker connected successfully!");
      setDialogOpen(false);
      resetForm();
      refetch();
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Failed to connect broker";
      toast.error(msg);
    } finally {
      setConnecting(false);
    }
  }
  const brokers: Broker[] = apiBrokers
    ? [
        ...apiBrokers.map((b) => ({ name: b.broker_name, status: (b.is_active ? "connected" : "expired") as Broker["status"], latencyMs: 35, lastLogin: b.created_at || "", id: b.id })),
        ...mockDashboard.brokers.filter((b) => b.status === "coming_soon"),
      ]
    : mockDashboard.brokers;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <motion.div variants={fadeUp}>
        <ReconnectInfoBanner />
      </motion.div>
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Landmark className="h-6 w-6 text-accent-blue" /> Connected Brokers
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Manage your broker connections</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
          <DialogTrigger>
            <GlowButton size="sm"><Plus className="h-4 w-4 mr-2" />Add Broker</GlowButton>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Add Broker Credentials</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-4">
              <div>
                <label htmlFor="broker-select" className="text-sm font-medium">Broker</label>
                <select
                  id="broker-select"
                  className="mt-1 h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                  value={brokerValue}
                  onChange={(e) => { setBrokerValue(e.target.value); setFieldValues({}); }}
                >
                  {BROKER_SCHEMAS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              {schema.fields.map((f) => (
                <div key={f.key}>
                  <div className="flex items-center gap-1.5">
                    <label htmlFor={`broker-field-${f.key}`} className="text-sm font-medium">{f.label}</label>
                    <Tooltip>
                      <TooltipTrigger
                        type="button"
                        aria-label={`Where to find ${f.label}`}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <HelpCircle className="h-3.5 w-3.5" />
                      </TooltipTrigger>
                      <TooltipContent>{f.helpText}</TooltipContent>
                    </Tooltip>
                  </div>
                  <Input
                    id={`broker-field-${f.key}`}
                    type={f.secret ? "password" : "text"}
                    placeholder={f.placeholder}
                    className="mt-1"
                    value={fieldValues[f.key] ?? ""}
                    onChange={(e) => setFieldValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                  />
                  {f.hint && <p className="mt-1 text-xs text-muted-foreground">{f.hint}</p>}
                </div>
              ))}
              <GlowButton className="w-full" onClick={handleConnect} disabled={connecting}>{connecting ? "Connecting..." : "Connect Broker"}</GlowButton>
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

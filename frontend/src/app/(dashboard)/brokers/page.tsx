"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Landmark, Wifi, Clock, Plus, RefreshCw, Trash2, Bell, HelpCircle, AlertTriangle } from "lucide-react";
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

type BackendCredentials = {
  client_id: string;
  api_key: string;
  api_secret: string;
  access_token?: string;
};

type BrokerField = {
  key: string;
  label: string;
  placeholder: string;
  secret?: boolean;
  helpText: string;
  hint?: string;
  /** When true, blank input is accepted (skipped by required-field validation). */
  optional?: boolean;
};

type BrokerFormSchema = {
  /** Wire value sent as `broker_name` (must match backend StrEnum). */
  value: string;
  /** Display label. */
  label: string;
  fields: readonly BrokerField[];
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
      {
        key: "accessToken",
        label: "Access Token (optional, for manual PAT flow)",
        placeholder: "Paste Fyers access token from myapi.fyers.in",
        secret: true,
        optional: true,
        helpText: "Generate from myapi.fyers.in → Apps → Generate Access Token.",
        hint: "Tokens expire daily — regenerate if connection fails.",
      },
    ],
    // Fyers' SDK uses api_key as the App ID; client_id is required by the
    // backend payload contract, so we send the App ID into both slots.
    // Optional access_token enables a manual PAT flow as a fallback to
    // OAuth — backend persists it via encrypt_credential when present.
    toBackend: (v) => ({
      client_id: v.appId,
      api_key: v.appId,
      api_secret: v.appSecret,
      ...(v.accessToken ? { access_token: v.accessToken } : {}),
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
    // Dhan is a PAT-based broker: the token itself is the session.
    // api_key/api_secret carry the token to satisfy the legacy schema (backend
    // ignores them on the order path); access_token is the canonical field
    // the order adapter actually reads.
    toBackend: (v) => ({
      client_id: v.clientId,
      api_key: v.accessToken,
      api_secret: v.accessToken,
      access_token: v.accessToken,
    }),
  },
];

export default function BrokersPage() {
  const { data: apiBrokers, error, isLoading, refetch } = useApi<
    Array<{
      id: string;
      broker_name: string;
      is_active: boolean;
      created_at: string | null;
      token_expires_at: string | null;
    }>
  >("/users/me/brokers");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [brokerValue, setBrokerValue] = useState<string>(BROKER_SCHEMAS[0].value);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [connecting, setConnecting] = useState(false);
  const [reconnectingId, setReconnectingId] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  // `now` drives the token-expiry comparison in the broker mapping. Captured
  // in state (lazy init) so the comparison is pure during render; refreshed
  // every 60 s so a token flips to "Expired" without a page reload.
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  const schema = useMemo(
    () => BROKER_SCHEMAS.find((s) => s.value === brokerValue) ?? BROKER_SCHEMAS[0],
    [brokerValue],
  );

  function resetForm() {
    setBrokerValue(BROKER_SCHEMAS[0].value);
    setFieldValues({});
  }

  async function handleConnect() {
    const missing = schema.fields.find(
      (f) => !f.optional && !(fieldValues[f.key] ?? "").trim(),
    );
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

  async function handleReconnect(broker: Broker) {
    if (!broker.id) return;
    const name = (broker.name || "").toLowerCase();
    setReconnectingId(broker.id);
    try {
      if (name === "fyers") {
        const res = await api.get<{ url: string }>("/brokers/fyers/connect");
        if (!res?.url) {
          toast.error("Backend returned no OAuth URL.");
          return;
        }
        toast.success("Redirecting to Fyers...");
        window.location.assign(res.url);
        return; // navigation in flight; reconnectingId cleanup is unnecessary
      }
      if (name === "dhan") {
        toast.info(
          "To reconnect Dhan: Remove this connection and click Add Broker → Select Dhan → Enter new Access Token from dhan.co",
          { duration: 10000 },
        );
        return;
      }
      toast.error(`Reconnect not supported for ${broker.name}.`);
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Failed to start reconnect";
      toast.error(msg);
    } finally {
      setReconnectingId(null);
    }
  }

  async function handleRemove(broker: Broker) {
    if (!broker.id) return;
    const ok = window.confirm(
      `Remove ${broker.name}? You can re-add it anytime. Existing audit history is preserved.`,
    );
    if (!ok) return;
    setRemovingId(broker.id);
    try {
      // Soft-delete: PUT is_active=false. Preserves audit trail; the
      // list filter below hides the row from the UI.
      await api.put(`/users/me/brokers/${broker.id}`, { is_active: false });
      toast.success("Broker disconnected successfully");
      refetch();
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Failed to remove broker";
      toast.error(msg);
    } finally {
      setRemovingId(null);
    }
  }

  // Real connected brokers come ONLY from the API. On API failure
  // we render the static "coming_soon" placeholders + an error banner —
  // never fake "connected" rows from mock data.
  // Inactive rows (deactivated duplicates from old debug sessions) are
  // filtered out client-side so they never reach the UI as "Expired"
  // cards. Backend cleanup is a separate concern.
  const realBrokers: Broker[] = apiBrokers
    ? apiBrokers
        .filter((b) => b.is_active)
        .map((b) => {
          // Null token_expires_at = no expiry tracked (Dhan paste-token flow);
          // do NOT mark as expired in that case — only flag rows whose stored
          // expiry has actually elapsed.
          const expired =
            b.token_expires_at !== null &&
            new Date(b.token_expires_at).getTime() <= now;
          return {
            name: b.broker_name,
            status: (expired ? "expired" : "connected") as Broker["status"],
            latencyMs: 0, // backend doesn't return latency yet — never show a fake number
            lastLogin: b.token_expires_at ?? b.created_at ?? "",
            id: b.id,
          };
        })
    : [];
  const comingSoon: Broker[] = mockDashboard.brokers.filter((b) => b.status === "coming_soon");
  const apiFailed = !!error && apiBrokers === null;

  // One render path used by both sections — keeps card markup in one
  // place while the parent splits the data into Connected vs Coming Soon.
  const renderBrokerCard = (broker: Broker) => (
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
              "bg-muted text-muted-foreground",
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
                  {broker.lastLogin && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      Valid until {new Date(broker.lastLogin).toLocaleString()}
                    </span>
                  )}
                </div>
              )}
              {broker.status === "expired" && (
                <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1 text-loss">
                    <AlertTriangle className="h-3.5 w-3.5" />Token expired
                  </span>
                  {broker.lastLogin && relativeTime(broker.lastLogin) && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      Expired {relativeTime(broker.lastLogin)} — Reconnect needed
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {(broker.status === "connected" || broker.status === "expired") && (
              <>
                <button
                  type="button"
                  onClick={() => handleReconnect(broker)}
                  disabled={reconnectingId === broker.id || removingId === broker.id}
                  className="px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-accent transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <RefreshCw className={cn("h-3.5 w-3.5", reconnectingId === broker.id && "animate-spin")} />
                  {reconnectingId === broker.id ? "Redirecting..." : "Reconnect"}
                </button>
                <button
                  type="button"
                  onClick={() => handleRemove(broker)}
                  disabled={removingId === broker.id || reconnectingId === broker.id}
                  className="px-3 py-1.5 rounded-lg text-sm border border-loss/30 text-loss hover:bg-loss/10 transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {removingId === broker.id ? "Removing..." : "Remove"}
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
  );

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

      {apiFailed && (
        <motion.div
          variants={fadeUp}
          role="alert"
          className="flex items-center justify-between gap-3 rounded-xl border border-loss/30 bg-loss/5 px-4 py-3"
        >
          <div className="flex items-start gap-2 min-w-0">
            <AlertTriangle className="h-4 w-4 text-loss shrink-0 mt-0.5" />
            <div className="min-w-0">
              <div className="text-sm font-medium">Couldn&rsquo;t load your brokers</div>
              <div className="text-xs text-muted-foreground mt-0.5 truncate">
                {error}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={refetch}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent transition-colors"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
            Retry
          </button>
        </motion.div>
      )}

      {realBrokers.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-1">
            Connected Brokers
          </h2>
          <div className="space-y-4">
            {realBrokers.map(renderBrokerCard)}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-1">
          Coming Soon
        </h2>
        <div className="space-y-4">
          {comingSoon.map(renderBrokerCard)}
        </div>
      </section>
    </motion.div>
  );
}

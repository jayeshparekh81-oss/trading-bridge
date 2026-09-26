"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Wifi, Clock, Plus, RefreshCw, Trash2, Bell, HelpCircle, AlertTriangle } from "lucide-react";
import { ProPage } from "@/components/dashboard/pro-page";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { GlowButton } from "@/shared/ui/glow-button";
import { Button } from "@/shared/ui/button";
import { Badge } from "@/shared/ui/badge";
import { type Broker } from "@/lib/mock-data";
import { useApi } from "@/shared/api/use-api";
import { api, ApiError } from "@/shared/api/client";
import { relativeTime, cn } from "@/shared/lib/utils";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";
import { Input } from "@/shared/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip";
import { ReconnectInfoBanner } from "@/components/brokers/ReconnectInfoBanner";
import { UpdateDhanTokenModal } from "@/components/brokers/UpdateDhanTokenModal";
import { useBrokerStatus } from "@/hooks/useBrokerStatus";

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

// DHAN FIRST — the safe default (founder's rule, 26 Sep, point 4): every customer screen
// says "Apna Dhan account jodo"; the dialog used to open on Fyers' App ID / App Secret.
const BROKER_SCHEMAS: readonly BrokerFormSchema[] = [
  {
    value: "dhan",
    label: "Dhan",
    fields: [
      {
        key: "clientId",
        label: "Dhan Client ID",
        placeholder: "jaise 1100123456",
        helpText: "Dhan ki website par Profile me likha number (sirf ank).",
      },
      {
        key: "accessToken",
        label: "Dhan ki chabi (access token)",
        placeholder: "Dhan se copy kiya hua lamba code",
        secret: true,
        helpText: "Dhan website → My Profile → 'Access DhanHQ Trading APIs' → 'Generate Token' — jo lamba code aaye, copy karo.",
        hint: "Yeh chabi roz badalti hai (24 ghante). Kal jud na paaye to yahi naya code daalna.",
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
  },  {
    value: "fyers",
    label: "Fyers",
    fields: [
      {
        key: "appId",
        label: "Fyers App ID",
        placeholder: "jaise VZCA6T6Z6O-100",
        helpText: "Fyers Dashboard → 'My Apps' → aapke app ki 'APP ID' wali line.",
        hint: "Fyers Dashboard → 'My Apps' se copy karo",
      },
      {
        key: "appSecret",
        label: "Fyers App Secret (gupt code)",
        placeholder: "jaise SWGO1703KU",
        secret: true,
        helpText: "Usi 'My Apps' line me 'APP SECRET' ke paas 'Show' dabao.",
      },
      {
        key: "accessToken",
        label: "Fyers ki chabi (access token) — zaroori nahi",
        placeholder: "Khaali chhodo to Fyers login page khulega",
        secret: true,
        optional: true,
        helpText: "myapi.fyers.in → 'Apps' → 'Generate Access Token'. Khaali chhodoge to hum Fyers ka login page kholenge.",
        hint: "Yeh chabi roz badalti hai.",
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
];

/**
 * Connect-screen error copy.
 *
 * 20 Sep 2026 — these used to read "Backend returned no OAuth URL." and
 * "Failed to connect broker" on the screen a customer touches every day.
 * They named what broke inside the server; they did not tell a
 * non-technical customer what to do next. RULES #40: one clear next step,
 * plain language, no jargon.
 */
const FYERS_CONNECT_FAILED =
  "Fyers ka login page nahi khul paya. 1 minute ruk kar dobara \u201cBroker jodo\u201d dabao. Phir bhi na chale to founder ko WhatsApp karo \u2014 hum dekh lenge.";
const CONNECT_FAILED =
  "Broker connect nahi ho paya. Internet check karke dobara try karo. Do baar fail ho to founder ko WhatsApp karo.";
const RECONNECT_FAILED =
  "Reconnect shuru nahi ho paya. Dobara try karo; na chale to \u201cHatao\u201d dabake naye sire se \u201cBroker jodo\u201d karo.";

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
  // Phase 1 (2026-05-16) — Dhan paste-token reconnect flow. Modal opens
  // from the new "Update Dhan Token" card below; refetches the badge
  // status on success so the card flips from "Expired" → "Connected"
  // without a page reload.
  const [updateDhanOpen, setUpdateDhanOpen] = useState(false);
  const dhanStatus = useBrokerStatus();
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
      toast.error(`Pehle "${missing.label}" bharo — tab broker judega.`);
      return;
    }
    const trimmed = Object.fromEntries(
      schema.fields.map((f) => [f.key, (fieldValues[f.key] ?? "").trim()]),
    );
    const creds = schema.toBackend(trimmed);
    setConnecting(true);
    try {
      // Fyers without an Access Token = OAuth path. We redirect to the
      // Fyers-generated auth URL; backend's /fyers/callback handles the
      // token exchange and persists the credential. Fyers users who DID
      // fill the Access Token field fall through to the PAT POST below.
      if (schema.value === "fyers" && !trimmed.accessToken) {
        const res = await api.get<{ url: string }>("/brokers/fyers/connect");
        if (!res?.url) {
          toast.error(FYERS_CONNECT_FAILED, { duration: 8000 });
          return;
        }
        toast.success("Fyers ka login page khol rahe hain…");
        window.location.assign(res.url);
        return;
      }
      await api.post("/users/me/brokers", {
        broker_name: schema.value,
        ...creds,
      });
      toast.success("Broker jud gaya!");
      window.dispatchEvent(new CustomEvent("tradetri:ladder", { detail: { brokerConnected: true } }));
      setDialogOpen(false);
      resetForm();
      refetch();
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.detail : CONNECT_FAILED;
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
          toast.error(FYERS_CONNECT_FAILED, { duration: 8000 });
          return;
        }
        toast.success("Fyers ka login page khol rahe hain…");
        window.location.assign(res.url);
        return; // navigation in flight; reconnectingId cleanup is unnecessary
      }
      if (name === "dhan") {
        // One tap, not four steps: the same "nayi chabi daalo" box the Dhan card opens.
        setUpdateDhanOpen(true);
        return;
      }
      toast.error(
        `${broker.name} ko yahan se reconnect nahi kar sakte. Is connection ko Remove karo, phir "Broker jodo" se dobara jodo.`,
        { duration: 8000 },
      );
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.detail : RECONNECT_FAILED;
      toast.error(msg);
    } finally {
      setReconnectingId(null);
    }
  }

  async function handleRemove(broker: Broker) {
    if (!broker.id) return;
    const ok = window.confirm(
      `${broker.name} hatana pakka hai? Baad me kabhi bhi dobara jod sakte ho. Purana record (history) mitega nahi.`,
    );
    if (!ok) return;
    setRemovingId(broker.id);
    try {
      // Soft-delete: PUT is_active=false. Preserves audit trail; the
      // list filter below hides the row from the UI.
      await api.put(`/users/me/brokers/${broker.id}`, { is_active: false });
      toast.success("Broker hata diya");
      refetch();
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Broker hata nahi paaye — dobara try karo.";
      toast.error(msg);
    } finally {
      setRemovingId(null);
    }
  }

  // Real connected brokers come ONLY from the API. On API failure we
  // render the error banner alone — never fake "connected" rows from
  // mock data.
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
  const apiFailed = !!error && apiBrokers === null;

  // Single render path for the connected-broker rows, so the card
  // markup lives in one place.
  const renderBrokerCard = (broker: Broker) => (
    <motion.div key={broker.name} variants={fadeUp}>
      <GlassmorphismCard glow={broker.status === "connected" ? "profit" : "none"}>
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
                {broker.status === "connected" && <Badge variant="outline" className="text-profit border-profit/30 text-xs">Juda hai</Badge>}
                {broker.status === "expired" && <Badge variant="outline" className="text-loss border-loss/30 text-xs">Chabi purani ho gayi</Badge>}
              </div>
              {broker.status === "connected" && (
                <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1"><Wifi className="h-3.5 w-3.5 text-profit" />Chalu</span>
                  {broker.lastLogin && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      Chalega {new Date(broker.lastLogin).toLocaleString("en-IN")} tak
                    </span>
                  )}
                </div>
              )}
              {broker.status === "expired" && (
                <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1 text-loss">
                    <AlertTriangle className="h-3.5 w-3.5" />Chabi (token) purani ho gayi
                  </span>
                  {broker.lastLogin && relativeTime(broker.lastLogin) && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {relativeTime(broker.lastLogin)} purani ho gayi — &ldquo;Dobara jodo&rdquo; dabao
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
                  className="min-h-11 px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-accent transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <RefreshCw className={cn("h-3.5 w-3.5", reconnectingId === broker.id && "animate-spin")} />
                  {reconnectingId === broker.id ? "Khol rahe hain…" : "Dobara jodo"}
                </button>
                <button
                  type="button"
                  onClick={() => handleRemove(broker)}
                  disabled={removingId === broker.id || reconnectingId === broker.id}
                  className="min-h-11 px-3 py-1.5 rounded-lg text-sm border border-loss/30 text-loss hover:bg-loss/10 transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {removingId === broker.id ? "Hata rahe hain…" : "Hatao"}
                </button>
              </>
            )}
            
          </div>
        </div>
      </GlassmorphismCard>
    </motion.div>
  );

  // THE single primary action for this page. It opens a dialog rather than
  // navigating, so it is handed to ProPage as `actionSlot`. Its label is the
  // one pro-nav declares for /brokers, so the button and the sidebar entry
  // cannot drift apart.
  const addBrokerAction = (
    <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
      {/* base-ui: `render` replaces the trigger's own <button> with this
          element (no nested button). base-ui has no `asChild`. */}
      {/* Quieter than the Dhan card's button (ONE big primary per screen, point 2): the
          Dhan card below is the thing a first-timer taps; this is for Fyers and later. */}
      <DialogTrigger render={<Button variant="outline" size="lg" />}>
        <Plus className="h-4 w-4 mr-2" />Broker jodo
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Broker jodo</DialogTitle></DialogHeader>
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
                    aria-label={`"${f.label}" kahan milega`}
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
          <GlowButton className="w-full" onClick={handleConnect} disabled={connecting}>{connecting ? "Jod rahe hain…" : "Broker jodo"}</GlowButton>
        </div>
      </DialogContent>
    </Dialog>
  );

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto">
      <ProPage actionSlot={addBrokerAction}>
        <motion.div variants={fadeUp}>
          <ReconnectInfoBanner />
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
                <div className="text-sm font-medium">Aapke broker ki list abhi load nahi ho payi</div>
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
              Dobara dekho
            </button>
          </motion.div>
        )}

        {/* Connected Brokers — single section, post 2026-05-16 cleanup.
            The Dhan paste-token card (driven by useBrokerStatus + the
            UpdateDhanTokenModal) sits at the top. Any non-Dhan brokers
            (Fyers OAuth etc.) render below via the existing
            renderBrokerCard helper so their Reconnect + Remove flows
            stay intact. Dhan is filtered out of the legacy
            realBrokers list to avoid the duplicate row the previous
            layout produced. */}
        <motion.section variants={fadeUp} className="space-y-3">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-1">
            Aapke broker
          </h2>
          <p className="px-1 text-xs text-muted-foreground">
            Dhan aur Fyers hi live hain — aur koi broker abhi connect nahi hota.
          </p>
          <GlassmorphismCard
            glow={dhanStatus.status === "connected" ? "profit" : "none"}
            data-testid="dhan-update-card"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div
                  className={cn(
                    "h-12 w-12 rounded-xl flex items-center justify-center text-lg font-bold",
                    dhanStatus.status === "connected"
                      ? "bg-profit/10 text-profit"
                      : dhanStatus.status === "expired"
                        ? "bg-loss/10 text-loss"
                        : "bg-muted text-muted-foreground",
                  )}
                >
                  D
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-lg">
                      {dhanStatus.label ?? "Dhan"}
                    </span>
                    {dhanStatus.status === "connected" && (
                      <Badge
                        variant="outline"
                        className="text-profit border-profit/30 text-xs"
                        data-testid="dhan-status-badge"
                      >
                        Juda hai
                      </Badge>
                    )}
                    {dhanStatus.status === "expired" && (
                      <Badge
                        variant="outline"
                        className="text-loss border-loss/30 text-xs"
                        data-testid="dhan-status-badge"
                      >
                        Chabi purani — nayi chabi daalo
                      </Badge>
                    )}
                    {dhanStatus.status === "not_connected" && (
                      <Badge
                        variant="outline"
                        className="text-muted-foreground text-xs"
                        data-testid="dhan-status-badge"
                      >
                        Abhi juda nahi
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-4 text-sm text-muted-foreground">
                    {dhanStatus.expiresAt && dhanStatus.status === "connected" && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        Chalega {new Date(dhanStatus.expiresAt).toLocaleString("en-IN")} tak
                      </span>
                    )}
                    {dhanStatus.lastUpdated && (
                      <span className="flex items-center gap-1">
                        Chabi daali: {relativeTime(dhanStatus.lastUpdated)}
                      </span>
                    )}
                    {!dhanStatus.lastUpdated && (
                      <span>
                        Dhan ki nayi chabi (24 ghante wali) daalo — tab chart, purana test aur seekhne wala mode chalu honge.
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <GlowButton
                  size="sm"
                  onClick={() => setUpdateDhanOpen(true)}
                  data-testid="open-update-dhan-modal"
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {dhanStatus.status === "not_connected" ? "Dhan jodo" : "Nayi chabi daalo"}
                </GlowButton>
              </div>
            </div>
          </GlassmorphismCard>
          {/* Non-Dhan connected brokers (Fyers etc.). Dhan rows are
              filtered out — the dedicated card above is the single
              source of truth for Dhan state. Case-insensitive match
              because the API serialises the enum as "dhan" but defensive
              code paths historically have used "Dhan"/"DHAN" too. */}
          {realBrokers
            .filter((b) => (b.name ?? "").toLowerCase() !== "dhan")
            .map(renderBrokerCard)}
        </motion.section>

        <UpdateDhanTokenModal
          open={updateDhanOpen}
          onClose={() => setUpdateDhanOpen(false)}
          onSuccess={() => {
            // Refresh both the dedicated Dhan badge poll AND the legacy
            // /users/me/brokers list so any Dhan row in the connected
            // brokers section flips to the new expiry timestamp
            // immediately.
            dhanStatus.refetch();
            refetch();
            toast.success("Dhan jud gaya — chart aur trading chalu.");
          }}
        />
      </ProPage>
    </motion.div>
  );
}

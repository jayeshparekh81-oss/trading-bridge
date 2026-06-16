"use client";

/**
 * /webhooks — TradingView webhook token CRUD.
 *
 * Wire: GET/POST/DELETE /api/users/me/webhooks (existing).
 *
 * Critical UX note: ``POST /me/webhooks`` returns ``webhook_token``
 * and ``hmac_secret`` ONCE — they are never retrievable again. The
 * "creation success" modal must give the operator a clear path to
 * copy both before dismissing.
 *
 * Style mirrors ``/brokers`` (GlassmorphismCard, GlowButton,
 * framer-motion stagger).
 */

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Webhook as WebhookIcon,
  Plus,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
  Clock,
} from "lucide-react";
import { toast } from "sonner";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApi } from "@/lib/use-api";
import { api, ApiError } from "@/lib/api";
import { relativeTime, cn } from "@/lib/utils";

interface WebhookListItem {
  id: string;
  label: string | null;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string | null;
}

interface CreateWebhookResponse {
  id: string;
  webhook_token: string;
  hmac_secret: string;
  webhook_url: string;
  message: string;
}

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

function useCopyToClipboard(): [(value: string, what: string) => void, string | null] {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = (value: string, what: string) => {
    if (typeof navigator === "undefined" || !navigator.clipboard) {
      toast.error("Clipboard unavailable. Copy manually.");
      return;
    }
    navigator.clipboard.writeText(value).then(
      () => {
        setCopied(what);
        toast.success(`${what} copied`);
        setTimeout(() => setCopied(null), 2000);
      },
      () => {
        toast.error("Copy failed. Try again.");
      },
    );
  };
  return [copy, copied];
}

export default function WebhooksPage() {
  const { data, isLoading, refetch } = useApi<WebhookListItem[]>("/users/me/webhooks", []);
  const webhooks = data ?? [];

  const [createOpen, setCreateOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [creating, setCreating] = useState(false);

  const [revoking, setRevoking] = useState<string | null>(null);

  const [created, setCreated] = useState<CreateWebhookResponse | null>(null);
  const [copy, copied] = useCopyToClipboard();

  const handleCreate = async () => {
    setCreating(true);
    try {
      const resp = await api.post<CreateWebhookResponse>("/users/me/webhooks", {
        label: label.trim() || null,
      });
      setCreateOpen(false);
      setLabel("");
      setCreated(resp);
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to create webhook.";
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: string, displayLabel: string) => {
    if (
      typeof window !== "undefined" &&
      !window.confirm(`Revoke webhook "${displayLabel}"? This cannot be undone.`)
    ) {
      return;
    }
    setRevoking(id);
    try {
      await api.delete(`/users/me/webhooks/${id}`);
      toast.success("Webhook revoked");
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to revoke webhook.";
      toast.error(msg);
    } finally {
      setRevoking(null);
    }
  };

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <WebhookIcon className="h-6 w-6 text-accent-blue" /> Webhooks
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            TradingView alert tokens. Each token gets a unique URL + HMAC secret.
          </p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <GlowButton size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create webhook
          </GlowButton>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create new webhook</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div className="space-y-1.5">
                <label className="text-sm text-muted-foreground" htmlFor="label">
                  Label <span className="text-xs">(optional)</span>
                </label>
                <Input
                  id="label"
                  placeholder="e.g., Nifty Scalper Strategy"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  disabled={creating}
                />
                <p className="text-xs text-muted-foreground">
                  A friendly name to identify this webhook later.
                </p>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  disabled={creating}
                  className="px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-accent transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <GlowButton size="sm" onClick={handleCreate} disabled={creating}>
                  {creating ? "Creating…" : "Generate"}
                </GlowButton>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </motion.div>

      {isLoading ? (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard className="p-12 text-center text-muted-foreground">
            Loading webhooks…
          </GlassmorphismCard>
        </motion.div>
      ) : webhooks.length === 0 ? (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard className="p-12 text-center space-y-3">
            <WebhookIcon className="h-12 w-12 text-muted-foreground mx-auto" />
            <h2 className="text-lg font-semibold">No webhooks yet</h2>
            <p className="text-muted-foreground text-sm max-w-md mx-auto">
              Create a webhook to receive TradingView alerts. Each webhook has its own URL and HMAC
              secret — copy them when shown; they cannot be retrieved later.
            </p>
            <GlowButton size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create your first webhook
            </GlowButton>
          </GlassmorphismCard>
        </motion.div>
      ) : (
        <motion.div variants={fadeUp} className="space-y-3">
          {webhooks.map((wh) => (
            <GlassmorphismCard key={wh.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-medium">{wh.label ?? "Untitled webhook"}</h3>
                    <Badge
                      variant={wh.is_active ? "default" : "secondary"}
                      className={cn(
                        wh.is_active
                          ? "bg-profit/15 text-profit border-profit/30"
                          : "bg-white/[0.03] text-muted-foreground",
                      )}
                    >
                      {wh.is_active ? "Active" : "Revoked"}
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground flex items-center gap-3 flex-wrap">
                    <span className="font-mono">{wh.id.slice(0, 8)}…</span>
                    {wh.created_at && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Created {relativeTime(wh.created_at)}
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      Last used: {wh.last_used_at ? relativeTime(wh.last_used_at) : "never"}
                    </span>
                  </div>
                </div>
                {wh.is_active && (
                  <button
                    type="button"
                    onClick={() => handleRevoke(wh.id, wh.label ?? "Untitled webhook")}
                    disabled={revoking === wh.id}
                    className="px-3 py-1.5 rounded-lg text-sm border border-loss/30 text-loss hover:bg-loss/10 transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    {revoking === wh.id ? "Revoking…" : "Revoke"}
                  </button>
                )}
              </div>
            </GlassmorphismCard>
          ))}
        </motion.div>
      )}

      <motion.div variants={fadeUp}>
        <GlassmorphismCard className="p-4 text-sm text-muted-foreground">
          <p>
            <strong className="text-foreground">TradingView setup:</strong> in your alert&apos;s
            webhook URL field, paste{" "}
            <code className="text-xs bg-white/[0.05] px-1 py-0.5 rounded">
              https://api.tradetri.com/api/webhook/strategy/&lt;your-token&gt;
            </code>
            . No signature needed — your token authenticates the request. Set the alert message
            (JSON) to{" "}
            <code className="text-xs bg-white/[0.05] px-1 py-0.5 rounded">
              {`{"symbol":"NIFTY","action":"BUY","quantity":1}`}
            </code>
            . Recent-hits audit panel is shipping in a future sprint.
          </p>
        </GlassmorphismCard>
      </motion.div>

      <Dialog
        open={!!created}
        onOpenChange={(open) => {
          if (!open) setCreated(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-400" />
              Save these now — shown only once
            </DialogTitle>
          </DialogHeader>
          {created && (
            <div className="space-y-4 pt-4">
              <p className="text-sm text-muted-foreground">
                Both values below are unrecoverable after you close this dialog. Copy them into your
                TradingView alert configuration first.
              </p>
              <CredField
                label="Webhook URL"
                value={`https://api.tradetri.com/api/webhook/strategy/${created.webhook_token}`}
                onCopy={(v) => copy(v, "Webhook URL")}
                copied={copied === "Webhook URL"}
              />
              <CredField
                label="Webhook token"
                value={created.webhook_token}
                onCopy={(v) => copy(v, "Token")}
                copied={copied === "Token"}
                secret
              />
              <CredField
                label="HMAC secret (optional — not required for TradingView)"
                value={created.hmac_secret}
                onCopy={(v) => copy(v, "HMAC secret")}
                copied={copied === "HMAC secret"}
                secret
              />
              <p className="text-xs text-muted-foreground">
                Paste the <strong className="text-foreground">Webhook URL</strong> into your
                TradingView alert. No signature needed — your token authenticates the request. Set
                the alert message to{" "}
                <code className="text-[11px] bg-white/[0.05] px-1 py-0.5 rounded">
                  {`{"symbol":"NIFTY","action":"BUY","quantity":1}`}
                </code>
                .
              </p>
              <div className="flex justify-end pt-2">
                <GlowButton size="sm" onClick={() => setCreated(null)}>
                  I&apos;ve saved these
                </GlowButton>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}

function CredField({
  label,
  value,
  onCopy,
  copied,
  secret = false,
}: {
  label: string;
  value: string;
  onCopy: (v: string) => void;
  copied: boolean;
  secret?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="flex gap-2 items-stretch">
        <code
          className={cn(
            "flex-1 px-3 py-2 rounded-lg border border-border bg-white/[0.02] font-mono text-xs break-all",
            secret && "select-all",
          )}
        >
          {value}
        </code>
        <button
          type="button"
          onClick={() => onCopy(value)}
          className="px-3 py-2 rounded-lg text-sm border border-border hover:bg-accent transition-colors flex items-center gap-1.5"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-profit" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </button>
      </div>
    </div>
  );
}

"use client";

/**
 * /admin/announcements — broadcast an in-app announcement to all
 * active users via the existing notification fan-out.
 *
 * Wire: POST /api/admin/announcements (body: {message}).
 *
 * Destructive-ish: this enqueues real notifications. Confirmation
 * dialog before send.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { Megaphone, Send, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";

interface SendResponse {
  message: string;
  total_users: number;
}

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

const MAX_CHARS = 500;

export default function AdminAnnouncementsPage() {
  const [message, setMessage] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [lastResult, setLastResult] = useState<SendResponse | null>(null);

  const trimmed = message.trim();
  const canSend = trimmed.length > 0 && trimmed.length <= MAX_CHARS;

  const handleSend = async () => {
    setSending(true);
    try {
      const resp = await api.post<SendResponse>("/admin/announcements", {
        message: trimmed,
      });
      setLastResult(resp);
      setMessage("");
      setConfirmOpen(false);
      toast.success(resp.message);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to send announcement.";
      toast.error(msg);
    } finally {
      setSending(false);
    }
  };

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Megaphone className="h-6 w-6 text-accent-blue" /> Announcements
        </h1>
        <p className="text-muted-foreground text-sm">
          Send an in-app notification to every active user. Each user receives it via their
          configured channels (in-app, optionally Telegram).
        </p>
      </header>

      <GlassmorphismCard className="p-5 space-y-4">
        <div className="space-y-2">
          <label htmlFor="msg" className="text-sm font-medium">
            Message
          </label>
          <textarea
            id="msg"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="e.g., Scheduled maintenance Saturday 11:30 PM IST. Live orders will pause for ~5 min."
            rows={5}
            disabled={sending}
            className="w-full px-3 py-2 rounded-lg border border-border bg-white/[0.02] text-sm focus:outline-none focus:ring-1 focus:ring-accent-blue disabled:opacity-50"
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Plain text only. Will be rendered in users&apos; notification feed.</span>
            <span
              className={
                trimmed.length > MAX_CHARS
                  ? "text-loss"
                  : trimmed.length > MAX_CHARS * 0.8
                    ? "text-amber-300"
                    : ""
              }
            >
              {trimmed.length} / {MAX_CHARS}
            </span>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setMessage("")}
            disabled={!message || sending}
            className="px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-accent transition-colors disabled:opacity-50"
          >
            Clear
          </button>
          <GlowButton size="sm" onClick={() => setConfirmOpen(true)} disabled={!canSend || sending}>
            <Send className="h-4 w-4 mr-2" />
            Send to all active users
          </GlowButton>
        </div>
      </GlassmorphismCard>

      {lastResult && (
        <GlassmorphismCard className="p-4">
          <p className="text-sm">
            <strong>Last send:</strong> {lastResult.message}
          </p>
        </GlassmorphismCard>
      )}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-400" />
              Confirm broadcast
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <p className="text-sm text-muted-foreground">
              This will send an in-app notification to <strong>every active user</strong>. You
              cannot recall the send.
            </p>
            <div className="rounded-lg border border-border bg-white/[0.02] p-3 text-sm whitespace-pre-wrap">
              {trimmed}
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                disabled={sending}
                className="px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-accent transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <GlowButton size="sm" onClick={handleSend} disabled={sending}>
                {sending ? "Sending…" : "Confirm send"}
              </GlowButton>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}

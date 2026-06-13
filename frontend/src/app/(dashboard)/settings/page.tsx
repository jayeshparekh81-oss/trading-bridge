"use client";

/**
 * /settings — user profile + communication preferences.
 *
 * Wire: GET /api/auth/me + PUT /api/users/me (both existing).
 * The PUT endpoint already accepts full_name, phone, telegram_chat_id,
 * notification_prefs — no new backend needed.
 *
 * NOT in scope (clearly flagged in summary):
 *   * Change password — needs new password-change UI flow
 *   * 2FA setup
 *   * Theme switcher (dark-only product per design memory)
 *   * Timezone preference (deferred — no backend field today)
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Settings as SettingsIcon, Save, Mail, Send } from "lucide-react";
import { toast } from "sonner";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ProfileForm {
  full_name: string;
  phone: string;
  telegram_chat_id: string;
  notification_prefs: {
    email: boolean;
    telegram: boolean;
  };
}

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function SettingsPage() {
  const { user, isLoading: authLoading } = useAuth();
  const [form, setForm] = useState<ProfileForm>({
    full_name: "",
    phone: "",
    telegram_chat_id: "",
    notification_prefs: { email: true, telegram: false },
  });
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Hydrate form when user loads.
  useEffect(() => {
    if (!user) return;
    setForm({
      full_name: user.full_name ?? "",
      phone: user.phone ?? "",
      telegram_chat_id: user.telegram_chat_id ?? "",
      notification_prefs: {
        email: !!user.notification_prefs?.email,
        telegram: !!user.notification_prefs?.telegram,
      },
    });
    setDirty(false);
  }, [user]);

  const update = <K extends keyof ProfileForm>(key: K, value: ProfileForm[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put("/users/me", {
        full_name: form.full_name.trim() || null,
        phone: form.phone.trim() || null,
        telegram_chat_id: form.telegram_chat_id.trim() || null,
        notification_prefs: form.notification_prefs,
      });
      toast.success("Settings saved.");
      setDirty(false);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to save settings.";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || !user) {
    return (
      <div className="p-8 text-center text-muted-foreground">Loading…</div>
    );
  }

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <SettingsIcon className="h-6 w-6 text-accent-blue" /> Settings
        </h1>
        <p className="text-muted-foreground text-sm">
          Profile + notification preferences.
        </p>
      </header>

      {/* ── Account info (read-only) ── */}
      <GlassmorphismCard className="p-5 space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Account
        </h2>
        <ReadOnlyRow label="Email" value={user.email} />
        <ReadOnlyRow
          label="Role"
          value={
            <Badge
              className={cn(
                user.is_admin
                  ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                  : "bg-white/[0.03] text-muted-foreground border-border",
              )}
            >
              {user.is_admin ? "Admin" : (user.role ?? "user")}
            </Badge>
          }
        />
        <ReadOnlyRow
          label="Joined"
          value={
            user.created_at
              ? new Date(user.created_at).toLocaleDateString("en-IN")
              : "—"
          }
        />
      </GlassmorphismCard>

      {/* ── Profile editable ── */}
      <GlassmorphismCard className="p-5 space-y-4">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Profile
        </h2>
        <FieldRow label="Full name">
          <Input
            value={form.full_name}
            onChange={(e) => update("full_name", e.target.value)}
            placeholder="Your name"
            maxLength={255}
          />
        </FieldRow>
        <FieldRow label="Phone">
          <Input
            value={form.phone}
            onChange={(e) => update("phone", e.target.value)}
            placeholder="+91 98765 43210"
            maxLength={32}
            type="tel"
          />
        </FieldRow>
      </GlassmorphismCard>

      {/* ── Notifications ── */}
      <GlassmorphismCard className="p-5 space-y-4">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Notifications
        </h2>

        <ToggleRow
          icon={Mail}
          label="Email"
          description="Order fills, kill-switch trips, daily summary."
          checked={form.notification_prefs.email}
          onChange={(v) =>
            update("notification_prefs", { ...form.notification_prefs, email: v })
          }
        />

        <ToggleRow
          icon={Send}
          label="Telegram"
          description="Real-time push to your Telegram. Requires chat ID."
          checked={form.notification_prefs.telegram}
          onChange={(v) =>
            update("notification_prefs", { ...form.notification_prefs, telegram: v })
          }
        />

        <FieldRow label="Telegram chat ID">
          <Input
            value={form.telegram_chat_id}
            onChange={(e) => update("telegram_chat_id", e.target.value)}
            placeholder="e.g., 123456789"
            maxLength={64}
          />
        </FieldRow>
        <p className="text-xs text-muted-foreground">
          Get your chat ID by messaging{" "}
          <code className="text-xs bg-white/[0.05] px-1 py-0.5 rounded">
            @userinfobot
          </code>{" "}
          on Telegram.
        </p>
      </GlassmorphismCard>

      {/* ── Save bar (sticky on mobile) ── */}
      <div className="flex justify-end gap-2 sticky bottom-4">
        <GlowButton onClick={handleSave} disabled={!dirty || saving} size="sm">
          <Save className="h-4 w-4 mr-2" />
          {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}
        </GlowButton>
      </div>

      <p className="text-xs text-muted-foreground text-center">
        Password change · 2FA · timezone — coming in a later sprint.
      </p>
    </motion.div>
  );
}

function ReadOnlyRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div>{value}</div>
    </div>
  );
}

function FieldRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

function ToggleRow({
  icon: Icon,
  label,
  description,
  checked,
  onChange,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-start gap-3 flex-1">
        <Icon className="h-5 w-5 text-muted-foreground mt-0.5" />
        <div>
          <div className="font-medium text-sm">{label}</div>
          <div className="text-xs text-muted-foreground">{description}</div>
        </div>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "w-10 h-6 rounded-full transition-colors relative shrink-0",
          checked ? "bg-accent-blue" : "bg-white/[0.08]",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform",
            checked && "translate-x-4",
          )}
        />
      </button>
    </div>
  );
}
